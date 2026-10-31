from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.models import StudentProfile
from accounts.roles import FACULTY_GROUP, STUDENT_GROUP
from subjects.models import Enrollment, Subject

User = get_user_model()


def ensure_groups():
    Group.objects.get_or_create(name=STUDENT_GROUP)
    Group.objects.get_or_create(name=FACULTY_GROUP)


def make_faculty(username="faculty1", password="ValidPass@123", first_name="Faculty", last_name="Member"):
    ensure_groups()
    user = User.objects.create_user(
        username=username,
        email=f"{username}@acadtrack.test",
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    user.groups.add(Group.objects.get(name=FACULTY_GROUP))
    return user


def make_student(
    username="student1",
    roll="AT0001",
    password="ValidPass@123",
    first_name="Student",
    last_name="Member",
    department="CSE",
    semester=5,
):
    ensure_groups()
    user = User.objects.create_user(
        username=username,
        email=f"{username}@acadtrack.test",
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    user.groups.add(Group.objects.get(name=STUDENT_GROUP))
    StudentProfile.objects.create(
        user=user,
        roll_number=roll,
        department=department,
        semester=semester,
    )
    return user


def make_subject(faculty, code="CS301", name="Database Systems"):
    subject = Subject.objects.create(
        subject_name=name,
        subject_code=code,
        description=f"{name} demonstration subject.",
    )
    subject.faculty.add(faculty)
    return subject


def enroll(student, subject):
    return Enrollment.objects.create(student=student, subject=subject)
