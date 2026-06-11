"""
Otimização semântica v3: RAG específico por serviço + campos estruturados.
"""

import logging
from django.core.management.base import BaseCommand
from core.models_carta_otimizada import ServicoOtimizado, LogOtimizacao
from core.services.vector_service import VectorService
from core.services.carta_rag_builder import construir_pacote_rag

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Otimiza RAG v3 com intenção, problemas e embedding regenerado"

    def add_arguments(self, parser):
        parser.add_argument("--servico-id", type=int)
        parser.add_argument("--limite", type=int, default=50)
        parser.add_argument(
            "--reprocessar-v2",
            action="store_true",
            help="Reprocessa serviços já na versão 2.0",
        )
        parser.add_argument(
            "--versao-alvo",
            default="3.1",
            help="Versão gravada após otimização (padrão 3.1)",
        )
        parser.add_argument(
            "--todos",
            action="store_true",
            help="Processa todos os pendentes (ignora --limite)",
        )
        parser.add_argument(
            "--forcar-todos",
            action="store_true",
            help="Reprocessa TODOS os serviços ativos, mesmo já na versão-alvo",
        )

    def handle(self, *args, **options):
        versao_alvo = (options["versao_alvo"] or "3.1")[:10]
        self.stdout.write(
            self.style.SUCCESS(f"Otimização RAG → versão {versao_alvo}...")
        )

        if options["servico_id"]:
            servicos = ServicoOtimizado.objects.filter(id=options["servico_id"])
        elif options.get("forcar_todos"):
            servicos = ServicoOtimizado.objects.filter(ativo=True).order_by("id")
        elif options["reprocessar_v2"]:
            servicos = ServicoOtimizado.objects.exclude(
                versao_otimizacao=versao_alvo
            ).order_by("id")
        else:
            servicos = ServicoOtimizado.objects.exclude(
                versao_otimizacao=versao_alvo
            ).order_by("id")

        if not options["todos"] and not options["servico_id"] and not options.get("forcar_todos"):
            servicos = servicos[: options["limite"]]

        total = servicos.count()
        self.stdout.write(f"Serviços a processar: {total}")

        vector_service = VectorService()
        sucesso = erros = 0

        for i, servico in enumerate(servicos, 1):
            try:
                versao_anterior = servico.versao_otimizacao
                pacote = construir_pacote_rag(
                    servico.titulo_otimizado,
                    servico.descricao_objetiva,
                    servico.sinapse_servico_id,
                )

                novo_embedding = vector_service.generate_embedding(pacote.texto_rag_otimizado)
                if not novo_embedding:
                    erros += 1
                    self.stdout.write(self.style.WARNING(f"  [{i}] sem embedding: {servico.titulo_otimizado[:40]}"))
                    continue

                servico.intencao_servico = pacote.intencao_servico
                servico.problemas_resolve = pacote.problemas_resolve
                servico.texto_rag_otimizado = pacote.texto_rag_otimizado
                servico.palavras_chave = pacote.palavras_chave
                servico.embedding_otimizado = novo_embedding
                servico.versao_otimizacao = versao_alvo  # noqa: versao definida acima
                servico.score_qualidade_otimizado = min(
                    max(servico.score_qualidade_otimizado, 7) + 1, 10
                )
                servico.save()

                LogOtimizacao.objects.create(
                    servico_otimizado=servico,
                    operacao="ATUALIZACAO",
                            detalhes={
                                "tipo": "RAG_V32",
                        "versao_anterior": versao_anterior,
                        "versao_nova": versao_alvo,
                        "categoria": pacote.categoria,
                        "embedding_regenerado": True,
                    },
                    usuario="sistema_v3",
                )

                sucesso += 1
                if i <= 3 or i % 25 == 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [{i}/{total}] {servico.titulo_otimizado[:45]} ({pacote.categoria})"
                        )
                    )
            except Exception as e:
                erros += 1
                logger.exception("Erro serviço %s", servico.id)
                self.stdout.write(self.style.ERROR(f"  [{i}] erro: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Concluído: {sucesso} ok, {erros} erros"))
