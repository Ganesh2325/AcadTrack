from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.roles import FACULTY_GROUP, STUDENT_GROUP
from accounts.testing import make_faculty, make_student

User = get_user_model()


class RegistrationTests(TestCase):
    def test_student_registration_creates_student_group_only(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Aarav Shah",
                "username": "Aarav.Shah",
                "email": "Aarav@Example.com",
                "roll_number": "at2026-01",
                "department": "CSE",
                "semester": 5,
                "password1": "ValidPass@123",
                "password2": "ValidPass@123",
            },
        )
        self.assertRedirects(response, reverse("dashboard:student"))
        user = User.objects.get(username="aarav.shah")
        self.assertEqual(user.email, "aarav@example.com")
        self.assertEqual(user.first_name, "Aarav")
        self.assertEqual(user.last_name, "Shah")
        self.assertTrue(user.groups.filter(name=STUDENT_GROUP).exists())
        self.assertFalse(user.groups.filter(name=FACULTY_GROUP).exists())
        self.assertFalse(user.is_staff)
        self.assertEqual(user.student_profile.roll_number, "AT2026-01")
        self.assertIn("display_name", self.client.session)
        self.assertEqual(self.client.session["active_role"], "Student")

    def test_invalid_registration_is_rejected(self):
        make_student(username="existing", roll="AT1001")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Onlyone",
                "username": "existing",
                "email": "existing@acadtrack.test",
                "roll_number": "AT1001",
                "department": "CSE",
                "semester": 9,
                "password1": "ValidPass@123",
                "password2": "different-pass",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already taken")
        self.assertEqual(User.objects.filter(username="existing").count(), 1)

    def test_registration_rejects_duplicate_email(self):
        make_student(username="existing", roll="AT1001")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "New Student",
                "username": "newstudent",
                "email": "existing@acadtrack.test",
                "roll_number": "AT1002",
                "department": "IT",
                "semester": 3,
                "password1": "ValidPass@123",
                "password2": "ValidPass@123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "email already exists")
        self.assertFalse(User.objects.filter(username="newstudent").exists())


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.student = make_student(username="student1", roll="AT2001")
        self.faculty = make_faculty(username="faculty1")

    def test_login_with_email_and_bad_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "student1@acadtrack.test", "password": "ValidPass@123"},
        )
        self.assertRedirects(response, reverse("dashboard:student"))
        self.client.post(reverse("accounts:logout"))
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "student1", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username/email or password")

    def test_faculty_login_redirects_to_faculty_dashboard(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "faculty1", "password": "ValidPass@123"},
        )
        self.assertRedirects(response, reverse("dashboard:faculty"))
        self.assertEqual(self.client.session["active_role"], "Faculty")

    def test_logout_ends_authenticated_access(self):
        self.client.login(username="student1", password="ValidPass@123")
        self.assertEqual(self.client.get(reverse("dashboard:student")).status_code, 200)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("landing"))
        response = self.client.get(reverse("dashboard:student"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('dashboard:student')}")
        self.assertNotIn("display_name", self.client.session)

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(reverse("dashboard:faculty"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('dashboard:faculty')}")


class PermissionAndCookieTests(TestCase):
    def setUp(self):
        self.student = make_student()
        self.faculty = make_faculty()

    def test_student_cannot_open_faculty_pages(self):
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.get(reverse("dashboard:faculty"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "do not have access", status_code=403)
        response = self.client.get(reverse("assignments:create"))
        self.assertEqual(response.status_code, 403)

    def test_faculty_cannot_open_student_dashboard(self):
        self.client.login(username="faculty1", password="ValidPass@123")
        response = self.client.get(reverse("dashboard:student"))
        self.assertEqual(response.status_code, 403)

    def test_profile_cannot_change_role(self):
        self.client.login(username="student1", password="ValidPass@123")
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Student",
                "last_name": "Member",
                "email": "student1@acadtrack.test",
                "department": "IT",
                "semester": 6,
                "is_staff": "1",
                "is_superuser": "1",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.student.refresh_from_db()
        self.student.student_profile.refresh_from_db()
        self.assertFalse(self.student.is_staff)
        self.assertFalse(self.student.is_superuser)
        self.assertEqual(self.student.student_profile.department, "IT")
        self.assertEqual(self.student.student_profile.semester, 6)
        self.assertEqual(self.student.student_profile.roll_number, "AT0001")
        self.assertTrue(self.student.groups.filter(name=STUDENT_GROUP).exists())
        self.assertFalse(self.student.groups.filter(name=FACULTY_GROUP).exists())

    def test_theme_cookie_is_set_and_read(self):
        response = self.client.post(
            reverse("accounts:set_theme"),
            {"theme": "dark", "next": "/"},
        )
        self.assertEqual(response.cookies["acadtrack_theme"].value, "dark")
        self.assertGreater(int(response.cookies["acadtrack_theme"]["max-age"]), 0)
        self.assertEqual(response.cookies["acadtrack_theme"]["httponly"], True)
        follow = self.client.get(reverse("landing"))
        self.assertContains(follow, 'data-theme="dark"')

    def test_csrf_protection_stays_enabled(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("accounts:login"),
            {"username": "student1", "password": "ValidPass@123"},
        )
        self.assertEqual(response.status_code, 403)
