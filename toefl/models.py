from django.db import models
from django.conf import settings
import re
from django.core.exceptions import ValidationError
import uuid
from pathlib import Path

class MockTest(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def get_all_blocks(self):
        return ReadingBlock.objects.filter(
            module__mock_test=self
        ).select_related(
            "module"
        ).order_by(
            "module__order",
            "order",
            "id"
        )

class FullTestAttempt(models.Model):
    """
    One continuous TOEFL test run.

    It links the Reading, Listening, Writing, and Speaking attempts so the
    application can resume the correct section and never mix attempts from
    different test runs.
    """

    READING = "reading"
    LISTENING = "listening"
    WRITING = "writing"
    SPEAKING = "speaking"
    COMPLETED = "completed"

    SECTION_CHOICES = (
        (READING, "Reading"),
        (LISTENING, "Listening"),
        (WRITING, "Writing"),
        (SPEAKING, "Speaking"),
        (COMPLETED, "Completed"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="full_toefl_attempts",
    )

    mock_test = models.ForeignKey(
        "MockTest",
        on_delete=models.CASCADE,
        related_name="full_attempts",
    )

    reading_attempt = models.OneToOneField(
        "MockAttempt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="full_test_run",
    )

    listening_attempt = models.OneToOneField(
        "ListeningAttempt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="full_test_run",
    )

    writing_attempt = models.OneToOneField(
        "WritingAttempt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="full_test_run",
    )

    speaking_attempt = models.OneToOneField(
        "SpeakingAttempt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="full_test_run",
    )

    current_section = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        default=READING,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_completed = models.BooleanField(
        default=False,
    )

    class Meta:
        ordering = [
            "-started_at",
            "-id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "mock_test",
                ],
                condition=models.Q(is_completed=False),
                name="unique_active_full_toefl_attempt",
            )
        ]

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.mock_test.title} - "
            f"{self.get_current_section_display()}"
        )


