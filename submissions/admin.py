from django.contrib import admin

from submissions.models import Evaluation, Submission, SubmissionAttempt


class SubmissionAttemptInline(admin.TabularInline):
    model = SubmissionAttempt
    extra = 0
    fields = ("attempt_number", "submitted_at", "is_late", "original_filename")
    readonly_fields = ("attempt_number", "submitted_at", "is_late", "original_filename")
    show_change_link = True
    can_delete = False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("student", "assignment", "status", "current_attempt_number", "updated_at")
    list_filter = ("status", "assignment__subject")
    search_fields = (
        "student__username",
        "student__first_name",
        "student__last_name",
        "student__student_profile__roll_number",
        "assignment__title",
    )
    list_select_related = ("student", "assignment")
    autocomplete_fields = ("student", "assignment")
    readonly_fields = ("created_at", "updated_at")
    inlines = [SubmissionAttemptInline]
    ordering = ("-updated_at",)


@admin.register(SubmissionAttempt)
class SubmissionAttemptAdmin(admin.ModelAdmin):
    list_display = ("submission", "attempt_number", "submitted_at", "is_late", "original_filename")
    list_filter = ("is_late",)
    search_fields = (
        "submission__student__username",
        "submission__assignment__title",
        "original_filename",
    )
    list_select_related = ("submission", "submission__student", "submission__assignment")
    readonly_fields = ("submission", "attempt_number", "submitted_at", "is_late")
    ordering = ("-submitted_at",)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("submission_attempt", "reviewed_by", "marks_obtained", "decision", "reviewed_at")
    list_filter = ("decision",)
    search_fields = (
        "submission_attempt__submission__student__username",
        "submission_attempt__submission__assignment__title",
        "comments",
        "reviewed_by__username",
    )
    list_select_related = (
        "submission_attempt",
        "submission_attempt__submission",
        "reviewed_by",
    )
    autocomplete_fields = ("reviewed_by",)
    readonly_fields = ("submission_attempt",)
    ordering = ("-reviewed_at",)
