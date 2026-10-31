from django.contrib.auth.decorators import login_required
from django.http import HttpResponseServerError
from django.shortcuts import render
from django.template import loader

from accounts.decorators import faculty_required, student_required
from accounts.roles import home_url_name, is_faculty, is_student
from dashboard.analytics import faculty_dashboard_data, student_dashboard_data


def landing(request):
    destination = None
    if request.user.is_authenticated:
        if is_faculty(request.user):
            destination = "dashboard:faculty"
        elif is_student(request.user):
            destination = "dashboard:student"
        else:
            destination = home_url_name(request.user)
    return render(request, "landing.html", {"destination": destination})


@student_required
def student_dashboard(request):
    context = student_dashboard_data(request.user)
    return render(request, "student/dashboard.html", context)


@student_required
def student_progress(request):
    context = student_dashboard_data(request.user)
    evaluated = (
        context["stats"]["completed"]
        + context["stats"]["revision"]
        + context["stats"]["awaiting"]
    )
    context["evaluated_or_open"] = evaluated
    return render(request, "student/progress.html", context)


@faculty_required
def faculty_dashboard(request):
    context = faculty_dashboard_data(request.user)
    return render(request, "faculty/dashboard.html", context)


def permission_denied_view(request, exception):
    return render(request, "errors/403.html", status=403)


def page_not_found_view(request, exception):
    return render(request, "errors/404.html", status=404)


def server_error_view(request):
    body = loader.get_template("errors/500.html").render()
    return HttpResponseServerError(body)