class ReadingModule(models.Model):
    mock_test = models.ForeignKey(
        MockTest,
        on_delete=models.CASCADE,
        related_name="reading_modules"
    )
    title = models.CharField(max_length=255, help_text="Module 1 or Module 2")
    instructions = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    time_limit_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Module time limit in seconds. Example: 13:25 = 805"
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.mock_test.title} - {self.title}"

    @property
    def time_limit_display(self):
        minutes, seconds = divmod(self.time_limit_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

class ReadingBlock(models.Model):
    # ----------------------------
    # Block type constants
    # ----------------------------
    COMPLETE_WORDS = "complete_words"
    NOTICE = "notice"
    EMAIL = "email"
    TEXT_MESSAGE = "text_message"
    DAILY_LIFE = "daily_life"
    ACADEMIC_PASSAGE = "academic_passage"
    OTHER = "other"

    BLOCK_TYPES = (
        (COMPLETE_WORDS, "Complete the Words"),
        (NOTICE, "Notice"),
        (EMAIL, "Email"),
        (TEXT_MESSAGE, "Text Message"),
        (DAILY_LIFE, "Daily Life Text"),
        (ACADEMIC_PASSAGE, "Academic Passage"),
        (OTHER, "Other"),
    )

    # ----------------------------
    # Relations
    # ----------------------------
    module = models.ForeignKey(
        "ReadingModule",
        on_delete=models.CASCADE,
        related_name="blocks",
    )

    # ----------------------------
    # Main fields
    # ----------------------------
    block_type = models.CharField(
        max_length=50,
        choices=BLOCK_TYPES,
    )
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    text = models.TextField(
        help_text="For complete_words use format: [fullword|startpart]"
    )
    order = models.PositiveIntegerField(default=1)

    # ----------------------------
    # Question numbering
    # ----------------------------
    start_question_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="First question number of this block, used for complete_words."
    )
    end_question_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Last question number of this block, optional."
    )

    # ----------------------------
    # Optional structured fields
    # Useful for email / message / notice blocks
    # ----------------------------
    sender = models.CharField(max_length=255, blank=True)
    recipient = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    sent_at_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Example: May 12, 10:30 AM"
    )

    class Meta:
        ordering = ["module__order", "order", "id"]

    def __str__(self):
        return f"{self.module} - {self.title}"

    @property
    def is_complete_words(self):
        return self.block_type == self.COMPLETE_WORDS

    @property
    def is_passage_type(self):
        return self.block_type in {
            self.NOTICE,
            self.EMAIL,
            self.TEXT_MESSAGE,
            self.DAILY_LIFE,
            self.ACADEMIC_PASSAGE,
            self.OTHER,
        }

    @property
    def question_count(self):
        """
        Returns number of blank/input items for complete_words blocks.
        For other block types, returns related question count.
        """
        if self.is_complete_words:
            return sum(
                1
                for part in self.get_processed_content()
                if part["type"] == "input"
            )
        return self.questions.count()

    def get_processed_content(self):
        """
        Parse Complete the Words text.

        Supported formats:
            att(ract)
            [attract|att]

        For att(ract):
            visible part = att
            missing answer = ract
            full word = attract
        """
        if not self.text:
            return [{"type": "text", "content": ""}]

        # Old format: [attract|att]
        # New format: att(ract)
        pattern = re.compile(
            r"\[([^\]\|]+)\|([^\]\|]+)\]"
            r"|"
            r"([A-Za-z][A-Za-z'-]*)"
            r"\(([A-Za-z][A-Za-z'-]*)\)"
        )

        matches = list(pattern.finditer(self.text))

        if not matches:
            return [{"type": "text", "content": self.text}]

        processed_parts = []
        last_index = 0
        question_number = self.start_question_number or 1

        for match in matches:
            if match.start() > last_index:
                processed_parts.append({
                    "type": "text",
                    "content": self.text[last_index:match.start()],
                })

            old_full_word = match.group(1)
            old_start_part = match.group(2)
            new_start_part = match.group(3)
            new_missing_part = match.group(4)

            if old_full_word is not None:
                full_word = old_full_word.strip()
                start_part = old_start_part.strip()

                if full_word.lower().startswith(start_part.lower()):
                    missing_part = full_word[len(start_part):]
                else:
                    # Invalid old-format entry: display it as normal text
                    # instead of creating an incorrectly graded blank.
                    processed_parts.append({
                        "type": "text",
                        "content": match.group(0),
                    })
                    last_index = match.end()
                    continue
            else:
                start_part = new_start_part.strip()
                missing_part = new_missing_part.strip()
                full_word = start_part + missing_part

            processed_parts.append({
                "type": "input",
                "full_word": full_word,
                "start_part": start_part,
                "missing_part": missing_part,
                "remaining_len": len(missing_part),
                "dashes": "_" * len(missing_part),
                "q_number": question_number,
            })

            question_number += 1
            last_index = match.end()

        if last_index < len(self.text):
            processed_parts.append({
                "type": "text",
                "content": self.text[last_index:],
            })

        return processed_parts

    def get_question_range(self):
        """
        Returns a readable question range for UI purposes.
        Example:
            10-14
        """
        if self.start_question_number and self.end_question_number:
            return f"{self.start_question_number}-{self.end_question_number}"
        if self.start_question_number:
            return str(self.start_question_number)
        return None


class ReadingQuestion(models.Model):
    block = models.ForeignKey(
        ReadingBlock,
        on_delete=models.CASCADE,
        related_name="questions"
    )
    question_number = models.PositiveIntegerField(help_text="Actual question number in the test.")
    question_text = models.TextField()
    order = models.PositiveIntegerField(default=1)
    points = models.FloatField(default=1)

    class Meta:
        ordering = ["question_number", "id"]

    def __str__(self):
        return f"Q{self.question_number} - {self.block.title}"


class ReadingChoice(models.Model):
    question = models.ForeignKey(
        ReadingQuestion,
        on_delete=models.CASCADE,
        related_name="choices"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.question} - {self.text[:50]}"


class MockAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    mock_test = models.ForeignKey(
        MockTest,
        on_delete=models.CASCADE,
        related_name="attempts"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Final Reading score on the new TOEFL 1-6 scale.
    score = models.FloatField(default=0)

    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    is_submitted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.username} - {self.mock_test.title}"

    @staticmethod
    def convert_reading_score(score_out_of_30):
        """
        Convert the legacy TOEFL Reading score (0-30)
        to the new TOEFL score scale (1-6).
        """
        if score_out_of_30 is None:
            return None

        score_out_of_30 = max(0, min(30, score_out_of_30))

        if score_out_of_30 >= 29:
            return 6.0
        if score_out_of_30 >= 27:
            return 5.5
        if score_out_of_30 >= 24:
            return 5.0
        if score_out_of_30 >= 22:
            return 4.5
        if score_out_of_30 >= 18:
            return 4.0
        if score_out_of_30 >= 12:
            return 3.5
        if score_out_of_30 >= 6:
            return 3.0
        if score_out_of_30 >= 4:
            return 2.5
        if score_out_of_30 >= 3:
            return 2.0
        if score_out_of_30 >= 2:
            return 1.5

        return 1.0

    @property
    def score_out_of_30(self):
        """
        Calculate the Reading score on the legacy 0-30 scale.
        """
        if self.total_questions <= 0:
            return None

        correct = min(self.correct_answers, self.total_questions)

        return round(
            (correct / self.total_questions) * 30
        )

    @property
    def score_percentage(self):
        if self.total_questions <= 0:
            return None

        return round(
            (self.correct_answers / self.total_questions) * 100,
            1
        )

    def calculate_score(self, save=True):
        """
        Calculate and optionally save the final Reading score.
        """
        score_out_of_30 = self.score_out_of_30

        if score_out_of_30 is None:
            self.score = 0
        else:
            self.score = self.convert_reading_score(score_out_of_30)

        if save:
            self.save(update_fields=["score"])

        return self.score


class UserAnswer(models.Model):
    attempt = models.ForeignKey(MockAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(
        ReadingQuestion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_answers"
    )
    global_question_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Used for complete word questions where there is no ReadingQuestion object."
    )
    text_answer = models.CharField(max_length=255, blank=True)
    selected_choice = models.ForeignKey(ReadingChoice, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["global_question_number", "question__question_number"]

    def __str__(self):
        q_num = self.question.question_number if self.question else self.global_question_number
        return f"{self.attempt} - Q{q_num}"

class ModuleAttempt(models.Model):
    attempt = models.ForeignKey(
        MockAttempt,
        on_delete=models.CASCADE,
        related_name="module_attempts",
    )

    module = models.ForeignKey(
        ReadingModule,
        on_delete=models.CASCADE,
        related_name="attempts",
    )

    remaining_time_seconds = models.PositiveIntegerField(
        default=0,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "The server-side deadline for this reading module."
        ),
    )

    current_block_index = models.PositiveIntegerField(
        default=0,
        help_text=(
            "The currently displayed block inside the module."
        ),
    )

    is_completed = models.BooleanField(
        default=False,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "attempt",
                    "module",
                ],
                name="unique_reading_module_attempt",
            )
        ]

        ordering = [
            "module__order",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.attempt} - "
            f"{self.module.title}"
        )

    @property
    def calculated_remaining_seconds(self):
        from django.utils import timezone

        if self.is_completed:
            return 0

        if self.expires_at is None:
            return self.remaining_time_seconds

        difference = (
            self.expires_at - timezone.now()
        ).total_seconds()

        return max(
            0,
            int(difference),
        )

class WritingModule(models.Model):
    mock_test = models.ForeignKey(
        MockTest,
        on_delete=models.CASCADE,
        related_name="writing_modules",
    )

    title = models.CharField(
        max_length=255,
        help_text="Example: Writing Module 1",
    )

    instructions = models.TextField(blank=True)

    order = models.PositiveIntegerField(default=1)

    time_limit_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Time limit in seconds",
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.mock_test.title} - {self.title}"



