from django.apps import AppConfig
from django.contrib import admin
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Accounts and profiles"

    def ready(self):
        from accounts.groups import create_default_groups

        post_migrate.connect(
            create_default_groups,
            sender=self,
            dispatch_uid="accounts.create_default_groups",
        )
        admin.site.site_header = "AcadTrack Administration"
        admin.site.site_title = "AcadTrack Admin"
        admin.site.index_title = "Institution data management"
