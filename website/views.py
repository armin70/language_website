import re

from django.shortcuts import render, redirect 
from .models import Course
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import ConsultationRequest 
from .forms import ContactMessageForm

def home(request):
    courses = Course.objects.filter(is_active=True)

    context = {
        'courses': courses,
    }
    return render(request, 'website/home.html', context)


def about(request):
    return render(request, 'website/about.html')

def contact(request):
    return render(request, 'website/contact.html')

def free_discussion(request):
    return render(request, 'website/free_discussion.html')

def private_course(request):
    return render(request, 'website/private_course.html')

def toefl(request):
    return render(request, 'website/toefl.html')




def normalize_digits(value):
    """تبدیل اعداد فارسی و عربی به انگلیسی."""
    translation_table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    return value.translate(translation_table)


@require_POST
def consultation_request_view(request):
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    email = request.POST.get("email", "").strip()
    course = request.POST.get("course", "").strip()

    # تبدیل اعداد فارسی شماره تماس به انگلیسی
    phone = normalize_digits(phone)

    # حذف فاصله، خط تیره و پرانتز
    phone = re.sub(r"[\s\-()]", "", phone)

    valid_courses = {
        "free_discussion",
        "a1_c1",
        "toefl_course",
        "mock_toefl",
    }

    # اعتبارسنجی نام
    if len(name) < 2:
        messages.error(request, "لطفاً نام خود را به‌درستی وارد کنید.")
        return redirect("/#consultation")

    # اعتبارسنجی شماره موبایل ایران
    if not re.fullmatch(r"(?:09\d{9}|\+989\d{9}|00989\d{9})", phone):
        messages.error(
            request,
            "لطفاً شماره تماس معتبر وارد کنید؛ مانند 09123456789."
        )
        return redirect("/#consultation")

    # اعتبارسنجی دوره
    if course not in valid_courses:
        messages.error(request, "لطفاً دوره موردنظر را انتخاب کنید.")
        return redirect("/#consultation")

    ConsultationRequest.objects.create(
        name=name,
        phone=phone,
        email=email,
        course=course,
    )

    messages.success(
        request,
        "درخواست مشاوره شما با موفقیت ثبت شد. به‌زودی با شما تماس می‌گیریم."
    )

    return redirect("/#consultation")






def contact_view(request):
    if request.method == "POST":
        form = ContactMessageForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "پیام شما با موفقیت ارسال شد. در اولین فرصت با شما در ارتباط خواهیم بود.",
            )

            # الگوی Post/Redirect/Get برای جلوگیری از ثبت مجدد
            return redirect(
                f"{reverse('website:contact')}#contact-form"
            )

        messages.error(
            request,
            "لطفاً خطاهای فرم را بررسی و اصلاح کنید.",
        )

    else:
        form = ContactMessageForm()

    context = {
        "contact_form": form,
    }

    return render(
        request,
        "website/contact.html",
        context,
    )