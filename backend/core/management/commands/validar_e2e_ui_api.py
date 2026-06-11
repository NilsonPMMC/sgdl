"""Validação E2E assistida — endpoints críticos da UI por perfil (H1 visual)."""

from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test.utils import override_settings
from rest_framework.test import APIClient

from core.models import Demanda, Usuario


@dataclass
class CheckUI:
    tela: str
    perfil: str
    esperado: str
    ok: bool
    obtido: str
    severidade: str = "bloqueante"


@dataclass
class RelatorioUI:
    checks: list[CheckUI] = field(default_factory=list)

    def add(self, tela, perfil, esperado, ok, obtido, severidade="bloqueante"):
        self.checks.append(CheckUI(tela, perfil, esperado, ok, obtido, severidade))

    @property
    def bloqueantes(self):
        return [c for c in self.checks if not c.ok and c.severidade == "bloqueante"]


USUARIOS = {
    "VEREADOR": "vereador_0_martinsnicole",
    "PROTOCOLO": "protocolo_0",
    "SECRETARIA": "sec_serviços_0",
    "GESTOR": "admin",
}
SENHA = "123"


def _status_data(response):
    code = getattr(response, "status_code", None)
    data = getattr(response, "data", None)
    if data is None and hasattr(response, "json"):
        try:
            data = response.json()
        except Exception:
            data = None
    return code, data


