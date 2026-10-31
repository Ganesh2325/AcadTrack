"""Shared upload rules.

Uploaded source code is stored and downloaded as an attachment. It is never executed.
"""
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

SUBMISSION_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".zip",
    ".java",
    ".py",
    ".html",
    ".css",
    ".js",
}

REFERENCE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
}


def validate_uploaded_file(uploaded, allowed_extensions):
    """Validate extension and size for an uploaded file or stored FieldFile."""
    if not uploaded:
        return
    name = getattr(uploaded, "name", "") or ""
    extension = Path(name).suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(item.lstrip(".") for item in allowed_extensions))
        raise ValidationError(f"Unsupported file type. Allowed types: {allowed}.")
    size = getattr(uploaded, "size", None)
    if size is None:
        return
    if size == 0:
        raise ValidationError("The uploaded file is empty.")
    if size > MAX_UPLOAD_BYTES:
        raise ValidationError("File size must be 5 MB or less.")


def unique_upload_path(folder, filename):
    extension = Path(filename).suffix.lower()
    return f"{folder}/{uuid.uuid4().hex}{extension}"


def assignment_attachment_path(instance, filename):
    return unique_upload_path("assignment_attachments", filename)


def submission_file_path(instance, filename):
    return unique_upload_path("submissions", filename)


def safe_original_name(filename):
    name = Path(filename or "download").name
    return name[:180] or "download"
