from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Max
from django.utils import timezone

from acadtrack.form_utils import BootstrapFormMixin
from acadtrack.uploads import REFERENCE_EXTENSIONS, validate_uploaded_file
from accounts.roles import STUDENT_GROUP
from assignments.models import Assignment
from assignments.queries import OVERDUE, NOT_SUBMITTED, STATUS_LABELS
from subjects.models import Enrollment, Subject

User = get_user_model()


class AssignmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Assignment
        fields = (
            "title",
            "description",
            "instructions",
            "subject",
            "audience",
            "assigned_students",
            "deadline",
            "max_marks",
            "attachment",
            "allow_late_submission",
            "allow_resubmission",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
            "deadline": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "assigned_students": forms.SelectMultiple(attrs={"size": 8}),
        }
        labels = {
            "max_marks": "Maximum marks",
            "allow_late_submission": "Allow late submission",
            "allow_resubmission": "Allow resubmission after a revision request",
            "audience": "Who should receive this assignment?",
        }

    def __init__(self, *args, faculty, publishing=False, **kwargs):
        self.faculty = faculty
        self.publishing = publishing
        super().__init__(*args, **kwargs)
        if faculty.is_superuser:
            subjects = Subject.objects.all()
        else:
            subjects = Subject.objects.filter(faculty=faculty)
        self.fields["subject"].queryset = subjects.order_by("subject_code")
        self.fields["assigned_students"].queryset = (
            User.objects.filter(
                groups__name=STUDENT_GROUP,
                enrollments__subject__in=subjects,
                enrollments__is_active=True,
            )
            .select_related("student_profile")
            .distinct()
            .order_by("first_name", "username")
        )
        self.fields["assigned_students"].required = False
        self.fields["assigned_students"].help_text = (
            "Used only when the audience is selected students. Each student must be enrolled in the subject."
        )
        self.fields["deadline"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ]
        self.fields["max_marks"].widget.attrs.update({"min": 1})
        if self.instance.pk and self.instance.deadline:
            self.initial["deadline"] = timezone.localtime(self.instance.deadline).strftime(
                "%Y-%m-%dT%H:%M"
            )

    def clean_title(self):
        title = " ".join(self.cleaned_data["title"].split())
        if not title:
            raise forms.ValidationError("Enter a title.")
        return title

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if not description:
            raise forms.ValidationError("Enter a description.")
        return description

    def clean_subject(self):
        subject = self.cleaned_data["subject"]
        if not self.faculty.is_superuser and not subject.faculty.filter(pk=self.faculty.pk).exists():
            raise forms.ValidationError("You can only use subjects assigned to you.")
        if (
            self.instance.pk
            and self.instance.submissions.exists()
            and subject.pk != self.instance.subject_id
        ):
            raise forms.ValidationError("Subject cannot be changed after students have submitted.")
        return subject

    def clean_max_marks(self):
        marks = self.cleaned_data["max_marks"]
        if marks < 1:
            raise forms.ValidationError("Maximum marks must be at least 1.")
        if self.instance.pk:
            from submissions.models import Evaluation

            highest = Evaluation.objects.filter(
                submission_attempt__submission__assignment=self.instance
            ).aggregate(highest=Max("marks_obtained"))["highest"]
            if highest is not None and marks < highest:
                raise forms.ValidationError(
                    "Maximum marks cannot be lower than marks already awarded."
                )
        return marks

    def clean_attachment(self):
        uploaded = self.cleaned_data.get("attachment")
        if not uploaded:
            return uploaded
        validate_uploaded_file(uploaded, REFERENCE_EXTENSIONS)
        return uploaded

    def clean(self):
        cleaned = super().clean()
        subject = cleaned.get("subject")
        audience = cleaned.get("audience")
        students = cleaned.get("assigned_students")
        deadline = cleaned.get("deadline")
        if audience == Assignment.Audience.SELECTED:
            if not students:
                self.add_error("assigned_students", "Select at least one student.")
            elif subject is not None:
                enrolled_ids = set(
                    Enrollment.objects.filter(subject=subject, is_active=True).values_list(
                        "student_id", flat=True
                    )
                )
                invalid = [student for student in students if student.id not in enrolled_ids]
                if invalid:
                    self.add_error(
                        "assigned_students",
                        "Selected students must be actively enrolled in the subject.",
                    )
        if self.publishing and deadline is not None:
            already_published = (
                self.instance.pk
                and self.instance.publication_status == Assignment.PublicationStatus.PUBLISHED
            )
            if not already_published and deadline <= timezone.now():
                self.add_error(
                    "deadline",
                    "Set a future deadline before publishing a new assignment.",
                )
        return cleaned


class StudentAssignmentFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, label="Title")
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        required=False,
        empty_label="All subjects",
    )
    status = forms.ChoiceField(required=False, label="Status")
    sort = forms.ChoiceField(required=False, label="Sort")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        subject_ids = Enrollment.objects.filter(student=user, is_active=True).values("subject_id")
        self.fields["subject"].queryset = Subject.objects.filter(pk__in=subject_ids).order_by(
            "subject_code"
        )
        self.fields["status"].choices = [("", "All statuses")] + [
            (key, STATUS_LABELS[key])
            for key in (
                NOT_SUBMITTED,
                OVERDUE,
                "submitted",
                "under_review",
                "revision_requested",
                "completed",
            )
        ]
        self.fields["sort"].choices = [
            ("deadline", "Deadline (soonest)"),
            ("deadline_desc", "Deadline (latest)"),
            ("newest", "Recently published"),
        ]
        self.fields["q"].widget.attrs["placeholder"] = "Search by title"


class FacultyAssignmentFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, label="Title")
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        required=False,
        empty_label="All subjects",
    )
    publication_status = forms.ChoiceField(required=False, label="Publication")
    sort = forms.ChoiceField(required=False, label="Sort")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        if user.is_superuser:
            subjects = Subject.objects.all()
        else:
            subjects = Subject.objects.filter(faculty=user)
        self.fields["subject"].queryset = subjects.order_by("subject_code")
        self.fields["publication_status"].choices = [("", "All statuses")] + list(
            Assignment.PublicationStatus.choices
        )
        self.fields["sort"].choices = [
            ("newest", "Newest"),
            ("deadline", "Deadline"),
            ("title", "Title"),
        ]
        self.fields["q"].widget.attrs["placeholder"] = "Search by title"
