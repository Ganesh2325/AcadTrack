from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from acadtrack.uploads import submission_file_path
from assignments.models import Assignment


class Submission(models.Model):
    """One submission record per student and assignment. Attempts live separately."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        REVISION_REQUESTED = "revision_requested", "Revision Requested"
        COMPLETED = "completed", "Completed"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    current_attempt_number = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "assignment"],
                name="unique_student_assignment_submission",
            )
        ]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["assignment", "status"]),
        ]

    def __str__(self):
        return f"{self.student} — {self.assignment}"


class SubmissionAttempt(models.Model):
    """Immutable student attempt. A new correction creates a new row."""

    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempt_number = models.PositiveIntegerField()
    submitted_text = models.TextField(blank=True)
    submitted_file = models.FileField(upload_to=submission_file_path, blank=True)
    original_filename = models.CharField(max_length=180, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_late = models.BooleanField(default=False)

    class Meta:
        ordering = ["attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "attempt_number"],
                name="unique_attempt_number_per_submission",
            )
        ]

    def __str__(self):
        return f"Attempt {self.attempt_number} for {self.submission}"

    def clean(self):
        if not (self.submitted_text or "").strip() and not self.submitted_file:
            raise ValidationError("Provide submission text or upload a file.")

    def delete(self, *args, **kwargs):
        stored = self.submitted_file
        super().delete(*args, **kwargs)
        if stored:
            stored.delete(save=False)


class Evaluation(models.Model):
    class Decision(models.TextChoices):
        ACCEPT = "accept", "Accepted"
        REVISION = "revision", "Revision requested"

    submission_attempt = models.OneToOneField(
        SubmissionAttempt,
        on_delete=models.CASCADE,
        related_name="evaluation",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evaluations_given",
    )
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    comments = models.TextField(blank=True)
    decision = models.CharField(max_length=20, choices=Decision.choices)
    reviewed_at = models.DateTimeField()

    class Meta:
        ordering = ["-reviewed_at"]

    def __str__(self):
        return f"Evaluation of {self.submission_attempt}"

    def clean(self):
        if not self.submission_attempt_id:
            return
        max_marks = self.submission_attempt.submission.assignment.max_marks
        if self.marks_obtained is None:
            return
        if self.marks_obtained < 0:
            raise ValidationError({"marks_obtained": "Marks cannot be negative."})
        if self.marks_obtained > max_marks:
            raise ValidationError(
                {"marks_obtained": f"Marks cannot exceed the maximum of {max_marks}."}
            )
