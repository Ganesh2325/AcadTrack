from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("student/dashboard/", views.student_dashboard, name="student"),
    path("student/progress/", views.student_progress, name="student_progress"),
    path("faculty/dashboard/", views.faculty_dashboard, name="faculty"),
]
