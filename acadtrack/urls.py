from django.contrib import admin
from django.urls import include, path

from dashboard import views as dashboard_views

handler403 = "dashboard.views.permission_denied_view"
handler404 = "dashboard.views.page_not_found_view"
handler500 = "dashboard.views.server_error_view"

urlpatterns = [
    path("", dashboard_views.landing, name="landing"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("subjects/", include("subjects.urls")),
    path("", include("dashboard.urls")),
    path("", include("assignments.urls")),
    path("", include("submissions.urls")),
]
