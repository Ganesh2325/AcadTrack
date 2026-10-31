from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from acadtrack.uploads import safe_original_name
from assignments.models import Assignment
from assignments.queries import student_can_view_assignment
from submissions.models import Evaluation, Submission, SubmissionAttempt


def submission_block_reason(assignment, submission, now=None):
    """Return a student-facing reason when a new attempt is not allowed."""
    now = now or timezone.now()
    if assignment.publication_status != Assignment.PublicationStatus.PUBLISHED:
        return "This assignment is not open for submission."
    is_late = now > assignment.deadline
    if submission is None:
        if is_late and not assignment.allow_late_submission:
            return "The deadline has passed and late submissions are not allowed."
        return None
    if submission.status == Submission.Status.REVISION_REQUESTED:
        if not assignment.allow_resubmission:
            return "Resubmission is not permitted for this assignment."
        if is_late and not assignment.allow_late_submission:
            return "The deadline has passed and late submissions are not allowed."
        return None
    if submission.status == Submission.Status.COMPLETED:
        return "This assignment is complete. Further submissions are closed."
    return "Your work is with the faculty. You can resubmit only if a revision is requested."


@transaction.atomic
def create_attempt(*, student, assignment, submitted_text, uploaded_file):
    if not student_can_view_assignment(student, assignment):
        raise PermissionDenied("You cannot submit this assignment.")
    now = timezone.now()
    submission = Submission.objects.filter(student=student, assignment=assignment).first()
    reason = submission_block_reason(assignment, submission, now)
    if reason:
        raise ValidationError(reason)

    is_late = now > assignment.deadline
    if submission is None:
        submission = Submission(
            student=student,
            assignment=assignment,
            status=Submission.Status.SUBMITTED,
            current_attempt_number=0,
        )
        try:
            with transaction.atomic():
                submission.save()
        except IntegrityError:
            submission = Submission.objects.get(student=student, assignment=assignment)
            reason = submission_block_reason(assignment, submission, now)
            if reason:
                raise ValidationError(reason)

    latest = submission.attempts.order_by("-attempt_number").first()
    next_number = submission.current_attempt_number + 1
    if latest is not None and latest.attempt_number >= next_number:
        next_number = latest.attempt_number + 1

    attempt = SubmissionAttempt(
        submission=submission,
        attempt_number=next_number,
        submitted_text=(submitted_text or "").strip(),
        is_late=is_late,
        original_filename=safe_original_name(uploaded_file.name) if uploaded_file else "",
    )
    if uploaded_file:
        attempt.submitted_file = uploaded_file
    attempt.full_clean()
    attempt.save()

    submission.current_attempt_number = next_number
    submission.status = Submission.Status.SUBMITTED
    submission.save(update_fields=["current_attempt_number", "status", "updated_at"])
    return attempt


@transaction.atomic
def record_evaluation(*, attempt, reviewer, marks, comments, decision):
    submission = attempt.submission
    assignment = submission.assignment
    if attempt.attempt_number != submission.current_attempt_number:
        raise ValidationError("Only the latest attempt can be evaluated.")
    if decision == Evaluation.Decision.REVISION and not assignment.allow_resubmission:
        raise ValidationError("This assignment does not permit resubmission.")
    if marks < 0 or marks > assignment.max_marks:
        raise ValidationError(
            f"Marks must be between 0 and {assignment.max_marks}."
        )
    evaluation, _created = Evaluation.objects.update_or_create(
        submission_attempt=attempt,
        defaults={
            "reviewed_by": reviewer,
            "marks_obtained": marks,
            "comments": comments,
            "decision": decision,
            "reviewed_at": timezone.now(),
        },
    )
    submission.status = (
        Submission.Status.COMPLETED
        if decision == Evaluation.Decision.ACCEPT
        else Submission.Status.REVISION_REQUESTED
    )
    submission.save(update_fields=["status", "updated_at"])
    return evaluation
