"""Tasks Celery do SGDL — fila exclusiva `sgdl_default`."""

from celery import shared_task


@shared_task(name="sgdl.verificar_atrasos", queue="sgdl_default", ignore_result=True)
def verificar_atrasos_task() -> dict:
    from core.services.atraso_demanda_service import AtrasoDemandaService

    return AtrasoDemandaService().executar().as_dict()
