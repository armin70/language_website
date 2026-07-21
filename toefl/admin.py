from django.contrib import admin

from .models import (
    MockTest,
    FullTestAttempt,
    ReadingModule,
    ReadingBlock,
    ReadingQuestion,
    ReadingChoice,
    MockAttempt,
    UserAnswer,
    ModuleAttempt,

    WritingModule,
    WritingBlock,
    WritingWord,
    WritingAttempt,
    WritingAnswer,
    AcademicDiscussionPost,
    WritingModuleAttempt,
    
    ListeningModule,
    ListeningBlock,
    ListeningQuestion,
    ListeningChoice,
    ListeningAttempt,
    ListeningAnswer,
    
    # Speaking
    SpeakingModule,
    SpeakingBlock,
    SpeakingAttempt,
    SpeakingAnswer,
)


# ======================================================
# Reading inlines
# ======================================================

class ReadingChoiceInline(admin.TabularInline):
    model = ReadingChoice
    extra = 4

    fields = (
        "text",
        "is_correct",
        "order",
    )


class ReadingQuestionInline(admin.StackedInline):
    model = ReadingQuestion
    extra = 1

    fields = (
        "question_number",
        "question_text",
        "points",
        "order",
    )

    show_change_link = True


class ReadingBlockInline(admin.StackedInline):
    model = ReadingBlock
    extra = 1

    fields = (
        "block_type",
        "title",
        "instructions",

        # Email / Message information
        "sender",
        "recipient",
        "subject",
        "sent_at_text",

        "text",
        "order",
        "start_question_number",
        "end_question_number",
    )

    show_change_link = True


# ======================================================
# Writing inlines
# ======================================================
class AcademicDiscussionPostInline(admin.StackedInline):
    model = AcademicDiscussionPost
    extra = 2

    fields = (
        "author_name",
        "avatar",
        "text",
        "order",
    )
class WritingWordInline(admin.TabularInline):
    model = WritingWord
    extra = 8

    fields = (
        "text",
        "display_order",
        "correct_position",
    )

    ordering = (
        "display_order",
        "id",
    )

class WritingBlockInline(admin.StackedInline):
    model = WritingBlock
    extra = 1
    show_change_link = True

    fields = (
        # General
        "block_type",
        "title",
        "instructions",
        "time_limit_seconds",
        "order",

        # Build a Sentence
        "speaker_one_name",
        "speaker_one_text",
        "speaker_two_name",
        "answer_template",

        # Write an Email
        "email_scenario",
        "email_recipient",
        "email_subject",
        "email_requirements",

        # Academic Discussion
        "discussion_class_title",
        "professor_name",
        "professor_avatar",
        "professor_prompt",
        "discussion_requirements",
        "minimum_words",
    )
# ======================================================
# Mock Test
# ======================================================

@admin.register(MockTest)
class MockTestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "is_active",
        "order",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "title",
        "slug",
        "description",
    )

    ordering = (
        "order",
        "id",
    )

    prepopulated_fields = {
        "slug": ("title",)
    }


# ======================================================
# Reading admin
# ======================================================

@admin.register(ReadingModule)
class ReadingModuleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "mock_test",
        "order",
        "time_limit_seconds",
    )

    list_filter = (
        "mock_test",
    )

    search_fields = (
        "title",
        "mock_test__title",
    )

    ordering = (
        "mock_test",
        "order",
        "id",
    )

    inlines = [
        ReadingBlockInline,
    ]


@admin.register(ReadingBlock)
class ReadingBlockAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "module",
        "block_type",
        "start_question_number",
        "end_question_number",
        "order",
    )

    list_filter = (
        "module__mock_test",
        "module",
        "block_type",
    )

    search_fields = (
        "title",
        "text",
        "subject",
        "sender",
        "recipient",
    )

    ordering = (
        "module__mock_test",
        "module__order",
        "order",
        "id",
    )

    fieldsets = (
        (
            "General Information",
            {
                "fields": (
                    "module",
                    "block_type",
                    "title",
                    "instructions",
                    "order",
                )
            },
        ),
        (
            "Email / Message Information",
            {
                "fields": (
                    "sender",
                    "recipient",
                    "subject",
                    "sent_at_text",
                ),
                "description": (
                    "Use these fields for Email, Text Message, "
                    "Notice, and similar blocks."
                ),
            },
        ),
        (
            "Reading Content",
            {
                "fields": (
                    "text",
                    "start_question_number",
                    "end_question_number",
                )
            },
        ),
    )

    inlines = [
        ReadingQuestionInline,
    ]


