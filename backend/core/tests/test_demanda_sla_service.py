"""Testes do filtro de SLA atrasado."""

from django.test import TestCase
from django.utils import timezone

from core.models import Demanda, Usuario
from core.services.demanda_sla_service import filtrar_demandas_atrasadas
import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class DemandaSlaFilterTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_sla", password="x", perfil="VEREADOR"
        )

    def test_filtra_apenas_com_prazo_vencido(self):
        ok = Demanda.objects.create(
            titulo="Atrasada",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
            data_inicio_prazo=timezone.now() - timezone.timedelta(days=20),
            prazo_efetivo_dias=5,
        )
        Demanda.objects.create(
            titulo="No prazo",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
            data_inicio_prazo=timezone.now() - timezone.timedelta(days=2),
            prazo_efetivo_dias=30,
        )
        ids = set(filtrar_demandas_atrasadas(Demanda.objects.all()).values_list("pk", flat=True))
        self.assertEqual(ids, {ok.pk})
