from django import template
from django.utils import timezone
from django.utils.html import format_html

from assignments.queries import STATUS_LABELS

register = template.Library()

BADGE_CLASSES = {
    "not_submitted": "status-neutral",
    "overdue": "status-danger",
    "submitted": "status-info",
    "under_review": "status-warning",
    "revision_requested": "status-warning",
    "completed": "status-success",
    "draft": "status-neutral",
    "published": "status-success",
    "archived": "status-neutral",
}


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            query.pop(key, None)
        else:
            query[key] = str(value)
    encoded = query.urlencode()
    return f"?{encoded}" if encoded else "?"


@register.simple_tag
def status_badge(code):
    label = STATUS_LABELS.get(code, str(code or "Unknown").replace("_", " ").title())
    css = BADGE_CLASSES.get(code, "status-neutral")
    return format_html('<span class="status-badge {}">{}</span>', css, label)


@register.simple_tag
def deadline_hint(deadline):
    now = timezone.now()
    delta = deadline - now
    seconds = delta.total_seconds()
    if seconds < 0:
        days = (-delta).days
        if days >= 1:
            suffix = "" if days == 1 else "s"
            return format_html('<span class="time-overdue">Overdue by {} day{}</span>', days, suffix)
        hours = max(1, int((-delta).total_seconds() // 3600))
        suffix = "" if hours == 1 else "s"
        return format_html('<span class="time-overdue">Overdue by {} hour{}</span>', hours, suffix)
    if delta.days > 1:
        return format_html('<span class="time-ok">{} days left</span>', delta.days)
    if delta.days == 1:
        return format_html('<span class="time-soon">{}</span>', "1 day left")
    hours = max(1, delta.seconds // 3600) if delta.seconds >= 3600 else 0
    if hours:
        suffix = "" if hours == 1 else "s"
        return format_html('<span class="time-soon">{} hour{} left</span>', hours, suffix)
    return format_html('<span class="time-soon">{}</span>', "Due soon")


@register.filter
def person_name(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    full_name = value.get_full_name().strip()
    return full_name or value.get_username()
