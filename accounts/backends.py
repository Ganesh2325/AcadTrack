from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Authenticate with either the username or the unique email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        user_model = get_user_model()
        user = user_model.objects.filter(username__iexact=username).first()
        if user is None:
            user = user_model.objects.filter(email__iexact=username).first()
        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


def theme_from_request(request):
    theme = request.COOKIES.get(settings.THEME_COOKIE_NAME, "light")
    if theme not in {"light", "dark"}:
        return "light"
    return theme
