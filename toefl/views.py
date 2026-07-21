import json
import logging
import re
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import (
    ListeningAnswer,
    ListeningAttempt,
    ListeningBlock,
    ListeningChoice,
    ListeningModule,
    FullTestAttempt,
    MockAttempt,
    MockTest,
    ModuleAttempt,
    ReadingBlock,
    ReadingChoice,
    ReadingModule,
    ReadingQuestion,
    SpeakingAnswer,
    SpeakingAttempt,
    SpeakingBlock,
    SpeakingModule,
    UserAnswer,
    WritingAnswer,
    WritingAttempt,
    WritingBlock,
    WritingModule,
    WritingModuleAttempt,
)

logger = logging.getLogger(__name__)


def _get_or_create_full_test_attempt(user, mock_test):
    """Return the user's active continuous test run, creating one if needed."""
    full_attempt = (
        FullTestAttempt.objects.filter(
            user=user,
            mock_test=mock_test,
            is_completed=False,
        )
        .select_related(
            "reading_attempt",
            "listening_attempt",
            "writing_attempt",
            "speaking_attempt",
        )
        .order_by("-started_at", "-id")
        .first()
    )

    if full_attempt is not None:
        return full_attempt

    try:
        return FullTestAttempt.objects.create(
            user=user,
            mock_test=mock_test,
            current_section=FullTestAttempt.READING,
            is_completed=False,
        )
    except IntegrityError:
        return FullTestAttempt.objects.get(
            user=user,
            mock_test=mock_test,
            is_completed=False,
        )


def _get_or_create_section_attempt(
    full_attempt,
    field_name,
    model,
):
    """Create a section attempt once and attach it to the full test run."""
    attempt = getattr(full_attempt, field_name)

    if attempt is not None:
        return attempt

    attempt = model.objects.create(
        user=full_attempt.user,
        mock_test=full_attempt.mock_test,
        is_submitted=False,
    )

    setattr(full_attempt, field_name, attempt)
    full_attempt.save(update_fields=[field_name])
    return attempt


def _full_attempt_for_section_attempt(
    user,
    mock_test,
    field_name,
    section_attempt,
):
    filters = {
        "user": user,
        "mock_test": mock_test,
        "is_completed": False,
        field_name: section_attempt,
    }

    full_attempt = FullTestAttempt.objects.filter(
        **filters
    ).first()

    if full_attempt is not None:
        return full_attempt

    full_attempt = _get_or_create_full_test_attempt(
        user,
        mock_test,
    )

    current_id = getattr(
        full_attempt,
        f"{field_name}_id",
    )

    if current_id is None:
        setattr(full_attempt, field_name, section_attempt)
        full_attempt.save(update_fields=[field_name])
        return full_attempt

    if current_id == section_attempt.id:
        return full_attempt

    return None


def _redirect_to_current_section(full_attempt):
    """
    Route a continuous test run through the two section-introduction screens.

    The introduction view immediately skips itself when it has already been
    completed for this FullTestAttempt, so this helper is safe to use for both
    first entry and resume behavior.
    """
    slug = full_attempt.mock_test.slug

    if full_attempt.current_section in {
        FullTestAttempt.READING,
        FullTestAttempt.LISTENING,
        FullTestAttempt.WRITING,
        FullTestAttempt.SPEAKING,
    }:
        return redirect(
            "toefl:section_intro",
            slug=slug,
            section=full_attempt.current_section,
            step=1,
        )

    return redirect(
        "toefl:full_test_result",
        slug=slug,
    )


def _advance_full_test(full_attempt, completed_section):
    """Advance once; repeated AJAX submissions remain idempotent."""
    if full_attempt.is_completed:
        return

    if full_attempt.current_section != completed_section:
        return

    next_sections = {
        FullTestAttempt.READING: FullTestAttempt.LISTENING,
        FullTestAttempt.LISTENING: FullTestAttempt.WRITING,
        FullTestAttempt.WRITING: FullTestAttempt.SPEAKING,
        FullTestAttempt.SPEAKING: FullTestAttempt.COMPLETED,
    }

    next_section = next_sections[completed_section]
    full_attempt.current_section = next_section

    update_fields = ["current_section"]

    if next_section == FullTestAttempt.COMPLETED:
        full_attempt.is_completed = True
        full_attempt.completed_at = timezone.now()
        update_fields.extend([
            "is_completed",
            "completed_at",
        ])

    full_attempt.save(update_fields=update_fields)

SECTION_INTRO_CONTENT = {
    FullTestAttempt.READING: {
        "display_name": "Reading",
        "overview": (
            "In the Reading section, you will answer questions that measure "
            "how well you understand academic and everyday texts in English."
        ),
        "tasks": [
            (
                "Complete the Words",
                "Fill in the missing letters in a paragraph.",
            ),
            (
                "Read in Daily Life",
                "Answer questions about everyday reading material.",
            ),
            (
                "Read an Academic Passage",
                "Answer questions about academic passages.",
            ),
        ],
    },
    FullTestAttempt.LISTENING: {
        "display_name": "Listening",
        "overview": (
            "In the Listening section, you will listen to conversations, "
            "announcements, and academic talks and answer questions about them."
        ),
        "tasks": [
            (
                "Listen and Choose a Response",
                "Choose the best response to a short spoken exchange.",
            ),
            (
                "Listen to a Conversation",
                "Answer questions about an everyday conversation.",
            ),
            (
                "Listen to an Announcement",
                "Answer questions about an announcement or message.",
            ),
            (
                "Listen to an Academic Talk",
                "Answer questions about an academic talk.",
            ),
        ],
    },
    FullTestAttempt.WRITING: {
        "display_name": "Writing",
        "overview": (
            "In the Writing section, you will complete tasks that measure "
            "how clearly and accurately you can write in English."
        ),
        "tasks": [
            (
                "Build a Sentence",
                "Arrange words or phrases to form a correct sentence.",
            ),
            (
                "Write an Email",
                "Write an email that responds to a practical situation.",
            ),
            (
                "Write for an Academic Discussion",
                "Write and support your opinion in an academic discussion.",
            ),
        ],
    },
    FullTestAttempt.SPEAKING: {
        "display_name": "Speaking",
        "overview": (
            "In the Speaking section, you will listen to or watch prompts and "
            "record spoken responses within the time shown."
        ),
        "tasks": [
            (
                "Listen and Repeat",
                "Listen to a sentence and repeat it clearly.",
            ),
            (
                "Watch and Respond",
                "Watch a prompt and record an appropriate response.",
            ),
        ],
    },
}


def _section_intro_key(full_attempt, section):
    return (
        f"toefl_full_attempt_{full_attempt.id}_"
        f"section_{section}_intro_complete"
    )


def _module_intro_key(full_attempt, section, module_id):
    return (
        f"toefl_full_attempt_{full_attempt.id}_"
        f"section_{section}_module_{module_id}_intro_complete"
    )


def _section_intro_complete(request, full_attempt, section):
    return bool(
        request.session.get(
            _section_intro_key(full_attempt, section),
            False,
        )
    )


def _mark_section_intro_complete(request, full_attempt, section):
    request.session[
        _section_intro_key(full_attempt, section)
    ] = True


def _module_intro_complete(
    request,
    full_attempt,
    section,
    module_id,
):
    return bool(
        request.session.get(
            _module_intro_key(
                full_attempt,
                section,
                module_id,
            ),
            False,
        )
    )


def _mark_module_intro_complete(
    request,
    full_attempt,
    section,
    module_id,
):
    request.session[
        _module_intro_key(
            full_attempt,
            section,
            module_id,
        )
    ] = True