@admin.register(ReadingQuestion)
class ReadingQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "question_number",
        "block",
        "short_question_text",
        "order",
        "points",
    )

    list_filter = (
        "block__module__mock_test",
        "block__module",
        "block",
    )

    search_fields = (
        "question_text",
        "block__title",
    )

    ordering = (
        "question_number",
        "order",
        "id",
    )

    inlines = [
        ReadingChoiceInline,
    ]

    @admin.display(description="Question")
    def short_question_text(self, obj):
        return obj.question_text[:80]


@admin.register(ReadingChoice)
class ReadingChoiceAdmin(admin.ModelAdmin):
    list_display = (
        "short_text",
        "question",
        "is_correct",
        "order",
    )

    list_filter = (
        "is_correct",
        "question__block__module__mock_test",
        "question__block",
    )

    search_fields = (
        "text",
        "question__question_text",
    )

    ordering = (
        "question",
        "order",
        "id",
    )

    @admin.display(description="Choice")
    def short_text(self, obj):
        return obj.text[:80]


@admin.register(MockAttempt)
class MockAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "mock_test",
        "started_at",
        "submitted_at",
        "is_submitted",
        "correct_answers",
        "total_questions",
        "score",
    )

    list_filter = (
        "mock_test",
        "is_submitted",
        "started_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "mock_test__title",
    )

    readonly_fields = (
        "started_at",
    )

    ordering = (
        "-started_at",
    )


@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "global_question_number",
        "selected_choice",
        "text_answer",
        "is_correct",
    )

    list_filter = (
        "is_correct",
        "attempt__mock_test",
    )

    search_fields = (
        "attempt__user__username",
        "text_answer",
        "question__question_text",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(ModuleAttempt)
class ModuleAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "module",
        "remaining_time_seconds",
        "started_at",
        "is_completed",
    )

    list_filter = (
        "is_completed",
        "module__mock_test",
        "module",
    )

    search_fields = (
        "attempt__user__username",
        "module__title",
        "module__mock_test__title",
    )


# ======================================================
# Writing admin
# ======================================================

@admin.register(WritingModule)
class WritingModuleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "mock_test",
        "order",
        "time_limit_seconds",
    )

    list_filter = (
        "mock_test",
    )

    search_fields = (
        "title",
        "mock_test__title",
    )

    ordering = (
        "mock_test",
        "order",
        "id",
    )

    inlines = [
        WritingBlockInline,
    ]

@admin.register(WritingBlock)
class WritingBlockAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "module",
        "block_type",
        "display_blank_count",
        "time_limit_seconds",
        "order",
    )

    list_filter = (
        "module__mock_test",
        "module",
        "block_type",
    )

    search_fields = (
        "title",
        "instructions",

        # Build a Sentence
        "speaker_one_name",
        "speaker_one_text",
        "speaker_two_name",
        "answer_template",

        # Write an Email
        "email_scenario",
        "email_recipient",
        "email_subject",
        "email_requirements",

        # Academic Discussion
        "discussion_class_title",
        "professor_name",
        "professor_prompt",
        "discussion_requirements",
    )

    ordering = (
        "module__mock_test",
        "module__order",
        "order",
        "id",
    )

    fieldsets = (
        (
            "General Information",
            {
                "fields": (
                    "module",
                    "block_type",
                    "title",
                    "instructions",
                    "time_limit_seconds",
                    "order",
                )
            },
        ),

        (
            "Build a Sentence",
            {
                "fields": (
                    "speaker_one_name",
                    "speaker_one_text",
                    "speaker_two_name",
                    "answer_template",
                ),
                "description": (
                    "Use these fields only for "
                    "Build a Sentence."
                ),
            },
        ),

        (
            "Write an Email",
            {
                "fields": (
                    "email_scenario",
                    "email_recipient",
                    "email_subject",
                    "email_requirements",
                ),
                "description": (
                    "Use these fields only for "
                    "Write an Email. Enter one requirement per line."
                ),
            },
        ),
    )

    inlines = [
        WritingWordInline,
        AcademicDiscussionPostInline,
    ]

    @admin.display(description="Blank Count")
    def display_blank_count(self, obj):
        return obj.blank_count


@admin.register(WritingWord)
class WritingWordAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "block",
        "display_order",
        "correct_position",
        "word_type",
    )

    list_filter = (
        "block__module__mock_test",
        "block__module",
        "block",
    )

    search_fields = (
        "text",
        "block__title",
    )

    ordering = (
        "block",
        "display_order",
        "id",
    )

    @admin.display(description="Type")
    def word_type(self, obj):
        if obj.correct_position is None:
            return "Distractor"

        return "Correct"


