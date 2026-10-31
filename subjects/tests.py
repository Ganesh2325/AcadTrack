from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.testing import enroll, make_faculty, make_student, make_subject
from subjects.models import Enrollment


class SubjectEnrollmentTests(TestCase):
    def setUp(self):
        self.faculty = make_faculty()
        self.other = make_faculty(username="faculty2")
        self.student = make_student()
        self.subject = make_subject(self.faculty)

    def test_duplicate_enrollment_is_rejected_by_the_database(self):
        enroll(self.student, self.subject)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrollment.objects.create(student=self.student, subject=self.subject)

    def test_faculty_can_enroll_and_student_can_view_subject(self):
        self.client.login(username="faculty1", password="ValidPass@123")
        response = self.client.post(
            reverse("subjects:enroll", args=[self.subject.pk]),
            {"student": self.student.pk},
        )
        self.assertRedirects(response, reverse("subjects:detail", args=[self.subject.pk]))
        self.client.logout()
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.get(reverse("subjects:detail", args=[self.subject.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Database Systems")

    def test_other_faculty_cannot_edit_the_subject(self):
        self.client.login(username="faculty2", password="ValidPass@123")
        response = self.client.get(reverse("subjects:edit", args=[self.subject.pk]))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_create_a_subject(self):
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.get(reverse("subjects:create"))
        self.assertEqual(response.status_code, 403)
