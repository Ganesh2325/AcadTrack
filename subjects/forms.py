from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from acadtrack.form_utils import BootstrapFormMixin
from accounts.roles import FACULTY_GROUP, STUDENT_GROUP
from subjects.models import Enrollment, Subject

User = get_user_model()


class StudentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        profile = getattr(obj, "student_profile", None)
        roll = profile.roll_number if profile else "no roll number"
        name = obj.get_full_name() or obj.username
        return f"{name} ({roll})"


class SubjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = ("subject_name", "subject_code", "description", "faculty")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "faculty": forms.SelectMultiple(attrs={"size": 6}),
        }

    def __init__(self, *args, faculty_user, **kwargs):
        self.faculty_user = faculty_user
        super().__init__(*args, **kwargs)
        self.fields["faculty"].queryset = User.objects.filter(
            groups__name=FACULTY_GROUP
        ).order_by("first_name", "username")
        self.fields["faculty"].help_text = "At least one faculty member must remain responsible for the subject."
        self.fields["subject_code"].help_text = "A short unique code, for example CS301."
        if not self.instance.pk:
            self.fields["faculty"].initial = [faculty_user.pk]

    def clean_subject_code(self):
        code = self.cleaned_data["subject_code"].strip().upper()
        existing = Subject.objects.filter(subject_code__iexact=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("A subject with this code already exists.")
        return code

    def clean_faculty(self):
        faculty = self.cleaned_data["faculty"]
        if not faculty:
            raise forms.ValidationError("Assign at least one faculty member.")
        return faculty


class EnrollmentForm(BootstrapFormMixin, forms.Form):
    student = StudentChoiceField(queryset=User.objects.none(), label="Student")

    def __init__(self, *args, subject, **kwargs):
        self.subject = subject
        super().__init__(*args, **kwargs)
        active_ids = Enrollment.objects.filter(subject=subject, is_active=True).values("student_id")
        self.fields["student"].queryset = (
            User.objects.filter(groups__name=STUDENT_GROUP)
            .exclude(pk__in=active_ids)
            .select_related("student_profile")
            .order_by("first_name", "username")
        )
        self.fields["student"].help_text = "A student can be enrolled in a subject only once."

    def clean_student(self):
        student = self.cleaned_data["student"]
        if not Group.objects.filter(name=STUDENT_GROUP, user=student).exists():
            raise forms.ValidationError("Only student accounts can be enrolled.")
        if Enrollment.objects.filter(student=student, subject=self.subject, is_active=True).exists():
            raise forms.ValidationError("This student is already enrolled in the subject.")
        return student
