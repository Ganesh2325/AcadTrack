"""WSGI config for AcadTrack."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "acadtrack.settings")

application = get_wsgi_application()
