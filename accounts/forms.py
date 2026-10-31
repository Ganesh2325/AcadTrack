import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction

from acadtrack.form_utils import BootstrapFormMixin
from accounts.models import StudentProfile
from accounts.roles import STUDENT_GROUP

User = get_user_model()


class AcadTrackAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Invalid username/email or password.",
        "inactive": "This account is inactive. Contact an administrator.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username or email"
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["username"].widget.attrs["placeholder"] = "username or email"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"
        self.apply_bootstrap()


class StudentRegistrationForm(BootstrapFormMixin, UserCreationForm):
    full_name = forms.CharField(
        max_length=150,
        label="Full name",
        help_text="Enter your first and last name.",
    )
    email = forms.EmailField(label="Email address")
    roll_number = forms.CharField(max_length=20, label="Roll number")
    department = forms.ChoiceField(choices=StudentProfile.Department.choices)
    semester = forms.IntegerField(min_value=1, max_value=8)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    field_order = [
        "full_name",
        "username",
        "email",
        "roll_number",
        "department",
        "semester",
        "password1",
        "password2",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Letters, digits, and @/./+/-/_ only. Stored in lowercase."
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
        self.apply_bootstrap()

    def clean_full_name(self):
        full_name = " ".join(self.cleaned_data["full_name"].split())
        if " " not in full_name:
            raise forms.ValidationError("Enter both a first name and a last name.")
        return full_name

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_roll_number(self):
        roll_number = self.cleaned_data["roll_number"].strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9/-]{3,19}", roll_number):
            raise forms.ValidationError(
                "Use 4–20 letters, numbers, or hyphens, starting with a letter or number."
            )
        if StudentProfile.objects.filter(roll_number__iexact=roll_number).exists():
            raise forms.ValidationError("This roll number is already registered.")
        return roll_number

    def save(self, commit=True):
        user = super().save(commit=False)
        first_name, *rest = self.cleaned_data["full_name"].split(" ")
        user.first_name = first_name
        user.last_name = " ".join(rest)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["username"]
        if commit:
            with transaction.atomic():
                user.save()
                StudentProfile.objects.create(
                    user=user,
                    roll_number=self.cleaned_data["roll_number"],
                    department=self.cleaned_data["department"],
                    semester=self.cleaned_data["semester"],
                )
                group, _created = Group.objects.get_or_create(name=STUDENT_GROUP)
                user.groups.add(group)
        return user


class AccountProfileForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.fields["email"].initial = user.email

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("That email is already in use.")
        return email

    def save(self):
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        self.user.email = self.cleaned_data["email"]
        self.user.save(update_fields=["first_name", "last_name", "email"])
        return self.user


class ProfileUpdateForm(BootstrapFormMixin, forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = StudentProfile
        fields = ("department", "semester")

    field_order = ["first_name", "last_name", "email", "department", "semester"]

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.fields["email"].initial = user.email
        self.fields["department"].help_text = "You can update your department. Roll number and role stay with the institution."
        self.fields["semester"].help_text = "Semester must be between 1 and 8."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("That email is already in use.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        self.user.email = self.cleaned_data["email"]
        if commit:
            with transaction.atomic():
                self.user.save(update_fields=["first_name", "last_name", "email"])
                profile.save()
        return profile
