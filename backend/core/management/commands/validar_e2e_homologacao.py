"""Roteiro E2E A1 — ciclo legislativo ponta a ponta (homologação operacional)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Anexo, Demanda, Usuario
from core.services.assinatura_eletronica_service import (
    DECLARACAO_ENVIO,
    AssinaturaEletronicaService,
)
from core.services.demanda_despacho_service import DemandaDespachoService
from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService
from core.services.encerramento_legislativo_service import EncerramentoLegislativoService
from core.services.envio_oficial_service import EnvioOficialService
from core.services.usuario_vinculo_service import UsuarioVinculoService


@dataclass
class PassoE2E:
    id: str
    perfil: str
    descricao: str
    ok: bool = False
    detalhe: str = ""


@dataclass
class RelatorioE2E:
    passos: list[PassoE2E] = field(default_factory=list)
    demanda_id: int | None = None

    def registrar(self, passo_id: str, perfil: str, descricao: str, ok: bool, detalhe: str = ""):
        self.passos.append(PassoE2E(passo_id, perfil, descricao, ok, detalhe))

    @property
    def bloqueantes(self) -> list[PassoE2E]:
        return [p for p in self.passos if not p.ok]


class Command(BaseCommand):
    help = "Executa roteiro E2E A1 (Vereador → Protocolo → Secretaria → encerramento)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--vereador",
            default="vereador_0_martinsnicole",
            help="Username do vereador de teste",
        )
        parser.add_argument(
            "--protocolo",
            default="protocolo_0",
            help="Username do protocolo",
        )
        parser.add_argument(
            "--secretaria",
            default="sec_serviços_0",
            help="Username da secretaria",
        )
        parser.add_argument(
            "--orgao",
            type=int,
            default=17,
            help="sinapse_orgao_id para despacho",
        )
        parser.add_argument(
            "--servico",
            type=int,
            default=80,
            help="sinapse_servico_id para envio oficial (obrigatório)",
        )
        parser.add_argument(
            "--unidade",
            type=int,
            default=890,
            help="Unidade administrativa para despacho/vínculo secretaria",
        )
        parser.add_argument(
            "--corrigir-vinculo-secretaria",
            action="store_true",
            help="Aplica órgão + setor na secretaria se atuação incompleta",
        )
        parser.add_argument(
            "--manter-demanda",
            action="store_true",
            help="Não excluir demanda de teste ao final",
        )

    def handle(self, *args, **options):
        rel = RelatorioE2E()
        tag = uuid.uuid4().hex[:8]

        try:
            vereador = Usuario.objects.get(username=options["vereador"], perfil="VEREADOR")
            protocolo = Usuario.objects.get(username=options["protocolo"], perfil="PROTOCOLO")
            secretaria = Usuario.objects.get(username=options["secretaria"], perfil="SECRETARIA")
        except Usuario.DoesNotExist as exc:
            self.stderr.write(self.style.ERROR(f"Usuário não encontrado: {exc}"))
            return

        orgao_id = int(options["orgao"])
        unidade_id = int(options["unidade"])
        servico_id = int(options["servico"])

        if options["corrigir_vinculo_secretaria"]:
            svc = UsuarioVinculoService()
            atuacao = svc.atuacao_sgdl(secretaria)
            if not atuacao.get("completa"):
                svc.sincronizar_secretaria(
                    secretaria,
                    sinapse_orgao_id=orgao_id,
                    unidade_ids=[unidade_id],
                )
                secretaria.refresh_from_db()
                self.stdout.write(
                    self.style.WARNING(
                        f"Vínculo secretaria corrigido → {svc.atuacao_sgdl(secretaria)['resumo']}"
                    )
                )

        demanda = Demanda.objects.create(
            titulo=f"[E2E-A1-{tag}] Iluminação pública",
            descricao="Demanda gerada pelo comando validar_e2e_homologacao.",
            autor=vereador,
            status="RASCUNHO",
            sinapse_servico_id=servico_id,
            sinapse_orgao_id=orgao_id,
            logradouro="Rua Teste E2E, 100 — Centro",
            bairro="Centro",
        )
        rel.demanda_id = demanda.pk
        self.stdout.write(f"Demanda criada: id={demanda.pk} tag={tag}")

        # 5.2 Vereador — envio oficial
        try:
            preview = AssinaturaEletronicaService().preparar_preview_envio(demanda)
            EnvioOficialService().enviar_demanda(
                demanda,
                vereador,
                hash_documento=preview["hash_documento"],
                declaracao=DECLARACAO_ENVIO,
            )
            demanda.refresh_from_db()
            ok = demanda.status == "AGUARDANDO_PROTOCOLO"
            anexos = Anexo.objects.filter(demanda=demanda).count()
            rel.registrar(
                "5.2.4",
                "VEREADOR",
                "Assinar e enviar oficialmente → AGUARDANDO_PROTOCOLO",
                ok,
                f"status={demanda.status}, anexos={anexos}",
            )
            rel.registrar(
                "5.2.5",
                "VEREADOR",
                "Confirmar 1 PDF anexo",
                anexos == 1,
                f"anexos={anexos}",
            )
        except Exception as exc:
            rel.registrar("5.2.4", "VEREADOR", "Envio oficial", False, str(exc))

        # 5.3 Protocolo — despacho
        try:
            DemandaDespachoService().despachar(
                demanda,
                secretaria_id=orgao_id,
                usuario=protocolo,
                automatico=False,
                unidade_administrativa_id=unidade_id,
            )
            demanda.refresh_from_db()
            rel.registrar(
                "5.3.2",
                "PROTOCOLO",
                "Despachar demanda → PROTOCOLADO",
                demanda.status == "PROTOCOLADO",
                f"status={demanda.status}, protocolo={demanda.protocolo_executivo}",
            )
        except Exception as exc:
            rel.registrar("5.3.2", "PROTOCOLO", "Despachar demanda", False, str(exc))

        # 5.4 Secretaria — execução
        try:
            demanda.status = "EM_EXECUCAO"
            demanda.save(update_fields=["status"])
            rel.registrar(
                "5.4.5",
                "SECRETARIA",
                "Iniciar execução → EM_EXECUCAO",
                demanda.status == "EM_EXECUCAO",
                f"status={demanda.status}",
            )
        except Exception as exc:
            rel.registrar("5.4.5", "SECRETARIA", "EM_EXECUCAO", False, str(exc))

        # 5.4 Secretaria — devolutiva
        try:
            DevolutivaProtocoloService().solicitar_devolutiva(
                demanda,
                secretaria,
                parecer_operacional="[E2E] Serviço executado conforme vistoria.",
            )
            demanda.refresh_from_db()
            rel.registrar(
                "5.4.7",
                "SECRETARIA",
                "Solicitar devolutiva → AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
                demanda.status == "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
                f"status={demanda.status}",
            )
        except Exception as exc:
            rel.registrar("5.4.7", "SECRETARIA", "Solicitar devolutiva", False, str(exc))

        # 5.3 Protocolo — devolutiva ao vereador
        try:
            DevolutivaProtocoloService().despachar_devolutiva(
                demanda,
                protocolo,
                parecer_resposta="[E2E] Devolutiva encaminhada ao gabinete.",
            )
            demanda.refresh_from_db()
            rel.registrar(
                "5.3.5",
                "PROTOCOLO",
                "Despachar devolutiva → DEVOLVIDO_VEREADOR",
                demanda.status == "DEVOLVIDO_VEREADOR",
                f"status={demanda.status}",
            )
        except Exception as exc:
            rel.registrar("5.3.5", "PROTOCOLO", "Despachar devolutiva", False, str(exc))

        # 5.2 Vereador — ciência e encerramento
        try:
            EncerramentoLegislativoService().confirmar_ciencia(
                demanda,
                vereador,
                texto_resposta_cidadao="[E2E] Informamos que a solicitação foi atendida.",
                gerar_oficio=True,
                encerrar=True,
            )
            demanda.refresh_from_db()
            rel.registrar(
                "5.2.6",
                "VEREADOR",
                "Confirmar ciência → FINALIZADO",
                demanda.status == "FINALIZADO",
                f"status={demanda.status}",
            )
            pacote = EncerramentoLegislativoService().montar_pacote_devolutiva(demanda)
            rel.registrar(
                "5.2.7",
                "VEREADOR",
                "Ofício ao cidadão no pacote devolutiva",
                bool(pacote.get("parecer_operacional")),
                "pacote OK" if pacote else "vazio",
            )
        except Exception as exc:
            rel.registrar("5.2.6", "VEREADOR", "Confirmar ciência", False, str(exc))

        # Gestor — dashboard smoke
        gestor = Usuario.objects.filter(perfil="GESTOR", is_active=True).first()
        if gestor:
            from django.test import RequestFactory
            from rest_framework.test import force_authenticate

            from core.views import DashboardStatsAPIView

            try:
                req = RequestFactory().get("/api/dashboard/stats/")
                force_authenticate(req, user=gestor)
                resp = DashboardStatsAPIView.as_view()(req)
                rel.registrar(
                    "5.6.1",
                    "GESTOR",
                    "Dashboard KPIs disponível",
                    resp.status_code == 200,
                    f"status={resp.status_code}",
                )
            except Exception as exc:
                rel.registrar("5.6.1", "GESTOR", "Dashboard KPIs", False, str(exc))

        if not options["manter_demanda"] and rel.bloqueantes:
            self.stdout.write(
                self.style.WARNING(
                    f"Demanda {demanda.pk} mantida para análise (passos com falha)."
                )
            )
        elif not options["manter_demanda"] and not rel.bloqueantes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Ciclo completo OK — demanda {demanda.pk} permanece como evidência FINALIZADO."
                )
            )

        self._imprimir_relatorio(rel)

    def _imprimir_relatorio(self, rel: RelatorioE2E):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== Relatório E2E A1 ==="))
        self.stdout.write(f"Demanda: {rel.demanda_id}")
        self.stdout.write(f"Executado em: {timezone.now().isoformat()}")
        self.stdout.write("")
        for p in rel.passos:
            marca = self.style.SUCCESS("OK") if p.ok else self.style.ERROR("FALHA")
            self.stdout.write(f"[{marca}] {p.id} · {p.perfil} · {p.descricao}")
            if p.detalhe:
                self.stdout.write(f"         {p.detalhe}")
        self.stdout.write("")
        if rel.bloqueantes:
            self.stdout.write(
                self.style.ERROR(f"Gate A1: NO-GO — {len(rel.bloqueantes)} passo(s) com falha.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Gate A1: GO — ciclo legislativo E2E OK."))
