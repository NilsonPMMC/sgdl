"""
Vincula serviços da carta Sinapse aos setores EPL por secretaria (gestão de fluxo C2).

Uso típico (homologação):
  python manage.py vincular_setores_epl_fluxo --dry-run
  python manage.py vincular_setores_epl_fluxo
  python manage.py vincular_setores_epl_fluxo --orgao-id 18
  python manage.py vincular_setores_epl_fluxo --orgao-id 293   # aceita ID de serviço referência
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models_carta_otimizada import ServicoOtimizado
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.carta_setor_service import CartaSetorService
from integrations import sinapse_catalog


@dataclass(frozen=True)
class RegraEplOrgao:
    """Órgão Sinapse (CatalogOrgao) + UA EPL destino."""

    sinapse_orgao_id: int
    orgao_nome: str
    sigla_ua: str
    servico_referencia_id: int | None = None


# Órgãos = IDs do catálogo Sinapse (CatalogOrgao), não IDs de serviço.
# servico_referencia_id = exemplo citado na operação (ex.: serviço 293 → órgão 18 SMMT).
REGRAS_EPL_PADRAO: tuple[RegraEplOrgao, ...] = (
    RegraEplOrgao(
        18,
        "Secretaria de Mobilidade e Trânsito",
        "MCRUZ-SMMT-DIVGG-EPL",
        servico_referencia_id=293,
    ),
    RegraEplOrgao(
        2,
        "Secretaria de Assistência Social",
        "MCRUZ-SMAS-DIVDGG-EXP-EPL",
        servico_referencia_id=700,
    ),
    RegraEplOrgao(
        12,
        "Secretaria de Governo e Transparência",
        "SMHSRF-EXP-EPL",
        servico_referencia_id=379,
    ),
    RegraEplOrgao(
        16,
        "Secretaria de Segurança",
        "MCRUZ-SMSEG-GAB-EPL",
        servico_referencia_id=369,
    ),
    RegraEplOrgao(
        17,
        "Secretaria de Serviços Urbanos e Zeladoria",
        "MCRUZ-SMSUZ-SGG-EPL",
        servico_referencia_id=822,
    ),
)


def iter_servicos_sinapse_orgao(orgao_id: int, *, limit: int = 500):
    """Lista todos os IDs de serviço ativos do órgão no catálogo Sinapse."""
    offset = 0
    while True:
        busca = sinapse_catalog.buscar_servicos_catalogo(
            orgao_id=int(orgao_id),
            limit=limit,
            offset=offset,
        )
        results = busca.get("results") or []
        for item in results:
            sid = item.get("id")
            if sid is not None:
                yield int(sid)
        total = int(busca.get("total") or 0)
        offset += limit
        if offset >= total or not results:
            break


def resolver_unidade_epl(regra: RegraEplOrgao) -> UnidadeAdministrativa | None:
    """Localiza UA pela sigla RM (única no banco importado)."""
    ua = (
        UnidadeAdministrativa.objects.filter(sigla__iexact=regra.sigla_ua, ativo=True)
        .order_by("pk")
        .first()
    )
    if not ua:
        return None
    if int(ua.sinapse_orgao_id) != int(regra.sinapse_orgao_id):
        # Sigla encontrada, mas de-para RM aponta outro órgão — ainda utilizável se única.
        return ua
    return ua


def filtrar_regras(orgao_filtro: int | None) -> tuple[RegraEplOrgao, ...]:
    if orgao_filtro is None:
        return REGRAS_EPL_PADRAO

    por_orgao = tuple(
        r for r in REGRAS_EPL_PADRAO if r.sinapse_orgao_id == orgao_filtro
    )
    if por_orgao:
        return por_orgao

    por_servico_ref = tuple(
        r for r in REGRAS_EPL_PADRAO if r.servico_referencia_id == orgao_filtro
    )
    if por_servico_ref:
        return por_servico_ref

    orgao_inferido = sinapse_catalog.get_orgao_id_for_servico(orgao_filtro)
    if orgao_inferido:
        por_inferencia = tuple(
            r for r in REGRAS_EPL_PADRAO if r.sinapse_orgao_id == int(orgao_inferido)
        )
        if por_inferencia:
            return por_inferencia

    return ()


class Command(BaseCommand):
    help = (
        "Vincula setores EPL (UA) aos serviços da carta otimizada por secretaria Sinapse — "
        "gestão de fluxo operacional."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula sem gravar vínculos.",
        )
        parser.add_argument(
            "--orgao-id",
            type=int,
            default=None,
            help="Filtra por órgão Sinapse (ex.: 18) ou ID de serviço referência (ex.: 293).",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help="Reaplica mesmo quando o serviço já está vinculado ao EPL correto.",
        )
        parser.add_argument(
            "--incluir-sem-base",
            action="store_true",
            help="Lista serviços Sinapse sem registro em ServicoOtimizado (não vincula).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        orgao_filtro: int | None = options["orgao_id"]
        forcar: bool = options["forcar"]
        incluir_sem_base: bool = options["incluir_sem_base"]

        if not sinapse_catalog.catalog_disponivel():
            self.stdout.write(
                self.style.ERROR(
                    "Catálogo Sinapse indisponível (DATABASES['sinapse']). Abortando."
                )
            )
            return

        regras = filtrar_regras(orgao_filtro)
        if orgao_filtro is not None and not regras:
            self.stdout.write(
                self.style.ERROR(
                    f"Nenhuma regra EPL para orgao-id/serviço {orgao_filtro}. "
                    f"Órgãos mapeados: {[r.sinapse_orgao_id for r in REGRAS_EPL_PADRAO]}"
                )
            )
            return

        setor_svc = CartaSetorService()
        totais = {
            "servicos_catalogo": 0,
            "vinculados": 0,
            "ja_corretos": 0,
            "sem_base_otimizada": 0,
            "erros": 0,
        }

        for regra in regras:
            self.stdout.write("")
            ref = (
                f" (serv. ref. {regra.servico_referencia_id})"
                if regra.servico_referencia_id
                else ""
            )
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Órgão {regra.sinapse_orgao_id}{ref} — {regra.orgao_nome} → {regra.sigla_ua}"
                )
            )

            ua = resolver_unidade_epl(regra)
            if not ua:
                self.stdout.write(
                    self.style.ERROR(
                        f"  UA «{regra.sigla_ua}» não encontrada. "
                        "Execute importar_unidades_rm271698 ou ajuste a sigla."
                    )
                )
                totais["erros"] += 1
                continue

            if int(ua.sinapse_orgao_id) != int(regra.sinapse_orgao_id):
                self.stdout.write(
                    self.style.WARNING(
                        f"  UA orgão={ua.sinapse_orgao_id} (esperado {regra.sinapse_orgao_id}) — "
                        "usando sigla RM como chave."
                    )
                )

            self.stdout.write(
                f"  UA resolvida: pk={ua.pk} sigla={ua.sigla} orgao={ua.sinapse_orgao_id}"
            )

            servico_ids = list(iter_servicos_sinapse_orgao(regra.sinapse_orgao_id))
            totais["servicos_catalogo"] += len(servico_ids)
            self.stdout.write(f"  Serviços no catálogo Sinapse: {len(servico_ids)}")

            if not servico_ids:
                continue

            otimizados = {
                int(s.sinapse_servico_id): s
                for s in ServicoOtimizado.objects.filter(
                    sinapse_servico_id__in=servico_ids,
                    ativo=True,
                ).select_related("unidade_administrativa")
            }

            for sid in servico_ids:
                svc = otimizados.get(sid)
                if not svc:
                    totais["sem_base_otimizada"] += 1
                    if incluir_sem_base:
                        self.stdout.write(
                            self.style.WARNING(f"    [sem base] serviço Sinapse {sid}")
                        )
                    continue

                atual_id = svc.unidade_administrativa_id
                if atual_id == ua.pk and not forcar:
                    totais["ja_corretos"] += 1
                    continue

                rotulo_atual = (
                    svc.unidade_administrativa.sigla if svc.unidade_administrativa else "—"
                )
                acao = "atualizar" if atual_id else "vincular"
                if dry_run:
                    self.stdout.write(
                        f"    [dry-run] {acao} serviço {sid}: {rotulo_atual} → {ua.sigla}"
                    )
                    totais["vinculados"] += 1
                    continue

                try:
                    with transaction.atomic():
                        setor_svc.vincular(sid, ua.pk)
                    totais["vinculados"] += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"    ✓ serviço {sid}: {rotulo_atual} → {ua.sigla}"
                        )
                    )
                except ValueError as exc:
                    totais["erros"] += 1
                    self.stdout.write(
                        self.style.ERROR(f"    ✗ serviço {sid}: {exc}")
                    )

        self.stdout.write("")
        prefixo = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefixo}Resumo: "
                f"{totais['servicos_catalogo']} serviço(s) no catálogo | "
                f"{totais['vinculados']} vinculado(s)/atualizado(s) | "
                f"{totais['ja_corretos']} já corretos | "
                f"{totais['sem_base_otimizada']} sem base otimizada | "
                f"{totais['erros']} erro(s)"
            )
        )
        if totais["sem_base_otimizada"] and not incluir_sem_base:
            self.stdout.write(
                self.style.WARNING(
                    "  Use --incluir-sem-base para listar serviços sem ServicoOtimizado."
                )
            )
