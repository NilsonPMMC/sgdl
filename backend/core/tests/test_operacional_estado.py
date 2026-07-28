"""Testes da máquina de estados operacional — Portal dos Vereadores."""

import importlib.util

from django.test import TestCase

from core.models import ClusterExecucao, Demanda, Tramitacao, Usuario
from core.models_operacional import (
    FluxoRoteamento,
    ModoEntradaProcesso,
    OrquestradorConclusao,
    PerfilProcesso,
    TipoEntrada,
)
from core.services.demanda_despacho_service import DemandaDespachoService
from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService
from core.services.operacional_estado_service import (
    OperacionalEstadoError,
    OperacionalEstadoService,
    OperacionalPermissaoError,
)

PARECER = "Parecer operacional com conteúdo suficiente para validação."

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class OperacionalEstadoServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.svc = OperacionalEstadoService()
        self.vereador = Usuario.objects.create_user(
            username="ver_op", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_op", password="x", perfil="PROTOCOLO"
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_op_a",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.sec_b = Usuario.objects.create_user(
            username="sec_op_b",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )

    def _demanda_carta(self, **kwargs):
        defaults = dict(
            titulo="Carta serviço",
            descricao="Relato",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            origem_vinculo=Demanda.ORIGEM_VINCULO_CARTA,
            protocolo_legislativo="OP-001",
        )
        defaults.update(kwargs)
        return Demanda.objects.create(**defaults)

    def _demanda_tendencia(self, **kwargs):
        return self._demanda_carta(
            sinapse_servico_id=None,
            origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA,
            **kwargs,
        )

    def test_classificar_entrada_carta_vs_tendencia(self):
        carta = self._demanda_carta()
        tendencia = self._demanda_tendencia()
        self.assertEqual(self.svc.classificar_entrada(carta), TipoEntrada.CARTA_SERVICO)
        self.assertEqual(self.svc.classificar_entrada(tendencia), TipoEntrada.TENDENCIA)

    def test_resolver_fluxo_por_destinos(self):
        self.assertEqual(
            self.svc.resolver_fluxo_roteamento(total_destinos=1),
            FluxoRoteamento.FLUXO_DIRETO,
        )
        self.assertEqual(
            self.svc.resolver_fluxo_roteamento(total_destinos=3),
            FluxoRoteamento.FLUXO_TRANSVERSAL,
        )

    def test_triagem_protocolo_negada_para_secretaria(self):
        demanda = self._demanda_carta()
        with self.assertRaises(OperacionalPermissaoError):
            self.svc.validar_triagem_protocolo(demanda, self.sec_a)

    def test_despacho_multiplo_registra_triagem_e_fluxo_transversal(self):
        demanda = self._demanda_carta()
        resultado = DemandaDespachoService().despachar_multiplo(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}, {"secretaria_id": SINAPSE_ORGAO_B}],
            usuario=self.protocolo,
            texto_despacho="Despacho transversal para secretarias integradas.",
        )
        principal = resultado["demanda"]
        principal.refresh_from_db()
        self.assertEqual(principal.fluxo_roteamento, FluxoRoteamento.FLUXO_TRANSVERSAL)
        self.assertEqual(principal.sinapse_orgao_lider_id, SINAPSE_ORGAO_A)
        self.assertTrue(
            Tramitacao.objects.filter(
                demanda=principal, tipo="DESPACHO"
            ).exists()
        )
        self.assertFalse(
            Tramitacao.objects.filter(
                demanda=principal, tipo="TRIAGEM_PROTOCOLO"
            ).exists()
        )
        clone = resultado["demandas_desdobradas"]
        self.assertEqual(len(clone), 0)
        from core.models_perna_operacional import PernaOperacional

        pernas = PernaOperacional.objects.filter(demanda=principal)
        self.assertEqual(pernas.count(), 2)
        self.assertEqual(
            set(pernas.values_list("sinapse_orgao_id", flat=True)),
            {SINAPSE_ORGAO_A, SINAPSE_ORGAO_B},
        )

    def test_conclusao_tecnica_bloqueada_em_fluxo_transversal(self):
        demanda = self._demanda_carta(
            status="EM_EXECUCAO",
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
        )
        with self.assertRaises(OperacionalPermissaoError):
            self.svc.validar_conclusao_tecnica(demanda, self.sec_a, parecer=PARECER)

    def test_conclusao_parcial_avanca_quando_todas_pernas_concluem(self):
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        lider = Demanda.objects.create(
            titulo="Líder",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
        )
        perna_a = PernaOperacional.objects.create(
            demanda=lider,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            ordem=1,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )
        perna_b = PernaOperacional.objects.create(
            demanda=lider,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            ordem=2,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )

        self.svc.aplicar_conclusao_parcial(
            lider, self.sec_b, parecer=PARECER, perna_id=perna_b.pk
        )
        lider.refresh_from_db()
        self.assertEqual(lider.status, "EM_EXECUCAO")

        resultado = self.svc.aplicar_conclusao_parcial(
            lider, self.sec_a, parecer=PARECER, perna_id=perna_a.pk
        )
        lider.refresh_from_db()
        self.assertTrue(resultado["processo_avancou"])
        self.assertEqual(lider.status, "AGUARDANDO_DEVOLUTIVA_PROTOCOLO")
        self.assertTrue(resultado["historico_tecnico"]["pronto_conclusao_final"])

    def test_conclusao_parcial_uma_perna_nao_avanca_processo(self):
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        lider = Demanda.objects.create(
            titulo="Líder",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
        )
        perna_a = PernaOperacional.objects.create(
            demanda=lider,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            ordem=1,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )
        perna_b = PernaOperacional.objects.create(
            demanda=lider,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            ordem=2,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )

        resultado = self.svc.aplicar_conclusao_parcial(
            lider, self.sec_b, parecer=PARECER, perna_id=perna_b.pk
        )
        lider.refresh_from_db()
        perna_a.refresh_from_db()
        perna_b.refresh_from_db()

        self.assertFalse(resultado["processo_avancou"])
        self.assertEqual(lider.status, "EM_EXECUCAO")
        self.assertEqual(perna_b.status, StatusPernaOperacional.CONCLUIDA)
        self.assertEqual(perna_a.status, StatusPernaOperacional.EM_EXECUCAO)
        self.assertEqual(len(resultado["pendencias_parciais"]), 1)
        self.assertEqual(
            int(resultado["pendencias_parciais"][0]["sinapse_orgao_id"]),
            SINAPSE_ORGAO_A,
        )

    def test_repara_status_prematuro_com_lider_pendente(self):
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        lider = Demanda.objects.create(
            titulo="Líder",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
        )
        PernaOperacional.objects.create(
            demanda=lider,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            ordem=1,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )
        PernaOperacional.objects.create(
            demanda=lider,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            ordem=2,
            status=StatusPernaOperacional.CONCLUIDA,
        )

        estado = self.svc.montar_estado_operacional(lider, self.sec_a)
        lider.refresh_from_db()

        self.assertEqual(lider.status, "EM_EXECUCAO")
        self.assertFalse(estado["historico_tecnico"]["pronto_conclusao_final"])

    def test_devolucao_secretaria_retorna_aguardando_protocolo(self):
        from core.models_assinatura_eletronica import AssinaturaEletronica
        from core.services.assinatura_eletronica_service import (
            DECLARACAO_DESPACHO,
            DECLARACAO_GESTOR_PROTOCOLO,
            AssinaturaEletronicaService,
        )

        demanda = self._demanda_carta(
            status="EM_EXECUCAO",
            fluxo_roteamento=FluxoRoteamento.FLUXO_DIRETO,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0100",
        )
        gestor = Usuario.objects.create_user(
            username="gest_dev", password="x", perfil="PROTOCOLO"
        )
        preview = AssinaturaEletronicaService().preparar_assinatura_despacho_inicial(
            demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            unidade_administrativa_id=None,
            protocolo_executivo="2026-0100",
        )
        AssinaturaEletronicaService().registrar_assinaturas_despacho_inicial(
            demanda,
            self.protocolo,
            hash_documento=preview["hash_documento"],
            declaracao_operador=DECLARACAO_DESPACHO,
            gestor_usuario_id=gestor.pk,
            declaracao_gestor=DECLARACAO_GESTOR_PROTOCOLO,
        )
        self.svc.aplicar_devolucao(
            demanda, self.sec_a, justificativa="Necessário reencaminhar para outro setor."
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, "AGUARDANDO_PROTOCOLO")
        self.assertEqual(demanda.fluxo_roteamento, "")
        self.assertIsNone(demanda.protocolo_executivo)
        self.assertFalse(
            AssinaturaEletronica.objects.filter(
                demanda=demanda,
                etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            ).exists()
        )
        self.assertTrue(
            Tramitacao.objects.filter(demanda=demanda, tipo="DEVOLUCAO").exists()
        )

    def test_recusa_protocolo_tendencia(self):
        demanda = self._demanda_tendencia()
        self.svc.aplicar_recusa_protocolo(
            demanda, self.protocolo, parecer="Demanda fora da competência municipal."
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, "DEVOLVIDO_VEREADOR")
        self.assertTrue(
            Tramitacao.objects.filter(demanda=demanda, tipo="RECUSA_PROTOCOLO").exists()
        )

    def test_conclusao_final_exclusiva_protocolo(self):
        demanda = self._demanda_carta(
            status="AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
            fluxo_roteamento=FluxoRoteamento.FLUXO_DIRETO,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0101",
        )
        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=self.sec_a,
            tipo="CONCLUSAO_TECNICA",
            descricao=f"Parecer:\n{PARECER}",
            metadata={"parecer": PARECER},
        )
        with self.assertRaises(OperacionalPermissaoError):
            self.svc.validar_conclusao_final(demanda, self.sec_a, parecer=PARECER)

        self.svc.aplicar_conclusao_final(demanda, self.protocolo, parecer=PARECER)
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, "FINALIZADO")
        self.assertTrue(
            Tramitacao.objects.filter(demanda=demanda, tipo="CONCLUSAO_FINAL").exists()
        )
        self.assertTrue(
            Tramitacao.objects.filter(demanda=demanda, tipo="ENCERRAMENTO_DEVOLUTIVA").exists()
        )

    def test_ciclo_devolutiva_legado_sem_fluxo_roteamento(self):
        demanda = Demanda.objects.create(
            titulo="Legado",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0099",
            protocolo_legislativo="LEG-0099",
        )
        dev_svc = DevolutivaProtocoloService()
        dev_svc.solicitar_devolutiva(demanda, self.sec_a, parecer_operacional=PARECER)
        dev_svc.despachar_devolutiva(
            demanda, self.protocolo, parecer_resposta="Resposta protocolo ao vereador."
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, "FINALIZADO")

    def test_solicitar_devolutiva_bloqueada_em_transversal(self):
        demanda = Demanda.objects.create(
            titulo="Transversal",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
        )
        with self.assertRaises(ValueError):
            DevolutivaProtocoloService().solicitar_devolutiva(
                demanda, self.sec_a, parecer_operacional=PARECER
            )

    def test_resolver_perfil_processo_matriz_cenarios(self):
        self.assertEqual(
            PerfilProcesso.resolver(
                modo_entrada=ModoEntradaProcesso.OFICIO_UNICO,
                fluxo_roteamento=FluxoRoteamento.FLUXO_DIRETO,
                orquestrador_conclusao=OrquestradorConclusao.SECRETARIA_LIDER,
            ),
            PerfilProcesso.CENARIO_4,
        )
        self.assertEqual(
            PerfilProcesso.resolver(
                modo_entrada=ModoEntradaProcesso.OFICIO_UNICO,
                fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
                orquestrador_conclusao=OrquestradorConclusao.SECRETARIA_LIDER,
            ),
            PerfilProcesso.CENARIO_2,
        )
        self.assertEqual(
            PerfilProcesso.resolver(
                modo_entrada=ModoEntradaProcesso.OFICIO_UNICO,
                fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
                orquestrador_conclusao=OrquestradorConclusao.PROTOCOLO,
            ),
            PerfilProcesso.CENARIO_3,
        )
        self.assertEqual(
            PerfilProcesso.resolver(
                modo_entrada=ModoEntradaProcesso.CLUSTER_SUPER_OS,
                fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
                orquestrador_conclusao=OrquestradorConclusao.SECRETARIA_LIDER,
            ),
            PerfilProcesso.CENARIO_1,
        )
        self.assertEqual(
            PerfilProcesso.resolver(
                modo_entrada=ModoEntradaProcesso.CLUSTER_SUPER_OS,
                fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
                orquestrador_conclusao=OrquestradorConclusao.PROTOCOLO,
            ),
            PerfilProcesso.CENARIO_5,
        )

    def test_despacho_multiplo_entra_em_operacao_scatter(self):
        demanda = self._demanda_carta()
        resultado = DemandaDespachoService().despachar_multiplo(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}, {"secretaria_id": SINAPSE_ORGAO_B}],
            usuario=self.protocolo,
            texto_despacho="Despacho inicial do protocolo para secretarias envolvidas.",
        )
        principal = resultado["demanda"]
        principal.refresh_from_db()
        self.assertEqual(principal.modo_entrada_processo, ModoEntradaProcesso.OFICIO_UNICO)
        self.assertEqual(principal.orquestrador_conclusao, "")
        self.assertTrue(principal.inicio_execucao_automatico)
        self.assertEqual(principal.status, "EM_EXECUCAO")
        self.assertEqual(principal.nos_ativos, 2)
        tram = principal.tramitacoes.filter(tipo="DESPACHO").first()
        self.assertEqual(
            tram.descricao,
            "Despacho inicial do protocolo para secretarias envolvidas.",
        )
        self.assertTrue(tram.metadata.get("scatter_gather"))
        self.assertTrue(tram.metadata.get("inicio_execucao_automatico"))
        self.assertFalse(
            principal.tramitacoes.filter(tipo="TRIAGEM_PROTOCOLO").exists()
        )

    def test_despacho_multiplo_cenario_3_protocolo_orquestra(self):
        """Legado — orquestrador ignorado; mesmo comportamento scatter."""
        self.test_despacho_multiplo_entra_em_operacao_scatter()

    def test_iniciar_execucao_cenario_2(self):
        """Após despacho, processo já está em EM_OPERACAO — iniciar execução é idempotente."""
        demanda = self._demanda_carta()
        resultado = DemandaDespachoService().despachar_multiplo(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}, {"secretaria_id": SINAPSE_ORGAO_B}],
            usuario=self.protocolo,
            texto_despacho="Despacho inicial para iniciar execução operacional.",
        )
        principal = resultado["demanda"]
        principal.refresh_from_db()
        self.assertEqual(principal.status, "EM_EXECUCAO")
        self.assertEqual(principal.nos_ativos, 2)
        self.svc.aplicar_inicio_execucao(principal, self.sec_a)
        principal.refresh_from_db()
        self.assertEqual(principal.status, "EM_EXECUCAO")
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        pernas = PernaOperacional.objects.filter(demanda=principal)
        self.assertTrue(
            pernas.filter(status=StatusPernaOperacional.EM_EXECUCAO).count() >= 2
        )

    def test_timeline_super_os_unificada_entre_lider_e_seguidora(self):
        """Líder e seguidora do cluster exibem a mesma timeline operacional agregada."""
        cluster = ClusterExecucao.objects.create(
            titulo="Cluster timeline",
            status="EM_ANDAMENTO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        ver_b = Usuario.objects.create_user(
            username="ver_op_b", password="x", perfil="VEREADOR"
        )
        lider = Demanda.objects.create(
            titulo="Líder",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OF-TL-1",
            cluster=cluster,
            fluxo_roteamento=FluxoRoteamento.FLUXO_DIRETO,
        )
        seguidora = Demanda.objects.create(
            titulo="Seguidora",
            descricao="x",
            autor=ver_b,
            status="FINALIZADO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OF-TL-2",
            cluster=cluster,
            fluxo_roteamento=FluxoRoteamento.FLUXO_DIRETO,
        )
        Tramitacao.objects.create(
            demanda=lider,
            responsavel=self.vereador,
            tipo="ENVIO_OFICIAL",
            descricao="Envio líder",
        )
        Tramitacao.objects.create(
            demanda=seguidora,
            responsavel=ver_b,
            tipo="ENVIO_OFICIAL",
            descricao="Envio seguidora",
        )
        Tramitacao.objects.create(
            demanda=lider,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Despacho líder",
        )
        Tramitacao.objects.create(
            demanda=seguidora,
            responsavel=self.protocolo,
            tipo="CONCLUSAO_FINAL",
            descricao="Devolutiva na seguidora",
            metadata={"parecer": "Resposta"},
        )
        Tramitacao.objects.create(
            demanda=seguidora,
            responsavel=self.protocolo,
            tipo="ENCERRAMENTO_DEVOLUTIVA",
            descricao="Encerramento na seguidora",
        )
        Tramitacao.objects.create(
            demanda=lider,
            responsavel=self.protocolo,
            tipo="OPERACAO_NO",
            descricao="Espelho oculto",
            metadata={
                "scatter_gather": True,
                "acao_no": "ENCERRAR",
                "espelhada_do_lider": True,
                "lider_demanda_id": lider.pk,
            },
        )

        tl_lider = self.svc.montar_timeline_operacional(lider, usuario=self.protocolo)
        tl_seg = self.svc.montar_timeline_operacional(seguidora, usuario=self.protocolo)

        def chave(items):
            return [(t["tipo"], t.get("demanda_id")) for t in items]

        self.assertEqual(
            chave([t for t in tl_lider if t["tipo"] != "ENVIO_OFICIAL"]),
            chave([t for t in tl_seg if t["tipo"] != "ENVIO_OFICIAL"]),
        )
        tipos_lider = {t["tipo"] for t in tl_lider}
        self.assertIn("CONCLUSAO_FINAL", tipos_lider)
        self.assertIn("ENCERRAMENTO_DEVOLUTIVA", tipos_lider)
        self.assertEqual(
            sum(1 for t in tl_lider if t["tipo"] == "ENVIO_OFICIAL"),
            1,
        )
        self.assertEqual(
            sum(1 for t in tl_seg if t["tipo"] == "ENVIO_OFICIAL"),
            1,
        )
