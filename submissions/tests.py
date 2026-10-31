import tempfile
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from acadtrack.uploads import SUBMISSION_EXTENSIONS, validate_uploaded_file
from accounts.testing import enroll, make_faculty, make_student, make_subject
from assignments.models import Assignment
from submissions.models import Evaluation, Submission, SubmissionAttempt
from submissions.services import create_attempt, record_evaluation

MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SubmissionLifecycleTests(TestCase):
    def setUp(self):
        self.faculty = make_faculty()
        self.other_faculty = make_faculty(username="faculty2")
        self.student = make_student()
        self.other_student = make_student(username="student2", roll="AT0002")
        self.subject = make_subject(self.faculty)
        enroll(self.student, self.subject)
        enroll(self.other_student, self.subject)
        self.assignment = Assignment.objects.create(
            title="Essay",
            description="Write the essay.",
            instructions="Stay under the limit.",
            subject=self.subject,
            created_by=self.faculty,
            audience=Assignment.Audience.ALL_ENROLLED,
            deadline=timezone.now() + timedelta(days=3),
            max_marks=20,
            allow_late_submission=False,
            allow_resubmission=True,
            publication_status=Assignment.PublicationStatus.PUBLISHED,
            published_at=timezone.now(),
        )

    def test_valid_submission_is_stored_and_history_shows_it(self):
        self.client.login(username="student1", password="ValidPass@123")
        upload = SimpleUploadedFile("notes.txt", b"print('hello')")
        response = self.client.post(
            reverse("submissions:submit", args=[self.assignment.pk]),
            {"submitted_text": "My answer", "submitted_file": upload},
        )
        self.assertRedirects(response, reverse("assignments:student_detail", args=[self.assignment.pk]))
        submission = Submission.objects.get(student=self.student, assignment=self.assignment)
        self.assertEqual(submission.status, Submission.Status.SUBMITTED)
        self.assertEqual(submission.attempts.count(), 1)
        self.assertFalse(submission.attempts.get().is_late)
        history = self.client.get(reverse("submissions:history"))
        self.assertContains(history, "Essay")

    def test_empty_submission_shows_errors(self):
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.post(reverse("submissions:submit", args=[self.assignment.pk]), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Provide submission text")
        self.assertFalse(Submission.objects.exists())

    def test_invalid_extension_is_rejected(self):
        self.client.login(username="student1", password="ValidPass@123")
        upload = SimpleUploadedFile("notes.exe", b"nope")
        response = self.client.post(
            reverse("submissions:submit", args=[self.assignment.pk]),
            {"submitted_file": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported file type")
        self.assertFalse(Submission.objects.exists())

    def test_duplicate_submission_record_is_prevented(self):
        Submission.objects.create(student=self.student, assignment=self.assignment, status=Submission.Status.SUBMITTED)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Submission.objects.create(student=self.student, assignment=self.assignment)

    def test_second_attempt_is_blocked_until_revision_and_then_preserved(self):
        create_attempt(
            student=self.student,
            assignment=self.assignment,
            submitted_text="First draft",
            uploaded_file=None,
        )
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.post(
            reverse("submissions:submit", args=[self.assignment.pk]),
            {"submitted_text": "Should not replace the first attempt"},
        )
        self.assertEqual(response.status_code, 200)
        submission = Submission.objects.get(student=self.student, assignment=self.assignment)
        self.assertEqual(submission.attempts.count(), 1)
        record_evaluation(
            attempt=submission.attempts.get(),
            reviewer=self.faculty,
            marks=8,
            comments="Fix diagrams",
            decision=Evaluation.Decision.REVISION,
        )
        response = self.client.post(
            reverse("submissions:submit", args=[self.assignment.pk]),
            {"submitted_text": "Corrected draft"},
        )
        self.assertRedirects(response, reverse("assignments:student_detail", args=[self.assignment.pk]))
        submission.refresh_from_db()
        self.assertEqual(submission.attempts.count(), 2)
        self.assertEqual(submission.current_attempt_number, 2)
        self.assertEqual(submission.status, Submission.Status.SUBMITTED)
        first = submission.attempts.get(attempt_number=1)
        self.assertEqual(first.evaluation.comments, "Fix diagrams")
        self.assertEqual(first.evaluation.marks_obtained, 8)

    def test_late_submission_rules(self):
        self.assignment.deadline = timezone.now() - timedelta(days=1)
        self.assignment.save(update_fields=["deadline"])
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.post(
            reverse("submissions:submit", args=[self.assignment.pk]),
            {"submitted_text": "Too late"},
        )
        self.assertContains(response, "late submissions are not allowed")
        self.assertFalse(Submission.objects.exists())
        self.assignment.allow_late_submission = True
        self.assignment.save(update_fields=["allow_late_submission"])
        response = self.client.post(
            reverse("submissions:submit", args=[self.assignment.pk]),
            {"submitted_text": "Late but allowed"},
        )
        self.assertEqual(response.status_code, 302)
        attempt = SubmissionAttempt.objects.get()
        self.assertTrue(attempt.is_late)
        detail = self.client.get(reverse("assignments:student_detail", args=[self.assignment.pk]))
        self.assertContains(detail, "Submitted")
        self.assertNotContains(detail, "Not Submitted")

    def test_resubmission_disabled_rejects_revision_decision(self):
        self.assignment.allow_resubmission = False
        self.assignment.save(update_fields=["allow_resubmission"])
        attempt = create_attempt(
            student=self.student,
            assignment=self.assignment,
            submitted_text="Only attempt",
            uploaded_file=None,
        )
        with self.assertRaises(ValidationError):
            record_evaluation(
                attempt=attempt,
                reviewer=self.faculty,
                marks=10,
                comments="Redo",
                decision=Evaluation.Decision.REVISION,
            )

    def test_student_cannot_view_another_students_submission_or_file(self):
        attempt = create_attempt(
            student=self.student,
            assignment=self.assignment,
            submitted_text="Private",
            uploaded_file=SimpleUploadedFile("answer.txt", b"secret"),
        )
        submission = attempt.submission
        self.client.login(username="student2", password="ValidPass@123")
        response = self.client.get(reverse("submissions:detail", args=[submission.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse("submissions:download_attempt", args=[attempt.pk]))
        self.assertEqual(response.status_code, 403)
        self.client.logout()
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.get(reverse("submissions:download_attempt", args=[attempt.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"secret", b"".join(response.streaming_content))

    def test_csrf_is_required_for_submission(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse("accounts:login")
        client.get(login_url)
        token = client.cookies["csrftoken"].value
        client.post(
            login_url,
            {
                "username": "student1",
                "password": "ValidPass@123",
                "csrfmiddlewaretoken": token,
            },
        )
        response = client.post(
            reverse("submissions:submit", args=[self.assignment.pk]),
            {"submitted_text": "missing token"},
        )
        self.assertEqual(response.status_code, 403)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class EvaluationTests(TestCase):
    def setUp(self):
        self.faculty = make_faculty()
        self.other_faculty = make_faculty(username="faculty2")
        self.student = make_student()
        self.subject = make_subject(self.faculty)
        enroll(self.student, self.subject)
        self.assignment = Assignment.objects.create(
            title="Marked work",
            description="Submit notes.",
            instructions="",
            subject=self.subject,
            created_by=self.faculty,
            audience=Assignment.Audience.ALL_ENROLLED,
            deadline=timezone.now() + timedelta(days=2),
            max_marks=20,
            allow_resubmission=True,
            publication_status=Assignment.PublicationStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        self.attempt = create_attempt(
            student=self.student,
            assignment=self.assignment,
            submitted_text="Answer",
            uploaded_file=None,
        )

    def test_authorized_faculty_can_evaluate_and_student_sees_feedback(self):
        self.client.login(username="faculty1", password="ValidPass@123")
        response = self.client.post(
            reverse("submissions:start_review", args=[self.attempt.submission.pk])
        )
        self.assertRedirects(response, reverse("submissions:evaluate", args=[self.attempt.submission.pk]))
        self.attempt.submission.refresh_from_db()
        self.assertEqual(self.attempt.submission.status, Submission.Status.UNDER_REVIEW)
        response = self.client.post(
            reverse("submissions:evaluate", args=[self.attempt.submission.pk]),
            {"marks_obtained": "18", "comments": "Clear structure", "decision": Evaluation.Decision.ACCEPT},
        )
        self.assertRedirects(response, reverse("submissions:evaluate", args=[self.attempt.submission.pk]))
        self.client.logout()
        self.client.login(username="student1", password="ValidPass@123")
        detail = self.client.get(reverse("assignments:student_detail", args=[self.assignment.pk]))
        self.assertContains(detail, "Clear structure")
        self.assertContains(detail, "18")

    def test_marks_cannot_exceed_the_maximum(self):
        self.client.login(username="faculty1", password="ValidPass@123")
        response = self.client.post(
            reverse("submissions:evaluate", args=[self.attempt.submission.pk]),
            {"marks_obtained": "21", "comments": "Too high", "decision": Evaluation.Decision.ACCEPT},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot exceed")
        self.assertFalse(Evaluation.objects.exists())
        response = self.client.post(
            reverse("submissions:evaluate", args=[self.attempt.submission.pk]),
            {"marks_obtained": "-1", "comments": "Negative", "decision": Evaluation.Decision.ACCEPT},
        )
        self.assertContains(response, "negative")

    def test_other_faculty_cannot_evaluate(self):
        self.client.login(username="faculty2", password="ValidPass@123")
        response = self.client.get(reverse("submissions:evaluate", args=[self.attempt.submission.pk]))
        self.assertEqual(response.status_code, 403)

    def test_previous_attempt_evaluation_remains_after_resubmission(self):
        record_evaluation(
            attempt=self.attempt,
            reviewer=self.faculty,
            marks=8,
            comments="Fix diagrams",
            decision=Evaluation.Decision.REVISION,
        )
        second = create_attempt(
            student=self.student,
            assignment=self.assignment,
            submitted_text="Revised",
            uploaded_file=None,
        )
        record_evaluation(
            attempt=second,
            reviewer=self.faculty,
            marks=18,
            comments="Good",
            decision=Evaluation.Decision.ACCEPT,
        )
        first_evaluation = Evaluation.objects.get(submission_attempt=self.attempt)
        self.assertEqual(first_evaluation.comments, "Fix diagrams")
        self.assertEqual(first_evaluation.marks_obtained, 8)
        self.assertEqual(second.evaluation.comments, "Good")
        self.assertEqual(second.submission.status, Submission.Status.COMPLETED)

    def test_upload_validator_rejects_oversized_files(self):
        class FakeFile:
            name = "notes.pdf"
            size = 5 * 1024 * 1024 + 1

        with self.assertRaises(ValidationError):
            validate_uploaded_file(FakeFile(), SUBMISSION_EXTENSIONS)
