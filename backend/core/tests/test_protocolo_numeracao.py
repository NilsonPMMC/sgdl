"""Testes P7 — numeração OFICIO por vereador e protocolo executivo global."""

import importlib.util

from django.test import TestCase
from django.utils import timezone

from core.models import Demanda, Usuario
from core.services.demanda_despacho_service import proximo_protocolo_executivo
from core.services.protocolo_numeracao_service import proximo_protocolo_legislativo

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin
payload_envio_oficial = _legacy.payload_envio_oficial


class ProtocoloNumeracaoServiceTests(TestCase):
    def setUp(self):
        self.vereador_a = Usuario.objects.create_user(
            username="ver_a_num", password="x", perfil="VEREADOR"
        )
        self.vereador_b = Usuario.objects.create_user(
            username="ver_b_num", password="x", perfil="VEREADOR"
        )
        self.ano = timezone.now().year

    def test_primeiro_oficio_por_vereador_mesmo_numero(self):
        num_a = proximo_protocolo_legislativo(self.vereador_a.id, ano=self.ano)
        num_b = proximo_protocolo_legislativo(self.vereador_b.id, ano=self.ano)
        self.assertEqual(num_a, f"{self.ano}-0001")
        self.assertEqual(num_b, f"{self.ano}-0001")

    def test_sequencia_independente_por_autor(self):
        Demanda.objects.create(
            titulo="Ofício 1 A",
            descricao="x",
            autor=self.vereador_a,
            protocolo_legislativo=f"OFICIO-{self.ano}-0001",
            status="AGUARDANDO_PROTOCOLO",
        )
        Demanda.objects.create(
            titulo="Ofício 1 B",
            descricao="x",
            autor=self.vereador_b,
            protocolo_legislativo=f"OFICIO-{self.ano}-0001",
            status="AGUARDANDO_PROTOCOLO",
        )
        self.assertEqual(
            proximo_protocolo_legislativo(self.vereador_a.id, ano=self.ano),
            f"{self.ano}-0002",
        )
        self.assertEqual(
            proximo_protocolo_legislativo(self.vereador_b.id, ano=self.ano),
            f"{self.ano}-0002",
        )

    def test_clone_multi_destino_nao_regride_sequencia(self):
        """B5 — sufixo -D2 no protocolo_legislativo não deve resetar numeração."""
        Demanda.objects.create(
            titulo="Principal",
            descricao="x",
            autor=self.vereador_a,
            protocolo_legislativo=f"OFICIO-{self.ano}-0035",
            status="PROTOCOLADO",
        )
        Demanda.objects.create(
            titulo="Clone",
            descricao="x",
            autor=self.vereador_a,
            protocolo_legislativo=f"OFICIO-{self.ano}-0035-D2",
            status="PROTOCOLADO",
        )
        self.assertEqual(
            proximo_protocolo_legislativo(self.vereador_a.id, ano=self.ano),
            f"{self.ano}-0036",
        )

    def test_sequencia_continua_apos_formato_legado_oficio(self):
        Demanda.objects.create(
            titulo="Legado",
            descricao="x",
            autor=self.vereador_a,
            protocolo_legislativo=f"OFICIO-{self.ano}-0010",
            status="PROTOCOLADO",
        )
        self.assertEqual(
            proximo_protocolo_legislativo(self.vereador_a.id, ano=self.ano),
            f"{self.ano}-0011",
        )

    def test_protocolo_executivo_global(self):
        Demanda.objects.create(
            titulo="D1",
            descricao="x",
            autor=self.vereador_a,
            protocolo_executivo=f"{self.ano}-0001",
            status="PROTOCOLADO",
        )
        self.assertEqual(proximo_protocolo_executivo(), f"{self.ano}-0002")


class ProtocoloNumeracaoEnviarAPITests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from django.urls import reverse
        from rest_framework.test import APIClient

        self.api_client = APIClient()
        self.reverse = reverse
        self.ano = timezone.now().year
        self.vereador_a = Usuario.objects.create_user(
            username="ver_api_a", password="x", perfil="VEREADOR"
        )
        self.vereador_b = Usuario.objects.create_user(
            username="ver_api_b", password="x", perfil="VEREADOR"
        )

    def _criar_rascunho(self, autor):
        return Demanda.objects.create(
            titulo=f"Demanda {autor.username}",
            descricao="Texto do ofício",
            autor=autor,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            status="RASCUNHO",
        )

    def _enviar(self, demanda, usuario):
        self.api_client.force_authenticate(user=usuario)
        url = self.reverse("demanda-enviar", kwargs={"pk": demanda.pk})
        return self.api_client.post(url, payload_envio_oficial(demanda), format="json")

    def test_enviar_dois_vereadores_mesmo_oficio_numero(self):
        d_a = self._criar_rascunho(self.vereador_a)
        d_b = self._criar_rascunho(self.vereador_b)

        r_a = self._enviar(d_a, self.vereador_a)
        r_b = self._enviar(d_b, self.vereador_b)

        self.assertEqual(r_a.status_code, 200)
        self.assertEqual(r_b.status_code, 200)

        d_a.refresh_from_db()
        d_b.refresh_from_db()
        self.assertEqual(d_a.protocolo_legislativo, f"{self.ano}-0001")
        self.assertEqual(d_b.protocolo_legislativo, f"{self.ano}-0001")

    def test_mesmo_vereador_segundo_oficio_incrementa(self):
        d1 = self._criar_rascunho(self.vereador_a)
        d2 = self._criar_rascunho(self.vereador_a)
        self._enviar(d1, self.vereador_a)
        self._enviar(d2, self.vereador_a)
        d2.refresh_from_db()
        self.assertEqual(d2.protocolo_legislativo, f"{self.ano}-0002")