class WritingBlock(models.Model):
    BUILD_SENTENCE = "build_sentence"
    WRITE_EMAIL = "write_email"
    ACADEMIC_DISCUSSION = "academic_discussion"
    BLOCK_TYPES = (
        (
            BUILD_SENTENCE,
            "Build a Sentence / Fill in the Blanks",
        ),
        (
            WRITE_EMAIL,
            "Write an Email",
        ),
        (
            ACADEMIC_DISCUSSION,
            "Write for an Academic Discussion",
        ),
    )

    module = models.ForeignKey(
        "WritingModule",
        on_delete=models.CASCADE,
        related_name="blocks",
    )

    block_type = models.CharField(
        max_length=50,
        choices=BLOCK_TYPES,
        default=BUILD_SENTENCE,
    )

    title = models.CharField(
        max_length=255,
        default="Make an appropriate sentence",
    )

    instructions = models.TextField(
        blank=True,
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    # حتماً باید داخل WritingBlock باشد
    time_limit_seconds = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Time limit for this task in seconds. "
            "For Write an Email, use 420 seconds."
        ),
    )

    # Build a Sentence fields
    speaker_one_name = models.CharField(
        max_length=100,
        blank=True,
    )

    speaker_one_text = models.TextField(
        blank=True,
    )

    speaker_two_name = models.CharField(
        max_length=100,
        blank=True,
    )

    answer_template = models.TextField(
        blank=True,
        help_text="Use [blank] for every empty position.",
    )

    # Write an Email fields
    email_scenario = models.TextField(
        blank=True,
    )

    email_recipient = models.CharField(
        max_length=255,
        blank=True,
    )

    email_subject = models.CharField(
        max_length=255,
        blank=True,
    )

    email_requirements = models.TextField(
        blank=True,
        help_text="Enter one requirement per line.",
    )

    # ==================================================
    # Academic Discussion fields
    # ==================================================

    discussion_class_title = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "Example: School - Debate & Suggestions"
        ),
    )

    professor_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Example: Prof. Martin",
    )

    professor_avatar = models.CharField(
        max_length=500,
        blank=True,
        help_text=(
            "Optional image URL or static path. "
            "Example: /static/toefl/avatars/professor.png"
        ),
    )

    professor_prompt = models.TextField(
        blank=True,
        help_text=(
            "The professor's discussion question."
        ),
    )

    discussion_requirements = models.TextField(
        blank=True,
        help_text=(
            "Enter one requirement per line."
        ),
    )

    minimum_words = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Recommended minimum word count. "
            "For this example use 100."
        ),
    )

    def get_discussion_requirements(self):
        """
        Convert requirements entered on separate lines
        into a Python list.
        """

        if not self.discussion_requirements:
            return []

        requirements = []

        for line in self.discussion_requirements.splitlines():
            cleaned_line = line.strip()

            if not cleaned_line:
                continue

            cleaned_line = cleaned_line.lstrip(
                "•*-–— "
            ).strip()

            if cleaned_line:
                requirements.append(cleaned_line)

        return requirements
    class Meta:
        ordering = [
            "module__order",
            "order",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.module} - "
            f"{self.get_block_type_display()} - "
            f"{self.title}"
        )

    @property
    def is_build_sentence(self):
        return self.block_type == self.BUILD_SENTENCE

    @property
    def is_write_email(self):
        return self.block_type == self.WRITE_EMAIL
    @property
    def is_academic_discussion(self):
        return (
            self.block_type
            == self.ACADEMIC_DISCUSSION
        )

    @property
    def discussion_requirement_count(self):
        return len(
            self.get_discussion_requirements()
        )
    @property
    def blank_count(self):
        if not self.answer_template:
            return 0

        return len(
            re.findall(
                r"\[blank\]",
                self.answer_template,
                flags=re.IGNORECASE,
            )
        )

    def get_processed_answer(self):
        if not self.answer_template:
            return []

        matches = list(
            re.finditer(
                r"\[blank\]",
                self.answer_template,
                flags=re.IGNORECASE,
            )
        )

        if not matches:
            return [
                {
                    "type": "text",
                    "content": self.answer_template,
                }
            ]

        processed_parts = []
        last_index = 0
        blank_index = 0

        for match in matches:
            if match.start() > last_index:
                processed_parts.append({
                    "type": "text",
                    "content": self.answer_template[
                        last_index:match.start()
                    ],
                })

            processed_parts.append({
                "type": "blank",
                "index": blank_index,
            })

            blank_index += 1
            last_index = match.end()

        if last_index < len(self.answer_template):
            processed_parts.append({
                "type": "text",
                "content": self.answer_template[last_index:],
            })

        return processed_parts

    def get_correct_word_ids(self):
        return list(
            self.words.filter(
                correct_position__isnull=False,
            )
            .order_by(
                "correct_position",
                "id",
            )
            .values_list(
                "id",
                flat=True,
            )
        )

    def get_email_requirements(self):
        if not self.email_requirements:
            return []

        requirements = []

        for line in self.email_requirements.splitlines():
            cleaned_line = line.strip()

            if not cleaned_line:
                continue

            cleaned_line = cleaned_line.lstrip(
                "•*-–— "
            ).strip()

            if cleaned_line:
                requirements.append(cleaned_line)

        return requirements

    @property
    def email_requirement_count(self):
        return len(self.get_email_requirements())

    @property
    def time_limit_display(self):
        minutes, seconds = divmod(
            self.time_limit_seconds,
            60,
        )

        return f"{minutes:02d}:{seconds:02d}"

