from django.db import models
from django.conf import settings
import re

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

class ReadingModule(models.Model):
    mock_test = models.ForeignKey(
        MockTest,
        on_delete=models.CASCADE,
        related_name="reading_modules"
    )
    title = models.CharField(max_length=255, help_text="Module 1 or Module 2")
    instructions = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.mock_test.title} - {self.title}"


class ReadingBlock(models.Model):
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

    module = models.ForeignKey(
        ReadingModule,
        on_delete=models.CASCADE,
        related_name="blocks"
    )
    block_type = models.CharField(max_length=50, choices=BLOCK_TYPES)
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    text = models.TextField(help_text="Format: [fullword|startpart]")
    order = models.PositiveIntegerField(default=1)
    start_question_number = models.PositiveIntegerField(null=True, blank=True)
    end_question_number = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["module__order", "order", "id"]

    def __str__(self):
        return f"{self.module} - {self.title}"

    def get_processed_content(self):
        pattern = r"\[([^\]\|]+)\|([^\]\|]+)\]"
        matches = list(re.finditer(pattern, self.text))
        processed_parts = []
        last_index = 0
        q_count = self.start_question_number or 1

        for match in matches:
            processed_parts.append({
                'type': 'text',
                'content': self.text[last_index:match.start()]
            })
            
            full_word, start_part = match.groups()
            remaining_len = len(full_word) - len(start_part)
            
            processed_parts.append({
                'type': 'input',
                'full_word': full_word,
                'start_part': start_part,
                'remaining_len': remaining_len,
                'dashes': "_" * remaining_len,
                'q_number': q_count
            })
            
            q_count += 1
            last_index = match.end()
        
        processed_parts.append({
            'type': 'text',
            'content': self.text[last_index:]
        })
        
        return processed_parts


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
