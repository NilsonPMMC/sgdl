"""Localização operacional aberta — listagem e filtro por setor."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.models_no_operacional import NoOperacional, StatusNoOperacional
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.models_unidade_administrativa import UnidadeAdministrativa, UnidadeAdministrativaResponsavel
from core.services.demanda_localizacao_operacional_service import (
    demanda_ids_com_setores_operacionais_abertos,
    map_localizacao_operacional_aberta,
)
from core.services.demanda_visibilidade import filtrar_demandas_por_unidades

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class DemandaLocalizacaoOperacionalTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_loc", password="x", perfil="VEREADOR"
        )
        self.ua_inicial = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor Inicial",
            sigla="SET-INI",
        )
        self.ua_atual = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor Atual",
            sigla="SET-ATU",
        )
        self.demanda = Demanda.objects.create(
            titulo="Demanda scatter",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.ua_inicial,
            protocolo_executivo="2026-LOC-01",
            nos_ativos=1,
        )
        self.no_aberto = NoOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.ua_atual,
            status=StatusNoOperacional.ABERTO,
        )

    def test_filtro_por_setor_usa_no_aberto_nao_despacho_inicial(self):
        ids_ini = demanda_ids_com_setores_operacionais_abertos([self.ua_inicial.pk])
        ids_atu = demanda_ids_com_setores_operacionais_abertos([self.ua_atual.pk])
        self.assertNotIn(self.demanda.pk, ids_ini)
        self.assertIn(self.demanda.pk, ids_atu)

    def test_map_localizacao_inclui_no_aberto(self):
        mapa = map_localizacao_operacional_aberta([self.demanda.pk])
        itens = mapa[self.demanda.pk]
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["tipo"], "no")
        self.assertEqual(itens[0]["setor_sigla"], "SET-ATU")
        self.assertEqual(itens[0]["no_id"], self.no_aberto.pk)
        self.assertTrue(itens[0]["aberto"])

    def test_map_localizacao_marca_no_concluido(self):
        NoOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.ua_inicial,
            status=StatusNoOperacional.CONCLUIDO,
        )
        mapa = map_localizacao_operacional_aberta([self.demanda.pk])
        itens = mapa[self.demanda.pk]
        self.assertEqual(len(itens), 2)
        por_sigla = {i["setor_sigla"]: i for i in itens}
        self.assertFalse(por_sigla["SET-INI"]["aberto"])
        self.assertTrue(por_sigla["SET-ATU"]["aberto"])

    def test_map_localizacao_agrupa_mesmo_setor(self):
        NoOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.ua_atual,
            status=StatusNoOperacional.CONCLUIDO,
        )
        mapa = map_localizacao_operacional_aberta([self.demanda.pk])
        itens = mapa[self.demanda.pk]
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["setor_sigla"], "SET-ATU")
        self.assertTrue(itens[0]["aberto"])
        self.assertEqual(itens[0]["quantidade"], 2)

    def test_filtrar_demandas_por_unidades_queryset(self):
        qs = filtrar_demandas_por_unidades(Demanda.objects.all(), [self.ua_atual.pk])
        self.assertIn(self.demanda.pk, set(qs.values_list("pk", flat=True)))
        qs_ini = filtrar_demandas_por_unidades(Demanda.objects.all(), [self.ua_inicial.pk])
        self.assertNotIn(self.demanda.pk, set(qs_ini.values_list("pk", flat=True)))


class DemandaLocalizacaoOperacionalAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor_setorial = Usuario.objects.create_user(
            username="gs_loc",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            is_staff=True,
        )
        self.vereador = Usuario.objects.create_user(
            username="ver_loc_api", password="x", perfil="VEREADOR"
        )
        self.ua_inicial = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Inicial API",
            sigla="INI-API",
        )
        self.ua_atual = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Atual API",
            sigla="ATU-API",
        )
        for ua in (self.ua_inicial, self.ua_atual):
            UnidadeAdministrativaResponsavel.objects.create(
                unidade=ua,
                usuario_id=self.gestor_setorial.pk,
                ativo=True,
            )
        self.demanda = Demanda.objects.create(
            titulo="API localizacao",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.ua_inicial,
            protocolo_executivo="2026-LOC-API",
            nos_ativos=1,
        )
        NoOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.ua_atual,
            status=StatusNoOperacional.ABERTO,
        )
        PernaOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.ua_inicial,
            status=StatusPernaOperacional.CONCLUIDA,
        )

    def test_api_listagem_traz_setores_operacionais_abertos(self):
        self.client.force_authenticate(user=self.gestor_setorial)
        r = self.client.get(
            "/api/demandas/",
            {"fila": "operacionais", "escopo_setor": "em_operacao"},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = r.data.get("results", r.data)
        row = next(item for item in payload if item["id"] == self.demanda.pk)
        setores = row.get("setores_operacionais_abertos") or []
        self.assertTrue(any(s.get("setor_sigla") == "ATU-API" for s in setores))

    def test_api_filtro_setor_atual_nao_inicial(self):
        self.client.force_authenticate(user=self.gestor_setorial)
        r_atu = self.client.get(
            "/api/demandas/",
            {
                "fila": "operacionais",
                "escopo_setor": "em_operacao",
                "unidades_administrativas": self.ua_atual.pk,
            },
        )
        ids_atu = {row["id"] for row in r_atu.data.get("results", r_atu.data)}
        self.assertIn(self.demanda.pk, ids_atu)

        r_ini = self.client.get(
            "/api/demandas/",
            {
                "fila": "operacionais",
                "escopo_setor": "em_operacao",
                "unidades_administrativas": self.ua_inicial.pk,
            },
        )
        ids_ini = {row["id"] for row in r_ini.data.get("results", r_ini.data)}
        self.assertNotIn(self.demanda.pk, ids_ini)
