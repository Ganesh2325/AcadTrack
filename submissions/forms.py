from django import forms
from django.db.models import Q

from acadtrack.form_utils import BootstrapFormMixin
from acadtrack.uploads import SUBMISSION_EXTENSIONS, validate_uploaded_file
from assignments.models import Assignment
from submissions.models import Evaluation, Submission


class AssignmentSubmissionForm(BootstrapFormMixin, forms.Form):
    submitted_text = forms.CharField(
        required=False,
        label="Submission text",
        widget=forms.Textarea(attrs={"rows": 8}),
        help_text="Write your answer here, attach a file, or do both.",
    )
    submitted_file = forms.FileField(
        required=False,
        label="Attachment",
        help_text="PDF, DOC, DOCX, TXT, ZIP, JAVA, PY, HTML, CSS, or JS. Maximum 5 MB.",
    )

    def clean_submitted_text(self):
        return (self.cleaned_data.get("submitted_text") or "").strip()

    def clean_submitted_file(self):
        uploaded = self.cleaned_data.get("submitted_file")
        if not uploaded:
            return None
        validate_uploaded_file(uploaded, SUBMISSION_EXTENSIONS)
        return uploaded

    def clean(self):
        cleaned = super().clean()
        text = cleaned.get("submitted_text")
        uploaded = cleaned.get("submitted_file")
        if not text and not uploaded:
            raise forms.ValidationError("Provide submission text or upload a file.")
        if text and len(text) > 20000:
            self.add_error("submitted_text", "Submission text must be 20,000 characters or fewer.")
        return cleaned


class EvaluationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ("marks_obtained", "comments", "decision")
        widgets = {
            "comments": forms.Textarea(attrs={"rows": 5}),
            "marks_obtained": forms.NumberInput(attrs={"min": 0, "step": "0.5"}),
        }
        labels = {
            "marks_obtained": "Marks obtained",
            "decision": "Decision",
        }

    def __init__(self, *args, assignment, **kwargs):
        self.assignment = assignment
        super().__init__(*args, **kwargs)
        self.fields["marks_obtained"].widget.attrs["max"] = assignment.max_marks
        self.fields["comments"].required = False
        if not assignment.allow_resubmission:
            self.fields["decision"].choices = [
                choice
                for choice in Evaluation.Decision.choices
                if choice[0] != Evaluation.Decision.REVISION
            ]
            self.fields["decision"].help_text = "This assignment does not allow a revision request."
        else:
            self.fields["decision"].help_text = (
                "Accept the work, or request a revision. The previous attempt stays on record."
            )

    def clean_marks_obtained(self):
        marks = self.cleaned_data["marks_obtained"]
        if marks < 0:
            raise forms.ValidationError("Marks cannot be negative.")
        if marks > self.assignment.max_marks:
            raise forms.ValidationError(
                f"Marks cannot exceed the maximum of {self.assignment.max_marks}."
            )
        return marks

    def clean(self):
        cleaned = super().clean()
        decision = cleaned.get("decision")
        if decision == Evaluation.Decision.REVISION and not self.assignment.allow_resubmission:
            self.add_error("decision", "This assignment does not permit resubmission.")
        return cleaned


class SubmissionFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, label="Student")
    status = forms.ChoiceField(required=False, label="Status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs["placeholder"] = "Name or roll number"
        self.fields["status"].choices = [
            ("", "All students"),
            ("not_submitted", "Not submitted"),
            (Submission.Status.SUBMITTED, "Submitted"),
            (Submission.Status.UNDER_REVIEW, "Under review"),
            (Submission.Status.REVISION_REQUESTED, "Revision requested"),
            (Submission.Status.COMPLETED, "Completed"),
            ("overdue", "Overdue and not submitted"),
        ]


def filter_eligible_students(assignment, query="", status=""):
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    user_model = get_user_model()
    submitted_ids = Submission.objects.filter(assignment=assignment).values("student_id")
    eligible = Q(
        enrollments__subject=assignment.subject,
        enrollments__is_active=True,
    )
    if assignment.audience == Assignment.Audience.SELECTED:
        eligible &= Q(pk__in=assignment.assigned_students.values("pk"))
    students = (
        user_model.objects.filter(eligible | Q(pk__in=submitted_ids))
        .select_related("student_profile")
        .distinct()
    )
    if query:
        students = students.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
            | Q(student_profile__roll_number__icontains=query)
        )
    if status == "not_submitted":
        students = students.exclude(submissions__assignment=assignment)
    elif status == "overdue":
        if assignment.deadline < timezone.now():
            students = students.exclude(submissions__assignment=assignment)
        else:
            students = students.none()
    elif status:
        students = students.filter(
            submissions__assignment=assignment,
            submissions__status=status,
        )
    return students.order_by("first_name", "last_name", "username")