class Command(BaseCommand):
    help = "Valida endpoints da UI por perfil (proxy da rodada visual H1)."

    def add_arguments(self, parser):
        parser.add_argument("--demanda-id", type=int, default=2966, help="Demanda evidência E2E")

    def handle(self, *args, **options):
        hosts = list(getattr(settings, "ALLOWED_HOSTS", []))
        if "testserver" not in hosts:
            hosts.append("testserver")

        with override_settings(ALLOWED_HOSTS=hosts):
            self._executar(*args, **options)

    def _executar(self, *args, **options):
        rel = RelatorioUI()
        demanda_id = options["demanda_id"]
        demanda = Demanda.objects.filter(pk=demanda_id).first()

        for perfil, username in USUARIOS.items():
            try:
                user = Usuario.objects.get(username=username, perfil=perfil)
            except Usuario.DoesNotExist:
                rel.add("Login", perfil, "usuário seed existe", False, f"{username} não encontrado")
                continue

            client = APIClient()
            client.force_authenticate(user=user)
            if perfil == "VEREADOR":
                self._perfil_vereador(client, rel, demanda)
            elif perfil == "PROTOCOLO":
                self._perfil_protocolo(client, rel)
            elif perfil == "SECRETARIA":
                self._perfil_secretaria(client, rel, user)
            elif perfil == "GESTOR":
                self._perfil_gestor(client, rel)

            r = client.get("/api/users/me/")
            code, data = _status_data(r)
            rel.add(
                "ProfileView",
                perfil,
                "GET /users/me/ 200 + atuacao_sgdl",
                code == 200 and isinstance(data, dict) and "atuacao_sgdl" in data,
                f"status={code}",
                "incômodo" if perfil != "SECRETARIA" else "bloqueante",
            )
            if perfil == "SECRETARIA" and code == 200 and isinstance(data, dict):
                atuacao = data.get("atuacao_sgdl") or {}
                rel.add(
                    "DemandasView",
                    perfil,
                    "atuacao_sgdl.completa para fila minha_unidade",
                    bool(atuacao.get("completa")),
                    str(atuacao.get("resumo", "")),
                )

        if demanda:
            self._demanda_evidencia(APIClient(), rel, demanda)

        self._imprimir(rel)

    def _demanda_evidencia(self, client, rel: RelatorioUI, demanda: Demanda):
        client.force_authenticate(user=demanda.autor)
        r = client.get(f"/api/demandas/{demanda.pk}/")
        code, data = _status_data(r)
        rel.add(
            "DemandaDetailView",
            "VEREADOR",
            f"Detalhe demanda {demanda.pk} FINALIZADO",
            code == 200 and isinstance(data, dict) and data.get("status") == "FINALIZADO",
            f"status={data.get('status') if isinstance(data, dict) else code}",
        )
        r2 = client.get(f"/api/demandas/{demanda.pk}/pacote-devolutiva/")
        rel.add(
            "DemandaDetailView",
            "VEREADOR",
            "Pacote devolutiva disponível",
            r2.status_code == 200,
            f"status={r2.status_code}",
            "incômodo",
        )

    def _perfil_vereador(self, client, rel: RelatorioUI, demanda):
        r = client.get("/api/consulta/hub/")
        rel.add("ConsultaHubView", "VEREADOR", "Hub consulta 200", r.status_code == 200, f"status={r.status_code}")

        r = client.get("/api/demandas/", {"status": "RASCUNHO"})
        code, data = _status_data(r)
        count = "n/a"
        if isinstance(data, dict):
            count = len(data.get("results", data))
        rel.add(
            "DemandasView",
            "VEREADOR",
            "Lista rascunhos 200",
            code == 200,
            f"count={count}",
            "incômodo",
        )

        if demanda and demanda.status == "FINALIZADO":
            r = client.get(f"/api/demandas/{demanda.pk}/preview-envio-oficial/")
            rel.add(
                "DemandaForm",
                "VEREADOR",
                "Preview indisponível p/ FINALIZADO (400)",
                r.status_code in (400, 403),
                f"status={r.status_code}",
                "cosmético",
            )

    def _perfil_protocolo(self, client, rel: RelatorioUI):
        for fila in ("protocolados", "operacionais", "devolutivas"):
            r = client.get("/api/demandas/", {"fila": fila})
            rel.add(
                "DemandasView",
                "PROTOCOLO",
                f"Fila {fila} responde 200",
                r.status_code == 200,
                f"status={r.status_code}",
            )

        r = client.get("/api/clusters/")
        rel.add(
            "ClustersView",
            "PROTOCOLO",
            "Lista clusters 200",
            r.status_code == 200,
            f"status={r.status_code}",
            "incômodo",
        )

        r = client.get("/api/dashboard/stats/")
        rel.add(
            "DashboardView",
            "PROTOCOLO",
            "Dashboard KPIs 200",
            r.status_code == 200,
            f"status={r.status_code}",
        )

        r = client.get("/api/tendencias/")
        rel.add(
            "TendenciasGestaoView",
            "PROTOCOLO",
            "Gestão tendências 200",
            r.status_code == 200,
            f"status={r.status_code}",
            "incômodo",
        )

        # P14: protocolo NÃO deve acessar reconciliação
        r = client.get("/api/integrations/sinapse/unmatched/")
        rel.add(
            "SinapseReconciliacaoView",
            "PROTOCOLO",
            "Reconciliação bloqueada (403)",
            r.status_code == 403,
            f"status={r.status_code}",
            "cosmético",
        )

    def _perfil_secretaria(self, client, rel: RelatorioUI, user):
        r = client.get("/api/demandas/", {"fila": "operacionais", "minha_unidade": "1"})
        rel.add(
            "DemandasView",
            "SECRETARIA",
            "Fila operacionais + minha_unidade 200",
            r.status_code == 200,
            f"status={r.status_code}",
        )

        r = client.get("/api/demandas/", {"fila": "operacionais"})
        rel.add(
            "DemandasView",
            "SECRETARIA",
            "Fila operacionais (toda secretaria) 200",
            r.status_code == 200,
            f"status={r.status_code}",
            "incômodo",
        )

    def _perfil_gestor(self, client, rel: RelatorioUI):
        r = client.get("/api/dashboard/stats/")
        rel.add("DashboardView", "GESTOR", "Dashboard 200", r.status_code == 200, f"status={r.status_code}")

        r = client.get("/api/reports/kpis/")
        rel.add(
            "RelatoriosView",
            "GESTOR",
            "Relatórios KPIs 200",
            r.status_code == 200,
            f"status={r.status_code}",
        )

        r = client.get("/api/integrations/sinapse/unmatched/")
        rel.add(
            "SinapseReconciliacaoView",
            "GESTOR",
            "Reconciliação Sinapse 200",
            r.status_code == 200,
            f"status={r.status_code}",
            "incômodo",
        )

        r = client.get("/api/gestao-usuarios/")
        rel.add(
            "GestaoUsuariosView",
            "GESTOR",
            "Hub gestão usuários 200",
            r.status_code == 200,
            f"status={r.status_code}",
        )

        r = client.get("/api/fluxo-servicos/")
        rel.add(
            "FluxoServicosView",
            "GESTOR",
            "Fluxo serviços 200",
            r.status_code == 200,
            f"status={r.status_code}",
            "incômodo",
        )

    def _imprimir(self, rel: RelatorioUI):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Validação UI (API) — H1/H2 ==="))
        for c in rel.checks:
            marca = "OK" if c.ok else "FALHA"
            style = self.style.SUCCESS if c.ok else self.style.ERROR
            self.stdout.write(style(f"[{marca}] {c.tela} · {c.perfil} · {c.esperado}"))
            self.stdout.write(f"         obtido: {c.obtido} · {c.severidade}")
        self.stdout.write("")
        if rel.bloqueantes:
            self.stdout.write(self.style.ERROR(f"Bloqueantes: {len(rel.bloqueantes)}"))
        else:
            self.stdout.write(self.style.SUCCESS("Sem bloqueantes na validação UI/API."))
