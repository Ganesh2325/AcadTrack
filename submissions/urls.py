from django.urls import path

from submissions import views

app_name = "submissions"

urlpatterns = [
    path("student/assignments/<int:pk>/submit/", views.submit_assignment, name="submit"),
    path("student/submissions/", views.submission_history, name="history"),
    path("student/submissions/<int:pk>/", views.submission_detail, name="detail"),
    path("faculty/assignments/<int:pk>/submissions/", views.faculty_submission_list, name="faculty_list"),
    path("faculty/submissions/<int:pk>/evaluate/", views.evaluate_submission, name="evaluate"),
    path("faculty/submissions/<int:pk>/start-review/", views.start_review, name="start_review"),
    path("submissions/attempts/<int:pk>/file/", views.download_attempt, name="download_attempt"),
    path("assignments/<int:pk>/attachment/", views.download_attachment, name="download_attachment"),
]
