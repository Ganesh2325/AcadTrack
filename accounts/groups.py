from django.contrib.auth.models import Group

from accounts.roles import FACULTY_GROUP, STUDENT_GROUP


def create_default_groups(sender, **kwargs):
    Group.objects.get_or_create(name=STUDENT_GROUP)
    Group.objects.get_or_create(name=FACULTY_GROUP)
