from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.forms import (
    AcadTrackAuthenticationForm,
    AccountProfileForm,
    ProfileUpdateForm,
    StudentRegistrationForm,
)
from accounts.roles import home_url_name, role_label


def remember_session_identity(request, user):
    """Store a display name in the session. Groups remain the source of authorization."""
    request.session["display_name"] = user.get_full_name() or user.username
    request.session["active_role"] = role_label(user)


class AcadTrackLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = AcadTrackAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        next_url = self.get_redirect_url()
        if next_url:
            return next_url
        return reverse(home_url_name(self.request.user))

    def form_valid(self, form):
        response = super().form_valid(form)
        remember_session_identity(self.request, self.request.user)
        messages.success(self.request, "Signed in successfully.")
        return response

    def form_invalid(self, form):
        return super().form_invalid(form)


class AcadTrackLogoutView(LogoutView):
    """POST-only logout. Django clears the session before redirecting."""

    http_method_names = ["post", "options"]


def register(request):
    if request.user.is_authenticated:
        return redirect(home_url_name(request.user))
    form = StudentRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
        remember_session_identity(request, user)
        messages.success(request, "Welcome to AcadTrack. Your student account is ready.")
        return redirect("dashboard:student")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def role_redirect(request):
    return redirect(home_url_name(request.user))


@login_required
def profile(request):
    student_profile = getattr(request.user, "student_profile", None)
    if student_profile is not None:
        form = ProfileUpdateForm(
            request.POST or None,
            instance=student_profile,
            user=request.user,
        )
    else:
        form = AccountProfileForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        request.user.refresh_from_db()
        remember_session_identity(request, request.user)
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "student_profile": student_profile,
        },
    )


@require_POST
def set_theme(request):
    """Persist a light/dark preference in a cookie. No secrets are stored."""
    theme = request.POST.get("theme", "light")
    if theme not in {"light", "dark"}:
        theme = "light"
    next_url = request.POST.get("next") or reverse("landing")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("landing")
    response = redirect(next_url)
    response.set_cookie(
        settings.THEME_COOKIE_NAME,
        theme,
        max_age=settings.THEME_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure(),
        path="/",
    )
    return response
