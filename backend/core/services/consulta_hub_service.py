"""Atalhos e contadores do hub de consultas (C4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone

from core.filters import DemandaFilter
from core.models import Demanda


@dataclass(frozen=True)
class AtalhoConsulta:
    id: str
    titulo: str
    descricao: str
    rota: str
    query: dict[str, str]
    contagem: int | None = None
    icone: str = "pi pi-inbox"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "rota": self.rota,
            "query": self.query,
            "contagem": self.contagem,
            "icone": self.icone,
        }


class ConsultaHubService:
    """Agrega contadores reutilizando DemandaFilter (sem duplicar queryset)."""

    def _base_qs(self, user):
        qs = Demanda.objects.all()
        if getattr(user, "perfil", None) == "SECRETARIA":
            from core.services.cluster_service import ClusterService

            qs = ClusterService().filtrar_listagem_apenas_lideres(qs)
        return qs

    def _count(self, user, params: dict[str, str]) -> int:
        class _Req:
            pass

        req = _Req()
        req.user = user
        filt = DemandaFilter(data=params, queryset=self._base_qs(user), request=req)
        if not filt.is_valid():
            return 0
        return filt.qs.count()

    def _atrasadas_count(self, user, extra: dict[str, str] | None = None) -> int:
        class _Req:
            pass

        req = _Req()
        req.user = user
        params = {
            "status__in": "PROTOCOLADO,EM_EXECUCAO,AGUARDANDO_TRANSFERENCIA",
            **(extra or {}),
        }
        filt = DemandaFilter(data=params, queryset=self._base_qs(user), request=req)
        if not filt.is_valid():
            return 0
        agora = timezone.now()
        total = 0
        for d in filt.qs.filter(data_inicio_prazo__isnull=False).only(
            "pk", "data_inicio_prazo", "prazo_efetivo_dias", "prazo_origem", "sinapse_servico_id"
        ):
            prazo = d.prazo_dias()
            if prazo is not None and d.data_inicio_prazo + timedelta(days=prazo) < agora:
                total += 1
        return total

    def atalhos(self, user) -> list[dict[str, Any]]:
        perfil = getattr(user, "perfil", None)
        if perfil == "VEREADOR":
            return self._atalhos_vereador(user)
        if perfil == "PROTOCOLO":
            return self._atalhos_protocolo(user)
        if perfil == "SECRETARIA":
            return self._atalhos_secretaria(user)
        if perfil == "GESTOR":
            return self._atalhos_gestor(user)
        return []

    def _atalhos_vereador(self, user) -> list[dict[str, Any]]:
        uid = str(user.pk)
        return [
            AtalhoConsulta(
                "rascunhos",
                "Meus rascunhos",
                "Ofícios ainda não enviados ao Protocolo",
                "/demandas",
                {"status": "RASCUNHO"},
                self._count(user, {"autor": uid, "status": "RASCUNHO"}),
                "pi pi-file-edit",
            ).as_dict(),
            AtalhoConsulta(
                "aguardando",
                "Aguardando protocolo",
                "Enviados e na fila do Protocolo",
                "/demandas",
                {"status": "AGUARDANDO_PROTOCOLO"},
                self._count(user, {"autor": uid, "status": "AGUARDANDO_PROTOCOLO"}),
                "pi pi-send",
            ).as_dict(),
            AtalhoConsulta(
                "atrasadas",
                "Prazo crítico",
                "Protocolados ou em execução com SLA vencido",
                "/demandas",
                {"consulta": "atrasadas"},
                self._atrasadas_count(user, {"autor": uid}),
                "pi pi-exclamation-triangle",
            ).as_dict(),
            AtalhoConsulta(
                "novo",
                "Novo ofício",
                "Abrir o Copiloto para registrar demanda",
                "/copiloto",
                {},
                None,
                "pi pi-comments",
            ).as_dict(),
        ]

    def _atalhos_protocolo(self, user) -> list[dict[str, Any]]:
        tendencias_abertas = 0
        try:
            from core.models import Tendencia

            tendencias_abertas = Tendencia.objects.filter(status="ABERTA").count()
        except Exception:
            pass

        return [
            AtalhoConsulta(
                "protocolados",
                "Fila protocolados",
                "Ofícios aguardando despacho",
                "/demandas",
                {"fila": "protocolados"},
                self._count(user, {"fila": "protocolados"}),
                "pi pi-inbox",
            ).as_dict(),
            AtalhoConsulta(
                "operacionais",
                "Fila operacional",
                "Demandas em execução nas secretarias",
                "/demandas",
                {"fila": "operacionais"},
                self._count(user, {"fila": "operacionais"}),
                "pi pi-cog",
            ).as_dict(),
            AtalhoConsulta(
                "devolutivas",
                "Devolutivas",
                "Aguardando resposta ou retorno ao vereador",
                "/demandas",
                {"fila": "devolutivas"},
                self._count(user, {"fila": "devolutivas"}),
                "pi pi-reply",
            ).as_dict(),
            AtalhoConsulta(
                "tendencias",
                "Tendências abertas",
                "Solicitações fora da carta Sinapse",
                "/gestao-tendencias",
                {},
                tendencias_abertas,
                "pi pi-chart-line",
            ).as_dict(),
        ]

    def _atalhos_secretaria(self, user) -> list[dict[str, Any]]:
        extra: dict[str, str] = {}
        if getattr(user, "sinapse_orgao_id", None):
            extra["secretaria_destino"] = str(user.sinapse_orgao_id)
        filtro_setor = {**extra, "fila": "operacionais", "minha_unidade": "1"}
        return [
            AtalhoConsulta(
                "minha_unidade",
                "Meu setor",
                "Demandas operacionais do seu setor",
                "/demandas",
                {"fila": "operacionais", "minha_unidade": "1"},
                self._count(user, filtro_setor),
                "pi pi-sitemap",
            ).as_dict(),
            AtalhoConsulta(
                "super_os",
                "Super Ordens",
                "Clusters e despacho em lote",
                "/clusters",
                {},
                None,
                "pi pi-objects-column",
            ).as_dict(),
            AtalhoConsulta(
                "atrasadas",
                "Vencendo / atrasados",
                "SLA estourado no seu setor",
                "/demandas",
                {"fila": "operacionais", "minha_unidade": "1", "consulta": "atrasadas"},
                self._atrasadas_count(user, filtro_setor),
                "pi pi-clock",
            ).as_dict(),
            AtalhoConsulta(
                "carta",
                "Carta de serviços",
                "Consultar prazos e setores sugeridos",
                "/carta-servicos",
                {},
                None,
                "pi pi-bookmark",
            ).as_dict(),
        ]

    def _atalhos_gestor(self, user) -> list[dict[str, Any]]:
        return [
            AtalhoConsulta(
                "explorer",
                "Explorer da carta",
                "Busca, ficha e simulação de triagem",
                "/carta-servicos",
                {},
                None,
                "pi pi-bookmark",
            ).as_dict(),
            AtalhoConsulta(
                "tendencias",
                "Gestão de tendências",
                "Promover solicitações à carta",
                "/gestao-tendencias",
                {},
                None,
                "pi pi-chart-line",
            ).as_dict(),
            AtalhoConsulta(
                "fluxo",
                "Fluxo e setores",
                "Despacho automático e vínculo carta-setor",
                "/gestao-fluxo-servicos",
                {},
                None,
                "pi pi-directions",
            ).as_dict(),
            AtalhoConsulta(
                "sla",
                "SLA da carta",
                "Prazo padrão e política institucional",
                "/admin/configuracao-carta",
                {},
                None,
                "pi pi-clock",
            ).as_dict(),
            AtalhoConsulta(
                "dashboard",
                "KPIs e trilhas",
                "Indicadores operacionais completos",
                "/",
                {},
                None,
                "pi pi-home",
            ).as_dict(),
        ]

    def buscar(self, user, q: str, *, limit: int = 15) -> dict[str, Any]:
        texto = (q or "").strip()
        if len(texto) < 2:
            return {"demandas": [], "servicos_carta": [], "q": texto}

        perfil = getattr(user, "perfil", None)
        params: dict[str, str] = {"q": texto}
        if perfil == "VEREADOR":
            params["autor"] = str(user.pk)
        elif perfil == "SECRETARIA" and getattr(user, "sinapse_orgao_id", None):
            params["secretaria_destino"] = str(user.sinapse_orgao_id)
            params["fila"] = "operacionais"
            params["minha_unidade"] = "1"

        class _Req:
            pass

        req = _Req()
        req.user = user
        filt = DemandaFilter(data=params, queryset=self._base_qs(user), request=req)
        demandas = []
        if filt.is_valid():
            qs = filt.qs.order_by("-data_criacao")[:limit]
            for d in qs:
                demandas.append(
                    {
                        "id": d.pk,
                        "titulo": d.titulo,
                        "status": d.status,
                        "protocolo_executivo": d.protocolo_executivo,
                        "protocolo_legislativo": d.protocolo_legislativo,
                        "bairro": d.bairro,
                        "endereco": d.endereco,
                    }
                )

        servicos = []
        if perfil in ("VEREADOR", "GESTOR", "PROTOCOLO", "SECRETARIA"):
            try:
                from integrations.services.carta_explorer_service import CartaExplorerService

                carta = CartaExplorerService().buscar(q=texto, limit=min(limit, 10))
                for item in carta.get("results") or []:
                    servicos.append(
                        {
                            "id": item.get("id"),
                            "nome": item.get("nome") or item.get("titulo"),
                            "orgao": (item.get("secretaria_responsavel") or {}).get("nome"),
                            "prazo_dias": item.get("prazo_efetivo_dias") or item.get("prazo_dias"),
                        }
                    )
            except Exception:
                servicos = []

        return {"q": texto, "demandas": demandas, "servicos_carta": servicos}
