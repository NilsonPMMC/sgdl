"""Testes scatter-gather — nós operacionais e gather automático."""

import importlib.util

from django.test import TestCase

from core.models import Demanda, Tramitacao
from core.models_no_operacional import AcaoNoOperacional, NoOperacional, StatusNoOperacional
from core.models_operacional import ESTADO_AGUARDANDO_CONCLUSAO_FINAL, FluxoRoteamento
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.operacional_estado_service import OperacionalEstadoService
from core.services.perna_operacional_service import PernaOperacionalService
from core.services.scatter_gather_service import (
    NoOperacionalService,
    ScatterGatherError,
    ScatterGatherDestinoDuplicadoError,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_ORGAO_C = 2003
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ScatterGatherServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.sg = NoOperacionalService()
        self.op = OperacionalEstadoService()
        self.perna_svc = PernaOperacionalService()
        from core.models import Usuario

        self.vereador = Usuario.objects.create_user(
            username="ver_sg", password="x", perfil="VEREADOR"
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_a_sg",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.sec_b = Usuario.objects.create_user(
            username="sec_b_sg",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        self.sec_c = Usuario.objects.create_user(
            username="sec_c_sg",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_C,
        )
        self.demanda = Demanda.objects.create(
            titulo="Scatter gather teste",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
        )
        self.perna_svc.criar_pernas_no_despacho(
            self.demanda,
            [
                {"secretaria_id": SINAPSE_ORGAO_A},
                {"secretaria_id": SINAPSE_ORGAO_B},
            ],
        )
        PernaOperacional.objects.filter(demanda=self.demanda).update(
            status=StatusPernaOperacional.EM_EXECUCAO
        )
        self.nos = self.sg.bootstrap_nos_iniciais(self.demanda, self.sec_a)
        self.demanda.refresh_from_db()
        self.no_a = next(n for n in self.nos if n.sinapse_orgao_id == SINAPSE_ORGAO_A)

    def test_bootstrap_cria_nos_raiz_por_perna(self):
        self.assertEqual(len(self.nos), 2)
        self.assertEqual(self.demanda.nos_ativos, 2)
        self.assertEqual(
            Tramitacao.objects.filter(
                demanda=self.demanda,
                tipo="OPERACAO_NO",
                metadata__acao_no="ABERTURA_NO",
            ).count(),
            2,
        )
        self.assertFalse(
            Tramitacao.objects.filter(
                demanda=self.demanda, tipo="OPERACAO_NO", metadata__acao_no="BOOTSTRAP"
            ).exists()
        )

    def test_despachar_registra_encaminhamento_por_filho(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destinos=[
                {"secretaria_id": SINAPSE_ORGAO_C},
                {"secretaria_id": SINAPSE_ORGAO_B},
            ],
            observacao="Encaminhamento múltiplo para secretarias B e C.",
        )
        encaminhamentos = Tramitacao.objects.filter(
            demanda=self.demanda,
            tipo="OPERACAO_NO",
            metadata__acao_no="ENCAMINHAMENTO_NO",
        )
        self.assertEqual(encaminhamentos.count(), 2)
        orgaos = {t.metadata.get("orgao_id") for t in encaminhamentos}
        self.assertIn(SINAPSE_ORGAO_B, orgaos)
        self.assertIn(SINAPSE_ORGAO_C, orgaos)

    def test_encerrar_lote_registra_tramitacao_por_no(self):
        abertos_b = list(
            NoOperacional.objects.filter(
                demanda=self.demanda,
                status=StatusNoOperacional.ABERTO,
                sinapse_orgao_id=SINAPSE_ORGAO_B,
            )
        )
        self.assertEqual(len(abertos_b), 2)
        self.sg.encerrar_nos_lote(
            self.demanda,
            self.sec_b,
            no_ids=[n.pk for n in abertos_b],
            observacao="Encerramento unificado dos nós equivalentes na secretaria B.",
        )
        encerramentos = Tramitacao.objects.filter(
            demanda=self.demanda,
            tipo="OPERACAO_NO",
            metadata__acao_no=AcaoNoOperacional.ENCERRAR,
        )
        self.assertGreaterEqual(encerramentos.count(), 2)
        self.assertFalse(
            Tramitacao.objects.filter(
                demanda=self.demanda,
                metadata__acao_no="ENCERRAR_LOTE",
            ).exists()
        )

    def test_despacho_registra_texto_do_usuario(self):
        parecer = "Solicito vistoria urgente na via Casarejos."
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao=parecer,
        )
        tram = Tramitacao.objects.filter(
            demanda=self.demanda,
            tipo="OPERACAO_NO",
            metadata__acao_no=AcaoNoOperacional.DESPACHAR,
        ).last()
        self.assertEqual(tram.descricao, parecer)

    def test_despachar_mantem_no_pai_aberto(self):
        antes = self.demanda.nos_ativos
        r = self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Encaminhar para análise técnica complementar.",
        )
        self.no_a.refresh_from_db()
        self.demanda.refresh_from_db()
        self.assertEqual(self.no_a.status, StatusNoOperacional.ABERTO)
        self.assertIsNotNone(r["no_filho"])
        self.assertEqual(self.demanda.nos_ativos, antes + 1)

    def test_despachar_encerrar_fecha_pai_abre_filho(self):
        r = self.sg.aplicar_despachar_encerrar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Despacho final deste setor com encaminhamento.",
        )
        self.no_a.refresh_from_db()
        self.demanda.refresh_from_db()
        self.assertEqual(self.no_a.status, StatusNoOperacional.CONCLUIDO)
        self.assertIsNotNone(r["no_filho"])
        self.assertEqual(r["no_filho"].status, StatusNoOperacional.ABERTO)

    def test_encerrar_bloqueia_com_filhos_internos_abertos(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_A,
            observacao="Encaminhamento interno para setor da mesma secretaria.",
        )
        with self.assertRaises(ScatterGatherError):
            self.sg.aplicar_encerrar(
                self.demanda,
                self.no_a.pk,
                self.sec_a,
                observacao="Tentativa de encerramento inválida.",
            )

    def test_encerrar_permitido_despacho_interno_outro_setor(self):
        """Despacho para outro setor da mesma secretaria não bloqueia encerramento do nó pai."""
        from core.models_unidade_administrativa import UnidadeAdministrativa

        ua_epl = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Equipe Planejamento",
            sigla="EPL",
            ativo=True,
        )
        ua_stb = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor Técnico B",
            sigla="STB",
            ativo=True,
        )
        self.no_a.unidade_administrativa = ua_epl
        self.no_a.save(update_fields=["unidade_administrativa"])

        filho = self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_A,
            destino_setor_id=ua_stb.pk,
            observacao="Encaminhamento interno para outro setor da mesma secretaria.",
        )["no_filho"]
        self.assertEqual(filho.unidade_administrativa_id, ua_stb.pk)

        r = self.sg.aplicar_encerrar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            observacao="Encerramento da participação do setor EPL após despacho interno.",
        )
        self.no_a.refresh_from_db()
        filho.refresh_from_db()
        self.assertEqual(self.no_a.status, StatusNoOperacional.CONCLUIDO)
        self.assertEqual(filho.status, StatusNoOperacional.ABERTO)
        self.assertIn("no_id", r)

    def test_encerrar_permitido_com_filhos_externos_abertos(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Encaminhar para vistoria técnica em outra secretaria.",
        )
        r = self.sg.aplicar_encerrar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            observacao="Encerramento da participação local com filhos externos abertos.",
        )
        self.no_a.refresh_from_db()
        self.assertEqual(self.no_a.status, StatusNoOperacional.CONCLUIDO)
        self.assertIn("no_id", r)

    def test_gather_quando_todos_nos_fechados(self):
        nos = list(
            NoOperacional.objects.filter(
                demanda=self.demanda, status=StatusNoOperacional.ABERTO
            )
        )
        for no in nos:
            if no.pk == self.no_a.pk:
                filho = self.sg.aplicar_despachar_encerrar(
                    self.demanda,
                    no.pk,
                    self.sec_a,
                    destino_orgao_id=SINAPSE_ORGAO_C,
                    observacao="Encaminhamento transversal para conclusão.",
                )["no_filho"]
                self.sg.aplicar_encerrar(
                    self.demanda, filho.pk, self.sec_c, observacao="Encerramento do nó operacional C."
                )
            else:
                self.sg.aplicar_encerrar(
                    self.demanda,
                    no.pk,
                    self.sec_b,
                    observacao="Encerramento do nó operacional B.",
                )
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.nos_ativos, 0)
        self.assertEqual(self.demanda.status, ESTADO_AGUARDANDO_CONCLUSAO_FINAL)
        self.assertFalse(
            Tramitacao.objects.filter(
                demanda=self.demanda, tipo="CONCLUSAO_TECNICA", metadata__consolidacao_nos=True
            ).exists()
        )

    def test_timeline_payload_scatter_gather(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Encaminhar análise.",
        )
        tram = Tramitacao.objects.filter(
            demanda=self.demanda,
            tipo="OPERACAO_NO",
            metadata__acao_no=AcaoNoOperacional.DESPACHAR,
        ).last()
        self.assertTrue(tram.metadata.get("scatter_gather"))
        self.assertEqual(tram.metadata.get("acao_no"), AcaoNoOperacional.DESPACHAR)
        self.assertIn("no_filho_id", tram.metadata)

    def test_despachar_multiplos_destinos_na_timeline(self):
        self.sg.aplicar_despachar_destinos(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destinos=[
                {"secretaria_id": SINAPSE_ORGAO_B},
                {"secretaria_id": SINAPSE_ORGAO_C},
            ],
            observacao="Despacho scatter para duas secretarias distintas.",
        )
        tram = Tramitacao.objects.filter(
            demanda=self.demanda,
            tipo="OPERACAO_NO",
            metadata__acao_no=AcaoNoOperacional.DESPACHAR,
        ).last()
        destinos = tram.metadata.get("destinos") or []
        self.assertEqual(len(destinos), 2)
        self.assertEqual(destinos[0]["secretaria_id"], SINAPSE_ORGAO_B)
        self.assertEqual(destinos[1]["secretaria_id"], SINAPSE_ORGAO_C)
        self.assertTrue(all(d.get("orgao_nome") for d in destinos))
        self.assertEqual(len(tram.metadata.get("no_filhos_ids") or []), 2)

        timeline = self.op.montar_timeline_operacional(self.demanda, usuario=self.sec_a)
        evento = next(t for t in timeline if t["id"] == tram.pk)
        self.assertEqual(len(evento["metadata"]["destinos"]), 2)

    def test_arvore_nos_estrutura_hierarquica(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Despacho operacional para árvore de nós.",
        )
        arvore = self.sg.montar_arvore_nos(self.demanda)
        self.assertEqual(len(arvore), 2)
        raiz_a = next(r for r in arvore if r["orgao_id"] == SINAPSE_ORGAO_A)
        self.assertEqual(len(raiz_a["filhos"]), 1)
        self.assertEqual(raiz_a["filhos"][0]["orgao_id"], SINAPSE_ORGAO_C)

    def test_despachar_destino_duplicado_exige_confirmacao(self):
        no_b = next(n for n in self.nos if n.sinapse_orgao_id == SINAPSE_ORGAO_B)
        with self.assertRaises(ScatterGatherDestinoDuplicadoError) as ctx:
            self.sg.aplicar_despachar(
                self.demanda,
                self.no_a.pk,
                self.sec_a,
                destino_orgao_id=SINAPSE_ORGAO_B,
                observacao="Reencaminhamento redundante para secretaria secundária.",
            )
        self.assertEqual(len(ctx.exception.conflitos), 1)
        self.assertEqual(ctx.exception.conflitos[0]["secretaria_id"], SINAPSE_ORGAO_B)
        self.assertEqual(ctx.exception.conflitos[0]["nos_existentes"][0]["id"], no_b.pk)
        self.assertEqual(
            ctx.exception.conflitos[0]["nos_existentes"][0]["origem_label"],
            "Via Protocolo",
        )

        antes = self.demanda.nos_ativos
        r = self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_B,
            observacao="Reencaminhamento confirmado pelo operador.",
            confirmar_destino_duplicado=True,
        )
        self.demanda.refresh_from_db()
        self.assertIsNotNone(r["no_filho"])
        self.assertEqual(self.demanda.nos_ativos, antes + 1)

    def test_serializar_no_inclui_origem_e_resumo(self):
        item = self.sg.serializar_no(self.no_a)
        self.assertIn("origem_label", item)
        self.assertIn("resumo_abertura", item)

    def test_consolidar_nos_equivalentes(self):
        filho = self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_B,
            observacao="Reencaminhamento redundante para secretaria secundária.",
            confirmar_destino_duplicado=True,
        )["no_filho"]
        self.demanda.refresh_from_db()
        no_b_bootstrap = next(
            n for n in self.nos if n.sinapse_orgao_id == SINAPSE_ORGAO_B
        )
        grupos = self.sg.listar_grupos_nos_usuario(self.demanda, self.sec_b)
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["quantidade"], 2)
        resultado = self.sg.consolidar_nos_equivalentes(
            self.demanda,
            self.sec_b,
            no_ids=[no_b_bootstrap.pk, filho.pk],
            observacao="Consolidação dos encaminhamentos equivalentes na secretaria B.",
        )
        self.demanda.refresh_from_db()
        self.assertEqual(len(resultado["nos_encerrados"]), 1)
        self.assertEqual(resultado["no_canonico"].pk, no_b_bootstrap.pk)
        self.assertEqual(
            NoOperacional.objects.filter(
                demanda=self.demanda, status=StatusNoOperacional.ABERTO, sinapse_orgao_id=SINAPSE_ORGAO_B
            ).count(),
            1,
        )

    def test_grupo_equivalente_mesma_secretaria_setores_distintos(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_B,
            observacao="Reencaminhamento redundante para secretaria secundária.",
            confirmar_destino_duplicado=True,
        )
        abertos = list(
            NoOperacional.objects.filter(
                demanda=self.demanda,
                status=StatusNoOperacional.ABERTO,
                sinapse_orgao_id=SINAPSE_ORGAO_B,
            )
        )
        self.assertEqual(len(abertos), 2)
        from core.models_unidade_administrativa import UnidadeAdministrativa

        ua = UnidadeAdministrativa.objects.filter(sinapse_orgao_id=SINAPSE_ORGAO_B).first()
        if ua:
            filho = max(abertos, key=lambda n: n.pk)
            filho.unidade_administrativa = ua
            filho.save(update_fields=["unidade_administrativa"])

        grupos = self.sg.listar_grupos_nos_usuario(self.demanda, self.sec_b)
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["quantidade"], 2)
        self.assertEqual(len(grupos[0]["no_ids"]), 2)

    def test_nos_usuario_respeita_vinculo_setor(self):
        from core.models_unidade_administrativa import (
            UnidadeAdministrativa,
            UnidadeAdministrativaResponsavel,
        )

        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_B,
            observacao="Reencaminhamento redundante para secretaria secundária.",
            confirmar_destino_duplicado=True,
        )
        abertos = list(
            NoOperacional.objects.filter(
                demanda=self.demanda,
                status=StatusNoOperacional.ABERTO,
                sinapse_orgao_id=SINAPSE_ORGAO_B,
            ).order_by("pk")
        )
        self.assertEqual(len(abertos), 2)
        uas = list(
            UnidadeAdministrativa.objects.filter(sinapse_orgao_id=SINAPSE_ORGAO_B)[:2]
        )
        if len(uas) < 2:
            self.skipTest("Catálogo Sinapse sem dois setores para org B.")
        abertos[0].unidade_administrativa = uas[0]
        abertos[0].save(update_fields=["unidade_administrativa"])
        abertos[1].unidade_administrativa = uas[1]
        abertos[1].save(update_fields=["unidade_administrativa"])

        sec_setor = self.sec_b
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=uas[1],
            usuario=sec_setor,
            ativo=True,
            pode_tramitar=True,
        )

        visiveis = self.sg.nos_abertos_do_usuario(self.demanda, sec_setor)
        self.assertEqual(len(visiveis), 1)
        self.assertEqual(visiveis[0].pk, abertos[1].pk)
        self.assertEqual(self.sg.listar_grupos_painel_nos_usuario(self.demanda, sec_setor), [])
        self.assertEqual(self.sg.listar_grupos_nos_usuario(self.demanda, sec_setor), [])

    def test_grupo_exclui_filho_direto_mesma_secretaria(self):
        """Despacho interno (pai→filho) não forma grupo equivalente com o pai."""
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_A,
            observacao="Encaminhamento interno para setor da mesma secretaria.",
        )
        abertos_a = list(
            NoOperacional.objects.filter(
                demanda=self.demanda,
                status=StatusNoOperacional.ABERTO,
                sinapse_orgao_id=SINAPSE_ORGAO_A,
            )
        )
        self.assertEqual(len(abertos_a), 2)
        self.assertEqual(len(self.sg.listar_grupos_nos_usuario(self.demanda, self.sec_a)), 0)

    def test_encerrar_lote_pai_filho_mesma_secretaria(self):
        """Encerramento em lote fecha filhos antes do pai quando ambos estão no grupo."""
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_A,
            observacao="Encaminhamento interno para encerramento em lote.",
        )
        abertos_a = list(
            NoOperacional.objects.filter(
                demanda=self.demanda,
                status=StatusNoOperacional.ABERTO,
                sinapse_orgao_id=SINAPSE_ORGAO_A,
            )
        )
        self.assertEqual(len(abertos_a), 2)
        self.sg.encerrar_nos_lote(
            self.demanda,
            self.sec_a,
            no_ids=[n.pk for n in abertos_a],
            observacao="Encerramento unificado dos nós internos da secretaria A.",
        )
        self.assertEqual(
            NoOperacional.objects.filter(
                demanda=self.demanda,
                status=StatusNoOperacional.ABERTO,
                sinapse_orgao_id=SINAPSE_ORGAO_A,
            ).count(),
            0,
        )

    def test_encerrar_lote_permitido_com_filhos_externos(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Encaminhamento externo — não impede encerrar o pai.",
        )
        self.sg.encerrar_nos_lote(
            self.demanda,
            self.sec_a,
            no_ids=[self.no_a.pk],
            observacao="Encerramento do nó pai com filhos em outra secretaria.",
        )
        self.no_a.refresh_from_db()
        self.assertEqual(self.no_a.status, StatusNoOperacional.CONCLUIDO)

    def test_encerrar_lote_parcial_fecha_pai_apos_filhos_internos(self):
        """Encerra filho interno e pai no lote mesmo com filhos externos abertos."""
        filho_externo = self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Encaminhamento externo SEMAE.",
        )["no_filho"]
        filho_interno = self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_A,
            observacao="Encaminhamento interno mesmo órgão.",
        )["no_filho"]
        resultado = self.sg.encerrar_nos_lote(
            self.demanda,
            self.sec_a,
            no_ids=[self.no_a.pk, filho_interno.pk],
            observacao="Encerramento dos nós internos da secretaria A.",
        )
        self.assertFalse(resultado.get("encerramento_parcial"))
        self.assertEqual(len(resultado["nos_encerrados"]), 2)
        filho_interno.refresh_from_db()
        self.no_a.refresh_from_db()
        filho_externo.refresh_from_db()
        self.assertEqual(filho_interno.status, StatusNoOperacional.CONCLUIDO)
        self.assertEqual(self.no_a.status, StatusNoOperacional.CONCLUIDO)
        self.assertEqual(filho_externo.status, StatusNoOperacional.ABERTO)

    def test_encerrar_nos_lote(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_B,
            observacao="Segundo encaminhamento para teste de lote.",
            confirmar_destino_duplicado=True,
        )
        no_b = next(n for n in self.nos if n.sinapse_orgao_id == SINAPSE_ORGAO_B)
        abertos_b = list(
            NoOperacional.objects.filter(
                demanda=self.demanda,
                status=StatusNoOperacional.ABERTO,
                sinapse_orgao_id=SINAPSE_ORGAO_B,
            )
        )
        self.assertEqual(len(abertos_b), 2)
        self.sg.encerrar_nos_lote(
            self.demanda,
            self.sec_b,
            no_ids=[n.pk for n in abertos_b],
            observacao="Encerramento unificado dos nós equivalentes na secretaria B.",
        )
        self.demanda.refresh_from_db()
        self.assertEqual(
            NoOperacional.objects.filter(
                demanda=self.demanda, status=StatusNoOperacional.ABERTO, sinapse_orgao_id=SINAPSE_ORGAO_B
            ).count(),
            0,
        )

    def test_reparar_gather_sincroniza_pernas_e_status(self):
        """Gather scatter deve liberar conclusão final mesmo com pernas legadas EM_EXECUCAO."""
        from core.models import Usuario
        from core.services.operacional_estado_service import OperacionalEstadoService

        protocolo = Usuario.objects.create_user(
            username="prot_sg_gather", password="x", perfil="PROTOCOLO"
        )
        op = OperacionalEstadoService()
        nos = list(
            NoOperacional.objects.filter(
                demanda=self.demanda, status=StatusNoOperacional.ABERTO
            )
        )
        for no in nos:
            self.sg.aplicar_encerrar(
                self.demanda,
                no.pk,
                self.sec_a if no.sinapse_orgao_id == SINAPSE_ORGAO_A else self.sec_b,
                observacao="Encerramento operacional scatter para gather.",
            )
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.nos_ativos, 0)
        # Simula pernas não sincronizadas (estado legado)
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        PernaOperacional.objects.filter(demanda=self.demanda).update(
            status=StatusPernaOperacional.EM_EXECUCAO
        )
        self.demanda.status = "EM_EXECUCAO"
        self.demanda.save(update_fields=["status"])

        self.sg.reparar_gather_pendente(self.demanda, protocolo)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, ESTADO_AGUARDANDO_CONCLUSAO_FINAL)
        self.assertTrue(op._historico_tecnico_pronto(self.demanda))
        self.assertIn(
            "conclusao_final",
            op.acoes_disponiveis(self.demanda, protocolo),
        )

    def test_orgaos_integrados_inclui_scatter_gather(self):
        from core.services.demanda_despacho_destinos import orgaos_integrados_demanda

        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destinos=[{"secretaria_id": SINAPSE_ORGAO_C}],
            observacao="Encaminha SMMT via scatter.",
        )
        orgaos = orgaos_integrados_demanda(self.demanda)
        ids = {item["sinapse_orgao_id"] for item in orgaos}
        self.assertIn(SINAPSE_ORGAO_B, ids)
        self.assertIn(SINAPSE_ORGAO_C, ids)
        self.assertNotIn(SINAPSE_ORGAO_A, ids)
        scatter = next(item for item in orgaos if item["sinapse_orgao_id"] == SINAPSE_ORGAO_C)
        self.assertEqual(scatter.get("origem"), "scatter_gather")

    def test_gestor_setorial_pode_encerrar_no_do_orgao(self):
        from core.models import Usuario

        gestor_b = Usuario.objects.create_user(
            username="gest_b_sg",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        no_b = next(n for n in self.nos if n.sinapse_orgao_id == SINAPSE_ORGAO_B)
        self.sg.aplicar_encerrar(
            self.demanda,
            no_b.pk,
            gestor_b,
            observacao="Encerramento da participação pelo gestor setorial.",
        )
        no_b.refresh_from_db()
        self.assertEqual(no_b.status, StatusNoOperacional.CONCLUIDO)

    def test_gestor_setorial_fora_escopo_nao_encerra_no(self):
        from core.models import Usuario
        from core.services.scatter_gather_service import ScatterGatherPermissaoError

        gestor_c = Usuario.objects.create_user(
            username="gest_c_sg",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_C,
        )
        with self.assertRaises(ScatterGatherPermissaoError):
            self.sg.aplicar_encerrar(
                self.demanda,
                self.no_a.pk,
                gestor_c,
                observacao="Tentativa fora do escopo.",
            )