class WritingWord(models.Model):
    block = models.ForeignKey(
        WritingBlock,
        on_delete=models.CASCADE,
        related_name="words",
    )

    text = models.CharField(
        max_length=255,
        help_text=(
            "A word or phrase such as: "
            "the problem, is more serious"
        ),
    )

    display_order = models.PositiveIntegerField(
        default=1,
        help_text="Position in the word bank",
    )

    correct_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Correct blank number: 1, 2, 3, etc. "
            "Leave empty if this word is a distractor."
        ),
    )

    class Meta:
        ordering = [
            "display_order",
            "id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "block",
                    "correct_position",
                ],
                name="uniq_writing_word_position",
            )
        ]

    def __str__(self):
        return f"{self.block} - {self.text}"


class WritingAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="writing_attempts",
    )

    mock_test = models.ForeignKey(
        MockTest,
        on_delete=models.CASCADE,
        related_name="writing_attempts",
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    total_questions = models.PositiveIntegerField(
        default=0,
    )

    correct_answers = models.PositiveIntegerField(
        default=0,
    )

    is_submitted = models.BooleanField(
        default=False,
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.mock_test} - Writing"
        )


class WritingAnswer(models.Model):
    attempt = models.ForeignKey(
        WritingAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )

    block = models.ForeignKey(
        WritingBlock,
        on_delete=models.CASCADE,
        related_name="user_answers",
    )

    selected_word_ids = models.JSONField(
        default=list,
        blank=True,
    )

    text_answer = models.TextField(
        blank=True,
    )

    word_count = models.PositiveIntegerField(
        default=0,
    )

    is_correct = models.BooleanField(
        default=False,
    )

    is_graded = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "attempt",
                    "block",
                ],
                name="uniq_writing_answer",
            )
        ]

    def __str__(self):
        return f"{self.attempt} - {self.block}"



class AcademicDiscussionPost(models.Model):
    block = models.ForeignKey(
        WritingBlock,
        on_delete=models.CASCADE,
        related_name="discussion_posts",
    )

    author_name = models.CharField(
        max_length=100,
        help_text="Example: Alex",
    )

    avatar = models.CharField(
        max_length=500,
        blank=True,
        help_text=(
            "Optional image URL or static path. "
            "Example: /static/toefl/avatars/student1.png"
        ),
    )

    text = models.TextField(
        help_text=(
            "The student's response to the professor."
        ),
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        ordering = [
            "order",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.block.title} - "
            f"{self.author_name}"
        )




class ListeningModule(models.Model):
    mock_test = models.ForeignKey(
        "MockTest",
        on_delete=models.CASCADE,
        related_name="listening_modules",
    )
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    time_limit_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Optional module time limit in seconds."
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.mock_test.title} - {self.title}"

