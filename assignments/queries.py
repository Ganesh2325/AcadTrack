from django.db.models import Q
from django.utils import timezone

from assignments.models import Assignment
from subjects.models import Enrollment


NOT_SUBMITTED = "not_submitted"
OVERDUE = "overdue"

STATUS_LABELS = {
    NOT_SUBMITTED: "Not Submitted",
    OVERDUE: "Overdue",
    "submitted": "Submitted",
    "under_review": "Under Review",
    "revision_requested": "Revision Requested",
    "completed": "Completed",
    "draft": "Draft",
    "published": "Published",
    "archived": "Archived",
}


def faculty_can_manage_assignment(user, assignment):
    """Only the creator or a superuser may edit, archive, or evaluate an assignment."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return assignment.created_by_id == user.id


def assignments_visible_to_student(user):
    """Published and archived work the student is eligible to access. Drafts are excluded."""
    enrolled_subject_ids = Enrollment.objects.filter(
        student=user,
        is_active=True,
    ).values("subject_id")
    return (
        Assignment.objects.filter(
            publication_status__in=[
                Assignment.PublicationStatus.PUBLISHED,
                Assignment.PublicationStatus.ARCHIVED,
            ],
            subject_id__in=enrolled_subject_ids,
        )
        .filter(
            Q(audience=Assignment.Audience.ALL_ENROLLED)
            | Q(audience=Assignment.Audience.SELECTED, assigned_students=user)
        )
        .distinct()
    )


def student_can_view_assignment(user, assignment):
    if assignment.publication_status == Assignment.PublicationStatus.DRAFT:
        return False
    if assignment.publication_status not in (
        Assignment.PublicationStatus.PUBLISHED,
        Assignment.PublicationStatus.ARCHIVED,
    ):
        return False
    enrolled = Enrollment.objects.filter(
        student=user,
        subject_id=assignment.subject_id,
        is_active=True,
    ).exists()
    if not enrolled:
        return False
    if assignment.audience == Assignment.Audience.ALL_ENROLLED:
        return True
    return assignment.assigned_students.filter(pk=user.pk).exists()


def display_status(assignment, submission, now=None):
    """Map an assignment and optional submission to one student-facing status.

    A late submission still has a submission row, so it is never labeled as an
    unsubmitted overdue assignment.
    """
    now = now or timezone.now()
    if submission is None:
        if assignment.deadline < now:
            return OVERDUE
        return NOT_SUBMITTED
    return submission.status


def filter_by_display_status(queryset, user, status):
    from submissions.models import Submission

    now = timezone.now()
    submitted_ids = Submission.objects.filter(student=user).values("assignment_id")
    if status == NOT_SUBMITTED:
        return queryset.filter(deadline__gte=now).exclude(pk__in=submitted_ids)
    if status == OVERDUE:
        return queryset.filter(deadline__lt=now).exclude(pk__in=submitted_ids)
    if status:
        return queryset.filter(submissions__student=user, submissions__status=status)
    return queryset
