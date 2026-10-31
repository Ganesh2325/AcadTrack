from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from acadtrack.uploads import safe_original_name
from accounts.decorators import faculty_required, student_required
from accounts.roles import is_faculty, is_student
from assignments.models import Assignment
from assignments.queries import (
    display_status,
    faculty_can_manage_assignment,
    student_can_view_assignment,
)
from submissions.forms import (
    AssignmentSubmissionForm,
    EvaluationForm,
    SubmissionFilterForm,
    filter_eligible_students,
)
from submissions.models import Submission, SubmissionAttempt
from submissions.services import create_attempt, record_evaluation, submission_block_reason


def _file_response(file_field, download_name):
    if not file_field:
        raise Http404("File not found.")
    try:
        handle = file_field.open("rb")
    except FileNotFoundError as exc:
        raise Http404("File not found.") from exc
    response = FileResponse(
        handle,
        as_attachment=True,
        filename=safe_original_name(download_name or file_field.name),
    )
    response["Content-Type"] = "application/octet-stream"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@student_required
def submit_assignment(request, pk):
    assignment = get_object_or_404(
        Assignment.objects.select_related("subject", "created_by"),
        pk=pk,
    )
    if not student_can_view_assignment(request.user, assignment):
        raise PermissionDenied("You are not allowed to submit this assignment.")
    submission = Submission.objects.filter(student=request.user, assignment=assignment).first()
    block_reason = submission_block_reason(assignment, submission)
    form = None
    if request.method == "POST":
        form = AssignmentSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                create_attempt(
                    student=request.user,
                    assignment=assignment,
                    submitted_text=form.cleaned_data["submitted_text"],
                    uploaded_file=form.cleaned_data["submitted_file"],
                )
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            except PermissionDenied:
                raise
            else:
                messages.success(request, "Submission received.")
                return redirect("assignments:student_detail", pk=assignment.pk)
    elif block_reason is None:
        form = AssignmentSubmissionForm()
    return render(
        request,
        "student/submit.html",
        {
            "assignment": assignment,
            "form": form,
            "block_reason": block_reason,
            "submission": submission,
        },
    )


@student_required
def submission_history(request):
    submissions = (
        Submission.objects.filter(student=request.user)
        .select_related("assignment", "assignment__subject")
        .prefetch_related("attempts__evaluation")
        .order_by("-updated_at")
    )
    paginator = Paginator(submissions, 8)
    page_obj = paginator.get_page(request.GET.get("page"))
    for submission in page_obj.object_list:
        latest = None
        for attempt in submission.attempts.all():
            if latest is None or attempt.attempt_number > latest.attempt_number:
                latest = attempt
        submission.latest_attempt = latest
        submission.student_status = submission.status
    return render(request, "student/submission_history.html", {"page_obj": page_obj})


@student_required
def submission_detail(request, pk):
    submission = get_object_or_404(
        Submission.objects.select_related("assignment", "assignment__subject", "student"),
        pk=pk,
    )
    if submission.student_id != request.user.id:
        raise PermissionDenied("You cannot view another student's submission.")
    attempts = submission.attempts.select_related("evaluation", "evaluation__reviewed_by").order_by(
        "-attempt_number"
    )
    return render(
        request,
        "student/submission_detail.html",
        {
            "submission": submission,
            "attempts": attempts,
            "status": display_status(submission.assignment, submission),
        },
    )


