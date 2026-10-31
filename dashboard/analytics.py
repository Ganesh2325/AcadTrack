from datetime import timedelta

from django.utils import timezone

from assignments.models import Assignment
from assignments.queries import assignments_visible_to_student, display_status
from subjects.models import Enrollment, Subject
from submissions.models import Evaluation, Submission, SubmissionAttempt


def percent(part, whole):
    if not whole:
        return 0
    return round((part / whole) * 100, 1)


def student_dashboard_data(user):
    """Build dashboard figures from the assignments this student can actually access."""
    now = timezone.now()
    assignment_list = list(
        assignments_visible_to_student(user).select_related("subject", "created_by")
    )
    submission_map = {
        item.assignment_id: item
        for item in Submission.objects.filter(
            student=user,
            assignment_id__in=[assignment.id for assignment in assignment_list],
        )
    }
    counts = {
        "total": 0,
        "pending": 0,
        "awaiting": 0,
        "revision": 0,
        "completed": 0,
        "overdue": 0,
    }
    subjects = {}
    for assignment in assignment_list:
        submission = submission_map.get(assignment.id)
        status = display_status(assignment, submission, now)
        assignment.student_submission = submission
        assignment.student_status = status
        counts["total"] += 1
        if status == "not_submitted":
            counts["pending"] += 1
        elif status == "overdue":
            counts["overdue"] += 1
        elif status == Submission.Status.COMPLETED:
            counts["completed"] += 1
        elif status == Submission.Status.REVISION_REQUESTED:
            counts["revision"] += 1
        else:
            counts["awaiting"] += 1
        bucket = subjects.setdefault(
            assignment.subject_id,
            {"subject": assignment.subject, "total": 0, "completed": 0},
        )
        bucket["total"] += 1
        if status == Submission.Status.COMPLETED:
            bucket["completed"] += 1
    for bucket in subjects.values():
        bucket["percent"] = percent(bucket["completed"], bucket["total"])
    counts["completion_percent"] = percent(counts["completed"], counts["total"])
    counts["subject_rows"] = sorted(subjects.values(), key=lambda row: row["subject"].subject_code)
    counts["turned_in"] = counts["awaiting"] + counts["revision"] + counts["completed"]

    upcoming = sorted(
        [
            assignment
            for assignment in assignment_list
            if assignment.publication_status == Assignment.PublicationStatus.PUBLISHED
            and assignment.deadline >= now
            and assignment.student_status != Submission.Status.COMPLETED
        ],
        key=lambda assignment: assignment.deadline,
    )[:5]
    recent_assignments = sorted(
        [
            assignment
            for assignment in assignment_list
            if assignment.publication_status == Assignment.PublicationStatus.PUBLISHED
        ],
        key=lambda assignment: assignment.published_at or assignment.created_at,
        reverse=True,
    )[:5]
    recent_attempts = list(
        SubmissionAttempt.objects.filter(submission__student=user)
        .select_related("submission__assignment")
        .order_by("-submitted_at")[:5]
    )
    recent_feedback = list(
        Evaluation.objects.filter(submission_attempt__submission__student=user)
        .select_related(
            "submission_attempt__submission__assignment",
            "reviewed_by",
        )
        .order_by("-reviewed_at")[:5]
    )
    return {
        "stats": counts,
        "assignments": assignment_list,
        "upcoming": upcoming,
        "recent_assignments": recent_assignments,
        "recent_attempts": recent_attempts,
        "recent_feedback": recent_feedback,
    }


