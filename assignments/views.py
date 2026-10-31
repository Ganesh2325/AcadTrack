import re
from datetime import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import faculty_required, student_required
from accounts.roles import is_faculty, is_student
from assignments.forms import (
    AssignmentForm,
    FacultyAssignmentFilterForm,
    StudentAssignmentFilterForm,
)
from assignments.models import Assignment
from assignments.queries import (
    assignments_visible_to_student,
    display_status,
    faculty_can_manage_assignment,
    filter_by_display_status,
    student_can_view_assignment,
)
from submissions.models import Submission


def _attach_student_status(assignments, user):
    submissions = {
        item.assignment_id: item
        for item in Submission.objects.filter(student=user, assignment__in=assignments)
    }
    now = timezone.now()
    for assignment in assignments:
        submission = submissions.get(assignment.id)
        assignment.student_submission = submission
        assignment.student_status = display_status(assignment, submission, now)
    return assignments


@student_required
def student_assignment_list(request):
    form = StudentAssignmentFilterForm(request.GET or None, user=request.user)
    queryset = assignments_visible_to_student(request.user).select_related("subject", "created_by")
    if form.is_valid():
        title = form.cleaned_data.get("q")
        if title:
            queryset = queryset.filter(title__icontains=title)
        subject = form.cleaned_data.get("subject")
        if subject:
            queryset = queryset.filter(subject=subject)
        status = form.cleaned_data.get("status")
        if status:
            queryset = filter_by_display_status(queryset, request.user, status)
        sort = form.cleaned_data.get("sort") or "deadline"
        if sort == "newest":
            queryset = queryset.order_by("-published_at", "-created_at")
        elif sort == "deadline_desc":
            queryset = queryset.order_by("-deadline")
        else:
            queryset = queryset.order_by("deadline")
    paginator = Paginator(queryset, 8)
    page_obj = paginator.get_page(request.GET.get("page"))
    _attach_student_status(page_obj.object_list, request.user)
    return render(
        request,
        "student/assignments.html",
        {"form": form, "page_obj": page_obj},
    )


@student_required
def student_assignment_detail(request, pk):
    assignment = get_object_or_404(
        Assignment.objects.select_related("subject", "created_by"),
        pk=pk,
    )
    if not student_can_view_assignment(request.user, assignment):
        raise PermissionDenied("You are not allowed to view this assignment.")
    submission = (
        Submission.objects.filter(student=request.user, assignment=assignment)
        .prefetch_related("attempts__evaluation__reviewed_by")
        .first()
    )
    attempts = []
    if submission is not None:
        attempts = list(submission.attempts.order_by("-attempt_number"))
    status = display_status(assignment, submission)
    from submissions.services import submission_block_reason

    return render(
        request,
        "student/assignment_detail.html",
        {
            "assignment": assignment,
            "submission": submission,
            "attempts": attempts,
            "status": status,
            "block_reason": submission_block_reason(assignment, submission),
        },
    )


@faculty_required
def faculty_assignment_list(request):
    form = FacultyAssignmentFilterForm(request.GET or None, user=request.user)
    if request.user.is_superuser:
        queryset = Assignment.objects.all()
    else:
        queryset = Assignment.objects.filter(created_by=request.user)
    queryset = queryset.select_related("subject", "created_by")
    if form.is_valid():
        title = form.cleaned_data.get("q")
        if title:
            queryset = queryset.filter(title__icontains=title)
        subject = form.cleaned_data.get("subject")
        if subject:
            queryset = queryset.filter(subject=subject)
        publication_status = form.cleaned_data.get("publication_status")
        if publication_status:
            queryset = queryset.filter(publication_status=publication_status)
        sort = form.cleaned_data.get("sort") or "newest"
        if sort == "deadline":
            queryset = queryset.order_by("deadline")
        elif sort == "title":
            queryset = queryset.order_by("title")
        else:
            queryset = queryset.order_by("-created_at")
    paginator = Paginator(queryset, 8)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "faculty/assignments.html",
        {"form": form, "page_obj": page_obj},
    )


def _save_assignment(form, request, existing=None):
    action = request.POST.get("action", "save")
    assignment = form.save(commit=False)
    if existing is None:
        assignment.created_by = request.user
    if action == "publish":
        assignment.publication_status = Assignment.PublicationStatus.PUBLISHED
        if assignment.published_at is None:
            assignment.published_at = timezone.now()
    elif action == "archive" and existing is not None:
        assignment.publication_status = Assignment.PublicationStatus.ARCHIVED
    elif action == "draft":
        if existing is not None and existing.submissions.exists():
            messages.error(
                request,
                "This assignment has submissions, so it cannot return to draft. Archive it instead.",
            )
            return None
        assignment.publication_status = Assignment.PublicationStatus.DRAFT
    elif existing is None:
        assignment.publication_status = Assignment.PublicationStatus.DRAFT
    assignment.save()
    form.save_m2m()
    if assignment.audience == Assignment.Audience.ALL_ENROLLED:
        assignment.assigned_students.clear()
    return assignment