@admin.register(AcademicDiscussionPost)
class AcademicDiscussionPostAdmin(admin.ModelAdmin):
    list_display = (
        "author_name",
        "block",
        "order",
        "short_text",
    )

    list_filter = (
        "block__module__mock_test",
        "block",
    )

    search_fields = (
        "author_name",
        "text",
        "block__title",
    )

    ordering = (
        "block",
        "order",
        "id",
    )

    @admin.display(description="Post")
    def short_text(self, obj):
        return obj.text[:100]


@admin.register(WritingAttempt)
class WritingAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "mock_test",
        "started_at",
        "submitted_at",
        "correct_answers",
        "total_questions",
        "is_submitted",
    )

    list_filter = (
        "mock_test",
        "is_submitted",
        "started_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "mock_test__title",
    )

    readonly_fields = (
        "started_at",
    )

    ordering = (
        "-started_at",
    )


@admin.register(WritingAnswer)
class WritingAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "block",
        "display_selected_words",
        "is_correct",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "is_correct",
        "attempt__mock_test",
        "block__module",
    )

    search_fields = (
        "attempt__user__username",
        "block__title",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-updated_at",
    )

    @admin.display(description="Selected Word IDs")
    def display_selected_words(self, obj):
        selected_ids = obj.selected_word_ids or []

        if not selected_ids:
            return "—"

        return ", ".join(
            str(word_id)
            for word_id in selected_ids
        )



class ListeningChoiceInline(admin.TabularInline):
    model = ListeningChoice
    extra = 4
    fields = (
        "text",
        "is_correct",
        "order",
    )


class ListeningQuestionInline(admin.StackedInline):
    model = ListeningQuestion
    extra = 1
    fields = (
        "question_number",
        "question_text",
        "points",
        "order",
    )
    show_change_link = True


class ListeningBlockInline(admin.StackedInline):
    model = ListeningBlock
    extra = 1
    fields = (
        "block_type",
        "title",
        "instructions",
        "speaker_image",
        "audio_file",
        "lock_questions_until_audio_ends",
        "time_limit_seconds",
        "order",
    )
    show_change_link = True

# ======================================================
# Listening admin
# ======================================================


@admin.register(ListeningModule)
class ListeningModuleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "mock_test",
        "order",
        "time_limit_seconds",
    )
    list_filter = ("mock_test",)
    ordering = ("mock_test", "order", "id")
    inlines = [ListeningBlockInline]


@admin.register(ListeningBlock)
class ListeningBlockAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "module",
        "block_type",
        "time_limit_seconds",
        "order",
    )
    list_filter = (
        "module__mock_test",
        "module",
        "block_type",
    )
    search_fields = (
        "title",
        "instructions",
    )
    fieldsets = (
        (
            "General Information",
            {
                "fields": (
                    "module",
                    "block_type",
                    "title",
                    "instructions",
                    "order",
                )
            },
        ),
        (
            "Media / Behavior",
            {
                "fields": (
                    "speaker_image",
                    "audio_file",
                    "lock_questions_until_audio_ends",
                    "time_limit_seconds",
                )
            },
        ),
    )
    inlines = [ListeningQuestionInline]


@admin.register(ListeningQuestion)
class ListeningQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "question_number",
        "block",
        "question_text",
        "order",
        "points",
    )
    list_filter = (
        "block__module__mock_test",
        "block__module",
        "block",
    )
    inlines = [ListeningChoiceInline]


@admin.register(ListeningChoice)
class ListeningChoiceAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "question",
        "is_correct",
        "order",
    )


@admin.register(ListeningAttempt)
class ListeningAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "mock_test",
        "started_at",
        "submitted_at",
        "correct_answers",
        "total_questions",
        "is_submitted",
    )


@admin.register(ListeningAnswer)
class ListeningAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "selected_choice",
        "is_correct",
    )


# ======================================================
# Speaking inlines
# ======================================================

class SpeakingBlockInline(admin.StackedInline):
    model = SpeakingBlock
    extra = 1

    fields = (
        "block_type",
        "title",
        "instructions",

        # Media
        "prompt_image",
        "prompt_audio",
        "prompt_video",
        # Hidden reference answer
        "reference_text",

        # Timing
        "preparation_time_seconds",
        "response_time_seconds",

        # Behavior
        "play_prompt_once",
        "auto_start_recording",

        "order",
    )

    show_change_link = True


# ======================================================
# Speaking admin
# ======================================================

@admin.register(SpeakingModule)
class SpeakingModuleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "mock_test",
        "order",
        "block_count",
    )

    list_filter = (
        "mock_test",
    )

    search_fields = (
        "title",
        "instructions",
        "mock_test__title",
    )

    ordering = (
        "mock_test",
        "order",
        "id",
    )

    inlines = [
        SpeakingBlockInline,
    ]

    @admin.display(description="Questions")
    def block_count(self, obj):
        return obj.blocks.count()


