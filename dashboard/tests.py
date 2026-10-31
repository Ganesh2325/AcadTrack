from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.testing import enroll, make_faculty, make_student, make_subject
from assignments.models import Assignment
from submissions.models import Evaluation
from submissions.services import create_attempt, record_evaluation


class DashboardQueryTests(TestCase):
    def setUp(self):
        self.faculty = make_faculty()
        self.student = make_student()
        self.outsider = make_student(username="student2", roll="AT0002")
        self.subject = make_subject(self.faculty, code="CS301", name="Database Systems")
        self.other_subject = make_subject(self.faculty, code="CS999", name="Not enrolled")
        enroll(self.student, self.subject)
        self.open_assignment = self._assignment("Open work", days=5)
        self.overdue_assignment = self._assignment("Missed work", days=-2)
        self.done_assignment = self._assignment("Finished work", days=4)
        self.draft = self._assignment("Secret draft", days=6, status=Assignment.PublicationStatus.DRAFT)
        self.selected = self._assignment(
            "Someone else",
            days=3,
            audience=Assignment.Audience.SELECTED,
        )
        self.selected.assigned_students.add(self.outsider)
        self.ineligible = self._assignment("Other subject", days=3, subject=self.other_subject)
        attempt = create_attempt(
            student=self.student,
            assignment=self.done_assignment,
            submitted_text="Done",
            uploaded_file=None,
        )
        record_evaluation(
            attempt=attempt,
            reviewer=self.faculty,
            marks=15,
            comments="Accepted",
            decision=Evaluation.Decision.ACCEPT,
        )

    def _assignment(self, title, days, status=Assignment.PublicationStatus.PUBLISHED, audience=Assignment.Audience.ALL_ENROLLED, subject=None):
        return Assignment.objects.create(
            title=title,
            description=title,
            instructions="",
            subject=subject or self.subject,
            created_by=self.faculty,
            audience=audience,
            deadline=timezone.now() + timedelta(days=days),
            max_marks=20,
            allow_late_submission=True,
            allow_resubmission=True,
            publication_status=status,
            published_at=timezone.now() if status == Assignment.PublicationStatus.PUBLISHED else None,
        )

    def test_student_counts_ignore_ineligible_and_draft_work(self):
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.get(reverse("dashboard:student"))
        self.assertEqual(response.context["stats"]["total"], 3)
        self.assertEqual(response.context["stats"]["completed"], 1)
        self.assertEqual(response.context["stats"]["pending"], 1)
        self.assertEqual(response.context["stats"]["overdue"], 1)
        self.assertEqual(response.context["stats"]["completion_percent"], 33.3)
        self.assertContains(response, "Open work")
        self.assertNotContains(response, "Secret draft")
        self.assertNotContains(response, "Someone else")
        self.assertNotContains(response, "Other subject")
        progress = self.client.get(reverse("dashboard:student_progress"))
        self.assertContains(progress, "Missed work")
        self.assertContains(progress, "Finished work")

    def test_faculty_counts_match_created_work(self):
        self.client.login(username="faculty1", password="ValidPass@123")
        response = self.client.get(reverse("dashboard:faculty"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending evaluations")
        self.assertContains(response, "CS301")
