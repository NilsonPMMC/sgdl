"""Flags operacionais do Copiloto (Vereador)."""

from django.conf import settings


def copiloto_faq_habilitada() -> bool:
    return getattr(settings, "COPILOTO_FAQ_ENABLED", False)


def copiloto_tendencias_habilitadas() -> bool:
    return getattr(settings, "COPILOTO_TENDENCIAS_ENABLED", True)


def corpus_legado_habilitado() -> bool:
    """Corpus CSV/JSON de aprendizado (read-only). Não altera Demandas existentes."""
    return getattr(settings, "CORPUS_LEGADO_ENABLED", True)


def corpus_legado_hints_copiloto_habilitados() -> bool:
    """Sugestões assistivas no Copiloto — desligado por padrão até homologação."""
    return getattr(settings, "CORPUS_LEGADO_HINTS_COPILOTO_ENABLED", False)