def _redirect_to_section_content(full_attempt):
    slug = full_attempt.mock_test.slug

    route_names = {
        FullTestAttempt.READING: "toefl:take_reading_test",
        FullTestAttempt.LISTENING: "toefl:take_listening_test",
        FullTestAttempt.WRITING: "toefl:take_writing_test",
        FullTestAttempt.SPEAKING: "toefl:take_speaking_test",
    }

    route_name = route_names.get(
        full_attempt.current_section
    )

    if route_name is None:
        return redirect(
            "toefl:full_test_result",
            slug=slug,
        )

    return redirect(
        route_name,
        slug=slug,
    )


def _module_model_for_section(section):
    module_models = {
        FullTestAttempt.READING: ReadingModule,
        FullTestAttempt.LISTENING: ListeningModule,
        FullTestAttempt.WRITING: WritingModule,
        FullTestAttempt.SPEAKING: SpeakingModule,
    }

    return module_models.get(section)


def _module_content_redirect(section, mock_test, module):
    if section == FullTestAttempt.READING:
        return redirect(
            "toefl:reading_module",
            slug=mock_test.slug,
            module_id=module.id,
        )

    if section == FullTestAttempt.WRITING:
        return redirect(
            "toefl:writing_module",
            slug=mock_test.slug,
            module_id=module.id,
        )

    if section == FullTestAttempt.LISTENING:
        first_block = (
            ListeningBlock.objects.filter(
                module=module,
            )
            .order_by("order", "id")
            .first()
        )

        if first_block is None:
            return redirect(
                "toefl:take_listening_test",
                slug=mock_test.slug,
            )

        return redirect(
            "toefl:listening_block",
            slug=mock_test.slug,
            block_id=first_block.id,
        )

    if section == FullTestAttempt.SPEAKING:
        return redirect(
            "toefl:take_speaking_test",
            slug=mock_test.slug,
        )

    return redirect(
        "toefl:take_mock_test",
        slug=mock_test.slug,
    )


@login_required
def section_intro_view(
    request,
    slug,
    section,
    step,
):
    """
    Two screens shown once at the beginning of each TOEFL section.

    Step 1: simulation-test notice.
    Step 2: section description and task table.
    """
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != section:
        return _redirect_to_current_section(full_attempt)

    section_content = SECTION_INTRO_CONTENT.get(section)

    if section_content is None or step not in {1, 2}:
        return redirect(
            "toefl:take_mock_test",
            slug=mock_test.slug,
        )

    if _section_intro_complete(
        request,
        full_attempt,
        section,
    ):
        return _redirect_to_section_content(full_attempt)

    if request.method == "POST":
        if step == 1:
            return redirect(
                "toefl:section_intro",
                slug=mock_test.slug,
                section=section,
                step=2,
            )

        _mark_section_intro_complete(
            request,
            full_attempt,
            section,
        )
        return _redirect_to_section_content(full_attempt)

    return render(
        request,
        "toefl/section_intro.html",
        {
            "mock_test": mock_test,
            "full_attempt": full_attempt,
            "section": section,
            "section_content": section_content,
            "section_display_name": (
                section_content["display_name"]
            ),
            "step": step,
        },
    )


@login_required
def module_intro_view(
    request,
    slug,
    section,
    module_id,
):
    """
    One untimed instruction screen shown before a module timer starts.
    """
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != section:
        return _redirect_to_current_section(full_attempt)

    if not _section_intro_complete(
        request,
        full_attempt,
        section,
    ):
        return redirect(
            "toefl:section_intro",
            slug=mock_test.slug,
            section=section,
            step=1,
        )

    module_model = _module_model_for_section(section)

    if module_model is None:
        return redirect(
            "toefl:take_mock_test",
            slug=mock_test.slug,
        )

    module = get_object_or_404(
        module_model,
        id=module_id,
        mock_test=mock_test,
    )

    if _module_intro_complete(
        request,
        full_attempt,
        section,
        module.id,
    ):
        return _module_content_redirect(
            section,
            mock_test,
            module,
        )

    if request.method == "POST":
        _mark_module_intro_complete(
            request,
            full_attempt,
            section,
            module.id,
        )
        return _module_content_redirect(
            section,
            mock_test,
            module,
        )

    section_content = SECTION_INTRO_CONTENT[section]

    return render(
        request,
        "toefl/module_intro.html",
        {
            "mock_test": mock_test,
            "full_attempt": full_attempt,
            "section": section,
            "section_display_name": (
                section_content["display_name"]
            ),
            "module": module,
        },
    )



@login_required
def take_mock_test_view(request, slug):
    """
    Start or resume one continuous TOEFL test:
    Reading -> Listening -> Writing -> Speaking -> Final Result.
    """
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    return _redirect_to_current_section(full_attempt)

@login_required
def submit_mock_test_view(request, slug, attempt_id):
    attempt = get_object_or_404(MockAttempt, id=attempt_id, user=request.user)
    
    if request.method == 'POST' and not attempt.is_submitted:
        correct_count = 0
        total_questions = 0
        
        # پاک کردن جواب‌های قبلی احتمالی برای این تلاش
        attempt.answers.all().delete()
        
        # بررسی پاسخ‌های آزمون
        for module in attempt.mock_test.reading_modules.all():
            for block in module.blocks.all():
                
                # حالت اول: بخش کلمات ناقص (Complete the Words)
                if block.block_type == ReadingBlock.COMPLETE_WORDS:
                    words_data = block.get_processed_content()
                    for part in words_data:
                        if part['type'] == 'input':
                            q_num = part['q_number']
                            total_questions += 1
                            
                            # دریافت جواب کاربر
                            user_val = request.POST.get(f'q_{q_num}', '').strip().lower()
                            # جواب درست، بخش انتهای کلمه است
                            correct_remainder = part['full_word'][len(part['start_part']):].lower()
                            
                            is_correct = (user_val == correct_remainder)
                            if is_correct:
                                correct_count += 1
                                
                            UserAnswer.objects.create(
                                attempt=attempt,
                                global_question_number=q_num,
                                text_answer=user_val,
                                is_correct=is_correct
                            )
                
                # حالت دوم: سوالات چند گزینه‌ای (Notice, Email, Passage و ...)
                else:
                    for question in block.questions.all():
                        total_questions += 1
                        selected_choice_id = request.POST.get(f'question_{question.id}')
                        
                        is_correct = False
                        selected_choice = None
                        
                        if selected_choice_id:
                            selected_choice = ReadingChoice.objects.filter(id=selected_choice_id).first()
                            if selected_choice and selected_choice.is_correct:
                                is_correct = True
                                correct_count += 1
                        
                        UserAnswer.objects.create(
                            attempt=attempt,
                            question=question,
                            selected_choice=selected_choice,
                            is_correct=is_correct
                        )
        
        # به روزرسانی وضعیت تلاش
        attempt.total_questions = total_questions
        attempt.correct_answers = correct_count
        attempt.calculate_score()
        attempt.submitted_at = timezone.now()
        attempt.is_submitted = True

        attempt.save(
            update_fields=[
                "total_questions",
                "correct_answers",
                "score",
                "submitted_at",
                "is_submitted",
            ]
        )
        
    return render(request, 'toefl/test_result.html', {'attempt': attempt})



def _reading_module_time_limit(module):
    """Return one fixed positive timer for the entire Reading module."""
    return max(0, module.time_limit_seconds) or 600


def finalize_attempt(attempt):
    correct_count = attempt.answers.filter(
        is_correct=True
    ).count()

    total_questions = 0

    for block in attempt.mock_test.get_all_blocks():
        if block.block_type == ReadingBlock.COMPLETE_WORDS:
            total_questions += sum(
                1
                for part in block.get_processed_content()
                if part["type"] == "input"
            )
        else:
            total_questions += block.questions.count()

    attempt.correct_answers = correct_count
    attempt.total_questions = total_questions
    attempt.calculate_score()
    attempt.is_submitted = True
    attempt.submitted_at = timezone.now()

    attempt.save(
        update_fields=[
            "correct_answers",
            "total_questions",
            "score",
            "is_submitted",
            "submitted_at",
        ]
    )


