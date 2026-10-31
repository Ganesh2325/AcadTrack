from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from acadtrack.uploads import assignment_attachment_path
from subjects.models import Subject


class Assignment(models.Model):
    """Faculty-owned coursework.

    Audience rules:
    - all enrolled: every active enrollment in the subject can see a published assignment
    - selected: only those students, and only if they are actively enrolled
    Drafts are never part of the student-visible queryset.
    """

    class Audience(models.TextChoices):
        ALL_ENROLLED = "all", "All enrolled students"
        SELECTED = "selected", "Selected students"

    class PublicationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=200)
    description = models.TextField()
    instructions = models.TextField(blank=True)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assignments_created",
    )
    assigned_students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="targeted_assignments",
        blank=True,
    )
    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.ALL_ENROLLED,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField()
    max_marks = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    attachment = models.FileField(
        upload_to=assignment_attachment_path,
        blank=True,
        null=True,
    )
    allow_late_submission = models.BooleanField(default=False)
    allow_resubmission = models.BooleanField(default=True)
    publication_status = models.CharField(
        max_length=20,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["deadline", "title"]
        indexes = [
            models.Index(fields=["publication_status", "deadline"]),
            models.Index(fields=["subject", "publication_status"]),
            models.Index(fields=["created_by", "publication_status"]),
        ]

    def __str__(self):
        return self.title
