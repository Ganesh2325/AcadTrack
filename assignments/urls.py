from django.urls import path, re_path

from assignments import views

app_name = "assignments"

urlpatterns = [
    path("student/assignments/", views.student_assignment_list, name="student_list"),
    path("student/assignments/<int:pk>/", views.student_assignment_detail, name="student_detail"),
    path("faculty/assignments/", views.faculty_assignment_list, name="faculty_list"),
    path("faculty/assignments/create/", views.assignment_create, name="create"),
    path("faculty/assignments/<int:pk>/edit/", views.assignment_edit, name="edit"),
    path("faculty/assignments/<int:pk>/archive/", views.assignment_archive, name="archive"),
    path("faculty/assignments/<int:pk>/delete/", views.assignment_delete, name="delete"),
    path("assignments/archive/", views.assignment_archive_jump, name="archive_jump"),
    re_path(
        r"^assignments/archive/(?P<year>[0-9]{4})/$",
        views.assignment_archive_year,
        name="archive_year",
    ),
]
