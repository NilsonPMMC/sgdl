"""Atalhos e contadores do hub de consultas (C4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from core.filters import DemandaFilter
from core.models import Demanda
from core.services.demanda_visibilidade import aplicar_escopo_demanda
from core.services.oficio_service import OficioService


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
        qs = aplicar_escopo_demanda(qs, user)
        if getattr(user, "perfil", None) == "SECRETARIA":
            from core.services.cluster_service import ClusterService

            qs = ClusterService().filtrar_listagem_apenas_lideres(qs)
        return qs

    def _count(self, user, params: dict[str, str]) -> int:
        class _Req:
            pass

        req = _Req()
        req.user = user
        qs = aplicar_escopo_demanda(Demanda.objects.all(), user)
        perfil = getattr(user, "perfil", None)
        if perfil in ("SECRETARIA", "PROTOCOLO"):
            from core.services.cluster_service import ClusterService

            fila = (params.get("fila") or "").strip().lower()
            qs = ClusterService().filtrar_listagem_por_perfil(
                qs, perfil=perfil, fila=fila
            )
        filt = DemandaFilter(data=params, queryset=qs, request=req)
        if not filt.is_valid():
            return 0
        return filt.qs.count()

    def _atrasadas_count(self, user, extra: dict[str, str] | None = None) -> int:
        params = {"consulta": "atrasadas", **(extra or {})}
        return self._count(user, params)

    def resumo_painel_protocolo(self, user) -> dict[str, int]:
        from django.db.models import Count, Q

        from core.services.demanda_sla_service import contar_demandas_atrasadas

        qs = self._base_qs(user)
        perfil = getattr(user, "perfil", None)
        if perfil == "PROTOCOLO":
            from core.services.cluster_service import ClusterService

            svc = ClusterService()
            qs_protocolados = svc.filtrar_listagem_apenas_lideres(qs)
            qs_demais = svc.filtrar_seguidoras_integradas(qs)
            agg_prot = qs_protocolados.aggregate(
                protocolados=Count("pk", filter=Q(status="AGUARDANDO_PROTOCOLO")),
            )
            agg_demais = qs_demais.aggregate(
                operacionais=Count(
                    "pk",
                    filter=Q(
                        status__in=(
                            "PROTOCOLADO",
                            "EM_EXECUCAO",
                            "AGUARDANDO_TRANSFERENCIA",
                        )
                    ),
                ),
                devolutivas=Count(
                    "pk",
                    filter=Q(
                        status__in=(
                            "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
                            "DEVOLVIDO_VEREADOR",
                        )
                    ),
                ),
                finalizados=Count("pk", filter=Q(status="FINALIZADO")),
            )
            protocolados = int(agg_prot["protocolados"] or 0)
            operacionais = int(agg_demais["operacionais"] or 0)
            devolutivas = int(agg_demais["devolutivas"] or 0)
            finalizados = int(agg_demais["finalizados"] or 0)
        elif perfil == "SECRETARIA":
            from core.services.cluster_service import ClusterService

            qs = ClusterService().filtrar_listagem_apenas_lideres(qs)
            agg = qs.aggregate(
                protocolados=Count("pk", filter=Q(status="AGUARDANDO_PROTOCOLO")),
                operacionais=Count(
                    "pk",
                    filter=Q(
                        status__in=(
                            "PROTOCOLADO",
                            "EM_EXECUCAO",
                            "AGUARDANDO_TRANSFERENCIA",
                        )
                    ),
                ),
                devolutivas=Count(
                    "pk",
                    filter=Q(
                        status__in=(
                            "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
                            "DEVOLVIDO_VEREADOR",
                        )
                    ),
                ),
                finalizados=Count("pk", filter=Q(status="FINALIZADO")),
            )
            protocolados = int(agg["protocolados"] or 0)
            operacionais = int(agg["operacionais"] or 0)
            devolutivas = int(agg["devolutivas"] or 0)
            finalizados = int(agg["finalizados"] or 0)
        else:
            agg = qs.aggregate(
                protocolados=Count("pk", filter=Q(status="AGUARDANDO_PROTOCOLO")),
                operacionais=Count(
                    "pk",
                    filter=Q(
                        status__in=(
                            "PROTOCOLADO",
                            "EM_EXECUCAO",
                            "AGUARDANDO_TRANSFERENCIA",
                        )
                    ),
                ),
                devolutivas=Count(
                    "pk",
                    filter=Q(
                        status__in=(
                            "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
                            "DEVOLVIDO_VEREADOR",
                        )
                    ),
                ),
                finalizados=Count("pk", filter=Q(status="FINALIZADO")),
            )
            protocolados = int(agg["protocolados"] or 0)
            operacionais = int(agg["operacionais"] or 0)
            devolutivas = int(agg["devolutivas"] or 0)
            finalizados = int(agg["finalizados"] or 0)

        atrasados = contar_demandas_atrasadas(
            qs.filter(
                status__in=(
                    "PROTOCOLADO",
                    "EM_EXECUCAO",
                    "AGUARDANDO_TRANSFERENCIA",
                    "AGUARDANDO_PROTOCOLO",
                )
            )
        )
        return {
            "protocolados": protocolados,
            "operacionais": operacionais,
            "devolutivas": devolutivas,
            "finalizados": finalizados,
            "abertos": protocolados + operacionais + devolutivas,
            "atrasados": atrasados,
        }

    def atalhos(self, user) -> list[dict[str, Any]]:
        perfil = getattr(user, "perfil", None)
        if perfil == "VEREADOR":
            return self._atalhos_vereador(user)
        if perfil == "CAMARA":
            return self._atalhos_camara(user)
        if perfil == "PROTOCOLO":
            return self._atalhos_protocolo(user)
        if perfil == "SECRETARIA":
            return self._atalhos_secretaria(user)
        if perfil == "GESTOR":
            return self._atalhos_gestor(user)
        return []

    def _atalhos_camara(self, user) -> list[dict[str, Any]]:
        uid = str(user.pk)
        return [
            AtalhoConsulta(
                "rascunhos",
                "Rascunhos de indicação",
                "Indicações ainda não protocoladas",
                "/demandas",
                {"status": "RASCUNHO"},
                self._count(user, {"autor": uid, "status": "RASCUNHO", "tipo_legislativo": "INDICACAO"}),
                "pi pi-file-edit",
            ).as_dict(),
            AtalhoConsulta(
                "aguardando",
                "Aguardando protocolo",
                "Enviadas à fila do Protocolo Executivo",
                "/demandas",
                {"status": "AGUARDANDO_PROTOCOLO"},
                self._count(user, {"autor": uid, "status": "AGUARDANDO_PROTOCOLO", "tipo_legislativo": "INDICACAO"}),
                "pi pi-send",
            ).as_dict(),
            AtalhoConsulta(
                "tramitacao",
                "Em tramitação",
                "Indicações protocoladas em execução",
                "/demandas",
                {"status__in": "PROTOCOLADO,EM_EXECUCAO,AGUARDANDO_TRANSFERENCIA"},
                self._count(
                    user,
                    {
                        "autor": uid,
                        "tipo_legislativo": "INDICACAO",
                        "status__in": "PROTOCOLADO,EM_EXECUCAO,AGUARDANDO_TRANSFERENCIA",
                    },
                ),
                "pi pi-sync",
            ).as_dict(),
            AtalhoConsulta(
                "nova",
                "Nova indicação",
                "Abrir o Copiloto para registrar indicação",
                "/copiloto",
                {},
                None,
                "pi pi-comments",
            ).as_dict(),
        ]

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
                "/configuracao-carta",
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
        elif perfil == "CAMARA":
            params["autor"] = str(user.pk)
            params["tipo_legislativo"] = "INDICACAO"
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
                        "tipo_legislativo": d.tipo_legislativo,
                        "bairro": d.bairro,
                        "endereco": OficioService._formatar_endereco(d) or None,
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
