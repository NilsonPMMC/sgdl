"""Testes U7 — Gestor Geral vs Gestor Setorial."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.models_unidade_administrativa import UnidadeAdministrativa, UnidadeAdministrativaResponsavel
from core.services.demanda_visibilidade import (
    aplicar_escopo_demanda,
    usuario_pode_acessar_demanda,
)
from core.services.gestor_escopo import (
    TIPO_GERAL,
    TIPO_SETORIAL,
    gestor_pode_crud_admin,
    gestor_protocolo_sgac,
    orgaos_escopo_gestor,
    pode_gerir_responsaveis_unidade,
    tipo_gestor,
    usuario_pode_painel_protocolo_central,
    usuario_pode_acessar_fila_demanda,
)
from core.services.usuario_vinculo_service import PROTOCOLO_UNIDADE_PK, UsuarioVinculoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class GestorEscopoServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.ua = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor A",
            sigla="SET-A",
        )
        self.gestor_geral = Usuario.objects.create_user(
            username="gest_geral",
            password="x",
            perfil="GESTOR",
        )
        self.gestor_setorial = Usuario.objects.create_user(
            username="gest_setor",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.service = UsuarioVinculoService()

    def test_tipo_gestor_sem_vinculo_e_geral(self):
        self.assertEqual(tipo_gestor(self.gestor_geral), TIPO_GERAL)
        self.assertTrue(gestor_pode_crud_admin(self.gestor_geral))

    def test_tipo_gestor_com_orgao_e_setorial(self):
        self.assertEqual(tipo_gestor(self.gestor_setorial), TIPO_SETORIAL)
        self.assertFalse(gestor_pode_crud_admin(self.gestor_setorial))

    def test_sincronizar_gestor_geral_aplica_superuser(self):
        Usuario.objects.filter(pk=self.gestor_geral.pk).update(
            is_staff=False, is_superuser=False
        )
        self.gestor_geral.refresh_from_db()
        self.service.sincronizar_gestor(self.gestor_geral)
        self.gestor_geral.refresh_from_db()
        self.assertTrue(self.gestor_geral.is_staff)
        self.assertTrue(self.gestor_geral.is_superuser)

    def test_sincronizar_gestor_setorial_sem_superuser(self):
        self.service.sincronizar_gestor(
            self.gestor_setorial,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_ids=[self.ua.pk],
        )
        self.gestor_setorial.refresh_from_db()
        self.assertTrue(self.gestor_setorial.is_staff)
        self.assertFalse(self.gestor_setorial.is_superuser)
        self.assertEqual(orgaos_escopo_gestor(self.gestor_setorial), [SINAPSE_ORGAO_A])

    def test_gestor_setorial_pode_gerir_responsaveis_no_escopo(self):
        self.assertTrue(pode_gerir_responsaveis_unidade(self.gestor_setorial, self.ua))
        ua_b = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            nome="Setor B",
            sigla="SET-B",
        )
        self.assertFalse(pode_gerir_responsaveis_unidade(self.gestor_setorial, ua_b))
        self.assertTrue(pode_gerir_responsaveis_unidade(self.gestor_geral, ua_b))

    def test_superuser_sem_orgao_permanece_geral_com_ua_residual(self):
        Usuario.objects.filter(pk=self.gestor_geral.pk).update(
            is_superuser=True,
            is_staff=True,
            sinapse_orgao_id=None,
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=self.ua,
            usuario_id=self.gestor_geral.pk,
            ativo=True,
            pode_tramitar=True,
        )
        self.gestor_geral.refresh_from_db()
        self.assertEqual(tipo_gestor(self.gestor_geral), TIPO_GERAL)
        self.assertTrue(gestor_pode_crud_admin(self.gestor_geral))


class GestorEscopoDemandaTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_gest", password="x", perfil="VEREADOR"
        )
        self.gestor_geral = Usuario.objects.create_user(
            username="gg", password="x", perfil="GESTOR", is_staff=True, is_superuser=True
        )
        self.gestor_setorial = Usuario.objects.create_user(
            username="gs",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            is_staff=True,
            is_superuser=False,
        )
        self.dem_a = Demanda.objects.create(
            titulo="A",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.dem_b = Demanda.objects.create(
            titulo="B",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )

    def test_gestor_geral_ve_todas(self):
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.gestor_geral)
        self.assertEqual(qs.count(), 2)

    def test_gestor_setorial_ve_apenas_org_vinculado(self):
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.gestor_setorial)
        ids = set(qs.values_list("pk", flat=True))
        self.assertEqual(ids, {self.dem_a.pk})

    def test_acesso_pontual_setorial(self):
        self.assertTrue(usuario_pode_acessar_demanda(self.gestor_setorial, self.dem_a))
        self.assertFalse(usuario_pode_acessar_demanda(self.gestor_setorial, self.dem_b))

    def test_gestor_setorial_nao_acessa_fila_devolutivas(self):
        self.dem_a.status = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"
        self.dem_a.save(update_fields=["status"])
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.gestor_setorial)
        self.assertNotIn(self.dem_a.pk, set(qs.values_list("pk", flat=True)))
        self.assertFalse(usuario_pode_acessar_demanda(self.gestor_setorial, self.dem_a))

    def test_gestor_geral_pode_painel_protocolo_central(self):
        self.assertTrue(usuario_pode_painel_protocolo_central(self.gestor_geral))
        self.assertFalse(usuario_pode_painel_protocolo_central(self.gestor_setorial))

    def test_gestor_setorial_filas_permitidas(self):
        self.assertTrue(usuario_pode_acessar_fila_demanda(self.gestor_setorial, "operacionais"))
        self.assertTrue(usuario_pode_acessar_fila_demanda(self.gestor_setorial, "stand_by"))
        self.assertTrue(usuario_pode_acessar_fila_demanda(self.gestor_setorial, "finalizados"))
        self.assertFalse(usuario_pode_acessar_fila_demanda(self.gestor_setorial, "devolutivas"))
        self.assertFalse(usuario_pode_acessar_fila_demanda(self.gestor_setorial, "protocolados"))


class GestorProtocoloSgacEscopoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_sgac", password="x", perfil="VEREADOR"
        )
        self.ua_sgac, _ = UnidadeAdministrativa.objects.get_or_create(
            pk=PROTOCOLO_UNIDADE_PK,
            defaults={
                "sinapse_orgao_id": 12,
                "nome": "Protocolo Geral",
                "sigla": "MCRUZ-SMGOV-SGAC",
            },
        )
        self.gestor_sgac = Usuario.objects.create_user(
            username="gest_sgac",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=12,
            is_staff=True,
            is_superuser=False,
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=self.ua_sgac,
            usuario=self.gestor_sgac,
            ativo=True,
        )
        self.dem_protocolada = Demanda.objects.create(
            titulo="Protocolada outro orgao",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            protocolo_executivo="2026-03921",
        )
        self.dem_rascunho = Demanda.objects.create(
            titulo="Rascunho",
            descricao="x",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )

    def test_gestor_sgac_identificado(self):
        self.assertTrue(gestor_protocolo_sgac(self.gestor_sgac))
        self.assertEqual(tipo_gestor(self.gestor_sgac), TIPO_SETORIAL)

    def test_gestor_sgac_ve_demanda_protocolada_outro_orgao(self):
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.gestor_sgac)
        self.assertIn(self.dem_protocolada.pk, set(qs.values_list("pk", flat=True)))
        self.assertNotIn(self.dem_rascunho.pk, set(qs.values_list("pk", flat=True)))

    def test_gestor_sgac_acessa_detalhe_protocolada(self):
        self.assertTrue(
            usuario_pode_acessar_demanda(self.gestor_sgac, self.dem_protocolada)
        )
        self.assertFalse(usuario_pode_acessar_demanda(self.gestor_sgac, self.dem_rascunho))

    def test_gestor_sgac_pode_painel_protocolo_central(self):
        self.assertTrue(usuario_pode_painel_protocolo_central(self.gestor_sgac))

    def test_gestor_sgac_fila_operacionais_ve_demanda_como_protocolo(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.gestor_sgac)
        r = client.get(
            "/api/demandas/",
            {"fila": "operacionais", "escopo_setor": "em_operacao"},
        )
        self.assertEqual(r.status_code, 200)
        payload = r.data.get("results", r.data)
        ids = {row["id"] for row in payload}
        self.assertIn(self.dem_protocolada.pk, ids)


class GestorEscopoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor_geral = Usuario.objects.create_user(
            username="gg_api",
            password="x",
            perfil="GESTOR",
            is_staff=True,
            is_superuser=True,
        )
        self.gestor_setorial = Usuario.objects.create_user(
            username="gs_api",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            is_staff=True,
            is_superuser=False,
        )

    def test_setorial_nao_acessa_gestao_usuarios(self):
        self.client.force_authenticate(user=self.gestor_setorial)
        r = self.client.get("/api/gestao-usuarios/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_geral_acessa_gestao_usuarios(self):
        self.client.force_authenticate(user=self.gestor_geral)
        r = self.client.get("/api/gestao-usuarios/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_setorial_acessa_orgaos_e_unidades_leitura(self):
        self.client.force_authenticate(user=self.gestor_setorial)
        r_org = self.client.get("/api/unidades-administrativas/orgaos/")
        self.assertEqual(r_org.status_code, status.HTTP_200_OK)
        r_ua = self.client.get("/api/unidades-administrativas/", {"incluir_inativos": "1"})
        self.assertEqual(r_ua.status_code, status.HTTP_200_OK)
        r_dep = self.client.get("/api/depara-rm-sinapse/")
        self.assertEqual(r_dep.status_code, status.HTTP_200_OK)

    def test_superuser_admin_acessa_gestao_usuarios(self):
        ua = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Residual",
            sigla="RES",
        )
        admin = Usuario.objects.create_user(
            username="admin_residual",
            password="x",
            perfil="GESTOR",
            is_staff=True,
            is_superuser=True,
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=ua,
            usuario_id=admin.pk,
            ativo=True,
        )
        self.client.force_authenticate(user=admin)
        r = self.client.get("/api/gestao-usuarios/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_setorial_fila_devolutivas_nao_lista_demandas(self):
        vereador = Usuario.objects.create_user(
            username="ver_dev_fila", password="x", perfil="VEREADOR"
        )
        Demanda.objects.create(
            titulo="Devolutiva",
            descricao="x",
            autor=vereador,
            status="AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.client.force_authenticate(user=self.gestor_setorial)
        r = self.client.get("/api/demandas/", {"fila": "devolutivas"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = r.data.get("results", r.data)
        self.assertEqual(len(payload), 0)

    def test_setorial_fila_operacionais_em_operacao_lista_demanda_no_setor(self):
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        ua = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor Operacional",
            sigla="SET-OP",
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=ua,
            usuario_id=self.gestor_setorial.pk,
            ativo=True,
        )
        vereador = Usuario.objects.create_user(
            username="ver_op_gs", password="x", perfil="VEREADOR"
        )
        demanda = Demanda.objects.create(
            titulo="Em execução setor",
            descricao="x",
            autor=vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-GS-OP-01",
            nos_ativos=1,
        )
        PernaOperacional.objects.create(
            demanda=demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=ua,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )
        self.client.force_authenticate(user=self.gestor_setorial)
        r = self.client.get(
            "/api/demandas/",
            {"fila": "operacionais", "escopo_setor": "em_operacao"},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = r.data.get("results", r.data)
        ids = {row["id"] for row in payload}
        self.assertIn(demanda.pk, ids)

    def test_setorial_filtro_unidades_administrativas(self):
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        ua_a = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor A Filtro",
            sigla="SET-AF",
        )
        ua_b = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor B Filtro",
            sigla="SET-BF",
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=ua_a,
            usuario_id=self.gestor_setorial.pk,
            ativo=True,
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=ua_b,
            usuario_id=self.gestor_setorial.pk,
            ativo=True,
        )
        vereador = Usuario.objects.create_user(
            username="ver_filtro_gs", password="x", perfil="VEREADOR"
        )
        dem_a = Demanda.objects.create(
            titulo="Setor A",
            descricao="x",
            autor=vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-GS-FA",
            nos_ativos=1,
        )
        dem_b = Demanda.objects.create(
            titulo="Setor B",
            descricao="x",
            autor=vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-GS-FB",
            nos_ativos=1,
        )
        PernaOperacional.objects.create(
            demanda=dem_a,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=ua_a,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )
        PernaOperacional.objects.create(
            demanda=dem_b,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=ua_b,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )
        self.client.force_authenticate(user=self.gestor_setorial)
        r = self.client.get(
            "/api/demandas/",
            {
                "fila": "operacionais",
                "escopo_setor": "em_operacao",
                "unidades_administrativas": ua_a.pk,
            },
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = r.data.get("results", r.data)
        ids = {row["id"] for row in payload}
        self.assertIn(dem_a.pk, ids)
        self.assertNotIn(dem_b.pk, ids)