@login_required
def test_result_view(request, attempt_id):
    attempt = get_object_or_404(
        MockAttempt,
        id=attempt_id,
        user=request.user,
        is_submitted=True
    )

    return render(
        request,
        "toefl/test_result.html",
        {"attempt": attempt}
    )


@login_required
def full_test_result_view(request, slug):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = (
        FullTestAttempt.objects.filter(
            user=request.user,
            mock_test=mock_test,
            is_completed=True,
            current_section=FullTestAttempt.COMPLETED,
        )
        .select_related(
            "reading_attempt",
            "listening_attempt",
            "writing_attempt",
            "speaking_attempt",
        )
        .order_by("-completed_at", "-id")
        .first()
    )

    if full_attempt is None:
        active_attempt = _get_or_create_full_test_attempt(
            request.user,
            mock_test,
        )
        return _redirect_to_current_section(active_attempt)

    if not all([
        full_attempt.reading_attempt_id,
        full_attempt.listening_attempt_id,
        full_attempt.writing_attempt_id,
        full_attempt.speaking_attempt_id,
    ]):
        return redirect(
            "toefl:take_mock_test",
            slug=mock_test.slug,
        )

    return render(
        request,
        "toefl/full_test_result.html",
        {
            "mock_test": mock_test,
            "full_attempt": full_attempt,
            "reading_attempt": full_attempt.reading_attempt,
            "listening_attempt": full_attempt.listening_attempt,
            "writing_attempt": full_attempt.writing_attempt,
            "speaking_attempt": full_attempt.speaking_attempt,
        },
    )
    


# ==================================================
# Writing — module-based flow
# ==================================================


def _writing_module_time_limit(module):
    """
    Return one fixed timer value for the entire WritingModule.

    The module-level value is authoritative. The block-level values are
    used only as a backward-compatible fallback while old admin data is
    being migrated.
    """
    if module.time_limit_seconds > 0:
        return module.time_limit_seconds

    fallback_seconds = sum(
        max(0, block.time_limit_seconds)
        for block in module.blocks.all()
    )

    return fallback_seconds or 600


def _next_writing_module(module):
    return (
        WritingModule.objects.filter(
            mock_test=module.mock_test,
        )
        .filter(
            Q(order__gt=module.order)
            | Q(
                order=module.order,
                id__gt=module.id,
            )
        )
        .order_by(
            "order",
            "id",
        )
        .first()
    )


def _complete_writing_module_attempt(module_attempt):
    if module_attempt.is_completed:
        return

    module_attempt.is_completed = True
    module_attempt.completed_at = timezone.now()
    module_attempt.remaining_time_seconds = 0

    module_attempt.save(
        update_fields=[
            "is_completed",
            "completed_at",
            "remaining_time_seconds",
        ]
    )


def finalize_writing_attempt(attempt):
    total_questions = WritingBlock.objects.filter(
        module__mock_test=attempt.mock_test,
    ).count()

    correct_answers = attempt.answers.filter(
        is_graded=True,
        is_correct=True,
    ).count()

    attempt.total_questions = total_questions
    attempt.correct_answers = correct_answers
    attempt.is_submitted = True
    attempt.submitted_at = timezone.now()

    attempt.save(
        update_fields=[
            "total_questions",
            "correct_answers",
            "is_submitted",
            "submitted_at",
        ]
    )


def _prepare_writing_blocks(blocks, saved_answers):
    """Attach display-only data used by writing_module_mock.html."""
    for block in blocks:
        saved_answer = saved_answers.get(block.id)

        block.saved_text = (
            saved_answer.text_answer
            if saved_answer
            else ""
        ) or ""

        block.saved_word_ids = list(
            saved_answer.selected_word_ids
            if saved_answer
            else []
        )

        block.saved_word_ids_json = json.dumps(
            block.saved_word_ids
        )

        block.answer_parts = block.get_processed_answer()
        block.display_words = list(
            block.words.all()
        )
        block.email_requirements_list = (
            block.get_email_requirements()
        )
        block.discussion_requirements_list = (
            block.get_discussion_requirements()
        )
        block.discussion_posts_list = list(
            block.discussion_posts.all()
        )
        block.display_minimum_words = (
            block.minimum_words or 100
        )


@login_required
def take_writing_test_view(request, slug):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != FullTestAttempt.WRITING:
        return _redirect_to_current_section(full_attempt)

    if not _section_intro_complete(
        request,
        full_attempt,
        FullTestAttempt.WRITING,
    ):
        return redirect(
            "toefl:section_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.WRITING,
            step=1,
        )

    attempt = _get_or_create_section_attempt(
        full_attempt,
        "writing_attempt",
        WritingAttempt,
    )

    if attempt.is_submitted:
        _advance_full_test(
            full_attempt,
            FullTestAttempt.WRITING,
        )
        return _redirect_to_current_section(full_attempt)

    modules = list(
        WritingModule.objects.filter(
            mock_test=mock_test,
        ).order_by("order", "id")
    )

    if not modules:
        return render(
            request,
            "toefl/no_writing_modules.html",
            {"mock_test": mock_test},
        )

    states = {
        state.module_id: state
        for state in WritingModuleAttempt.objects.filter(
            attempt=attempt,
            module__mock_test=mock_test,
        )
    }

    for module in modules:
        state = states.get(module.id)

        if state is None:
            return redirect(
                "toefl:module_intro",
                slug=mock_test.slug,
                section=FullTestAttempt.WRITING,
                module_id=module.id,
            )

        if not state.is_completed:
            return redirect(
                "toefl:writing_module",
                slug=mock_test.slug,
                module_id=module.id,
            )

    finalize_writing_attempt(attempt)
    _advance_full_test(
        full_attempt,
        FullTestAttempt.WRITING,
    )
    return _redirect_to_current_section(full_attempt)


@login_required
def writing_block_view(request, slug, block_id):
    """
    Backward-compatible redirect for old writing/block/<id>/ links.
    The actual Writing UI is now module-based.
    """
    block = get_object_or_404(
        WritingBlock.objects.select_related(
            "module",
            "module__mock_test",
        ),
        id=block_id,
        module__mock_test__slug=slug,
        module__mock_test__is_active=True,
    )

    return redirect(
        "toefl:writing_module",
        slug=slug,
        module_id=block.module_id,
    )


