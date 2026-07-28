"""Testes de assinatura eletrônica no envio oficial."""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Tramitacao
from core.models_assinatura_eletronica import AssinaturaEletronica, AssinaturaPendingAcao, AssinaturaValidacaoGestor
from core.services.assinatura_eletronica_service import (
    DECLARACAO_DESPACHO,
    DECLARACAO_ENVIO,
    DECLARACAO_GESTOR_PROTOCOLO,
    AssinaturaEletronicaService,
)

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class AssinaturaEletronicaServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = _legacy.Usuario.objects.create_user(
            username="ver_assin", password="x", perfil="VEREADOR"
        )
        self.demanda = Demanda.objects.create(
            titulo="Ofício teste",
            descricao="<p>Solicito reparo.</p>",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_registrar_assinatura_exige_declaracao(self):
        svc = AssinaturaEletronicaService()
        with self.assertRaises(ValueError):
            svc.registrar_assinatura(
                self.demanda,
                self.vereador,
                hash_documento_informado="",
                declaracao="sim",
            )

    def test_preview_nao_cria_anexo(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        self.assertTrue(preview["preview_pdf_disponivel"])
        self.assertEqual(self.demanda.anexos.count(), 0)

    def test_pending_despacho_persiste_no_banco(self):
        svc = AssinaturaEletronicaService()
        preview = svc.preparar_assinatura_despacho_inicial(
            self.demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            unidade_administrativa_id=None,
            protocolo_executivo="2026/0001",
        )
        row = AssinaturaPendingAcao.objects.get(
            demanda=self.demanda,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
        )
        self.assertEqual(row.hash_documento, preview["hash_documento"])
        pending = svc._validar_hash_pending(
            int(self.demanda.pk),
            AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            preview["hash_documento"],
        )
        self.assertEqual(pending["payload"]["protocolo_executivo"], "2026/0001")

    def test_registrar_assinatura_um_unico_anexo(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        oficios = self.demanda.anexos.filter(
            descricao__icontains="Ofício assinado eletronicamente"
        )
        self.assertEqual(oficios.count(), 1)

    def test_registrar_assinatura_cria_registro(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        assinatura = AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        self.assertEqual(len(assinatura.hash_documento), 64)
        self.assertEqual(len(assinatura.codigo_validacao), 32)

    def test_validar_codigo(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        assinatura = AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        payload = AssinaturaEletronicaService().validar_codigo(assinatura.codigo_validacao)
        self.assertTrue(payload["valido"])
        self.assertEqual(payload["demanda_id"], self.demanda.pk)

    def test_cargo_signatario_prefere_usuario_cargo(self):
        self.vereador.cargo = "Vereador Municipal"
        self.vereador.save(update_fields=["cargo"])
        from core.services.assinatura_eletronica_service import cargo_signatario

        self.assertEqual(
            cargo_signatario(self.vereador, AssinaturaEletronica.PAPEL_OPERADOR),
            "Vereador Municipal",
        )

    def test_listar_gestores_inclui_cargo(self):
        gestor = _legacy.Usuario.objects.create_user(
            username="gest_cargo",
            password="x",
            perfil="PROTOCOLO",
            cargo="Chefe de Seção de Protocolo",
        )
        lista = AssinaturaEletronicaService().listar_gestores_protocolo()
        item = next((g for g in lista if g["id"] == gestor.pk), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["cargo"], "Chefe de Seção de Protocolo")

    def test_validar_codigo_inclui_cargo(self):
        self.vereador.cargo = "Vereador"
        self.vereador.save(update_fields=["cargo"])
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        assinatura = AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        payload = AssinaturaEletronicaService().validar_codigo(assinatura.codigo_validacao)
        self.assertEqual(payload["cargo"], "Vereador")

    def test_resumo_assinaturas_demanda(self):
        svc = AssinaturaEletronicaService()
        operador = _legacy.Usuario.objects.create_user(
            username="op_res", password="x", perfil="PROTOCOLO"
        )
        gestor = _legacy.Usuario.objects.create_user(
            username="gest_res", password="x", perfil="PROTOCOLO"
        )
        preview = svc.preparar_preview_envio(self.demanda)
        svc.registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        resumo = svc.resumo_assinaturas_demanda(self.demanda)
        self.assertTrue(resumo["envio_oficio_assinado"])
        self.assertFalse(resumo["despacho_inicial_assinado"])

        preview_d = svc.preparar_assinatura_despacho_inicial(
            self.demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            unidade_administrativa_id=None,
            protocolo_executivo="2026/0099",
        )
        svc.registrar_assinaturas_despacho_inicial(
            self.demanda,
            operador,
            hash_documento=preview_d["hash_documento"],
            declaracao_operador=DECLARACAO_DESPACHO,
            contexto_operacao={
                "destinos": [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_id": None}],
                "texto_despacho": "Despacho teste resumo.",
            },
        )
        resumo2 = svc.resumo_assinaturas_demanda(self.demanda)
        self.assertFalse(resumo2["despacho_inicial_assinado"])
        self.assertTrue(resumo2["despacho_inicial_pendente_gestor"])

        validacao = AssinaturaValidacaoGestor.objects.get(
            demanda=self.demanda,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
        )
        gestor_sgac = _legacy.Usuario.objects.create_user(
            username="gest_res_sgac", password="x", perfil="GESTOR"
        )
        from core.models_unidade_administrativa import UnidadeAdministrativaResponsavel
        from core.services.usuario_vinculo_service import PROTOCOLO_UNIDADE_PK

        UnidadeAdministrativaResponsavel.objects.create(
            unidade_id=PROTOCOLO_UNIDADE_PK,
            usuario=gestor_sgac,
            ativo=True,
        )
        svc.registrar_validacao_gestor(
            validacao,
            gestor_sgac,
            hash_documento=preview_d["hash_documento"],
            declaracao_gestor=DECLARACAO_GESTOR_PROTOCOLO,
        )
        resumo3 = svc.resumo_assinaturas_demanda(self.demanda)
        self.assertTrue(resumo3["despacho_inicial_assinado"])

    def test_liberar_assinaturas_despacho_inicial(self):
        self.demanda.status = "AGUARDANDO_PROTOCOLO"
        self.demanda.save(update_fields=["status"])
        svc = AssinaturaEletronicaService()
        operador = _legacy.Usuario.objects.create_user(
            username="op_lib", password="x", perfil="PROTOCOLO"
        )
        gestor = _legacy.Usuario.objects.create_user(
            username="gest_lib", password="x", perfil="PROTOCOLO"
        )
        preview_d = svc.preparar_assinatura_despacho_inicial(
            self.demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            unidade_administrativa_id=None,
            protocolo_executivo="2026/0099",
        )
        svc.registrar_assinaturas_despacho_inicial(
            self.demanda,
            operador,
            hash_documento=preview_d["hash_documento"],
            declaracao_operador=DECLARACAO_DESPACHO,
            contexto_operacao={
                "destinos": [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_id": None}],
                "texto_despacho": "Despacho teste resumo.",
            },
        )
        self.assertEqual(
            AssinaturaEletronica.objects.filter(
                demanda=self.demanda,
                etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            ).count(),
            1,
        )
        removed = svc.liberar_assinaturas_despacho_inicial(self.demanda)
        self.assertEqual(removed, 1)
        self.assertFalse(svc.possui_assinatura_despacho_inicial(self.demanda))

    def test_preparar_redespacho_limpa_rastros_orfaos(self):
        from core.services.demanda_despacho_service import DemandaDespachoService

        self.demanda.status = "AGUARDANDO_PROTOCOLO"
        self.demanda.protocolo_executivo = "2026-0100"
        self.demanda.fluxo_roteamento = "FLUXO_DIRETO"
        self.demanda.save(
            update_fields=["status", "protocolo_executivo", "fluxo_roteamento"]
        )
        svc = AssinaturaEletronicaService()
        operador = _legacy.Usuario.objects.create_user(
            username="op_red", password="x", perfil="PROTOCOLO"
        )
        gestor = _legacy.Usuario.objects.create_user(
            username="gest_red", password="x", perfil="PROTOCOLO"
        )
        preview_d = svc.preparar_assinatura_despacho_inicial(
            self.demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            unidade_administrativa_id=None,
            protocolo_executivo="2026/0100",
        )
        svc.registrar_assinaturas_despacho_inicial(
            self.demanda,
            operador,
            hash_documento=preview_d["hash_documento"],
            declaracao_operador=DECLARACAO_DESPACHO,
            contexto_operacao={
                "destinos": [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_id": None}],
                "texto_despacho": "Despacho teste resumo.",
            },
        )
        DemandaDespachoService().preparar_redespacho_protocolo(self.demanda)
        self.demanda.refresh_from_db()
        self.assertFalse(svc.possui_assinatura_despacho_inicial(self.demanda))
        self.assertIsNone(self.demanda.protocolo_executivo)
        self.assertEqual(self.demanda.fluxo_roteamento, "")


class EnviarOficialAssinaturaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = _legacy.Usuario.objects.create_user(
            username="ver_env_ass", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.vereador)
        self.demanda = Demanda.objects.create(
            titulo="Enviar assinado",
            descricao="<p>Texto do ofício.</p>",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_enviar_sem_declaracao_falha(self):
        r = self.client.post(f"/api/demandas/{self.demanda.pk}/enviar/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enviar_com_assinatura_protocola(self):
        preview = self.client.get(
            f"/api/demandas/{self.demanda.pk}/preview-envio-oficial/"
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        r = self.client.post(
            f"/api/demandas/{self.demanda.pk}/enviar/",
            {
                "declaracao": DECLARACAO_ENVIO,
                "hash_documento": preview.data["hash_documento"],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_PROTOCOLO")
        self.assertTrue(self.demanda.protocolo_legislativo)
        self.assertTrue(
            AssinaturaEletronica.objects.filter(
                demanda=self.demanda, etapa=AssinaturaEletronica.ETAPA_ENVIO_OFICIO
            ).exists()
        )
        self.assertTrue(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="ENVIO_OFICIAL").exists()
        )

    def test_validar_assinatura_publico(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        assinatura = AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        from rest_framework.test import APIClient

        public_client = APIClient()
        r = public_client.get(f"/api/v1/validar-assinatura/{assinatura.codigo_validacao}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["valido"])


class EnviarLoteAssinaturaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = _legacy.Usuario.objects.create_user(
            username="ver_lote", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.vereador)
        self.d1 = Demanda.objects.create(
            titulo="Lote A",
            descricao="<p>A</p>",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.d2 = Demanda.objects.create(
            titulo="Lote B",
            descricao="<p>B</p>",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_preview_envio_lote(self):
        r = self.client.post(
            "/api/demandas/preview-envio-lote/",
            {"demanda_ids": [self.d1.pk, self.d2.pk]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["total"], 2)
        self.assertEqual(len(r.data["itens"]), 2)

    def test_enviar_lote_assina_todos(self):
        preview = self.client.post(
            "/api/demandas/preview-envio-lote/",
            {"demanda_ids": [self.d1.pk, self.d2.pk]},
            format="json",
        )
        hashes = [
            {"demanda_id": item["demanda_id"], "hash_documento": item["hash_documento"]}
            for item in preview.data["itens"]
        ]
        r = self.client.post(
            "/api/demandas/enviar-lote/",
            {
                "demanda_ids": [self.d1.pk, self.d2.pk],
                "declaracao": DECLARACAO_ENVIO,
                "hashes": hashes,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["total"], 2)
        self.d1.refresh_from_db()
        self.d2.refresh_from_db()
        self.assertEqual(self.d1.status, "AGUARDANDO_PROTOCOLO")
        self.assertEqual(self.d2.status, "AGUARDANDO_PROTOCOLO")
        self.assertEqual(AssinaturaEletronica.objects.filter(demanda__in=[self.d1, self.d2]).count(), 2)