class ListeningBlock(models.Model):
    # ==================================================
    # Main block types
    # ==================================================

    CHOOSE_BEST_RESPONSE = "choose_best_response"
    LISTEN_AND_ANSWER = "listen_and_answer"

    BLOCK_TYPES = (
        (
            CHOOSE_BEST_RESPONSE,
            "Choose the Best Response",
        ),
        (
            LISTEN_AND_ANSWER,
            "Listen and Answer Questions",
        ),
    )

    # ==================================================
    # Listening content types
    # Used only for Listen and Answer blocks
    # ==================================================

    CONVERSATION = "conversation"
    ANNOUNCEMENT = "announcement"
    TALK = "talk"

    LISTENING_CONTENT_TYPES = (
        (
            CONVERSATION,
            "Conversation",
        ),
        (
            ANNOUNCEMENT,
            "Announcement",
        ),
        (
            TALK,
            "Talk",
        ),
    )

    # ==================================================
    # Relations
    # ==================================================

    module = models.ForeignKey(
        "ListeningModule",
        on_delete=models.CASCADE,
        related_name="blocks",
    )

    # ==================================================
    # General fields
    # ==================================================

    block_type = models.CharField(
        max_length=50,
        choices=BLOCK_TYPES,
        default=CHOOSE_BEST_RESPONSE,
    )

    listening_content_type = models.CharField(
        max_length=30,
        choices=LISTENING_CONTENT_TYPES,
        blank=True,
        default="",
        help_text=(
            "Select Conversation, Announcement, or Talk "
            "for Listen and Answer blocks."
        ),
    )

    title = models.CharField(
        max_length=255,
        default="Choose the best response",
    )

    instructions = models.TextField(
        blank=True,
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    # ==================================================
    # Media
    # ==================================================

    speaker_image = models.ImageField(
        upload_to="toefl/listening/images/",
        blank=True,
        null=True,
        help_text=(
            "Optional image shown beside the question "
            "or while the audio is playing."
        ),
    )

    audio_file = models.FileField(
        upload_to="toefl/listening/audio/",
        blank=True,
        null=True,
        help_text=(
            "Upload the audio file for this listening block."
        ),
    )

    # ==================================================
    # Audio and question behavior
    # ==================================================

    lock_questions_until_audio_ends = models.BooleanField(
        default=True,
        help_text=(
            "Prevent the user from answering before "
            "the audio finishes."
        ),
    )

    hide_questions_until_audio_ends = models.BooleanField(
        default=False,
        help_text=(
            "When selected, the questions are completely hidden "
            "while the audio is playing. Use this for Conversation, "
            "Announcement, and Talk blocks."
        ),
    )

    time_limit_seconds = models.PositiveIntegerField(
        default=15,
        help_text=(
            "Time available for answering after or during the task. "
            "Example: 15 seconds."
        ),
    )

    # ==================================================
    # Meta
    # ==================================================

    class Meta:
        ordering = [
            "module__order",
            "order",
            "id",
        ]

    def __str__(self):
        content_label = ""

        if self.listening_content_type:
            content_label = (
                f" - {self.get_listening_content_type_display()}"
            )

        return (
            f"{self.module} - "
            f"{self.get_block_type_display()}"
            f"{content_label} - "
            f"{self.title}"
        )

    # ==================================================
    # Validation
    # ==================================================

    def clean(self):
        """
        Validate combinations of block settings.
        """

        super().clean()

        errors = {}

        if (
            self.block_type == self.LISTEN_AND_ANSWER
            and not self.listening_content_type
        ):
            errors["listening_content_type"] = (
                "Choose Conversation, Announcement, or Talk "
                "for a Listen and Answer block."
            )

        if (
            self.hide_questions_until_audio_ends
            and not self.lock_questions_until_audio_ends
        ):
            errors["hide_questions_until_audio_ends"] = (
                "Questions can only be hidden until the audio ends "
                "when question locking is enabled."
            )

        if errors:
            raise ValidationError(errors)

    # ==================================================
    # Block helpers
    # ==================================================

    @property
    def is_choose_best_response(self):
        return (
            self.block_type
            == self.CHOOSE_BEST_RESPONSE
        )

    @property
    def is_listen_and_answer(self):
        return (
            self.block_type
            == self.LISTEN_AND_ANSWER
        )

    @property
    def is_conversation(self):
        return (
            self.listening_content_type
            == self.CONVERSATION
        )

    @property
    def is_announcement(self):
        return (
            self.listening_content_type
            == self.ANNOUNCEMENT
        )

    @property
    def is_talk(self):
        return (
            self.listening_content_type
            == self.TALK
        )

    @property
    def should_hide_questions_during_audio(self):
        return (
            self.lock_questions_until_audio_ends
            and self.hide_questions_until_audio_ends
        )

    @property
    def should_disable_questions_during_audio(self):
        return (
            self.lock_questions_until_audio_ends
            and not self.hide_questions_until_audio_ends
        )

    @property
    def time_limit_display(self):
        minutes, seconds = divmod(
            self.time_limit_seconds,
            60,
        )

        return f"{minutes:02d}:{seconds:02d}"

class ListeningQuestion(models.Model):
    block = models.ForeignKey(
        ListeningBlock,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_number = models.PositiveIntegerField(
        default=1
    )
    question_text = models.TextField(
        blank=True,
        help_text="For this first type, you can leave it blank."
    )
    order = models.PositiveIntegerField(default=1)
    points = models.FloatField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Listening Q{self.question_number} - {self.block.title}"


class ListeningChoice(models.Model):
    question = models.ForeignKey(
        ListeningQuestion,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.question} - {self.text[:50]}"


class ListeningAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    mock_test = models.ForeignKey(
        "MockTest",
        on_delete=models.CASCADE,
        related_name="listening_attempts",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    is_submitted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.username} - {self.mock_test.title} - Listening"


class ListeningAnswer(models.Model):
    attempt = models.ForeignKey(
        ListeningAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        ListeningQuestion,
        on_delete=models.CASCADE,
        related_name="user_answers",
    )
    selected_choice = models.ForeignKey(
        ListeningChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("attempt", "question")
        ordering = ["question__order", "id"]

    def __str__(self):
        return f"{self.attempt} - {self.question}"



def speaking_response_upload_to(instance, filename):
    """
    Store every recorded response in a unique location.

    Example:
    toefl/speaking/responses/
        attempt_12/
        block_4/
        a12bc34d.webm
    """

    extension = Path(filename).suffix.lower()

    if not extension:
        extension = ".webm"

    unique_filename = (
        f"{uuid.uuid4().hex}{extension}"
    )

    return (
        "toefl/speaking/responses/"
        f"attempt_{instance.attempt_id}/"
        f"block_{instance.block_id}/"
        f"{unique_filename}"
    )


class SpeakingModule(models.Model):
    mock_test = models.ForeignKey(
        "MockTest",
        on_delete=models.CASCADE,
        related_name="speaking_modules",
    )

    title = models.CharField(
        max_length=255,
        help_text="Example: Speaking Module 1",
    )

    instructions = models.TextField(
        blank=True,
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        ordering = [
            "order",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.mock_test.title} - "
            f"{self.title}"
        )

class SpeakingBlock(models.Model):
    LISTEN_AND_REPEAT = "listen_and_repeat"
    WATCH_AND_RESPOND = "watch_and_respond"

    BLOCK_TYPES = (
        (
            LISTEN_AND_REPEAT,
            "Listen and Repeat",
        ),
        (
            WATCH_AND_RESPOND,
            "Watch and Respond",
        ),
    )

    module = models.ForeignKey(
        "SpeakingModule",
        on_delete=models.CASCADE,
        related_name="blocks",
    )

    block_type = models.CharField(
        max_length=50,
        choices=BLOCK_TYPES,
        default=LISTEN_AND_REPEAT,
    )

    title = models.CharField(
        max_length=255,
        default="Speaking Task",
    )

    instructions = models.TextField(
        blank=True,
    )

    order = models.PositiveIntegerField(
        default=1,
    )

    prompt_image = models.ImageField(
        upload_to="toefl/speaking/images/",
        blank=True,
        null=True,
    )

    prompt_audio = models.FileField(
        upload_to="toefl/speaking/prompts/",
        blank=True,
        null=True,
        help_text=(
            "Use this for Listen and Repeat."
        ),
    )

    prompt_video = models.FileField(
        upload_to="toefl/speaking/videos/",
        blank=True,
        null=True,
        help_text=(
            "Use this for Watch and Respond."
        ),
    )

    reference_text = models.TextField(
        blank=True,
        help_text=(
            "Hidden transcript or grading reference. "
            "This is not shown to the student."
        ),
    )

    preparation_time_seconds = (
        models.PositiveSmallIntegerField(
            default=0,
        )
    )

    response_time_seconds = (
        models.PositiveSmallIntegerField(
            default=15,
        )
    )

    play_prompt_once = models.BooleanField(
        default=True,
    )

    auto_start_recording = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = [
            "module__order",
            "order",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.module} - "
            f"{self.get_block_type_display()} - "
            f"{self.title}"
        )

    @property
    def is_listen_and_repeat(self):
        return (
            self.block_type
            == self.LISTEN_AND_REPEAT
        )

    @property
    def is_watch_and_respond(self):
        return (
            self.block_type
            == self.WATCH_AND_RESPOND
        )

    @property
    def response_time_display(self):
        minutes, seconds = divmod(
            self.response_time_seconds,
            60,
        )

        return f"{minutes:02d}:{seconds:02d}"


class SpeakingAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="speaking_attempts",
    )

    mock_test = models.ForeignKey(
        "MockTest",
        on_delete=models.CASCADE,
        related_name="speaking_attempts",
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    total_questions = models.PositiveIntegerField(
        default=0,
    )

    completed_questions = models.PositiveIntegerField(
        default=0,
    )

    is_submitted = models.BooleanField(
        default=False,
    )

    class Meta:
        ordering = [
            "-started_at",
        ]

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.mock_test.title} - Speaking"
        )


