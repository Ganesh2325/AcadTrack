STUDENT_GROUP = "Students"
FACULTY_GROUP = "Faculty"


def is_student(user):
    return user.is_authenticated and user.groups.filter(name=STUDENT_GROUP).exists()


def is_faculty(user):
    return user.is_authenticated and user.groups.filter(name=FACULTY_GROUP).exists()


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def role_label(user):
    """Display label stored in the session. Authorization never trusts this value."""
    labels = []
    if is_admin(user) and user.is_superuser:
        labels.append("Administrator")
    if is_faculty(user):
        labels.append("Faculty")
    if is_student(user):
        labels.append("Student")
    if not labels and user.is_staff:
        labels.append("Administrator")
    return " and ".join(labels) or "User"


def home_url_name(user):
    if is_faculty(user):
        return "dashboard:faculty"
    if is_student(user):
        return "dashboard:student"
    if is_admin(user):
        return "admin:index"
    return "landing"
