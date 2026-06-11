from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Descontinuado: serviços e órgãos vêm do catálogo Sinapse (CatalogServico / CatalogOrgao). "
        "Use: python manage.py sync_sinapse_services"
    )

    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.WARNING(
                "import_servicos foi descontinuado. "
                "Execute sync_sinapse_services para espelhar a carta Sinapse no SGDL."
            )
        )