@faculty_required
def assignment_create(request):
    publishing = request.method == "POST" and request.POST.get("action") == "publish"
    form = AssignmentForm(
        request.POST or None,
        request.FILES or None,
        faculty=request.user,
        publishing=publishing,
    )
    if request.method == "POST" and form.is_valid():
        assignment = _save_assignment(form, request)
        if assignment is not None:
            messages.success(request, "Assignment saved.")
            if assignment.publication_status == Assignment.PublicationStatus.PUBLISHED:
                return redirect("submissions:faculty_list", pk=assignment.pk)
            return redirect("assignments:edit", pk=assignment.pk)
    return render(
        request,
        "faculty/assignment_form.html",
        {"form": form, "is_edit": False},
    )


@faculty_required
def assignment_edit(request, pk):
    assignment = get_object_or_404(
        Assignment.objects.select_related("subject", "created_by"),
        pk=pk,
    )
    if not faculty_can_manage_assignment(request.user, assignment):
        raise PermissionDenied("You cannot edit another faculty member's assignment.")
    publishing = request.method == "POST" and request.POST.get("action") == "publish"
    form = AssignmentForm(
        request.POST or None,
        request.FILES or None,
        instance=assignment,
        faculty=request.user,
        publishing=publishing,
    )
    if request.method == "POST" and form.is_valid():
        saved = _save_assignment(form, request, existing=assignment)
        if saved is not None:
            messages.success(request, "Assignment updated.")
            return redirect("assignments:edit", pk=saved.pk)
    return render(
        request,
        "faculty/assignment_form.html",
        {"form": form, "is_edit": True, "assignment": assignment},
    )


@faculty_required
@require_POST
def assignment_archive(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if not faculty_can_manage_assignment(request.user, assignment):
        raise PermissionDenied("You cannot archive another faculty member's assignment.")
    assignment.publication_status = Assignment.PublicationStatus.ARCHIVED
    assignment.save(update_fields=["publication_status", "updated_at"])
    messages.success(request, "Assignment archived.")
    return redirect("assignments:faculty_list")


@faculty_required
@require_POST
def assignment_delete(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if not faculty_can_manage_assignment(request.user, assignment):
        raise PermissionDenied("You cannot delete another faculty member's assignment.")
    if assignment.submissions.exists():
        messages.error(
            request,
            "This assignment has submissions and cannot be deleted. Archive it instead.",
        )
        return redirect("assignments:edit", pk=assignment.pk)
    try:
        assignment.delete()
    except ProtectedError:
        messages.error(request, "This assignment cannot be deleted because other records depend on it.")
        return redirect("assignments:edit", pk=assignment.pk)
    messages.success(request, "Assignment deleted.")
    return redirect("assignments:faculty_list")


def assignment_archive_jump(request):
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(request.get_full_path())
    year = (request.GET.get("year") or "").strip()
    if not re.fullmatch(r"\d{4}", year):
        messages.error(request, "Enter a four-digit year.")
        fallback = "assignments:faculty_list" if is_faculty(request.user) else "assignments:student_list"
        if is_faculty(request.user) or is_student(request.user):
            return redirect(fallback)
        return redirect("landing")
    return redirect("assignments:archive_year", year=year)


def assignment_archive_year(request, year):
    """Four-digit archive route implemented with a regular-expression URL."""
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(request.get_full_path())
    try:
        year_number = int(year)
        start = timezone.make_aware(datetime(year_number, 1, 1))
        end = timezone.make_aware(datetime(year_number + 1, 1, 1))
    except (TypeError, ValueError, OverflowError):
        from django.http import Http404

        raise Http404("That archive year is not available.")
    if is_student(request.user) and not is_faculty(request.user):
        queryset = assignments_visible_to_student(request.user)
    elif is_faculty(request.user) or request.user.is_superuser:
        if request.user.is_superuser:
            queryset = Assignment.objects.all()
        else:
            queryset = Assignment.objects.filter(created_by=request.user)
    else:
        raise PermissionDenied("You cannot browse this archive.")
    assignments = (
        queryset.filter(created_at__gte=start, created_at__lt=end)
        .select_related("subject", "created_by")
        .order_by("-created_at")
    )
    if is_student(request.user):
        _attach_student_status(assignments, request.user)
    return render(
        request,
        "assignments/archive.html",
        {"year": year_number, "assignments": assignments},
    )
