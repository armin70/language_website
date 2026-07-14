from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import MockTest, MockAttempt, ReadingBlock, UserAnswer, ReadingChoice, ReadingQuestion

@login_required
def take_mock_test_view(request, slug):
    # ۱. پیدا کردن آزمون
    mock_test = get_object_or_404(MockTest, slug=slug, is_active=True)
    
    # ۲. ایجاد یا پیدا کردن یک Attempt فعال برای کاربر در این آزمون
    attempt = MockAttempt.objects.filter(
        user=request.user,
        mock_test=mock_test,
        is_submitted=False
    ).order_by('-started_at').first()

    if not attempt:
        attempt = MockAttempt.objects.create(
            user=request.user,
            mock_test=mock_test,
            is_submitted=False
        )
        
    # ۳. دریافت تمام ماژول‌ها و بلاک‌های متصل به این آزمون به ترتیب چیدمان
    modules = mock_test.reading_modules.all().prefetch_related('blocks__questions__choices')
    
    context = {
        'mock_test': mock_test,
        'attempt': attempt,
        'modules': modules,
    }
    first_block = mock_test.get_all_blocks().first()

    if first_block is None:
        return render(request, "toefl/no_blocks.html", {
            "mock_test": mock_test,
        })

    return redirect(
        "toefl:reading_block",
        slug=mock_test.slug,
        block_id=first_block.id
    )


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


def save_block_answers(request, attempt, block):
    if block.block_type == ReadingBlock.COMPLETE_WORDS:
        for part in block.get_processed_content():
            if part["type"] != "input":
                continue

            question_number = part["q_number"]
            user_value = request.POST.get(
                f"q_{question_number}",
                ""
            ).strip().lower()

            correct_remainder = part["full_word"][
                len(part["start_part"]):
            ].strip().lower()

            UserAnswer.objects.update_or_create(
                attempt=attempt,
                question=None,
                global_question_number=question_number,
                defaults={
                    "text_answer": user_value,
                    "selected_choice": None,
                    "is_correct": user_value == correct_remainder,
                }
            )

        return

    for question in block.questions.prefetch_related("choices"):
        selected_choice_id = request.POST.get(
            f"question_{question.id}"
        )

        selected_choice = None

        if selected_choice_id:
            selected_choice = question.choices.filter(
                id=selected_choice_id
            ).first()

        UserAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                "global_question_number": None,
                "text_answer": "",
                "selected_choice": selected_choice,
                "is_correct": bool(
                    selected_choice and selected_choice.is_correct
                ),
            }
        )


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
def reading_block_view(request, slug, block_id):
    mock_test = get_object_or_404(
        MockTest,
        slug=slug,
        is_active=True
    )

    block = get_object_or_404(
        ReadingBlock.objects.select_related("module"),
        id=block_id,
        module__mock_test=mock_test
    )

    attempt = MockAttempt.objects.filter(
        user=request.user,
        mock_test=mock_test,
        is_submitted=False
    ).order_by("-started_at").first()

    if not attempt:
        attempt = MockAttempt.objects.create(
            user=request.user,
            mock_test=mock_test
        )

    all_blocks = list(mock_test.get_all_blocks())
    current_index = all_blocks.index(block)

    if request.method == "POST":
        save_block_answers(request, attempt, block)

        if current_index + 1 < len(all_blocks):
            next_block = all_blocks[current_index + 1]

            return redirect(
                "toefl:reading_block",
                slug=slug,
                block_id=next_block.id
            )

        finalize_attempt(attempt)

        return redirect(
            "toefl:test_result",
            attempt_id=attempt.id
        )

    next_block = (
        all_blocks[current_index + 1]
        if current_index + 1 < len(all_blocks)
        else None
    )

    return render(request, "toefl/reading_block.html", {
        "mock_test": mock_test,
        "block": block,
        "next_block": next_block,
        "attempt": attempt,
    })

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