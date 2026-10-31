from accounts.backends import theme_from_request
from accounts.roles import home_url_name, is_admin, is_faculty, is_student, role_label


def ui_preferences(request):
    user = getattr(request, "user", None)
    return {
        "theme": theme_from_request(request),
        "is_student_user": is_student(user) if user is not None else False,
        "is_faculty_user": is_faculty(user) if user is not None else False,
        "is_admin_user": is_admin(user) if user is not None else False,
        "role_label": role_label(user) if user is not None and user.is_authenticated else "",
        "home_url_name": home_url_name(user) if user is not None and user.is_authenticated else "landing",
    }
