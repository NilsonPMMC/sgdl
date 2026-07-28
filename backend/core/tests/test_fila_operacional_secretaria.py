"""Fila operacional — escopo por pendência real da secretaria."""

import importlib.util

from django.test import TestCase

from core.models import Demanda, Tramitacao, Usuario
from core.models_no_operacional import NoOperacional, StatusNoOperacional
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.demanda_visibilidade import (
    aplicar_escopo_fila_operacional,
    demanda_ids_pendencia_operacional,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class FilaOperacionalSecretariaTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_fila", password="x", perfil="VEREADOR"
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_fila_a",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.demanda_a = Demanda.objects.create(
            titulo="Mobilidade titular",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            fluxo_roteamento="FLUXO_TRANSVERSAL",
            nos_ativos=0,
        )
        self.demanda_b = Demanda.objects.create(
            titulo="SSU transversal",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            fluxo_roteamento="FLUXO_TRANSVERSAL",
            protocolo_executivo="2026-FILA-01",
            nos_ativos=1,
        )
        self.perna_a = PernaOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status=StatusPernaOperacional.CONCLUIDA,
        )
        self.perna_b = PernaOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )
        NoOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            status=StatusNoOperacional.ABERTO,
        )

    def test_pendencia_exclui_perna_concluida_orgao_a(self):
        ids = demanda_ids_pendencia_operacional(SINAPSE_ORGAO_A)
        self.assertNotIn(self.demanda_b.pk, ids)

    def test_pendencia_inclui_fluxo_direto_orgao_titular(self):
        self.demanda_a.fluxo_roteamento = "FLUXO_DIRETO"
        self.demanda_a.save(update_fields=["fluxo_roteamento"])
        ids = demanda_ids_pendencia_operacional(SINAPSE_ORGAO_A)
        self.assertIn(self.demanda_a.pk, ids)

    def test_fila_operacional_api_exclui_demanda_outro_orgao(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.sec_a)
        r = client.get(
            "/api/demandas/",
            {"fila": "operacionais", "escopo_setor": "em_operacao"},
        )
        self.assertEqual(r.status_code, 200)
        ids = {row["id"] for row in r.data}
        self.assertNotIn(self.demanda_b.pk, ids)

    def test_encerrado_setor_inclui_participacao_concluida(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional
        from core.services.demanda_visibilidade import demanda_ids_encerrado_setor

        NoOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status=StatusNoOperacional.CONCLUIDO,
        )
        ids = demanda_ids_encerrado_setor(self.sec_a)
        self.assertIn(self.demanda_b.pk, ids)

    def test_encerrado_setor_inclui_scatter_outro_setor_mesmo_orgao(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional
        from core.models_unidade_administrativa import UnidadeAdministrativa
        from core.services.demanda_visibilidade import (
            aplicar_escopo_demanda,
            demanda_ids_encerrado_setor,
        )

        outro_setor = UnidadeAdministrativa.objects.create(
            nome="Outro setor mobilidade",
            sigla="OUTRO-SMMT",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            ativo=True,
        )
        NoOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=outro_setor,
            status=StatusNoOperacional.CONCLUIDO,
        )
        ids = demanda_ids_encerrado_setor(self.sec_a)
        self.assertIn(self.demanda_b.pk, ids)
        qs = aplicar_escopo_demanda(Demanda.objects.filter(pk=self.demanda_b.pk), self.sec_a)
        self.assertTrue(qs.exists())

    def test_sincronizar_pernas_obsoletas_apos_encerramento_scatter(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional
        from core.services.scatter_gather_service import NoOperacionalService

        self.perna_a.status = StatusPernaOperacional.EM_EXECUCAO
        self.perna_a.save(update_fields=["status"])
        NoOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status=StatusNoOperacional.CONCLUIDO,
        )
        self.assertEqual(
            NoOperacionalService().sincronizar_pernas_scatter_obsoletas(
                demanda_id=self.demanda_b.pk
            ),
            1,
        )
        self.perna_a.refresh_from_db()
        self.assertEqual(self.perna_a.status, StatusPernaOperacional.CONCLUIDA)
        ids = demanda_ids_pendencia_operacional(SINAPSE_ORGAO_A)
        self.assertNotIn(self.demanda_b.pk, ids)

    def test_listagem_encerrado_mostra_encaminhamento_pos_despacho(self):
        from core.models import Tramitacao
        from core.services.demanda_listagem_secretaria import map_encaminhamento_pos_encerramento

        Tramitacao.objects.create(
            demanda=self.demanda_b,
            tipo="OPERACAO_NO",
            descricao="Encerramento scatter",
            metadata={
                "scatter_gather": True,
                "orgao_id": SINAPSE_ORGAO_A,
                "acao_no": "DESPACHAR_ENCERRAR",
                "destinos": [
                    {
                        "secretaria_id": SINAPSE_ORGAO_B,
                        "orgao_nome": "SSU",
                        "unidade_administrativa_id": None,
                        "setor_nome": "SETOR-SSU",
                    }
                ],
                "destino_orgao_id": SINAPSE_ORGAO_B,
            },
        )
        ctx = map_encaminhamento_pos_encerramento(SINAPSE_ORGAO_A, [self.demanda_b.pk])
        self.assertIn(self.demanda_b.pk, ctx)
        self.assertEqual(ctx[self.demanda_b.pk]["secretaria_destino"]["id"], SINAPSE_ORGAO_B)

    def test_setor_encerrado_mesmo_orgao_outro_setor_aberto(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional
        from core.models_unidade_administrativa import (
            UnidadeAdministrativa,
            UnidadeAdministrativaResponsavel,
        )
        from core.services.demanda_visibilidade import (
            demanda_ids_em_operacao_setor,
            demanda_ids_encerrado_setor,
        )

        ua_a = UnidadeAdministrativa.objects.create(
            nome="Setor A SSU",
            sigla="SSU-A",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            ativo=True,
        )
        ua_b = UnidadeAdministrativa.objects.create(
            nome="Setor B SSU",
            sigla="SSU-B",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            ativo=True,
        )
        sec_setor_a = Usuario.objects.create_user(
            username="sec_ssu_a",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=ua_a,
            usuario=sec_setor_a,
            ativo=True,
            pode_tramitar=True,
        )
        NoOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            unidade_administrativa=ua_a,
            status=StatusNoOperacional.CONCLUIDO,
        )
        NoOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            unidade_administrativa=ua_b,
            status=StatusNoOperacional.ABERTO,
        )
        self.assertNotIn(self.demanda_b.pk, demanda_ids_em_operacao_setor(sec_setor_a))
        self.assertIn(self.demanda_b.pk, demanda_ids_encerrado_setor(sec_setor_a))

    def test_encerrado_inclui_devolvido_vereador_com_participacao_concluida(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional
        from core.services.demanda_visibilidade import demanda_ids_encerrado_setor

        self.demanda_b.status = "DEVOLVIDO_VEREADOR"
        self.demanda_b.save(update_fields=["status"])
        NoOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status=StatusNoOperacional.CONCLUIDO,
        )
        self.assertIn(self.demanda_b.pk, demanda_ids_encerrado_setor(self.sec_a))

    def test_encerrado_nao_bloqueado_por_alerta_devolutiva_leitura(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional
        from core.services.demanda_visibilidade import demanda_ids_encerrado_setor

        self.demanda_b.status = "DEVOLVIDO_VEREADOR"
        self.demanda_b.save(update_fields=["status"])
        NoOperacional.objects.create(
            demanda=self.demanda_b,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status=StatusNoOperacional.CONCLUIDO,
        )
        Tramitacao.objects.create(
            demanda=self.demanda_b,
            tipo="CONCLUSAO_FINAL",
            descricao="Conclusão final",
            metadata={
                "alerta_destinos": [{"secretaria_id": SINAPSE_ORGAO_A}],
                "devolutiva_leitura": True,
            },
        )
        self.assertIn(self.demanda_b.pk, demanda_ids_encerrado_setor(self.sec_a))