@admin.register(SpeakingBlock)
class SpeakingBlockAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "module",
        "block_type",
        "response_time_seconds",
        "preparation_time_seconds",
        "has_prompt_audio",
        "has_prompt_image",
        "order",
    )

    list_filter = (
        "module__mock_test",
        "module",
        "block_type",
        "play_prompt_once",
        "auto_start_recording",
    )

    search_fields = (
        "title",
        "instructions",
        "reference_text",
        "module__title",
        "module__mock_test__title",
    )

    ordering = (
        "module__mock_test",
        "module__order",
        "order",
        "id",
    )

    fieldsets = (
        (
            "General Information",
            {
                "fields": (
                    "module",
                    "block_type",
                    "title",
                    "instructions",
                    "order",
                )
            },
        ),

        (
            "Prompt Media",
            {
                "fields": (
                    "prompt_image",
                    "prompt_audio",
                    "prompt_video",
                ),
            },
        ),

        (
            "Reference Answer",
            {
                "fields": (
                    "reference_text",
                ),
                "description": (
                    "Enter the transcript of the prompt audio. "
                    "This text will not be shown to the student."
                ),
            },
        ),

        (
            "Timing",
            {
                "fields": (
                    "preparation_time_seconds",
                    "response_time_seconds",
                ),
                "description": (
                    "Preparation time is the delay after the prompt. "
                    "Response time is the maximum recording duration."
                ),
            },
        ),

        (
            "Recording Behavior",
            {
                "fields": (
                    "play_prompt_once",
                    "auto_start_recording",
                )
            },
        ),
    )

    @admin.display(
        boolean=True,
        description="Audio",
    )
    def has_prompt_audio(self, obj):
        return bool(obj.prompt_audio)

    @admin.display(
        boolean=True,
        description="Image",
    )
    def has_prompt_image(self, obj):
        return bool(obj.prompt_image)



@admin.register(SpeakingAttempt)
class SpeakingAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "mock_test",
        "started_at",
        "submitted_at",
        "completed_questions",
        "total_questions",
        "is_submitted",
    )

    list_filter = (
        "mock_test",
        "is_submitted",
        "started_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "mock_test__title",
    )

    readonly_fields = (
        "started_at",
        "submitted_at",
    )

    ordering = (
        "-started_at",
    )

@admin.register(SpeakingAnswer)
class SpeakingAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "block",
        "has_recording",
        "duration_seconds",
        "mime_type",
        "is_completed",
        "is_graded",
        "score",
        "updated_at",
    )

    list_filter = (
        "is_completed",
        "is_graded",
        "attempt__mock_test",
        "block__module",
        "mime_type",
    )

    search_fields = (
        "attempt__user__username",
        "attempt__user__email",
        "block__title",
        "block__reference_text",
        "feedback",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-updated_at",
    )

    fieldsets = (
        (
            "Response Information",
            {
                "fields": (
                    "attempt",
                    "block",
                    "recorded_audio",
                    "duration_seconds",
                    "mime_type",
                    "is_completed",
                )
            },
        ),

        (
            "Grading",
            {
                "fields": (
                    "is_graded",
                    "score",
                    "feedback",
                )
            },
        ),

        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(
        boolean=True,
        description="Recording",
    )
    def has_recording(self, obj):
        return bool(obj.recorded_audio)


@admin.register(WritingModuleAttempt)
class WritingModuleAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "module",
        "current_block_index",
        "remaining_time_seconds",
        "started_at",
        "completed_at",
        "is_completed",
    )

    list_filter = (
        "is_completed",
        "module__mock_test",
        "module",
    )

    search_fields = (
        "attempt__user__username",
        "module__title",
        "module__mock_test__title",
    )

    readonly_fields = (
        "started_at",
        "completed_at",
    )


# ======================================================
# Full TOEFL test attempt
# ======================================================

@admin.register(FullTestAttempt)
class FullTestAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "mock_test",
        "current_section",
        "is_completed",
        "started_at",
        "completed_at",
    )

    list_filter = (
        "is_completed",
        "current_section",
        "mock_test",
    )

    search_fields = (
        "user__username",
        "user__email",
        "mock_test__title",
        "mock_test__slug",
    )

    readonly_fields = (
        "started_at",
        "completed_at",
    )

    fieldsets = (
        (
            "Test Run",
            {
                "fields": (
                    "user",
                    "mock_test",
                    "current_section",
                    "is_completed",
                )
            },
        ),
        (
            "Section Attempts",
            {
                "fields": (
                    "reading_attempt",
                    "listening_attempt",
                    "writing_attempt",
                    "speaking_attempt",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "started_at",
                    "completed_at",
                )
            },
        ),
    )
