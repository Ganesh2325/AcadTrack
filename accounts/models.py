from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Project user. Email is unique so login by email is unambiguous."""

    email = models.EmailField(_("email address"), unique=True)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        full_name = self.get_full_name().strip()
        return full_name or self.username


class StudentProfile(models.Model):
    class Department(models.TextChoices):
        CSE = "CSE", "Computer Science and Engineering"
        IT = "IT", "Information Technology"
        ECE = "ECE", "Electronics and Communication"
        EE = "EE", "Electrical Engineering"
        ME = "ME", "Mechanical Engineering"
        CE = "CE", "Civil Engineering"
        OTHER = "OTHER", "Other"

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    roll_number = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=20, choices=Department.choices)
    semester = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(8)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["roll_number"]
        indexes = [
            models.Index(fields=["department", "semester"]),
        ]

    def __str__(self):
        return f"{self.roll_number} — {self.user}"

    def save(self, *args, **kwargs):
        self.roll_number = (self.roll_number or "").strip().upper()
        super().save(*args, **kwargs)
