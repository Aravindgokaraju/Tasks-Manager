from django.apps import AppConfig


class BaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "base"
    
    def ready(self):
        # Import signals when app is ready
        import base.signals  # noqa
