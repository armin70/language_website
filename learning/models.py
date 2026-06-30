from django.db import models
from django.conf import settings

class Level(models.Model):
    name = models.CharField(max_length=5)

    def __str__(self):
        return self.name

class Stage(models.Model):
    level = models.ForeignKey(Level, on_delete=models.CASCADE)
    number = models.IntegerField()

    def __str__(self):
        return f"{self.level.name} - Stage {self.number}"


class Program(models.Model):
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title


class ProgramDay(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    day_number = models.IntegerField()

    def __str__(self):
        return f"{self.program.title} - Day {self.day_number}"


class Task(models.Model):
    day = models.ForeignKey(ProgramDay, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title

class Resource(models.Model):

    RESOURCE_TYPES = [
        ("pdf", "PDF"),
        ("video", "Video"),
        ("link", "External Link"),
    ]

    day = models.ForeignKey(ProgramDay, on_delete=models.CASCADE)

    title = models.CharField(max_length=255)

    file = models.FileField(upload_to="resources/", blank=True, null=True)

    link = models.URLField(blank=True)

    type = models.CharField(max_length=10, choices=RESOURCE_TYPES)

    def __str__(self):
        return self.title


class TaskCompletion(models.Model):

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    task = models.ForeignKey(Task, on_delete=models.CASCADE)

    completed = models.BooleanField(default=False)

    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.task}"