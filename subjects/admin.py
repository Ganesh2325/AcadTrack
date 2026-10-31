from django.contrib import admin

from subjects.models import Enrollment, Subject


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    autocomplete_fields = ("student",)
    fields = ("student", "enrollment_date", "is_active")
    readonly_fields = ("enrollment_date",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("subject_code", "subject_name", "updated_at")
    search_fields = ("subject_code", "subject_name", "description")
    filter_horizontal = ("faculty",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [EnrollmentInline]
    fieldsets = (
        (None, {"fields": ("subject_code", "subject_name", "description", "faculty")}),
        ("Record", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "enrollment_date", "is_active")
    list_filter = ("is_active", "subject")
    search_fields = (
        "student__username",
        "student__first_name",
        "student__last_name",
        "student__student_profile__roll_number",
        "subject__subject_code",
        "subject__subject_name",
    )
    list_select_related = ("student", "subject")
    autocomplete_fields = ("student", "subject")
    ordering = ("-enrollment_date",)
