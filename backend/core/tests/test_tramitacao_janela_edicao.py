"""Janela temporal de correção de tramitações/despachos após registro."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ClusterExecucao, Demanda, Tramitacao
from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService

User = get_user_model()


class TramitacaoJanelaEdicaoServiceTests(TestCase):
    def setUp(self):
        self.vereador = User.objects.create_user(
            username="ver_janela", password="x", perfil="VEREADOR"
        )
        self.protocolo = User.objects.create_user(
            username="prot_janela", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Demanda janela",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
        )

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_abre_janela_ao_criar_despacho(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Texto inicial",
        )
        tram.refresh_from_db()
        self.assertIsNotNone(tram.editavel_ate)
        self.assertTrue(TramitacaoJanelaEdicaoService.tramitacao_editavel(tram))
        self.assertGreater(TramitacaoJanelaEdicaoService.segundos_restantes(tram), 0)

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_nao_abre_janela_para_status_update(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="STATUS_UPDATE",
            descricao="Status automático",
        )
        tram.refresh_from_db()
        self.assertIsNone(tram.editavel_ate)

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_nao_abre_janela_para_staging(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Rascunho",
            metadata={"staging": True},
        )
        tram.refresh_from_db()
        self.assertIsNone(tram.editavel_ate)

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_abre_janela_para_aguardando_gestor(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Despacho pendente gestor",
            metadata={"aguardando_validacao_gestor": True, "etapa": "DESPACHO_PROTOCOLO"},
        )
        tram.refresh_from_db()
        self.assertIsNotNone(tram.editavel_ate)
        self.assertTrue(TramitacaoJanelaEdicaoService.tramitacao_aguardando_gestor(tram))
        self.assertTrue(TramitacaoJanelaEdicaoService.tramitacao_editavel(tram))
        self.assertGreater(TramitacaoJanelaEdicaoService.segundos_restantes(tram), 0)
        self.assertTrue(
            TramitacaoJanelaEdicaoService.usuario_pode_corrigir(self.protocolo, tram)
        )

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_expira_apos_prazo(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="COMENTARIO",
            descricao="Andamento",
        )
        tram.editavel_ate = timezone.now() - timedelta(seconds=1)
        tram.save(update_fields=["editavel_ate"])
        self.assertFalse(TramitacaoJanelaEdicaoService.tramitacao_editavel(tram))
        self.assertFalse(
            TramitacaoJanelaEdicaoService.usuario_pode_corrigir(self.protocolo, tram)
        )

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=0)
    def test_janela_desabilitada_quando_zero(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Sem janela",
        )
        tram.refresh_from_db()
        self.assertIsNone(tram.editavel_ate)


class TramitacaoJanelaEdicaoAPITests(APITestCase):
    def setUp(self):
        self.vereador = User.objects.create_user(
            username="ver_janela_api", password="x", perfil="VEREADOR"
        )
        self.protocolo = User.objects.create_user(
            username="prot_janela_api", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Demanda API janela",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
        )

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_patch_descricao_dentro_da_janela(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Texto original",
        )
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.patch(
            f"/api/tramitacoes/{tram.pk}/",
            {"descricao": "Texto corrigido"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tram.refresh_from_db()
        self.assertEqual(tram.descricao, "Texto corrigido")
        self.assertIn("pode_editar", resp.data)
        self.assertGreater(resp.data.get("segundos_restantes_edicao", 0), 50)

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_patch_reinicia_janela_de_edicao(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Texto original",
        )
        tram.editavel_ate = timezone.now() + timedelta(seconds=5)
        tram.save(update_fields=["editavel_ate"])
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.patch(
            f"/api/tramitacoes/{tram.pk}/",
            {"descricao": "Texto corrigido com janela reiniciada"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreater(resp.data.get("segundos_restantes_edicao", 0), 50)

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_patch_sincroniza_payload_pendente_gestor(self):
        from core.models_assinatura_eletronica import (
            AssinaturaEletronica,
            AssinaturaValidacaoGestor,
        )

        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Texto original",
            metadata={"aguardando_validacao_gestor": True, "etapa": "DESPACHO_PROTOCOLO"},
        )
        payload = {"texto_despacho": "Texto original", "destinos": []}
        validacao = AssinaturaValidacaoGestor.objects.create(
            demanda=self.demanda,
            tramitacao=tram,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            tipo_gestor=AssinaturaValidacaoGestor.TIPO_GESTOR_PROTOCOLO,
            hash_documento="abc123",
            payload=payload,
            operador=self.protocolo,
            status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
        )
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.patch(
            f"/api/tramitacoes/{tram.pk}/",
            {"descricao": "Texto corrigido pendente"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        validacao.refresh_from_db()
        self.assertEqual(validacao.payload.get("texto_despacho"), "Texto corrigido pendente")

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_patch_bloqueado_apos_expirar(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Texto original",
        )
        tram.editavel_ate = timezone.now() - timedelta(seconds=1)
        tram.save(update_fields=["editavel_ate"])
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.patch(
            f"/api/tramitacoes/{tram.pk}/",
            {"descricao": "Tarde demais"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_delete_dentro_da_janela(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="COMENTARIO",
            descricao="Desfazer",
        )
        tram_id = tram.pk
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.delete(f"/api/tramitacoes/{tram_id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Tramitacao.objects.filter(pk=tram_id).exists())

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_sincroniza_copia_cluster_no_patch(self):
        cluster = ClusterExecucao.objects.create(
            titulo="Super OS janela",
            protocolo_super_os="SUPER-JANELA",
        )
        lider = Demanda.objects.create(
            titulo="Líder janela",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            cluster=cluster,
            sinapse_orgao_lider_id=1,
        )
        irma = Demanda.objects.create(
            titulo="Irmã janela",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            cluster=cluster,
        )
        tram = Tramitacao.objects.create(
            demanda=lider,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Original líder",
        )
        copia = Tramitacao(
            demanda=irma,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="[Super OS] Original líder",
            metadata={"propagacao_cluster": True, "tramitacao_origem_id": tram.pk},
        )
        copia._propagando_cluster_tramitacao = True  # noqa: SLF001
        copia.save()
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.patch(
            f"/api/tramitacoes/{tram.pk}/",
            {"descricao": "Corrigido líder"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        copia.refresh_from_db()
        self.assertEqual(copia.descricao, "[Super OS] Corrigido líder")

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_delete_remove_assinatura_scatter_sem_integrity_error(self):
        from core.models_assinatura_eletronica import AssinaturaEletronica
        from core.models_no_operacional import NoOperacional, StatusNoOperacional

        no = NoOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=9001,
            status=StatusNoOperacional.ABERTO,
        )
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="OPERACAO_NO",
            descricao="Encerramento teste",
            metadata={"acao_no": "ENCERRAR", "no_id": no.pk},
        )
        AssinaturaEletronica.objects.create(
            demanda=self.demanda,
            tramitacao=tram,
            usuario=self.protocolo,
            etapa=AssinaturaEletronica.ETAPA_OPERACAO_SCATTER,
            papel=AssinaturaEletronica.PAPEL_CHEFIA_SETOR,
            hash_documento="a" * 64,
            hash_assinatura="b" * 64,
            codigo_validacao="c" * 32,
        )
        AssinaturaEletronica.objects.create(
            demanda=self.demanda,
            tramitacao=None,
            usuario=self.protocolo,
            etapa=AssinaturaEletronica.ETAPA_OPERACAO_SCATTER,
            papel=AssinaturaEletronica.PAPEL_CHEFIA_SETOR,
            hash_documento="d" * 64,
            hash_assinatura="e" * 64,
            codigo_validacao="f" * 32,
        )
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.delete(f"/api/tramitacoes/{tram.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AssinaturaEletronica.objects.filter(tramitacao_id=tram.pk).exists())
        self.assertEqual(
            AssinaturaEletronica.objects.filter(
                demanda=self.demanda,
                etapa=AssinaturaEletronica.ETAPA_OPERACAO_SCATTER,
                papel=AssinaturaEletronica.PAPEL_CHEFIA_SETOR,
                tramitacao__isnull=True,
            ).count(),
            1,
        )

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_delete_reverte_encerramento_no_scatter(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional

        no = NoOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=9001,
            status=StatusNoOperacional.CONCLUIDO,
        )
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="OPERACAO_NO",
            descricao="Encerramento revertível",
            metadata={"acao_no": "ENCERRAR", "no_id": no.pk},
        )
        no.encerramento_tramitacao = tram
        no.save(update_fields=["encerramento_tramitacao"])
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.delete(f"/api/tramitacoes/{tram.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        no.refresh_from_db()
        self.assertEqual(no.status, StatusNoOperacional.ABERTO)
        self.assertIsNone(no.encerramento_tramitacao_id)

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_delete_reverte_despacho_protocolo(self):
        demanda = Demanda.objects.create(
            titulo="Protocolo janela",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
        )
        tram = Tramitacao.objects.create(
            demanda=demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Despacho protocolo",
            metadata={"etapa": "DESPACHO_PROTOCOLO"},
        )
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.delete(f"/api/tramitacoes/{tram.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, "AGUARDANDO_PROTOCOLO")

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_delete_remove_nos_filhos_criados_por_despacho_scatter(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional

        no_pai = NoOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=9001,
            status=StatusNoOperacional.ABERTO,
        )
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="OPERACAO_NO",
            descricao="Despacho scatter",
            metadata={
                "acao_no": "DESPACHAR",
                "no_id": no_pai.pk,
                "no_filhos_ids": [],
            },
        )
        filho = NoOperacional.objects.create(
            demanda=self.demanda,
            parent=no_pai,
            sinapse_orgao_id=9002,
            status=StatusNoOperacional.ABERTO,
            metadata={"origem_acao": "DESPACHAR", "tramitacao_despacho_id": tram.pk},
        )
        enc = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="OPERACAO_NO",
            descricao="Encaminhamento",
            metadata={"acao_no": "ENCAMINHAMENTO_NO", "no_id": filho.pk},
        )
        filho.abertura_tramitacao = enc
        filho.save(update_fields=["abertura_tramitacao"])
        tram.metadata["no_filhos_ids"] = [filho.pk]
        tram.save(update_fields=["metadata"])

        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.delete(f"/api/tramitacoes/{tram.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(NoOperacional.objects.filter(pk=filho.pk).exists())
        self.assertFalse(Tramitacao.objects.filter(pk=enc.pk).exists())

    @override_settings(DESPACHO_JANELA_EDICAO_SEGUNDOS=60)
    def test_delete_conclusao_final_reverte_estado_e_encerramento(self):
        from core.models_operacional import ESTADO_AGUARDANDO_CONCLUSAO_FINAL

        demanda = Demanda.objects.create(
            titulo="Conclusão janela",
            descricao="x",
            autor=self.vereador,
            status="FINALIZADO",
            fluxo_roteamento="TRANSVERSAL",
        )
        tram = Tramitacao.objects.create(
            demanda=demanda,
            responsavel=self.protocolo,
            tipo="CONCLUSAO_FINAL",
            descricao="Conclusão final",
            metadata={"parecer": "Ok"},
        )
        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=self.protocolo,
            tipo="ENCERRAMENTO_DEVOLUTIVA",
            descricao="Auto encerramento",
        )
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.delete(f"/api/tramitacoes/{tram.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, ESTADO_AGUARDANDO_CONCLUSAO_FINAL)
        self.assertFalse(
            demanda.tramitacoes.filter(tipo="ENCERRAMENTO_DEVOLUTIVA").exists()
        )
