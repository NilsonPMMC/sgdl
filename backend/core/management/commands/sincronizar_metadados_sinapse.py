"""
Sincroniza metadados do Sinapse para ServicoOtimizado:
atendimento/sistema, prazo, documentos e taxas.
"""

import logging
import re
from django.core.management.base import BaseCommand
from core.models_carta_otimizada import ServicoOtimizado, LogOtimizacao
from core.services.carta_sinapse_sync import (
    regenerar_embedding_servico,
    sincronizar_gestao_operacional_local,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Preenche tipos_atendimento, sistema_solicitacao, link_sistema, "
        "prazo, documentos e taxas a partir do Sinapse"
    )

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=0, help="0 = todos")
        parser.add_argument("--servico-id", type=int, help="ID local ServicoOtimizado")
        parser.add_argument(
            "--sem-embedding",
            action="store_true",
            help="Não regenera embedding após atualizar bloco RAG operacional",
        )

    def handle(self, *args, **options):
        from integrations.models_sinapse import CatalogServico, SINAPSE_DB_ALIAS

        qs = ServicoOtimizado.objects.all().order_by("id")
        if options["servico_id"]:
            qs = qs.filter(id=options["servico_id"])
        if options["limite"]:
            qs = qs[: options["limite"]]

        total = qs.count()
        self.stdout.write(self.style.SUCCESS(f"Sincronizando {total} serviços..."))

        vector_service = None
        if not options["sem_embedding"]:
            from core.services.vector_service import VectorService

            vector_service = VectorService()

        ok_atendimento = 0
        ok_gestao = 0
        ok_embedding = 0

        for i, local in enumerate(qs, 1):
            try:
                sin = (
                    CatalogServico.objects.using(SINAPSE_DB_ALIAS)
                    .select_related("id_tipo_atendimento")
                    .filter(id=local.sinapse_servico_id)
                    .first()
                )
                if not sin:
                    continue

                alterou = False
                detalhes: dict = {"tipo": "SYNC_SINAPSE"}

                tipos = []
                if sin.id_tipo_atendimento_id:
                    nome_tipo = getattr(sin.id_tipo_atendimento, "descricao", None)
                    if nome_tipo:
                        tipos.append(str(nome_tipo).strip())
                if sin.atendimento_dia_hora and sin.atendimento_dia_hora.strip():
                    tipos.append("Consultar horário no catálogo")

                sistema, link = _inferir_sistema(sin.solicitacao_internet, sin.solicitacao_perfil)

                update_atendimento: list[str] = []
                if tipos and local.tipos_atendimento != tipos:
                    local.tipos_atendimento = tipos
                    update_atendimento.append("tipos_atendimento")
                    detalhes["tipos"] = tipos
                if sistema and local.sistema_solicitacao != sistema:
                    local.sistema_solicitacao = sistema
                    update_atendimento.append("sistema_solicitacao")
                    detalhes["sistema"] = sistema
                if link and local.link_sistema != link:
                    local.link_sistema = link
                    update_atendimento.append("link_sistema")
                    detalhes["link"] = link

                if update_atendimento:
                    local.save(update_fields=update_atendimento)
                    ok_atendimento += 1
                    alterou = True

                update_gestao, rag_alterou = sincronizar_gestao_operacional_local(local, sin)
                if update_gestao:
                    if rag_alterou and not options["sem_embedding"]:
                        if regenerar_embedding_servico(local, vector_service):
                            update_gestao.append("embedding_otimizado")
                            ok_embedding += 1
                    local.save(update_fields=update_gestao)
                    ok_gestao += 1
                    alterou = True
                    detalhes["gestao"] = {
                        "prazo_dias": local.prazo_dias,
                        "docs": len(local.dependencias_documentos or []),
                        "pagamentos": len(local.dependencias_pagamentos or []),
                        "rag_atualizado": rag_alterou,
                    }

                if alterou:
                    LogOtimizacao.objects.create(
                        servico_otimizado=local,
                        operacao="ATUALIZACAO",
                        detalhes=detalhes,
                        usuario="sistema_sync",
                    )
                    if i <= 5 or i % 100 == 0:
                        self.stdout.write(
                            f"  [{i}/{total}] {local.titulo_otimizado[:50]} "
                            f"(prazo={local.prazo_dias}, docs={len(local.dependencias_documentos or [])})"
                        )

            except Exception as e:
                logger.exception("Erro sync %s: %s", local.id, e)

        self.stdout.write(
            self.style.SUCCESS(
                f"Concluído: atendimento={ok_atendimento}, gestão={ok_gestao}, "
                f"embeddings={ok_embedding} de {total}"
            )
        )


def _inferir_sistema(solicitacao_internet: str, solicitacao_perfil: str) -> tuple[str, str]:
    texto = f"{solicitacao_internet or ''} {solicitacao_perfil or ''}".strip()
    if not texto:
        return "", ""

    link = ""
    if solicitacao_internet and re.match(r"^https?://", solicitacao_internet.strip(), re.I):
        link = solicitacao_internet.strip()

    t = texto.lower()
    if "colab" in t:
        return "ColabGov", link
    if "sei" in t:
        return "SEI", link
    if "portal" in t or "internet" in t:
        return "Portal online", link
    if solicitacao_internet:
        return solicitacao_internet[:100], link
    return "", link
