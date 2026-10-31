from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from accounts.models import StudentProfile, User
from accounts.roles import FACULTY_GROUP, STUDENT_GROUP


@admin.action(description="Add selected users to the Faculty group")
def add_to_faculty(modeladmin, request, queryset):
    group, _created = Group.objects.get_or_create(name=FACULTY_GROUP)
    for user in queryset:
        user.groups.add(group)


@admin.action(description="Promote to faculty and remove student access")
def promote_to_faculty(modeladmin, request, queryset):
    faculty_group, _created = Group.objects.get_or_create(name=FACULTY_GROUP)
    student_group, _created = Group.objects.get_or_create(name=STUDENT_GROUP)
    for user in queryset:
        user.groups.add(faculty_group)
        user.groups.remove(student_group)


@admin.action(description="Add selected users to the Students group")
def add_to_students(modeladmin, request, queryset):
    group, _created = Group.objects.get_or_create(name=STUDENT_GROUP)
    for user in queryset:
        user.groups.add(group)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    actions = [add_to_faculty, promote_to_faculty, add_to_students]


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("roll_number", "user", "department", "semester", "updated_at")
    list_filter = ("department", "semester")
    search_fields = (
        "roll_number",
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("user", "roll_number", "department", "semester")}),
        ("Record", {"fields": ("created_at", "updated_at")}),
    )