@login_required
def writing_module_view(request, slug, module_id):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    module = get_object_or_404(
        WritingModule.objects.select_related(
            "mock_test",
        ).prefetch_related(
            "blocks",
        ),
        id=module_id,
        mock_test=mock_test,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != FullTestAttempt.WRITING:
        return _redirect_to_current_section(full_attempt)

    attempt = _get_or_create_section_attempt(
        full_attempt,
        "writing_attempt",
        WritingAttempt,
    )

    if attempt.is_submitted:
        _advance_full_test(
            full_attempt,
            FullTestAttempt.WRITING,
        )
        return _redirect_to_current_section(full_attempt)

    existing_module_attempt = (
        WritingModuleAttempt.objects.filter(
            attempt=attempt,
            module=module,
        ).first()
    )

    if (
        existing_module_attempt is None
        and not _module_intro_complete(
            request,
            full_attempt,
            FullTestAttempt.WRITING,
            module.id,
        )
    ):
        return redirect(
            "toefl:module_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.WRITING,
            module_id=module.id,
        )

    module_time_limit = _writing_module_time_limit(
        module
    )

    module_attempt, created = (
        WritingModuleAttempt.objects.get_or_create(
            attempt=attempt,
            module=module,
            defaults={
                "remaining_time_seconds": module_time_limit,
                "expires_at": (
                    timezone.now()
                    + timedelta(
                        seconds=module_time_limit,
                    )
                ),
                "current_block_index": 0,
                "is_completed": False,
            },
        )
    )

    if (
        not created
        and module_attempt.expires_at is None
    ):
        remaining = max(
            0,
            module_attempt.remaining_time_seconds,
        )

        module_attempt.expires_at = (
            timezone.now()
            + timedelta(seconds=remaining)
        )

        module_attempt.save(
            update_fields=["expires_at"]
        )

    if module_attempt.is_completed:
        next_module = _next_writing_module(module)

        if next_module is not None:
            return redirect(
                "toefl:module_intro",
                slug=mock_test.slug,
                section=FullTestAttempt.WRITING,
                module_id=next_module.id,
            )

        if not attempt.is_submitted:
            finalize_writing_attempt(attempt)

        _advance_full_test(
            full_attempt,
            FullTestAttempt.WRITING,
        )
        return _redirect_to_current_section(full_attempt)

    remaining_seconds = (
        module_attempt.calculated_remaining_seconds
    )

    if remaining_seconds <= 0:
        _complete_writing_module_attempt(
            module_attempt
        )

        next_module = _next_writing_module(module)

        if next_module is not None:
            return redirect(
                "toefl:module_intro",
                slug=mock_test.slug,
                section=FullTestAttempt.WRITING,
                module_id=next_module.id,
            )

        if not attempt.is_submitted:
            finalize_writing_attempt(attempt)

        _advance_full_test(
            full_attempt,
            FullTestAttempt.WRITING,
        )
        return _redirect_to_current_section(full_attempt)

    blocks = list(
        WritingBlock.objects.filter(
            module=module,
        )
        .prefetch_related(
            "words",
            "discussion_posts",
        )
        .order_by(
            "order",
            "id",
        )
    )

    saved_answers = {
        answer.block_id: answer
        for answer in WritingAnswer.objects.filter(
            attempt=attempt,
            block__module=module,
        )
    }

    _prepare_writing_blocks(
        blocks,
        saved_answers,
    )

    current_block_index = min(
        max(
            0,
            module_attempt.current_block_index,
        ),
        max(
            0,
            len(blocks) - 1,
        ),
    )

    return render(
        request,
        "toefl/writing_module_mock.html",
        {
            "mock_test": mock_test,
            "attempt": attempt,
            "module": module,
            "module_attempt": module_attempt,
            "blocks": blocks,
            "remaining_seconds": remaining_seconds,
            "current_block_index": current_block_index,
        },
    )


def _normalize_selected_word_ids(raw_ids):
    if not isinstance(raw_ids, list):
        return []

    normalized = []

    for raw_id in raw_ids:
        try:
            word_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if word_id not in normalized:
            normalized.append(word_id)

    return normalized


def _save_writing_answer(attempt, block, answer_data):
    if block.block_type == WritingBlock.BUILD_SENTENCE:
        submitted_ids = _normalize_selected_word_ids(
            answer_data.get(
                "selected_word_ids",
                [],
            )
        )

        valid_word_ids = set(
            block.words.values_list(
                "id",
                flat=True,
            )
        )

        selected_word_ids = [
            word_id
            for word_id in submitted_ids
            if word_id in valid_word_ids
        ][:block.blank_count]

        correct_word_ids = (
            block.get_correct_word_ids()
        )

        is_correct = (
            len(selected_word_ids)
            == block.blank_count
            and selected_word_ids
            == correct_word_ids
        )

        WritingAnswer.objects.update_or_create(
            attempt=attempt,
            block=block,
            defaults={
                "selected_word_ids": selected_word_ids,
                "text_answer": "",
                "word_count": 0,
                "is_correct": is_correct,
                "is_graded": True,
            },
        )

        return

    if block.block_type in {
        WritingBlock.WRITE_EMAIL,
        WritingBlock.ACADEMIC_DISCUSSION,
    }:
        text_answer = str(
            answer_data.get(
                "text_answer",
                "",
            )
        ).strip()

        word_count = len(
            re.findall(
                r"\b[\w’'-]+\b",
                text_answer,
                flags=re.UNICODE,
            )
        )

        WritingAnswer.objects.update_or_create(
            attempt=attempt,
            block=block,
            defaults={
                "selected_word_ids": [],
                "text_answer": text_answer,
                "word_count": word_count,
                "is_correct": False,
                "is_graded": False,
            },
        )


@login_required
@transaction.atomic
def save_writing_module_progress_view(
    request,
    module_attempt_id,
):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "error": "POST request required.",
            },
            status=405,
        )

    module_attempt = get_object_or_404(
        WritingModuleAttempt.objects.select_related(
            "attempt",
            "attempt__user",
            "module",
        ),
        id=module_attempt_id,
        attempt__user=request.user,
        is_completed=False,
    )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON data.",
            },
            status=400,
        )

    block_count = WritingBlock.objects.filter(
        module=module_attempt.module,
    ).count()

    try:
        current_block_index = int(
            payload.get(
                "current_block_index",
                module_attempt.current_block_index,
            )
        )
    except (TypeError, ValueError):
        current_block_index = 0

    current_block_index = max(
        0,
        min(
            current_block_index,
            max(0, block_count - 1),
        ),
    )

    module_attempt.current_block_index = (
        current_block_index
    )
    module_attempt.remaining_time_seconds = (
        module_attempt.calculated_remaining_seconds
    )

    module_attempt.save(
        update_fields=[
            "current_block_index",
            "remaining_time_seconds",
        ]
    )

    module_blocks = {
        block.id: block
        for block in WritingBlock.objects.filter(
            module=module_attempt.module,
        ).prefetch_related(
            "words",
        )
    }

    for answer_data in payload.get(
        "answers",
        [],
    ):
        try:
            block_id = int(
                answer_data.get("block_id")
            )
        except (TypeError, ValueError):
            continue

        block = module_blocks.get(block_id)

        if block is None:
            continue

        _save_writing_answer(
            module_attempt.attempt,
            block,
            answer_data,
        )

    return JsonResponse(
        {
            "success": True,
            "remaining_seconds": (
                module_attempt
                .calculated_remaining_seconds
            ),
        }
    )


@login_required
@transaction.atomic
def submit_writing_module_view(request, module_attempt_id):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "error": "POST request required.",
            },
            status=405,
        )

    module_attempt = get_object_or_404(
        WritingModuleAttempt.objects.select_related(
            "attempt",
            "attempt__user",
            "attempt__mock_test",
            "module",
            "module__mock_test",
        ),
        id=module_attempt_id,
        attempt__user=request.user,
    )

    attempt = module_attempt.attempt
    mock_test = module_attempt.module.mock_test
    full_attempt = _full_attempt_for_section_attempt(
        request.user,
        mock_test,
        "writing_attempt",
        attempt,
    )

    _complete_writing_module_attempt(module_attempt)
    next_module = _next_writing_module(
        module_attempt.module
    )

    if next_module is not None:
        next_url = reverse(
            "toefl:module_intro",
            kwargs={
                "slug": mock_test.slug,
                "section": FullTestAttempt.WRITING,
                "module_id": next_module.id,
            },
        )
    else:
        if not attempt.is_submitted:
            finalize_writing_attempt(attempt)

        if full_attempt is not None:
            _advance_full_test(
                full_attempt,
                FullTestAttempt.WRITING,
            )
            next_url = reverse(
                "toefl:section_intro",
                kwargs={
                    "slug": mock_test.slug,
                    "section": FullTestAttempt.SPEAKING,
                    "step": 1,
                },
            )
        else:
            next_url = reverse(
                "toefl:writing_result",
                kwargs={"attempt_id": attempt.id},
            )

    return JsonResponse(
        {
            "success": True,
            "next_url": next_url,
        }
    )


