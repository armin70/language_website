from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Course(models.Model):
    COURSE_TYPES = [
        ('online', 'Online Course'),
        ('offline', 'Offline Package'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses'
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=0)
    course_type = models.CharField(
        max_length=10,
        choices=COURSE_TYPES,
        default='online',
    )
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title



class ConsultationRequest(models.Model):
    COURSE_CHOICES = [
        ("free_discussion", "Free Discussion"),
        ("a1_c1", "دوره‌های A1 تا C1"),
        ("toefl_course", "دوره تخصصی تافل"),
        ("mock_toefl", "ماک تافل"),
    ]

    STATUS_CHOICES = [
        ("new", "جدید"),
        ("contacted", "تماس گرفته شد"),
        ("completed", "تکمیل شد"),
        ("cancelled", "لغو شد"),
    ]

    name = models.CharField(
        max_length=150,
        verbose_name="نام"
    )

    phone = models.CharField(
        max_length=20,
        verbose_name="شماره تماس"
    )

    email = models.EmailField(
        blank=True,
        verbose_name="ایمیل"
    )

    course = models.CharField(
        max_length=30,
        choices=COURSE_CHOICES,
        verbose_name="دوره موردنظر"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
        verbose_name="وضعیت"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ثبت"
    )

    class Meta:
        verbose_name = "درخواست مشاوره"
        verbose_name_plural = "درخواست‌های مشاوره"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.phone}"
    
    
class ContactMessage(models.Model):
    STATUS_CHOICES = [
        ("new", "جدید"),
        ("reviewing", "در حال بررسی"),
        ("answered", "پاسخ داده شده"),
        ("closed", "بسته شده"),
    ]

    name = models.CharField(
        max_length=150,
        verbose_name="نام و نام خانوادگی",
    )

    email = models.EmailField(
        verbose_name="آدرس ایمیل",
    )

    subject = models.CharField(
        max_length=200,
        verbose_name="موضوع",
    )

    message = models.TextField(
        verbose_name="متن پیام",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
        verbose_name="وضعیت",
    )

    admin_note = models.TextField(
        blank=True,
        verbose_name="یادداشت مدیر",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ارسال",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین تغییر",
    )

    class Meta:
        verbose_name = "پیام تماس"
        verbose_name_plural = "پیام‌های تماس"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.subject}"