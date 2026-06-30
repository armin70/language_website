from django.conf import settings
from django.db import models


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    placement_completed = models.BooleanField(default=False)

    level = models.CharField(max_length=10, blank=True, null=True)
    stage = models.IntegerField(blank=True, null=True)

    start_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.user.username