@login_required
def writing_result_view(request, attempt_id):
    attempt = get_object_or_404(
        WritingAttempt,
        id=attempt_id,
        user=request.user,
        is_submitted=True,
    )

    return render(
        request,
        "toefl/writing_result.html",
        {
            "attempt": attempt,
        },
    )


def finalize_listening_attempt(attempt):
    correct_count = attempt.answers.filter(
        is_correct=True
    ).count()

    total_questions = 0

    all_blocks = ListeningBlock.objects.filter(
        module__mock_test=attempt.mock_test
    ).prefetch_related("questions")

    for block in all_blocks:
        total_questions += block.questions.count()

    attempt.correct_answers = correct_count
    attempt.total_questions = total_questions
    attempt.is_submitted = True
    attempt.submitted_at = timezone.now()

    attempt.save(
        update_fields=[
            "correct_answers",
            "total_questions",
            "is_submitted",
            "submitted_at",
        ]
    )


@login_required
def take_listening_test_view(request, slug):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != FullTestAttempt.LISTENING:
        return _redirect_to_current_section(full_attempt)

    if not _section_intro_complete(
        request,
        full_attempt,
        FullTestAttempt.LISTENING,
    ):
        return redirect(
            "toefl:section_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.LISTENING,
            step=1,
        )

    attempt = _get_or_create_section_attempt(
        full_attempt,
        "listening_attempt",
        ListeningAttempt,
    )

    if attempt.is_submitted:
        _advance_full_test(
            full_attempt,
            FullTestAttempt.LISTENING,
        )
        return _redirect_to_current_section(full_attempt)

    blocks = list(
        ListeningBlock.objects.filter(
            module__mock_test=mock_test,
        )
        .select_related("module")
        .prefetch_related("questions")
        .order_by(
            "module__order",
            "order",
            "id",
        )
    )

    if not blocks:
        return render(
            request,
            "toefl/no_blocks.html",
            {"mock_test": mock_test},
        )

    answer_counts = {
        row["question__block_id"]: row["count"]
        for row in ListeningAnswer.objects.filter(
            attempt=attempt,
            question__block__module__mock_test=mock_test,
        )
        .values("question__block_id")
        .annotate(count=Count("id"))
    }

    for block in blocks:
        question_count = block.questions.count()
        completed_count = answer_counts.get(block.id, 0)

        if question_count > completed_count:
            module_has_answers = (
                ListeningAnswer.objects.filter(
                    attempt=attempt,
                    question__block__module_id=(
                        block.module_id
                    ),
                ).exists()
            )

            if (
                not module_has_answers
                and not _module_intro_complete(
                    request,
                    full_attempt,
                    FullTestAttempt.LISTENING,
                    block.module_id,
                )
            ):
                return redirect(
                    "toefl:module_intro",
                    slug=mock_test.slug,
                    section=FullTestAttempt.LISTENING,
                    module_id=block.module_id,
                )

            return redirect(
                "toefl:listening_block",
                slug=mock_test.slug,
                block_id=block.id,
            )

    finalize_listening_attempt(attempt)
    _advance_full_test(
        full_attempt,
        FullTestAttempt.LISTENING,
    )
    return _redirect_to_current_section(full_attempt)


@login_required
def listening_block_view(request, slug, block_id):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != FullTestAttempt.LISTENING:
        return _redirect_to_current_section(full_attempt)

    if not _section_intro_complete(
        request,
        full_attempt,
        FullTestAttempt.LISTENING,
    ):
        return redirect(
            "toefl:section_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.LISTENING,
            step=1,
        )

    block = get_object_or_404(
        ListeningBlock.objects.select_related(
            "module",
            "module__mock_test",
        ).prefetch_related(
            "questions__choices",
        ),
        id=block_id,
        module__mock_test=mock_test,
    )

    attempt = _get_or_create_section_attempt(
        full_attempt,
        "listening_attempt",
        ListeningAttempt,
    )

    if attempt.is_submitted:
        _advance_full_test(
            full_attempt,
            FullTestAttempt.LISTENING,
        )
        return _redirect_to_current_section(full_attempt)

    module_has_answers = (
        ListeningAnswer.objects.filter(
            attempt=attempt,
            question__block__module=block.module,
        ).exists()
    )

    if (
        request.method == "GET"
        and not module_has_answers
        and not _module_intro_complete(
            request,
            full_attempt,
            FullTestAttempt.LISTENING,
            block.module_id,
        )
    ):
        return redirect(
            "toefl:module_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.LISTENING,
            module_id=block.module_id,
        )

    all_blocks = list(
        ListeningBlock.objects.filter(
            module__mock_test=mock_test,
        )
        .select_related("module")
        .order_by(
            "module__order",
            "order",
            "id",
        )
    )

    try:
        current_index = next(
            index
            for index, candidate in enumerate(all_blocks)
            if candidate.id == block.id
        )
    except StopIteration:
        return redirect(
            "toefl:take_listening_test",
            slug=mock_test.slug,
        )

    next_block = (
        all_blocks[current_index + 1]
        if current_index + 1 < len(all_blocks)
        else None
    )

    saved_answers = {
        answer.question_id: answer.selected_choice_id
        for answer in ListeningAnswer.objects.filter(
            attempt=attempt,
            question__block=block,
        )
    }

    if request.method == "POST":
        with transaction.atomic():
            for question in block.questions.all():
                selected_choice_id = request.POST.get(
                    f"question_{question.id}"
                )

                selected_choice = None
                is_correct = False

                if selected_choice_id:
                    selected_choice = question.choices.filter(
                        id=selected_choice_id,
                    ).first()
                    is_correct = bool(
                        selected_choice
                        and selected_choice.is_correct
                    )

                ListeningAnswer.objects.update_or_create(
                    attempt=attempt,
                    question=question,
                    defaults={
                        "selected_choice": selected_choice,
                        "is_correct": is_correct,
                    },
                )

        if next_block is not None:
            if next_block.module_id != block.module_id:
                return redirect(
                    "toefl:module_intro",
                    slug=mock_test.slug,
                    section=FullTestAttempt.LISTENING,
                    module_id=next_block.module_id,
                )

            return redirect(
                "toefl:listening_block",
                slug=mock_test.slug,
                block_id=next_block.id,
            )

        finalize_listening_attempt(attempt)
        _advance_full_test(
            full_attempt,
            FullTestAttempt.LISTENING,
        )
        return _redirect_to_current_section(full_attempt)

    return render(
        request,
        "toefl/listening_block.html",
        {
            "mock_test": mock_test,
            "attempt": attempt,
            "block": block,
            "questions": block.questions.all(),
            "next_block": next_block,
            "saved_answers": saved_answers,
            "time_limit_seconds": block.time_limit_seconds,
        },
    )


@login_required
def listening_result_view(request, attempt_id):
    attempt = get_object_or_404(
        ListeningAttempt,
        id=attempt_id,
        user=request.user,
        is_submitted=True,
    )

    return render(
        request,
        "toefl/listening_result.html",
        {"attempt": attempt},
    )



def _ordered_speaking_blocks(mock_test):
    return list(
        SpeakingBlock.objects.filter(
            module__mock_test=mock_test,
        )
        .select_related(
            "module",
            "module__mock_test",
        )
        .order_by(
            "module__order",
            "order",
            "id",
        )
    )


def _finalize_speaking_attempt(attempt):
    total_questions = SpeakingBlock.objects.filter(
        module__mock_test=attempt.mock_test,
    ).count()

    completed_questions = attempt.answers.filter(
        block__module__mock_test=attempt.mock_test,
        is_completed=True,
    ).count()

    attempt.total_questions = total_questions
    attempt.completed_questions = completed_questions
    attempt.is_submitted = (
        total_questions > 0
        and completed_questions >= total_questions
    )

    if attempt.is_submitted:
        attempt.submitted_at = timezone.now()

    attempt.save(
        update_fields=[
            "total_questions",
            "completed_questions",
            "is_submitted",
            "submitted_at",
        ]
    )

    return attempt.is_submitted


