from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Registra signals (notificações, embedding IA / VectorService, etc.)
        import core.signals  # noqa: F401
        import core.services.copiloto_faq_service  # noqa: F401 — cache FAQ Copiloto