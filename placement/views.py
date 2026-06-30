from django.shortcuts import render, redirect
from .models import Question
from students.models import StudentProfile
from django.utils import timezone
from learning.models import Stage

def take_test(request):

    questions = Question.objects.all()
    stages = Stage.objects.all()
    if request.method == "POST":

        score = 0

        for question in questions:
            selected = request.POST.get(str(question.id))

            if selected:
                choice = question.choice_set.get(id=selected)
                if choice.is_correct:
                    score += 1

        total = questions.count()
        percent = (score / total) * 100

        if percent < 40:
            level = "A1"
        elif percent < 60:
            level = "A2"
        elif percent < 75:
            level = "B1"
        elif percent < 90:
            level = "B2"
        else:
            level = "C1"

        selected_stage = request.POST.get("stage")

        profile = request.user.studentprofile
        profile.level = level
        profile.stage = selected_stage
        profile.placement_completed = True
        profile.start_date = timezone.now().date()
        profile.save()

        return redirect("dashboard")

    return render(request, "placement/test.html", {
        "questions": questions,
        "stages": stages
    })
