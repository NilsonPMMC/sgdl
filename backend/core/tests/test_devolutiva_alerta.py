"""Testes de alertas de devolutiva e retry idempotente de assinatura."""

import importlib.util

from django.test import TestCase

from core.models import AssinaturaEletronica, Demanda, Notificacao, Tramitacao, Usuario
from core.services.assinatura_eletronica_service import (
    DECLARACAO_DEVOLUTIVA,
    AssinaturaEletronicaService,
)
from core.services.devolutiva_alerta_service import (
    demanda_ids_alerta_devolutiva,
    registrar_alertas_devolutiva,
    usuario_tem_alerta_devolutiva_leitura,
)
from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin

PARECER = "Resposta final do protocolo ao gabinete parlamentar."


class DevolutivaAlertaTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_alerta", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_alerta", password="x", perfil="PROTOCOLO"
        )
        self.secretaria_a = Usuario.objects.create_user(
            username="sec_a_alerta",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.secretaria_b = Usuario.objects.create_user(
            username="sec_b_alerta",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        self.demanda = Demanda.objects.create(
            titulo="Alerta devolutiva",
            descricao="Teste",
            autor=self.vereador,
            status="AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-03272",
        )
        self.tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DEVOLUTIVA_PROTOCOLO",
            descricao=f"Resposta:\n{PARECER}",
        )

    def test_registrar_alertas_grava_metadata_e_notifica(self):
        registrar_alertas_devolutiva(
            self.demanda,
            self.tram,
            [{"secretaria_id": SINAPSE_ORGAO_B}],
            operador=self.protocolo,
        )
        self.tram.refresh_from_db()
        self.assertTrue(self.tram.metadata.get("devolutiva_leitura"))
        self.assertEqual(
            self.tram.metadata["alerta_destinos"],
            [{"secretaria_id": SINAPSE_ORGAO_B}],
        )
        self.assertEqual(
            Notificacao.objects.filter(
                destinatario=self.secretaria_b, tipo="DEVOLUTIVA"
            ).count(),
            1,
        )
        self.assertIn(self.demanda.pk, demanda_ids_alerta_devolutiva(SINAPSE_ORGAO_B))

    def test_registrar_alertas_com_setor_usa_vinculo_responsavel(self):
        from core.models_unidade_administrativa import (
            UnidadeAdministrativa,
            UnidadeAdministrativaResponsavel,
        )

        setor = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            nome="Setor B",
            sigla="SET-B",
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=setor,
            usuario=self.secretaria_b,
            ativo=True,
        )
        outro = Usuario.objects.create_user(
            username="sec_b2_alerta",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        registrar_alertas_devolutiva(
            self.demanda,
            self.tram,
            [{"secretaria_id": SINAPSE_ORGAO_B, "unidade_administrativa_id": setor.pk}],
            operador=self.protocolo,
        )
        self.assertEqual(
            Notificacao.objects.filter(tipo="DEVOLUTIVA", destinatario=self.secretaria_b).count(),
            1,
        )
        self.assertEqual(
            Notificacao.objects.filter(tipo="DEVOLUTIVA", destinatario=outro).count(),
            0,
        )

    def test_remover_devolutiva_redundante_quando_conclusao_final(self):
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="CONCLUSAO_FINAL",
            descricao="Conclusão final",
            metadata={"parecer": PARECER},
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DEVOLUTIVA_PROTOCOLO",
            descricao="Duplicata",
            metadata={"parecer": PARECER},
        )
        removidas = DevolutivaProtocoloService().remover_devolutiva_redundante(self.demanda)
        self.assertEqual(removidas, 1)
        self.assertFalse(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="DEVOLUTIVA_PROTOCOLO").exists()
        )

    def test_usuario_tem_alerta_leitura_sem_perna_operacional(self):
        registrar_alertas_devolutiva(
            self.demanda,
            self.tram,
            [{"secretaria_id": SINAPSE_ORGAO_B}],
            operador=self.protocolo,
        )
        self.assertTrue(
            usuario_tem_alerta_devolutiva_leitura(self.secretaria_b, self.demanda)
        )
        self.assertFalse(
            usuario_tem_alerta_devolutiva_leitura(self.secretaria_a, self.demanda)
        )

    def test_despachar_com_alerta_via_service(self):
        svc = DevolutivaProtocoloService()
        svc.despachar_devolutiva(
            self.demanda,
            self.protocolo,
            parecer_resposta=PARECER,
            alerta_destinos=[{"secretaria_id": SINAPSE_ORGAO_B}],
        )
        tram = Tramitacao.objects.filter(
            demanda=self.demanda, tipo="DEVOLUTIVA_PROTOCOLO"
        ).latest("id")
        self.assertEqual(tram.metadata.get("alerta_destinos"), [{"secretaria_id": SINAPSE_ORGAO_B}])


class AssinaturaDevolutivaRetryTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_retry", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_retry", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Retry assinatura",
            descricao="Teste",
            autor=self.vereador,
            status="AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-03273",
        )
        self.svc = AssinaturaEletronicaService()

    def test_nova_previa_limpa_assinaturas_orfas(self):
        preview1 = self.svc.preparar_assinatura_despacho_devolutiva(
            self.demanda, parecer_resposta=PARECER
        )
        self.svc._criar_assinatura(
            self.demanda,
            self.protocolo,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento=preview1["hash_documento"],
            declaracao=DECLARACAO_DEVOLUTIVA,
        )
        self.assertEqual(
            AssinaturaEletronica.objects.filter(
                demanda=self.demanda,
                etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
            ).count(),
            1,
        )

        preview2 = self.svc.preparar_assinatura_despacho_devolutiva(
            self.demanda, parecer_resposta="Outra resposta válida ao vereador."
        )
        self.assertEqual(
            AssinaturaEletronica.objects.filter(
                demanda=self.demanda,
                etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
            ).count(),
            0,
        )
        self.assertNotEqual(preview1["hash_documento"], preview2["hash_documento"])

    def test_criar_assinatura_idempotente_mesmo_hash(self):
        preview = self.svc.preparar_assinatura_despacho_devolutiva(
            self.demanda, parecer_resposta=PARECER
        )
        ass1 = self.svc._criar_assinatura(
            self.demanda,
            self.protocolo,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento=preview["hash_documento"],
            declaracao=DECLARACAO_DEVOLUTIVA,
        )
        ass2 = self.svc._criar_assinatura(
            self.demanda,
            self.protocolo,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento=preview["hash_documento"],
            declaracao=DECLARACAO_DEVOLUTIVA,
        )
        self.assertEqual(ass1.pk, ass2.pk)
        self.assertEqual(
            AssinaturaEletronica.objects.filter(
                demanda=self.demanda,
                etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
                papel=AssinaturaEletronica.PAPEL_OPERADOR,
            ).count(),
            1,
        )