@login_required
def take_speaking_test_view(request, slug):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != FullTestAttempt.SPEAKING:
        return _redirect_to_current_section(full_attempt)

    if not _section_intro_complete(
        request,
        full_attempt,
        FullTestAttempt.SPEAKING,
    ):
        return redirect(
            "toefl:section_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.SPEAKING,
            step=1,
        )

    attempt = _get_or_create_section_attempt(
        full_attempt,
        "speaking_attempt",
        SpeakingAttempt,
    )

    if attempt.is_submitted:
        _advance_full_test(
            full_attempt,
            FullTestAttempt.SPEAKING,
        )
        return _redirect_to_current_section(full_attempt)

    blocks = _ordered_speaking_blocks(mock_test)

    if not blocks:
        return render(
            request,
            "toefl/no_speaking_blocks.html",
            {"mock_test": mock_test},
        )

    first_module = blocks[0].module
    speaking_has_answers = SpeakingAnswer.objects.filter(
        attempt=attempt,
        block__module=first_module,
    ).exists()

    if (
        not speaking_has_answers
        and not _module_intro_complete(
            request,
            full_attempt,
            FullTestAttempt.SPEAKING,
            first_module.id,
        )
    ):
        return redirect(
            "toefl:module_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.SPEAKING,
            module_id=first_module.id,
        )

    saved_answers = {
        answer.block_id: answer
        for answer in SpeakingAnswer.objects.filter(
            attempt=attempt,
            block__module__mock_test=mock_test,
        ).select_related("block")
    }

    current_block_index = None

    for index, block in enumerate(blocks):
        saved_answer = saved_answers.get(block.id)
        block.saved_answer = saved_answer
        block.is_already_completed = bool(
            saved_answer
            and saved_answer.is_completed
            and saved_answer.recorded_audio
        )

        if (
            current_block_index is None
            and not block.is_already_completed
        ):
            current_block_index = index

    if current_block_index is None:
        _finalize_speaking_attempt(attempt)
        _advance_full_test(
            full_attempt,
            FullTestAttempt.SPEAKING,
        )
        return _redirect_to_current_section(full_attempt)

    return render(
        request,
        "toefl/speaking_module_mock.html",
        {
            "mock_test": mock_test,
            "attempt": attempt,
            "blocks": blocks,
            "current_block_index": current_block_index,
            "total_blocks": len(blocks),
        },
    )


@login_required
@transaction.atomic
def speaking_block_view(request, slug, block_id):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    block = get_object_or_404(
        SpeakingBlock.objects.select_related(
            "module",
            "module__mock_test",
        ),
        id=block_id,
        module__mock_test=mock_test,
    )

    if request.method != "POST":
        return redirect(
            "toefl:take_speaking_test",
            slug=mock_test.slug,
        )

    full_attempt = (
        FullTestAttempt.objects.select_for_update()
        .filter(
            user=request.user,
            mock_test=mock_test,
            is_completed=False,
            current_section=FullTestAttempt.SPEAKING,
        )
        .select_related("speaking_attempt")
        .first()
    )

    if full_attempt is None:
        return JsonResponse(
            {
                "success": False,
                "error": "No active full TOEFL attempt was found.",
            },
            status=409,
        )

    attempt = _get_or_create_section_attempt(
        full_attempt,
        "speaking_attempt",
        SpeakingAttempt,
    )

    posted_attempt_id = request.POST.get("attempt_id")
    if posted_attempt_id:
        try:
            posted_attempt_id = int(posted_attempt_id)
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "success": False,
                    "error": "Invalid Speaking attempt ID.",
                },
                status=400,
            )

        if posted_attempt_id != attempt.id:
            return JsonResponse(
                {
                    "success": False,
                    "error": "This recording belongs to another test run.",
                },
                status=409,
            )

    try:
        recorded_audio = request.FILES.get("recorded_audio")

        if recorded_audio is None:
            return JsonResponse(
                {
                    "success": False,
                    "error": "No audio file was received by Django.",
                    "received_file_fields": list(request.FILES.keys()),
                },
                status=400,
            )

        if recorded_audio.size <= 0:
            return JsonResponse(
                {
                    "success": False,
                    "error": "The uploaded recording is empty.",
                },
                status=400,
            )

        if recorded_audio.size > 20 * 1024 * 1024:
            return JsonResponse(
                {
                    "success": False,
                    "error": "The recording is larger than 20 MB.",
                },
                status=400,
            )

        try:
            duration_seconds = max(
                0,
                float(request.POST.get("duration_seconds", "0")),
            )
        except (TypeError, ValueError):
            duration_seconds = 0

        mime_type = (
            request.POST.get("mime_type", "").strip()
            or getattr(recorded_audio, "content_type", "")
            or "application/octet-stream"
        )

        answer, created = SpeakingAnswer.objects.get_or_create(
            attempt=attempt,
            block=block,
        )

        old_audio = (
            answer.recorded_audio
            if not created and answer.recorded_audio
            else None
        )

        answer.recorded_audio = recorded_audio
        answer.duration_seconds = duration_seconds
        answer.mime_type = mime_type
        answer.is_completed = True
        answer.save()

        if old_audio:
            old_audio_name = old_audio.name
            old_storage = old_audio.storage

            def delete_previous_recording():
                try:
                    old_storage.delete(old_audio_name)
                except Exception:
                    logger.exception(
                        "Could not delete the previous Speaking recording."
                    )

            transaction.on_commit(delete_previous_recording)

        blocks = _ordered_speaking_blocks(mock_test)
        completed_block_ids = set(
            SpeakingAnswer.objects.filter(
                attempt=attempt,
                block__module__mock_test=mock_test,
                is_completed=True,
                recorded_audio__isnull=False,
            ).values_list("block_id", flat=True)
        )

        next_incomplete_block = next(
            (
                candidate
                for candidate in blocks
                if candidate.id not in completed_block_ids
            ),
            None,
        )

        if next_incomplete_block is None:
            _finalize_speaking_attempt(attempt)
            _advance_full_test(
                full_attempt,
                FullTestAttempt.SPEAKING,
            )

            return JsonResponse(
                {
                    "success": True,
                    "finished": True,
                    "next_block_id": None,
                    "next_url": reverse(
                        "toefl:full_test_result",
                        kwargs={"slug": mock_test.slug},
                    ),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "finished": False,
                "next_block_id": next_incomplete_block.id,
                "next_url": reverse(
                    "toefl:take_speaking_test",
                    kwargs={"slug": mock_test.slug},
                ),
            }
        )

    except Exception as exc:
        logger.exception(
            "Speaking recording upload failed. attempt=%s block=%s",
            attempt.id,
            block.id,
        )
        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
            },
            status=500,
        )


@login_required
def speaking_result_view(request, attempt_id):
    attempt = get_object_or_404(
        SpeakingAttempt.objects.select_related(
            "mock_test",
            "user",
        ).prefetch_related(
            "answers__block",
        ),
        id=attempt_id,
        user=request.user,
        is_submitted=True,
    )

    return render(
        request,
        "toefl/speaking_result.html",
        {
            "attempt": attempt,
        },
    )

