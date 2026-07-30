"""Testes de textos padrão de despacho — escopo e API."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Usuario
from core.models_texto_padrao_despacho import (
    CategoriaTextoPadraoDespacho,
    EscopoTextoPadraoDespacho,
    TextoPadraoDespacho,
)
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.texto_padrao_despacho_service import (
    aplicar_placeholders,
    categoria_padrao_criacao,
    categorias_visiveis_usuario,
    contexto_demanda,
    queryset_visivel,
    resolver_escopo_criacao,
)
from core.services.usuario_vinculo_service import (
    PROTOCOLO_SINAPSE_ORGAO_ID,
    UsuarioVinculoService,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class TextoPadraoDespachoServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.ua_a = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor A",
            sigla="SET-A",
        )
        self.ua_b = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            nome="Setor B",
            sigla="SET-B",
        )
        self.protocolo = Usuario.objects.create_user(
            username="proto_tp",
            password="x",
            perfil="PROTOCOLO",
        )
        self.secretaria = Usuario.objects.create_user(
            username="sec_tp",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            first_name="Maria",
            last_name="Secretaria",
        )
        self.gestor_geral = Usuario.objects.create_user(
            username="gg_tp",
            password="x",
            perfil="GESTOR",
            is_staff=True,
        )
        self.gestor_setorial = Usuario.objects.create_user(
            username="gs_tp",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        UsuarioVinculoService().sincronizar_secretaria(
            self.secretaria,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_ids=[self.ua_a.pk],
        )
        UsuarioVinculoService().sincronizar_gestor(
            self.gestor_setorial,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_ids=[self.ua_a.pk],
        )

        self.modelo_geral = TextoPadraoDespacho.objects.create(
            titulo="Geral",
            categoria=CategoriaTextoPadraoDespacho.OPERACIONAL,
            corpo="<p>Texto geral</p>",
            escopo_tipo=EscopoTextoPadraoDespacho.GERAL,
            criado_por=self.gestor_geral,
        )
        self.modelo_protocolo = TextoPadraoDespacho.objects.create(
            titulo="Protocolo",
            categoria=CategoriaTextoPadraoDespacho.PROTOCOLO,
            corpo="<p>Texto protocolo</p>",
            escopo_tipo=EscopoTextoPadraoDespacho.PROTOCOLO,
            sinapse_orgao_id=PROTOCOLO_SINAPSE_ORGAO_ID,
            criado_por=self.protocolo,
        )
        self.modelo_secretaria = TextoPadraoDespacho.objects.create(
            titulo="Secretaria A",
            categoria=CategoriaTextoPadraoDespacho.OPERACIONAL,
            corpo="<p>Texto secretaria</p>",
            escopo_tipo=EscopoTextoPadraoDespacho.SECRETARIA,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            criado_por=self.secretaria,
        )
        self.modelo_secretaria.unidades.set([self.ua_a.pk])
        self.modelo_setorial_b = TextoPadraoDespacho.objects.create(
            titulo="Setorial B",
            categoria=CategoriaTextoPadraoDespacho.OPERACIONAL,
            corpo="<p>Texto setor B</p>",
            escopo_tipo=EscopoTextoPadraoDespacho.SETORIAL,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            criado_por=self.gestor_geral,
        )
        self.modelo_setorial_b.unidades.set([self.ua_b.pk])

    def test_categoria_padrao_por_perfil(self):
        self.assertEqual(
            categoria_padrao_criacao(self.protocolo),
            CategoriaTextoPadraoDespacho.PROTOCOLO,
        )
        self.assertEqual(
            categoria_padrao_criacao(self.secretaria),
            CategoriaTextoPadraoDespacho.OPERACIONAL,
        )

    def test_categorias_visiveis_protocolo(self):
        self.assertEqual(
            categorias_visiveis_usuario(self.protocolo),
            [CategoriaTextoPadraoDespacho.PROTOCOLO],
        )

    def test_categorias_visiveis_secretaria(self):
        self.assertEqual(
            categorias_visiveis_usuario(self.secretaria),
            [CategoriaTextoPadraoDespacho.OPERACIONAL],
        )

    def test_resolver_escopo_protocolo(self):
        escopo = resolver_escopo_criacao(self.protocolo)
        self.assertEqual(escopo["escopo_tipo"], EscopoTextoPadraoDespacho.PROTOCOLO)
        self.assertEqual(escopo["sinapse_orgao_id"], PROTOCOLO_SINAPSE_ORGAO_ID)

    def test_visibilidade_protocolo_so_categoria_protocolo(self):
        ids = set(queryset_visivel(self.protocolo).values_list("pk", flat=True))
        self.assertIn(self.modelo_protocolo.pk, ids)
        self.assertNotIn(self.modelo_secretaria.pk, ids)

    def test_visibilidade_secretaria_operacional(self):
        ids = set(queryset_visivel(self.secretaria).values_list("pk", flat=True))
        self.assertIn(self.modelo_secretaria.pk, ids)
        self.assertNotIn(self.modelo_protocolo.pk, ids)

    def test_aplicar_placeholders(self):
        out = aplicar_placeholders(
            "<p>Ref. {{protocolo_executivo}} — {{autor_nome}}</p>",
            {"protocolo_executivo": "2026-001", "autor_nome": "João"},
        )
        self.assertIn("2026-001", out)
        self.assertIn("João", out)

    def test_contexto_demanda_autor(self):
        from core.models import Demanda

        demanda = Demanda.objects.create(
            titulo="Teste",
            autor=self.secretaria,
            status="EM_EXECUCAO",
        )
        ctx = contexto_demanda(demanda)
        self.assertIn("Maria", ctx["autor_nome"])


class TextoPadraoDespachoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="proto_api",
            password="x",
            perfil="PROTOCOLO",
        )
        self.vereador = Usuario.objects.create_user(
            username="ver_tp",
            password="x",
            perfil="VEREADOR",
        )
        self.client.force_authenticate(user=self.protocolo)

    def test_lista_requer_perfil_operacional(self):
        resp = self.client.get("/api/textos-padrao-despacho/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.vereador)
        resp = self.client.get("/api/textos-padrao-despacho/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_criar_modelo_protocolo_categoria_automatica(self):
        resp = self.client.post(
            "/api/textos-padrao-despacho/",
            {
                "titulo": "Encaminhamento padrão",
                "corpo": "<p>Encaminhamos à secretaria competente.</p>",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["categoria"], "PROTOCOLO")
        self.assertEqual(resp.data["escopo_tipo"], "PROTOCOLO")

    def test_criar_exige_setor_com_multiplos_vinculos(self):
        ua_a = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor A",
            sigla="SET-A",
        )
        ua2 = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor A2",
            sigla="SET-A2",
        )
        secretaria = Usuario.objects.create_user(
            username="sec_multi",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        UsuarioVinculoService().sincronizar_secretaria(
            secretaria,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_ids=[ua_a.pk, ua2.pk],
        )
        self.client.force_authenticate(user=secretaria)
        resp = self.client.post(
            "/api/textos-padrao-despacho/",
            {"titulo": "Sem setor", "corpo": "<p>Texto</p>"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp2 = self.client.post(
            "/api/textos-padrao-despacho/",
            {
                "titulo": "Com setores",
                "corpo": "<p>Texto</p>",
                "unidades_administrativas_ids": [ua_a.pk, ua2.pk],
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp2.data["categoria"], "OPERACIONAL")

    def test_meta_criacao(self):
        resp = self.client.get("/api/textos-padrao-despacho/meta-criacao/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["categoria_padrao"], "PROTOCOLO")

    def test_aplicar_modelo_com_contexto(self):
        modelo = TextoPadraoDespacho.objects.create(
            titulo="Teste aplicar",
            categoria=CategoriaTextoPadraoDespacho.PROTOCOLO,
            corpo="<p>Ref. {{protocolo_executivo}}</p>",
            escopo_tipo=EscopoTextoPadraoDespacho.PROTOCOLO,
            sinapse_orgao_id=PROTOCOLO_SINAPSE_ORGAO_ID,
            criado_por=self.protocolo,
        )
        resp = self.client.post(
            f"/api/textos-padrao-despacho/{modelo.pk}/aplicar/",
            {"contexto": {"protocolo_executivo": "2026-999"}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("2026-999", resp.data["corpo"])
