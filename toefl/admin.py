from django.contrib import admin
from .models import (
    MockTest,
    ReadingModule,
    ReadingBlock,
    ReadingQuestion,
    ReadingChoice,
    MockAttempt,
    UserAnswer,
)

class ReadingChoiceInline(admin.TabularInline):
    model = ReadingChoice
    extra = 4

class ReadingQuestionInline(admin.TabularInline):
    model = ReadingQuestion
    extra = 1

class ReadingBlockInline(admin.StackedInline):
    model = ReadingBlock
    extra = 1
    fields = ("block_type", "title", "text", "order", "start_question_number", "end_question_number")

@admin.register(MockTest)
class MockTestAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_active", "order")
    prepopulated_fields = {"slug": ("title",)}

@admin.register(ReadingModule)
class ReadingModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "mock_test", "order")
    inlines = [ReadingBlockInline]

@admin.register(ReadingBlock)
class ReadingBlockAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "block_type", "start_question_number", "end_question_number", "order")
    list_filter = ("module__mock_test", "block_type")
    inlines = [ReadingQuestionInline]

@admin.register(ReadingQuestion)
class ReadingQuestionAdmin(admin.ModelAdmin):
    list_display = ("question_number", "block", "question_text", "order")
    inlines = [ReadingChoiceInline]

admin.site.register(ReadingChoice)
admin.site.register(MockAttempt)
admin.site.register(UserAnswer)
