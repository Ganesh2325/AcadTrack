from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.AcadTrackLoginView.as_view(), name="login"),
    path("logout/", views.AcadTrackLogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("theme/", views.set_theme, name="set_theme"),
    path("redirect/", views.role_redirect, name="role_redirect"),
]
