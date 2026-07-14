from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from toefl.models import MockTest, MockAttempt
# اینجا بعداً مدل دوره‌ها را ایمپورت می‌کنیم

@login_required
def student_dashboard(request):
    # ۱. واکشی آزمون‌های ماک
    # آزمون‌هایی که کاربر هنوز تمام نکرده
    ongoing_exams = MockAttempt.objects.filter(
        user=request.user, 
        is_submitted=False
    ).select_related('mock_test')

    # آزمون‌های تمام شده
    completed_exams = MockAttempt.objects.filter(
        user=request.user, 
        is_submitted=True
    ).select_related('mock_test').order_by('-submitted_at')

    # آزمون‌های جدیدی که کاربر هنوز شروع نکرده (اختیاری)
    attempted_test_ids = MockAttempt.objects.filter(user=request.user).values_list('mock_test_id', flat=True)
    new_exams = MockTest.objects.filter(is_active=True).exclude(id__in=attempted_test_ids)

    context = {
        'ongoing_exams': ongoing_exams,
        'completed_exams': completed_exams,
        'new_exams': new_exams,
        'user': request.user,
    }
    
    return render(request, 'dashboard/student_panel.html', context)


@login_required
def mock_tests_view(request):
    ongoing_attempts = MockAttempt.objects.filter(
        user=request.user,
        is_submitted=False
    ).select_related('mock_test').order_by('-started_at')

    completed_attempts = MockAttempt.objects.filter(
        user=request.user,
        is_submitted=True
    ).select_related('mock_test').order_by('-submitted_at')

    attempted_ids = MockAttempt.objects.filter(user=request.user).values_list('mock_test_id', flat=True)

    new_tests = MockTest.objects.filter(is_active=True).exclude(id__in=attempted_ids).order_by('id')

    context = {
        'ongoing_attempts': ongoing_attempts,
        'completed_attempts': completed_attempts,
        'new_tests': new_tests,
    }
    return render(request, 'dashboard/mock_tests.html', context)