def faculty_dashboard_data(user):
    """Faculty figures use assignments they created. Superusers see the full catalogue."""
    now = timezone.now()
    soon = now + timedelta(days=7)
    if user.is_superuser and not user.groups.filter(name="Faculty").exists():
        subjects = list(Subject.objects.all())
        assignment_list = list(
            Assignment.objects.select_related("subject", "created_by").prefetch_related("assigned_students")
        )
    else:
        subjects = list(Subject.objects.filter(faculty=user).distinct())
        assignment_list = list(
            Assignment.objects.filter(created_by=user)
            .select_related("subject", "created_by")
            .prefetch_related("assigned_students")
        )

    subject_ids = [subject.id for subject in subjects]
    enrollment_map = {}
    for subject_id, student_id in Enrollment.objects.filter(
        subject_id__in=subject_ids,
        is_active=True,
    ).values_list("subject_id", "student_id"):
        enrollment_map.setdefault(subject_id, set()).add(student_id)

    sub_map = {
        (assignment_id, student_id): status
        for assignment_id, student_id, status in Submission.objects.filter(
            assignment_id__in=[assignment.id for assignment in assignment_list]
        ).values_list("assignment_id", "student_id", "status")
    }

    def eligible_ids(assignment):
        enrolled = enrollment_map.get(assignment.subject_id, set())
        if assignment.audience == Assignment.Audience.SELECTED:
            selected = {student.id for student in assignment.assigned_students.all()}
            return enrolled & selected
        return set(enrolled)

    per_subject = {
        subject.id: {
            "subject": subject,
            "students": len(enrollment_map.get(subject.id, set())),
            "assignments": 0,
            "eligible": 0,
            "completed": 0,
            "submissions": 0,
        }
        for subject in subjects
    }
    published = []
    drafts = 0
    eligible_total = 0
    completed_total = 0
    counted_statuses = {
        Assignment.PublicationStatus.PUBLISHED,
        Assignment.PublicationStatus.ARCHIVED,
    }
    for assignment in assignment_list:
        if assignment.publication_status == Assignment.PublicationStatus.DRAFT:
            drafts += 1
        if assignment.publication_status == Assignment.PublicationStatus.PUBLISHED:
            published.append(assignment)
        if assignment.publication_status not in counted_statuses:
            continue
        students = eligible_ids(assignment)
        bucket = per_subject.setdefault(
            assignment.subject_id,
            {
                "subject": assignment.subject,
                "students": len(enrollment_map.get(assignment.subject_id, set())),
                "assignments": 0,
                "eligible": 0,
                "completed": 0,
                "submissions": 0,
            },
        )
        bucket["assignments"] += 1
        bucket["eligible"] += len(students)
        eligible_total += len(students)
        for student_id in students:
            status = sub_map.get((assignment.id, student_id))
            if status:
                bucket["submissions"] += 1
            if status == Submission.Status.COMPLETED:
                bucket["completed"] += 1
                completed_total += 1
    for bucket in per_subject.values():
        bucket["completion_rate"] = percent(bucket["completed"], bucket["eligible"])

    counted_ids = [
        assignment.id
        for assignment in assignment_list
        if assignment.publication_status in counted_statuses
    ]
    pending_evaluations = Submission.objects.filter(
        assignment_id__in=counted_ids,
        status__in=[Submission.Status.SUBMITTED, Submission.Status.UNDER_REVIEW],
    ).count()
    submission_count = Submission.objects.filter(
        assignment_id__in=[assignment.id for assignment in assignment_list]
    ).count()
    approaching = sorted(
        [assignment for assignment in published if now <= assignment.deadline <= soon],
        key=lambda assignment: assignment.deadline,
    )[:6]
    recent_submissions = list(
        Submission.objects.filter(assignment_id__in=[assignment.id for assignment in assignment_list])
        .select_related("student", "student__student_profile", "assignment")
        .order_by("-updated_at")[:6]
    )
    return {
        "subject_count": len(subjects),
        "published_count": len(published),
        "draft_count": drafts,
        "submission_count": submission_count,
        "pending_evaluations": pending_evaluations,
        "completion_rate": percent(completed_total, eligible_total),
        "completed_pairs": completed_total,
        "eligible_pairs": eligible_total,
        "approaching": approaching,
        "subject_rows": sorted(per_subject.values(), key=lambda row: row["subject"].subject_code),
        "recent_submissions": recent_submissions,
    }