@faculty_required
def faculty_submission_list(request, pk):
    assignment = get_object_or_404(
        Assignment.objects.select_related("subject", "created_by"),
        pk=pk,
    )
    if not faculty_can_manage_assignment(request.user, assignment):
        raise PermissionDenied("You cannot monitor another faculty member's assignment.")
    form = SubmissionFilterForm(request.GET or None)
    query = ""
    status = ""
    if form.is_valid():
        query = form.cleaned_data.get("q") or ""
        status = form.cleaned_data.get("status") or ""
    students = filter_eligible_students(assignment, query, status)
    paginator = Paginator(students, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    submissions = {
        item.student_id: item
        for item in Submission.objects.filter(
            assignment=assignment,
            student__in=page_obj.object_list,
        )
    }
    rows = []
    for student in page_obj.object_list:
        submission = submissions.get(student.id)
        rows.append(
            {
                "student": student,
                "submission": submission,
                "status": display_status(assignment, submission),
            }
        )
    return render(
        request,
        "faculty/submission_list.html",
        {
            "assignment": assignment,
            "form": form,
            "page_obj": page_obj,
            "rows": rows,
        },
    )


@faculty_required
def evaluate_submission(request, pk):
    submission = get_object_or_404(
        Submission.objects.select_related(
            "assignment",
            "assignment__subject",
            "assignment__created_by",
            "student",
            "student__student_profile",
        ),
        pk=pk,
    )
    if not faculty_can_manage_assignment(request.user, submission.assignment):
        raise PermissionDenied("You cannot evaluate another faculty member's assignment.")
    attempts = list(
        submission.attempts.select_related("evaluation", "evaluation__reviewed_by").order_by(
            "attempt_number"
        )
    )
    latest = attempts[-1] if attempts else None
    existing = getattr(latest, "evaluation", None) if latest else None
    form = None
    if latest is not None:
        form = EvaluationForm(
            request.POST or None,
            instance=existing,
            assignment=submission.assignment,
        )
        if request.method == "POST" and form.is_valid():
            try:
                record_evaluation(
                    attempt=latest,
                    reviewer=request.user,
                    marks=form.cleaned_data["marks_obtained"],
                    comments=form.cleaned_data["comments"],
                    decision=form.cleaned_data["decision"],
                )
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            else:
                messages.success(request, "Evaluation saved.")
                return redirect("submissions:evaluate", pk=submission.pk)
    return render(
        request,
        "faculty/evaluate_submission.html",
        {
            "submission": submission,
            "attempts": attempts,
            "latest": latest,
            "form": form,
        },
    )


@faculty_required
@require_POST
def start_review(request, pk):
    submission = get_object_or_404(
        Submission.objects.select_related("assignment"),
        pk=pk,
    )
    if not faculty_can_manage_assignment(request.user, submission.assignment):
        raise PermissionDenied("You cannot review another faculty member's assignment.")
    if submission.status == Submission.Status.SUBMITTED:
        submission.status = Submission.Status.UNDER_REVIEW
        submission.save(update_fields=["status", "updated_at"])
        messages.success(request, "Submission marked as under review.")
    return redirect("submissions:evaluate", pk=submission.pk)


@login_required
def download_attempt(request, pk):
    attempt = get_object_or_404(
        SubmissionAttempt.objects.select_related(
            "submission__student",
            "submission__assignment__created_by",
        ),
        pk=pk,
    )
    submission = attempt.submission
    owns_submission = submission.student_id == request.user.id and is_student(request.user)
    manages_assignment = faculty_can_manage_assignment(request.user, submission.assignment)
    if not (owns_submission or manages_assignment):
        raise PermissionDenied("You cannot download this file.")
    filename = attempt.original_filename or f"attempt-{attempt.attempt_number}"
    return _file_response(attempt.submitted_file, filename)


def download_attachment(request, pk):
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(request.get_full_path())
    assignment = get_object_or_404(Assignment.objects.select_related("created_by", "subject"), pk=pk)
    allowed = faculty_can_manage_assignment(request.user, assignment) or (
        is_faculty(request.user) and assignment.subject.faculty.filter(pk=request.user.pk).exists()
    )
    if is_student(request.user) and student_can_view_assignment(request.user, assignment):
        allowed = True
    if not allowed:
        raise PermissionDenied("You cannot download this attachment.")
    return _file_response(assignment.attachment, assignment.attachment.name if assignment.attachment else "")
