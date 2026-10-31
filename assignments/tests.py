from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.testing import enroll, make_faculty, make_student, make_subject
from assignments.models import Assignment
from assignments.queries import assignments_visible_to_student


class AssignmentAccessTests(TestCase):
    def setUp(self):
        self.faculty = make_faculty()
        self.other = make_faculty(username="faculty2")
        self.student = make_student()
        self.other_student = make_student(username="student2", roll="AT0002")
        self.subject = make_subject(self.faculty)
        enroll(self.student, self.subject)
        enroll(self.other_student, self.subject)

    def _deadline(self, days=4):
        return timezone.localtime(timezone.now() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")

    def test_faculty_can_publish_and_student_can_see_it(self):
        self.client.login(username="faculty1", password="ValidPass@123")
        response = self.client.post(
            reverse("assignments:create"),
            {
                "title": "Schema Lab",
                "description": "Draw the schema.",
                "instructions": "Include keys.",
                "subject": self.subject.pk,
                "audience": Assignment.Audience.ALL_ENROLLED,
                "deadline": self._deadline(),
                "max_marks": 20,
                "allow_resubmission": "on",
                "action": "publish",
            },
        )
        assignment = Assignment.objects.get(title="Schema Lab")
        self.assertEqual(assignment.publication_status, Assignment.PublicationStatus.PUBLISHED)
        self.assertEqual(assignment.created_by, self.faculty)
        self.assertRedirects(response, reverse("submissions:faculty_list", args=[assignment.pk]))
        self.client.logout()
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.get(reverse("assignments:student_list"))
        self.assertContains(response, "Schema Lab")
        detail = self.client.get(reverse("assignments:student_detail", args=[assignment.pk]))
        self.assertEqual(detail.status_code, 200)

    def test_drafts_are_hidden_and_new_publish_rejects_a_past_deadline(self):
        self.client.login(username="faculty1", password="ValidPass@123")
        self.client.post(
            reverse("assignments:create"),
            {
                "title": "Hidden Draft",
                "description": "Not ready.",
                "instructions": "",
                "subject": self.subject.pk,
                "audience": Assignment.Audience.ALL_ENROLLED,
                "deadline": self._deadline(),
                "max_marks": 10,
                "action": "save",
            },
        )
        draft = Assignment.objects.get(title="Hidden Draft")
        self.assertEqual(draft.publication_status, Assignment.PublicationStatus.DRAFT)
        self.client.logout()
        self.client.login(username="student1", password="ValidPass@123")
        self.assertFalse(assignments_visible_to_student(self.student).filter(pk=draft.pk).exists())
        response = self.client.get(reverse("assignments:student_detail", args=[draft.pk]))
        self.assertEqual(response.status_code, 403)
        self.client.logout()
        self.client.login(username="faculty1", password="ValidPass@123")
        response = self.client.post(
            reverse("assignments:create"),
            {
                "title": "Already Due",
                "description": "Too late to publish.",
                "instructions": "",
                "subject": self.subject.pk,
                "audience": Assignment.Audience.ALL_ENROLLED,
                "deadline": self._deadline(-2),
                "max_marks": 10,
                "action": "publish",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "future deadline")
        self.assertFalse(Assignment.objects.filter(title="Already Due").exists())

    def test_selected_students_are_the_only_audience(self):
        self.client.login(username="faculty1", password="ValidPass@123")
        self.client.post(
            reverse("assignments:create"),
            {
                "title": "Selected Lab",
                "description": "Only one student.",
                "instructions": "",
                "subject": self.subject.pk,
                "audience": Assignment.Audience.SELECTED,
                "assigned_students": [self.student.pk],
                "deadline": self._deadline(),
                "max_marks": 5,
                "action": "publish",
            },
        )
        assignment = Assignment.objects.get(title="Selected Lab")
        self.client.logout()
        self.client.login(username="student1", password="ValidPass@123")
        self.assertEqual(self.client.get(reverse("assignments:student_detail", args=[assignment.pk])).status_code, 200)
        self.client.logout()
        self.client.login(username="student2", password="ValidPass@123")
        self.assertEqual(self.client.get(reverse("assignments:student_detail", args=[assignment.pk])).status_code, 403)
        self.assertFalse(assignments_visible_to_student(self.other_student).filter(pk=assignment.pk).exists())

    def test_other_faculty_cannot_edit_or_open_submissions(self):
        assignment = Assignment.objects.create(
            title="Owned",
            description="Owned work",
            instructions="",
            subject=self.subject,
            created_by=self.faculty,
            audience=Assignment.Audience.ALL_ENROLLED,
            deadline=timezone.now() + timedelta(days=2),
            max_marks=10,
            publication_status=Assignment.PublicationStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        self.client.login(username="faculty2", password="ValidPass@123")
        self.assertEqual(self.client.get(reverse("assignments:edit", args=[assignment.pk])).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("submissions:faculty_list", args=[assignment.pk])).status_code,
            403,
        )

    def test_archive_year_route_uses_four_digits(self):
        Assignment.objects.create(
            title="This Year",
            description="Created now",
            instructions="",
            subject=self.subject,
            created_by=self.faculty,
            audience=Assignment.Audience.ALL_ENROLLED,
            deadline=timezone.now() + timedelta(days=2),
            max_marks=10,
            publication_status=Assignment.PublicationStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        self.client.login(username="faculty1", password="ValidPass@123")
        year = timezone.localtime().year
        response = self.client.get(reverse("assignments:archive_year", kwargs={"year": year}))
        self.assertContains(response, "This Year")
        response = self.client.get(
            reverse("assignments:archive_jump"),
            {"year": str(year)},
        )
        self.assertRedirects(response, reverse("assignments:archive_year", kwargs={"year": str(year)}))
