from django.contrib import admin
from .models import Category, Course ,ConsultationRequest, ContactMessage

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'course_type', 'price', 'is_active', 'category')
    list_filter = ('course_type', 'is_active', 'category')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}



@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "phone",
        "email",
        "course",
        "status",
        "created_at",
    )

    list_filter = (
        "course",
        "status",
        "created_at",
    )

    search_fields = (
        "name",
        "phone",
        "email",
    )

    list_editable = (
        "status",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "-created_at",
    )
    


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "subject",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "name",
        "email",
        "subject",
        "message",
    )

    list_editable = (
        "status",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "اطلاعات فرستنده",
            {
                "fields": (
                    "name",
                    "email",
                ),
            },
        ),
        (
            "محتوای پیام",
            {
                "fields": (
                    "subject",
                    "message",
                ),
            },
        ),
        (
            "مدیریت پیام",
            {
                "fields": (
                    "status",
                    "admin_note",
                ),
            },
        ),
        (
            "زمان‌ها",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