class SpeakingAnswer(models.Model):
    attempt = models.ForeignKey(
        "SpeakingAttempt",
        on_delete=models.CASCADE,
        related_name="answers",
    )

    block = models.ForeignKey(
        "SpeakingBlock",
        on_delete=models.CASCADE,
        related_name="user_answers",
    )

    recorded_audio = models.FileField(
        upload_to=speaking_response_upload_to,
        blank=True,
        null=True,
    )

    duration_seconds = models.FloatField(
        default=0,
        help_text=(
            "Actual duration of the user's recording."
        ),
    )

    mime_type = models.CharField(
        max_length=100,
        blank=True,
        help_text=(
            "Example: audio/webm or audio/mp4."
        ),
    )

    is_completed = models.BooleanField(
        default=False,
    )

    # Future grading fields
    is_graded = models.BooleanField(
        default=False,
    )

    score = models.FloatField(
        null=True,
        blank=True,
    )

    feedback = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "attempt",
                    "block",
                ],
                name="unique_speaking_answer_per_block",
            )
        ]

        ordering = [
            "block__module__order",
            "block__order",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.attempt} - "
            f"{self.block.title}"
        )




class WritingModuleAttempt(models.Model):
    attempt = models.ForeignKey(
        WritingAttempt,
        on_delete=models.CASCADE,
        related_name="module_attempts",
    )

    module = models.ForeignKey(
        WritingModule,
        on_delete=models.CASCADE,
        related_name="attempts",
    )

    remaining_time_seconds = models.PositiveIntegerField(
        default=0,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Server-side deadline for this Writing module."
        ),
    )

    current_block_index = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Currently displayed block inside the Writing module."
        ),
    )

    is_completed = models.BooleanField(
        default=False,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "attempt",
                    "module",
                ],
                name="unique_writing_module_attempt",
            )
        ]

        ordering = [
            "module__order",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.attempt} - "
            f"{self.module.title}"
        )

    @property
    def calculated_remaining_seconds(self):
        from django.utils import timezone

        if self.is_completed:
            return 0

        if self.expires_at is None:
            return self.remaining_time_seconds

        difference = (
            self.expires_at - timezone.now()
        ).total_seconds()

        return max(
            0,
            int(difference),
        )
