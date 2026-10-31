from django.contrib import admin

from assignments.models import Assignment


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "subject",
        "created_by",
        "publication_status",
        "audience",
        "deadline",
        "max_marks",
    )
    list_filter = ("publication_status", "audience", "allow_late_submission", "subject")
    search_fields = ("title", "description", "subject__subject_code", "created_by__username")
    list_select_related = ("subject", "created_by")
    filter_horizontal = ("assigned_students",)
    autocomplete_fields = ("subject", "created_by")
    readonly_fields = ("created_at", "updated_at", "published_at")
    date_hierarchy = "deadline"
    ordering = ("-created_at",)
    fieldsets = (
        (
            "Assignment",
            {"fields": ("title", "subject", "created_by", "description", "instructions", "attachment")},
        ),
        (
            "Audience and schedule",
            {"fields": ("audience", "assigned_students", "deadline", "published_at", "publication_status")},
        ),
        (
            "Marking rules",
            {"fields": ("max_marks", "allow_late_submission", "allow_resubmission")},
        ),
        ("Record", {"fields": ("created_at", "updated_at")}),
    )
