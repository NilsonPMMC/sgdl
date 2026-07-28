"""Branding e cabeçalhos do Django Admin do SGDL."""

from django.contrib import admin


def configurar_admin_site() -> None:
    admin.site.site_header = "SGDL — Administração"
    admin.site.site_title = "SGDL Admin"
    admin.site.index_title = "Gestão de dados do sistema"