@login_required
def take_reading_test_view(request, slug):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != FullTestAttempt.READING:
        return _redirect_to_current_section(full_attempt)

    if not _section_intro_complete(
        request,
        full_attempt,
        FullTestAttempt.READING,
    ):
        return redirect(
            "toefl:section_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.READING,
            step=1,
        )

    attempt = _get_or_create_section_attempt(
        full_attempt,
        "reading_attempt",
        MockAttempt,
    )

    if attempt.is_submitted:
        _advance_full_test(
            full_attempt,
            FullTestAttempt.READING,
        )
        return _redirect_to_current_section(full_attempt)

    modules = list(
        ReadingModule.objects.filter(
            mock_test=mock_test,
        ).order_by("order", "id")
    )

    if not modules:
        return render(
            request,
            "toefl/no_reading_modules.html",
            {"mock_test": mock_test},
        )

    states = {
        state.module_id: state
        for state in ModuleAttempt.objects.filter(
            attempt=attempt,
            module__mock_test=mock_test,
        )
    }

    for module in modules:
        state = states.get(module.id)

        if state is None:
            return redirect(
                "toefl:module_intro",
                slug=mock_test.slug,
                section=FullTestAttempt.READING,
                module_id=module.id,
            )

        if not state.is_completed:
            return redirect(
                "toefl:reading_module",
                slug=mock_test.slug,
                module_id=module.id,
            )

    finalize_attempt(attempt)
    _advance_full_test(
        full_attempt,
        FullTestAttempt.READING,
    )
    return _redirect_to_current_section(full_attempt)


@login_required
def reading_module_view(
    request,
    slug,
    module_id,
):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True,
    )

    module = get_object_or_404(
        ReadingModule.objects.select_related(
            "mock_test",
        ),
        id=module_id,
        mock_test=mock_test,
    )

    full_attempt = _get_or_create_full_test_attempt(
        request.user,
        mock_test,
    )

    if full_attempt.current_section != FullTestAttempt.READING:
        return _redirect_to_current_section(full_attempt)

    attempt = _get_or_create_section_attempt(
        full_attempt,
        "reading_attempt",
        MockAttempt,
    )

    if attempt.is_submitted:
        _advance_full_test(
            full_attempt,
            FullTestAttempt.READING,
        )
        return _redirect_to_current_section(full_attempt)

    existing_module_attempt = (
        ModuleAttempt.objects.filter(
            attempt=attempt,
            module=module,
        ).first()
    )

    if (
        existing_module_attempt is None
        and not _module_intro_complete(
            request,
            full_attempt,
            FullTestAttempt.READING,
            module.id,
        )
    ):
        return redirect(
            "toefl:module_intro",
            slug=mock_test.slug,
            section=FullTestAttempt.READING,
            module_id=module.id,
        )

    module_time_limit = _reading_module_time_limit(module)

    module_attempt, created = (
        ModuleAttempt.objects.get_or_create(
            attempt=attempt,
            module=module,
            defaults={
                "remaining_time_seconds": module_time_limit,
                "expires_at": (
                    timezone.now()
                    + timedelta(seconds=module_time_limit)
                ),
                "current_block_index": 0,
                "is_completed": False,
            },
        )
    )

    if (
        not created
        and module_attempt.expires_at is None
    ):
        module_attempt.expires_at = (
            timezone.now()
            + timedelta(
                seconds=max(
                    0,
                    module_attempt.remaining_time_seconds,
                )
            )
        )

        module_attempt.save(
            update_fields=[
                "expires_at",
            ]
        )

    if module_attempt.is_completed:
        next_module = (
            ReadingModule.objects.filter(
                mock_test=mock_test,
            )
            .filter(
                Q(order__gt=module.order)
                | Q(
                    order=module.order,
                    id__gt=module.id,
                )
            )
            .order_by(
                "order",
                "id",
            )
            .first()
        )

        if next_module is not None:
            return redirect(
                "toefl:module_intro",
                slug=mock_test.slug,
                section=FullTestAttempt.READING,
                module_id=next_module.id,
            )

        # آخرین Module قبلاً کامل شده،
        # ولی Attempt اصلی هنوز نهایی نشده است.
        if not attempt.is_submitted:
            finalize_attempt(attempt)

        _advance_full_test(
            full_attempt,
            FullTestAttempt.READING,
        )
        return _redirect_to_current_section(full_attempt)

    remaining_seconds = (
        module_attempt.calculated_remaining_seconds
    )

    if remaining_seconds <= 0:
        module_attempt.is_completed = True
        module_attempt.completed_at = timezone.now()
        module_attempt.remaining_time_seconds = 0

        module_attempt.save(
            update_fields=[
                "is_completed",
                "completed_at",
                "remaining_time_seconds",
            ]
        )

        next_module = (
            ReadingModule.objects.filter(
                mock_test=mock_test,
            )
            .filter(
                Q(order__gt=module.order)
                | Q(
                    order=module.order,
                    id__gt=module.id,
                )
            )
            .order_by(
                "order",
                "id",
            )
            .first()
        )

        if next_module is not None:
            return redirect(
                "toefl:module_intro",
                slug=mock_test.slug,
                section=FullTestAttempt.READING,
                module_id=next_module.id,
            )

        if not attempt.is_submitted:
            finalize_attempt(attempt)

        _advance_full_test(
            full_attempt,
            FullTestAttempt.READING,
        )
        return _redirect_to_current_section(full_attempt)

    blocks = list(
        ReadingBlock.objects.filter(
            module=module,
        )
        .prefetch_related(
            "questions__choices",
        )
        .order_by(
            "order",
            "id",
        )
    )

    # ==============================================
    # Saved multiple-choice answers
    # ==============================================

    choice_answers = (
        UserAnswer.objects.filter(
            attempt=attempt,
            question__block__module=module,
        )
        .select_related(
            "question",
            "selected_choice",
        )
    )

    saved_choice_ids = {
        answer.question_id:
            answer.selected_choice_id
        for answer in choice_answers
        if answer.question_id is not None
    }

    for block in blocks:
        for question in block.questions.all():
            question.saved_choice_id = (
                saved_choice_ids.get(
                    question.id
                )
            )

    # ==============================================
    # Prepare Complete Words content
    # ==============================================

    complete_word_question_numbers = []

    for block in blocks:
        if (
            block.block_type
            != ReadingBlock.COMPLETE_WORDS
        ):
            continue

        normalized_parts = []

        for original_part in (
            block.get_processed_content()
        ):
            part = dict(original_part)

            if part.get("type") == "input":
                full_word = str(
                    part.get(
                        "full_word",
                        "",
                    )
                )

                start_part = str(
                    part.get(
                        "start_part",
                        "",
                    )
                )

                question_number = int(
                    part.get(
                        "q_number"
                    )
                )

                missing_count = (
                    len(full_word)
                    - len(start_part)
                )

                if missing_count <= 0:
                    missing_count = len(
                        str(
                            part.get(
                                "dashes",
                                "",
                            )
                        )
                    )

                if missing_count <= 0:
                    missing_count = 1

                part["missing_count"] = (
                    missing_count
                )

                part["q_number"] = (
                    question_number
                )

                complete_word_question_numbers.append(
                    question_number
                )

            else:
                part["display_text"] = (
                    part.get("text")
                    or part.get("content")
                    or part.get("value")
                    or ""
                )

            normalized_parts.append(part)

        block.processed_content = (
            normalized_parts
        )

    # ==============================================
    # Saved Complete Words answers
    # ==============================================

    saved_word_answers = {}

    if complete_word_question_numbers:
        saved_word_answers = {
            answer.global_question_number:
                answer.text_answer or ""
            for answer in UserAnswer.objects.filter(
                attempt=attempt,
                question__isnull=True,
                global_question_number__in=(
                    complete_word_question_numbers
                ),
            )
        }

    # ساخت یک input جدا برای هر حرف ناقص
    for block in blocks:
        if (
            block.block_type
            != ReadingBlock.COMPLETE_WORDS
        ):
            continue

        for part in block.processed_content:
            if part.get("type") != "input":
                continue

            question_number = part["q_number"]

            saved_value = str(
                saved_word_answers.get(
                    question_number,
                    "",
                )
            )

            missing_count = part[
                "missing_count"
            ]

            saved_value = saved_value[
                :missing_count
            ]

            letter_slots = []

            for index in range(missing_count):
                value = ""

                if index < len(saved_value):
                    value = saved_value[index]

                letter_slots.append(
                    {
                        "index": index,
                        "value": value,
                    }
                )

            part["letter_slots"] = (
                letter_slots
            )

    # ==============================================
    # Total number of Reading questions
    # ==============================================

    total_test_questions = 0

    all_test_blocks = (
        ReadingBlock.objects.filter(
            module__mock_test=mock_test,
        )
        .prefetch_related(
            "questions",
        )
    )

    for test_block in all_test_blocks:
        if (
            test_block.block_type
            == ReadingBlock.COMPLETE_WORDS
        ):
            total_test_questions += sum(
                1
                for part in (
                    test_block.get_processed_content()
                )
                if part.get("type") == "input"
            )
        else:
            total_test_questions += (
                test_block.questions.count()
            )

    current_block_index = min(
        module_attempt.current_block_index,
        max(
            0,
            len(blocks) - 1,
        ),
    )

    context = {
        "mock_test": mock_test,
        "attempt": attempt,
        "module": module,
        "module_attempt": module_attempt,
        "blocks": blocks,
        "remaining_seconds": remaining_seconds,
        "current_block_index": (
            current_block_index
        ),
        "total_test_questions": (
            total_test_questions
        ),
    }

    return render(
        request,
        "toefl/reading_module_mock.html",
        context,
    )


