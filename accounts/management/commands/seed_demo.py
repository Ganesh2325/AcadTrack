from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.groups import create_default_groups
from accounts.models import StudentProfile
from accounts.roles import FACULTY_GROUP, STUDENT_GROUP
from assignments.models import Assignment
from subjects.models import Enrollment, Subject
from submissions.services import create_attempt

User = get_user_model()

DEMO_PASSWORD = "AcadTrack@123"


class Command(BaseCommand):
    help = "Create clearly marked demonstration users, subjects, enrollments, and assignments."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo runs only when DEBUG is True. It is not for production.")

        with transaction.atomic():
            create_default_groups(sender=None)
            faculty = self._user(
                username="faculty.demo",
                email="faculty.demo@acadtrack.local",
                first_name="Meera",
                last_name="Iyer",
                group_name=FACULTY_GROUP,
            )
            aarav = self._student("student.demo", "aarav.shah@acadtrack.local", "Aarav", "Shah", "AT2026001")
            priya = self._student("student.priya", "priya.nair@acadtrack.local", "Priya", "Nair", "AT2026002")
            rohan = self._student("student.rohan", "rohan.das@acadtrack.local", "Rohan", "Das", "AT2026003")

            databases = self._subject(
                faculty,
                "CS301",
                "Database Systems",
                "Relational design, normalization, and SQL for the current semester.",
            )
            software = self._subject(
                faculty,
                "CS302",
                "Software Engineering",
                "Requirements, design, and delivery of maintainable software.",
            )
            for student in (aarav, priya, rohan):
                self._enroll(student, databases)
                self._enroll(student, software)

            now = timezone.now()
            schema = self._assignment(
                faculty,
                databases,
                "Relational Schema Design",
                "Design a normalized schema for a library circulation system.",
                "Submit a short explanation and, if useful, a SQL or text attachment.",
                now + timedelta(days=10),
                20,
                Assignment.PublicationStatus.PUBLISHED,
                Assignment.Audience.ALL_ENROLLED,
                allow_late=True,
                allow_resubmission=True,
            )
            indexing = self._assignment(
                faculty,
                databases,
                "Indexing Exercise",
                "Explain which indexes you would add to the circulation schema and why.",
                "This exercise is assigned only to selected students.",
                now + timedelta(days=4),
                10,
                Assignment.PublicationStatus.PUBLISHED,
                Assignment.Audience.SELECTED,
                allow_late=False,
                allow_resubmission=True,
                students=[aarav, priya],
            )
            self._assignment(
                faculty,
                databases,
                "Normalization Worksheet",
                "Identify and remove partial and transitive dependencies.",
                "Late submissions are closed for this worksheet.",
                now - timedelta(days=2),
                15,
                Assignment.PublicationStatus.PUBLISHED,
                Assignment.Audience.ALL_ENROLLED,
                allow_late=False,
                allow_resubmission=False,
            )
            self._assignment(
                faculty,
                software,
                "Sprint Planning Draft",
                "Draft a sprint plan. This assignment is not published.",
                "Faculty notes only.",
                now + timedelta(days=14),
                25,
                Assignment.PublicationStatus.DRAFT,
                Assignment.Audience.ALL_ENROLLED,
                allow_late=False,
                allow_resubmission=True,
            )
            if not schema.submissions.filter(student=rohan).exists():
                create_attempt(
                    student=rohan,
                    assignment=schema,
                    submitted_text="Demo submission: users, books, loans, and fines in 3NF.",
                    uploaded_file=None,
                )

        self.stdout.write(self.style.SUCCESS("Demonstration data is ready."))
        self.stdout.write("These accounts are for local demonstration only.")
        self.stdout.write(f"Password for every demonstration account: {DEMO_PASSWORD}")
        self.stdout.write("Faculty: faculty.demo")
        self.stdout.write("Students: student.demo, student.priya, student.rohan")
        self.stdout.write("Rohan Das has a sample submission on Relational Schema Design.")
        self.stdout.write("Indexing Exercise is hidden from student.rohan.")
        self.stdout.write("Sprint Planning Draft is hidden from every student.")
        self.stdout.write(f"Subjects ready: {databases.subject_code} and {software.subject_code}.")
        self.stdout.write(f"Published examples include {schema.title} and {indexing.title}.")

    def _user(self, username, email, first_name, last_name, group_name):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        if created or user.email != email:
            user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.set_password(DEMO_PASSWORD)
        user.save()
        group = Group.objects.get(name=group_name)
        user.groups.add(group)
        return user

    def _student(self, username, email, first_name, last_name, roll_number):
        user = self._user(username, email, first_name, last_name, STUDENT_GROUP)
        StudentProfile.objects.update_or_create(
            user=user,
            defaults={
                "roll_number": roll_number,
                "department": StudentProfile.Department.CSE,
                "semester": 5,
            },
        )
        return user

    def _subject(self, faculty, code, name, description):
        subject, _created = Subject.objects.get_or_create(
            subject_code=code,
            defaults={"subject_name": name, "description": description},
        )
        subject.subject_name = name
        subject.description = description
        subject.save()
        subject.faculty.add(faculty)
        return subject

    def _enroll(self, student, subject):
        enrollment, _created = Enrollment.objects.get_or_create(
            student=student,
            subject=subject,
            defaults={"is_active": True},
        )
        if not enrollment.is_active:
            enrollment.is_active = True
            enrollment.save(update_fields=["is_active"])
        return enrollment

    def _assignment(
        self,
        faculty,
        subject,
        title,
        description,
        instructions,
        deadline,
        max_marks,
        status,
        audience,
        allow_late,
        allow_resubmission,
        students=None,
    ):
        assignment, _created = Assignment.objects.get_or_create(
            subject=subject,
            title=title,
            defaults={
                "description": description,
                "instructions": instructions,
                "created_by": faculty,
                "audience": audience,
                "deadline": deadline,
                "max_marks": max_marks,
                "allow_late_submission": allow_late,
                "allow_resubmission": allow_resubmission,
                "publication_status": status,
                "published_at": timezone.now() if status == Assignment.PublicationStatus.PUBLISHED else None,
            },
        )
        if students:
            assignment.audience = Assignment.Audience.SELECTED
            assignment.save(update_fields=["audience"])
            assignment.assigned_students.set(students)
        return assignment
