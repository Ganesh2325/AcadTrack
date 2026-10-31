from django.urls import path

from subjects import views

app_name = "subjects"

urlpatterns = [
    path("", views.subject_list, name="list"),
    path("create/", views.subject_create, name="create"),
    path("<int:pk>/", views.subject_detail, name="detail"),
    path("<int:pk>/edit/", views.subject_edit, name="edit"),
    path("<int:pk>/enroll/", views.enroll_student, name="enroll"),
    path("<int:pk>/unenroll/<int:student_id>/", views.unenroll_student, name="unenroll"),
]
