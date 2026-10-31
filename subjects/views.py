from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import faculty_required
from accounts.roles import is_faculty, is_student
from assignments.queries import assignments_visible_to_student
from subjects.access import faculty_can_manage_subject
from subjects.forms import EnrollmentForm, SubjectForm
from subjects.models import Enrollment, Subject
from django.contrib.auth.decorators import login_required


@login_required
def subject_list(request):
    query = request.GET.get("q", "").strip()
    if request.user.is_superuser:
        subjects = Subject.objects.all()
    elif is_faculty(request.user):
        subjects = Subject.objects.filter(faculty=request.user)
    elif is_student(request.user):
        subjects = Subject.objects.filter(
            enrollments__student=request.user,
            enrollments__is_active=True,
        )
    else:
        raise PermissionDenied("You do not have access to subjects.")
    subjects = subjects.distinct().prefetch_related("faculty")
    if query:
        subjects = subjects.filter(
            Q(subject_name__icontains=query) | Q(subject_code__icontains=query)
        )
    return render(
        request,
        "subjects/subject_list.html",
        {"subjects": subjects, "query": query},
    )


@login_required
def subject_detail(request, pk):
    subject = get_object_or_404(
        Subject.objects.prefetch_related("faculty"),
        pk=pk,
    )
    can_manage = faculty_can_manage_subject(request.user, subject)
    enrollment = None
    if is_student(request.user):
        enrollment = Enrollment.objects.filter(
            student=request.user,
            subject=subject,
            is_active=True,
        ).first()
    if not can_manage and enrollment is None:
        raise PermissionDenied("You are not allowed to view this subject.")

    enrollments = []
    form = None
    assignments = []
    if can_manage:
        enrollments = (
            subject.enrollments.filter(is_active=True)
            .select_related("student", "student__student_profile")
            .order_by("student__first_name", "student__username")
        )
        form = EnrollmentForm(subject=subject)
        assignment_queryset = subject.assignments.select_related("created_by")
        if not request.user.is_superuser:
            assignment_queryset = assignment_queryset.filter(
                Q(created_by=request.user)
                | Q(
                    publication_status__in=[
                        "published",
                        "archived",
                    ]
                )
            )
        assignments = assignment_queryset.order_by("-created_at")
    elif enrollment is not None:
        assignments = (
            assignments_visible_to_student(request.user)
            .filter(subject=subject)
            .select_related("created_by")
            .order_by("deadline")
        )
    return render(
        request,
        "subjects/subject_detail.html",
        {
            "subject": subject,
            "can_manage": can_manage,
            "enrollments": enrollments,
            "form": form,
            "assignments": assignments,
        },
    )


@faculty_required
def subject_create(request):
    form = SubjectForm(request.POST or None, faculty_user=request.user)
    if request.method == "POST" and form.is_valid():
        subject = form.save(commit=False)
        subject.save()
        form.save_m2m()
        if not request.user.is_superuser:
            subject.faculty.add(request.user)
        messages.success(request, "Subject created.")
        return redirect("subjects:detail", pk=subject.pk)
    return render(request, "subjects/subject_form.html", {"form": form, "is_edit": False})


@faculty_required
def subject_edit(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if not faculty_can_manage_subject(request.user, subject):
        raise PermissionDenied("You can edit only subjects assigned to you.")
    form = SubjectForm(request.POST or None, instance=subject, faculty_user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        if not request.user.is_superuser:
            subject.faculty.add(request.user)
        messages.success(request, "Subject updated.")
        return redirect("subjects:detail", pk=subject.pk)
    return render(
        request,
        "subjects/subject_form.html",
        {"form": form, "is_edit": True, "subject": subject},
    )


@faculty_required
def enroll_student(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if not faculty_can_manage_subject(request.user, subject):
        raise PermissionDenied("You cannot change enrollment for this subject.")
    if request.method != "POST":
        return redirect("subjects:detail", pk=subject.pk)
    form = EnrollmentForm(request.POST, subject=subject)
    if not form.is_valid():
        enrollments = (
            subject.enrollments.filter(is_active=True)
            .select_related("student", "student__student_profile")
        )
        return render(
            request,
            "subjects/subject_detail.html",
            {
                "subject": subject,
                "can_manage": True,
                "enrollments": enrollments,
                "form": form,
                "assignments": subject.assignments.select_related("created_by"),
            },
        )
    student = form.cleaned_data["student"]
    try:
        with transaction.atomic():
            enrollment, created = Enrollment.objects.get_or_create(
                student=student,
                subject=subject,
                defaults={"is_active": True},
            )
            if not created and not enrollment.is_active:
                enrollment.is_active = True
                enrollment.save(update_fields=["is_active"])
    except IntegrityError:
        messages.error(request, "This student is already enrolled in the subject.")
        return redirect("subjects:detail", pk=subject.pk)
    messages.success(request, f"{student.get_full_name() or student.username} is enrolled.")
    return redirect("subjects:detail", pk=subject.pk)


@faculty_required
def unenroll_student(request, pk, student_id):
    subject = get_object_or_404(Subject, pk=pk)
    if not faculty_can_manage_subject(request.user, subject):
        raise PermissionDenied("You cannot change enrollment for this subject.")
    if request.method != "POST":
        return redirect("subjects:detail", pk=subject.pk)
    enrollment = get_object_or_404(
        Enrollment,
        subject=subject,
        student_id=student_id,
        is_active=True,
    )
    enrollment.is_active = False
    enrollment.save(update_fields=["is_active"])
    messages.success(request, "Student removed from the active enrollment list.")
    return redirect("subjects:detail", pk=subject.pk)
