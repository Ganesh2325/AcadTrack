from django.db import models
from django.conf import settings


class Subject(models.Model):
    subject_name = models.CharField(max_length=200)
    subject_code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    faculty = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="subjects_taught",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subject_code"]

    def __str__(self):
        return f"{self.subject_code} — {self.subject_name}"

    def save(self, *args, **kwargs):
        self.subject_code = (self.subject_code or "").strip().upper()
        super().save(*args, **kwargs)


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    enrollment_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["subject__subject_code", "student__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "subject"],
                name="unique_student_subject_enrollment",
            )
        ]
        indexes = [
            models.Index(fields=["subject", "is_active"]),
        ]

    def __str__(self):
        state = "active" if self.is_active else "inactive"
        return f"{self.student} in {self.subject.subject_code} ({state})"