@login_required
@transaction.atomic
def save_reading_module_progress_view(
    request,
    module_attempt_id,
):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "error": "POST request required.",
            },
            status=405,
        )

    module_attempt = get_object_or_404(
        ModuleAttempt.objects.select_related(
            "attempt",
            "attempt__user",
            "module",
        ),
        id=module_attempt_id,
        attempt__user=request.user,
        is_completed=False,
    )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON data.",
            },
            status=400,
        )

    raw_index = payload.get(
        "current_block_index",
        module_attempt.current_block_index,
    )

    block_count = ReadingBlock.objects.filter(
        module=module_attempt.module,
    ).count()

    try:
        current_block_index = int(raw_index)
    except (TypeError, ValueError):
        current_block_index = 0

    current_block_index = max(
        0,
        min(
            current_block_index,
            max(0, block_count - 1),
        ),
    )

    module_attempt.current_block_index = (
        current_block_index
    )

    module_attempt.remaining_time_seconds = (
        module_attempt.calculated_remaining_seconds
    )

    module_attempt.save(
        update_fields=[
            "current_block_index",
            "remaining_time_seconds",
        ]
    )

    answers = payload.get(
        "answers",
        [],
    )

    # Build the correct-answer map for Complete the Words.
    complete_word_correct_answers = {}

    complete_word_blocks = (
        ReadingBlock.objects.filter(
            module=module_attempt.module,
            block_type=(
                ReadingBlock.COMPLETE_WORDS
            ),
        )
        .order_by(
            "order",
            "id",
        )
    )

    for complete_word_block in complete_word_blocks:
        for part in (
            complete_word_block
            .get_processed_content()
        ):
            if part.get("type") != "input":
                continue

            try:
                question_number = int(
                    part["q_number"]
                )
            except (KeyError, TypeError, ValueError):
                continue

            full_word = str(
                part.get(
                    "full_word",
                    "",
                )
            )

            start_part = str(
                part.get(
                    "start_part",
                    "",
                )
            )

            correct_remainder = full_word[
                len(start_part):
            ].strip().lower()

            complete_word_correct_answers[
                question_number
            ] = correct_remainder

    # Save all answers sent by the module page.
    for answer_data in answers:
        question_id = answer_data.get(
            "question_id"
        )

        global_question_number = (
            answer_data.get(
                "global_question_number"
            )
        )

        selected_choice_id = (
            answer_data.get(
                "selected_choice_id"
            )
        )

        text_answer = str(
            answer_data.get(
                "text_answer",
                "",
            )
        )

        # Multiple-choice question.
        if question_id:
            question = (
                ReadingQuestion.objects.filter(
                    id=question_id,
                    block__module=(
                        module_attempt.module
                    ),
                )
                .first()
            )

            if question is None:
                continue

            selected_choice = None

            if selected_choice_id:
                selected_choice = (
                    ReadingChoice.objects.filter(
                        id=selected_choice_id,
                        question=question,
                    )
                    .first()
                )

            UserAnswer.objects.update_or_create(
                attempt=module_attempt.attempt,
                question=question,
                defaults={
                    "global_question_number": None,
                    "selected_choice": selected_choice,
                    "text_answer": "",
                    "is_correct": bool(
                        selected_choice
                        and selected_choice.is_correct
                    ),
                },
            )

            continue

        # Complete the Words question.
        if global_question_number:
            try:
                question_number = int(
                    global_question_number
                )
            except (TypeError, ValueError):
                continue

            if (
                question_number
                not in complete_word_correct_answers
            ):
                continue

            normalized_answer = (
                text_answer.strip().lower()
            )

            correct_answer = (
                complete_word_correct_answers[
                    question_number
                ]
            )

            UserAnswer.objects.update_or_create(
                attempt=module_attempt.attempt,
                question=None,
                global_question_number=(
                    question_number
                ),
                defaults={
                    "selected_choice": None,
                    "text_answer": (
                        normalized_answer
                    ),
                    "is_correct": (
                        normalized_answer
                        == correct_answer
                    ),
                },
            )

    return JsonResponse(
        {
            "success": True,
            "remaining_seconds": (
                module_attempt
                .calculated_remaining_seconds
            ),
        }
    )


@login_required
@transaction.atomic
def submit_reading_module_view(request, module_attempt_id):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "error": "POST request required.",
            },
            status=405,
        )

    module_attempt = get_object_or_404(
        ModuleAttempt.objects.select_related(
            "attempt",
            "attempt__mock_test",
            "module",
            "module__mock_test",
        ),
        id=module_attempt_id,
        attempt__user=request.user,
    )

    attempt = module_attempt.attempt
    mock_test = module_attempt.module.mock_test
    full_attempt = _full_attempt_for_section_attempt(
        request.user,
        mock_test,
        "reading_attempt",
        attempt,
    )

    module_attempt.is_completed = True
    module_attempt.completed_at = timezone.now()
    module_attempt.remaining_time_seconds = 0
    module_attempt.save(
        update_fields=[
            "is_completed",
            "completed_at",
            "remaining_time_seconds",
        ]
    )

    next_module = (
        ReadingModule.objects.filter(
            mock_test=mock_test,
        )
        .filter(
            Q(order__gt=module_attempt.module.order)
            | Q(
                order=module_attempt.module.order,
                id__gt=module_attempt.module.id,
            )
        )
        .order_by("order", "id")
        .first()
    )

    if next_module is not None:
        next_url = reverse(
            "toefl:module_intro",
            kwargs={
                "slug": mock_test.slug,
                "section": FullTestAttempt.READING,
                "module_id": next_module.id,
            },
        )
    else:
        if not attempt.is_submitted:
            finalize_attempt(attempt)

        if full_attempt is not None:
            _advance_full_test(
                full_attempt,
                FullTestAttempt.READING,
            )
            next_url = reverse(
                "toefl:section_intro",
                kwargs={
                    "slug": mock_test.slug,
                    "section": FullTestAttempt.LISTENING,
                    "step": 1,
                },
            )
        else:
            next_url = reverse(
                "toefl:test_result",
                kwargs={"attempt_id": attempt.id},
            )

    return JsonResponse(
        {
            "success": True,
            "next_url": next_url,
        }
    )
