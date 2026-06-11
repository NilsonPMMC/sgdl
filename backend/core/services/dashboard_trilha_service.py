"""KPIs do motor de trilhas (Carta / Tendência / Recusa) para dashboard Protocolo."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from core.models import ChatSession, Demanda


def _parse_data_param(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        dt = datetime.strptime(valor.strip()[:10], "%Y-%m-%d")
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    except ValueError:
        return None


def _extrair_recusas_sessao(sessao: ChatSession) -> list[str]:
    """Retorna motivos de recusa (ou placeholder) por item bloqueado no rascunho."""
    motivos: list[str] = []
    for item in sessao.demandas_rascunho or []:
        if not isinstance(item, dict):
            continue
        if not item.get("fora_competencia") and not item.get("descartada"):
            continue
        motivo = (item.get("motivo_recusa") or "").strip()
        if not motivo:
            motivo = (item.get("categoria_orientacao") or "").strip()
        motivos.append(motivo or "Recusa de competência (sem motivo registrado)")
    return motivos


class DashboardTrilhaService:
    """Agrega volumes por trilha e amostra de motivos de recusa no Copiloto."""

    def calcular(
        self,
        *,
        demandas_qs: QuerySet[Demanda] | None = None,
        autor_id: int | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
    ) -> dict[str, Any]:
        base = demandas_qs if demandas_qs is not None else Demanda.objects.exclude(
            status="RASCUNHO"
        )

        inicio = _parse_data_param(data_inicio)
        fim = _parse_data_param(data_fim)
        if inicio:
            base = base.filter(data_criacao__gte=inicio)
        if fim:
            fim_exclusive = fim.replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta

            fim_exclusive = fim_exclusive + timedelta(days=1)
            base = base.filter(data_criacao__lt=fim_exclusive)

        carta = base.filter(
            origem_vinculo=Demanda.ORIGEM_VINCULO_CARTA,
            tendencia__isnull=True,
        ).count()
        tendencia = base.filter(
            Q(origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA)
            | Q(tendencia_id__isnull=False)
        ).count()
        total_demandas = carta + tendencia

        sessoes = ChatSession.objects.all()
        if autor_id:
            sessoes = sessoes.filter(autor_id=autor_id)
        if inicio:
            sessoes = sessoes.filter(atualizado_em__gte=inicio)
        if fim:
            from datetime import timedelta

            fim_exclusive = fim + timedelta(days=1)
            sessoes = sessoes.filter(atualizado_em__lt=fim_exclusive)

        contador_motivos: Counter[str] = Counter()
        total_recusas = 0
        for sessao in sessoes.only("demandas_rascunho"):
            for motivo in _extrair_recusas_sessao(sessao):
                total_recusas += 1
                contador_motivos[motivo] += 1

        amostra = [
            {"motivo": motivo, "total": qtd}
            for motivo, qtd in contador_motivos.most_common(8)
        ]

        def pct(parte: int, total: int) -> float:
            if total <= 0:
                return 0.0
            return round(100.0 * parte / total, 1)

        total_motor = total_demandas + total_recusas

        return {
            "carta": {
                "total": carta,
                "percentual_demandas": pct(carta, total_demandas),
                "percentual_motor": pct(carta, total_motor),
            },
            "tendencia": {
                "total": tendencia,
                "percentual_demandas": pct(tendencia, total_demandas),
                "percentual_motor": pct(tendencia, total_motor),
            },
            "recusa": {
                "total": total_recusas,
                "percentual_motor": pct(total_recusas, total_motor),
                "fonte": "copiloto_sessoes",
            },
            "totais": {
                "demandas_formalizadas": total_demandas,
                "motor_ingressos": total_motor,
            },
            "amostra_motivo_recusa": amostra,
            "grafico_trilhas": [
                {"trilha": "Carta", "total": carta},
                {"trilha": "Tendência", "total": tendencia},
                {"trilha": "Recusa (Copiloto)", "total": total_recusas},
            ],
        }

    def mensal_por_trilha(
        self, demandas_qs: QuerySet[Demanda]
    ) -> list[dict[str, Any]]:
        """Série mensal carta × tendência (demandas formalizadas)."""
        from django.db.models.functions import TruncMonth

        rows = (
            demandas_qs.annotate(mes=TruncMonth("data_criacao"))
            .values("mes")
            .annotate(
                carta=Count(
                    "id",
                    filter=Q(
                        origem_vinculo=Demanda.ORIGEM_VINCULO_CARTA,
                        tendencia__isnull=True,
                    ),
                ),
                tendencia=Count(
                    "id",
                    filter=Q(origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA)
                    | Q(tendencia_id__isnull=False),
                ),
            )
            .order_by("mes")
        )
        out = []
        for row in rows:
            if not row["mes"]:
                continue
            out.append(
                {
                    "mes": row["mes"].strftime("%Y-%m"),
                    "carta": row["carta"],
                    "tendencia": row["tendencia"],
                }
            )
        return out

    def listar_recusas(
        self,
        *,
        autor_id: int | None = None,
        motivo: str | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Lista itens bloqueados no Copiloto (fora de competência / descartados)."""
        sessoes = ChatSession.objects.select_related("autor").order_by("-atualizado_em")
        if autor_id:
            sessoes = sessoes.filter(autor_id=autor_id)
        inicio = _parse_data_param(data_inicio)
        fim = _parse_data_param(data_fim)
        if inicio:
            sessoes = sessoes.filter(atualizado_em__gte=inicio)
        if fim:
            from datetime import timedelta

            sessoes = sessoes.filter(atualizado_em__lt=fim + timedelta(days=1))

        motivo_busca = (motivo or "").strip().lower()
        rows: list[dict[str, Any]] = []
        for sessao in sessoes.only("demandas_rascunho", "atualizado_em", "autor_id"):
            autor = sessao.autor
            autor_nome = (
                f"{autor.first_name or ''} {autor.last_name or ''}".strip()
                or autor.username
            )
            for item in sessao.demandas_rascunho or []:
                if not isinstance(item, dict):
                    continue
                if not item.get("fora_competencia") and not item.get("descartada"):
                    continue
                motivo_txt = (item.get("motivo_recusa") or "").strip()
                if not motivo_txt:
                    motivo_txt = (item.get("categoria_orientacao") or "").strip()
                motivo_txt = motivo_txt or "Recusa de competência (sem motivo registrado)"
                if motivo_busca and motivo_busca not in motivo_txt.lower():
                    continue
                rows.append(
                    {
                        "session_id": str(sessao.id),
                        "atualizado_em": sessao.atualizado_em.isoformat(),
                        "autor_id": sessao.autor_id,
                        "autor_nome": autor_nome,
                        "titulo": (item.get("titulo") or "Sem título").strip(),
                        "motivo_recusa": motivo_txt,
                        "categoria_orientacao": item.get("categoria_orientacao"),
                        "descartada": bool(item.get("descartada")),
                    }
                )
                if len(rows) >= limit:
                    return rows
        return rows
