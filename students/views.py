from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import StudentProfile
from learning.models import Program, ProgramDay , Task, Resource ,TaskCompletion 
from django.utils import timezone

@login_required
def dashboard(request):

    profile, created = StudentProfile.objects.get_or_create(
        user=request.user
    )

    if not profile.placement_completed:
        return render(request, "students/take_test.html")

    program = Program.objects.filter(
        stage__level__name=profile.level,
        stage__number=profile.stage
    ).first()

    days = ProgramDay.objects.filter(program=program).order_by("day_number")
    today = timezone.now().date()

    current_day = (today - profile.start_date).days + 1
    return render(request, "students/dashboard.html", {
        "profile": profile,
        "days": days,
        "current_day": current_day
    })


@login_required
def day_view(request, day_id):

    day = ProgramDay.objects.get(id=day_id)
    tasks = Task.objects.filter(day=day)
    resources = Resource.objects.filter(day=day)

    # اول همیشه وضعیت تیک‌های فعلی را بگیریم
    completions = TaskCompletion.objects.filter(
        user=request.user,
        task__in=tasks
    )

    completed_task_ids = [
        c.task.id for c in completions if c.completed
    ]

    # سپس اگر POST بود، وضعیت جدید را ذخیره کنیم
    if request.method == "POST":

        for task in tasks:

            checked = request.POST.get(f"task_{task.id}")

            obj, created = TaskCompletion.objects.get_or_create(
                user=request.user,
                task=task
            )

            if checked:
                obj.completed = True
                obj.completed_at = timezone.now()
            else:
                obj.completed = False

            obj.save()

        # بعد از ذخیره دوباره وضعیت جدید را بگیریم
        completions = TaskCompletion.objects.filter(
            user=request.user,
            task__in=tasks
        )

        completed_task_ids = [
            c.task.id for c in completions if c.completed
        ]

    return render(request, "students/day.html", {
        "day": day,
        "tasks": tasks,
        "resources": resources,
        "completed_task_ids": completed_task_ids
    })
