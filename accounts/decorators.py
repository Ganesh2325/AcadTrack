from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from accounts.roles import is_faculty, is_student


def student_required(view_func):
    """Allow only users in the Students group who have a student profile."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_student(request.user) or not hasattr(request.user, "student_profile"):
            raise PermissionDenied("Student access is required.")
        return view_func(request, *args, **kwargs)

    return wrapped


def faculty_required(view_func):
    """Allow faculty members and superusers. Students are rejected on the server."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (is_faculty(request.user) or request.user.is_superuser):
            raise PermissionDenied("Faculty access is required.")
        return view_func(request, *args, **kwargs)

    return wrapped
