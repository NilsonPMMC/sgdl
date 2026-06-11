"""
Otimização semântica via LLM para serviços da carta (long tail / genéricos).

Complementa otimizar_texto_inteligente (templates) com texto único por serviço.
"""

import logging
import re
import time

from django.core.management.base import BaseCommand

from core.models_carta_otimizada import ServicoOtimizado, LogOtimizacao
from core.services.llm_service import LLMService
from core.services.carta_rag_builder import _detectar_categoria, _uniq_palavras
from core.services.carta_triagem_validacao import listar_servicos_genericos
from core.services.vector_service import VectorService

logger = logging.getLogger(__name__)

VERSAO_LLM = "3.3_LLM"


class Command(BaseCommand):
    help = """
    Enriquece RAG via LLM + regenera embedding.

    python manage.py otimizar_texto_llm_real --apenas-genericos --todos
    python manage.py otimizar_texto_llm_real --servico-id 12 --dry-run
    """

    def add_arguments(self, parser):
        parser.add_argument("--servico-id", type=int, help="ID local ServicoOtimizado")
        parser.add_argument("--limite", type=int, default=50)
        parser.add_argument("--todos", action="store_true", help="Ignora --limite")
        parser.add_argument("--force", action="store_true", help="Reprocessa mesmo com versão LLM")
        parser.add_argument(
            "--apenas-genericos",
            action="store_true",
            help="Somente serviços classificados como generico no builder",
        )
        parser.add_argument("--dry-run", action="store_true", help="Não grava no banco")
        parser.add_argument(
            "--versao-alvo",
            default=VERSAO_LLM,
            help=f"Versão gravada (padrão {VERSAO_LLM})",
        )

    def handle(self, *args, **options):
        versao = (options["versao_alvo"] or VERSAO_LLM)[:12]
        self.stdout.write(self.style.SUCCESS(f"Otimização LLM → versão {versao}"))

        llm = LLMService()
        if not llm.api_key:
            self.stdout.write(self.style.ERROR("GROQ_API_KEY não configurada no .env"))
            return
        ping = llm.completar_texto("Responda apenas: ok", "ping")
        if not ping:
            self.stdout.write(
                self.style.ERROR(
                    "Groq indisponível ou chave inválida — verifique GROQ_API_KEY e GROQ_BASE_URL"
                )
            )
            return
        self.stdout.write(f"Groq OK (modelo {llm.model})")
        self.stdout.write(
            "Embeddings: Kernel (AI_KERNEL_BASE_URL) — chat LLM: Groq API"
        )

        servicos = self._selecionar_servicos(options)
        if not options["todos"] and not options.get("servico_id"):
            servicos = servicos[: options["limite"]]

        total = len(servicos)
        self.stdout.write(f"Serviços a processar: {total}")
        if not total:
            return

        vector = VectorService()
        ok = erros = 0

        for i, servico in enumerate(servicos, 1):
            try:
                texto_llm = self._otimizar_com_llm(llm, servico)
                if not texto_llm:
                    erros += 1
                    self.stdout.write(self.style.WARNING(f"  [{i}] sem resposta LLM"))
                    continue

                pacote = self._texto_para_campos(servico, texto_llm)
                if options["dry_run"]:
                    self.stdout.write(f"  [{i}] DRY {servico.titulo_otimizado[:40]}")
                    self.stdout.write(texto_llm[:200] + "...")
                    ok += 1
                    continue

                emb = vector.generate_embedding(pacote["texto_rag_otimizado"])
                if not emb:
                    erros += 1
                    continue

                versao_ant = servico.versao_otimizacao
                servico.intencao_servico = pacote["intencao_servico"]
                servico.problemas_resolve = pacote["problemas_resolve"]
                servico.texto_rag_otimizado = pacote["texto_rag_otimizado"]
                servico.palavras_chave = pacote["palavras_chave"]
                servico.embedding_otimizado = emb
                servico.versao_otimizacao = versao
                servico.score_qualidade_otimizado = min(
                    max(servico.score_qualidade_otimizado, 7) + 1, 10
                )
                servico.save()

                LogOtimizacao.objects.create(
                    servico_otimizado=servico,
                    operacao="OTIMIZACAO_LLM",
                    detalhes={
                        "tipo": "RAG_LLM",
                        "versao_anterior": versao_ant,
                        "versao_nova": versao,
                        "categoria_builder": _detectar_categoria(
                            servico.titulo_otimizado, servico.descricao_objetiva or ""
                        ),
                    },
                    usuario="sistema_llm",
                )
                ok += 1
                if i <= 3 or i % 25 == 0:
                    self.stdout.write(
                        self.style.SUCCESS(f"  [{i}/{total}] {servico.titulo_otimizado[:45]}")
                    )
                time.sleep(1.2)
            except Exception as e:
                erros += 1
                logger.exception("Erro serviço %s", servico.id)
                self.stdout.write(self.style.ERROR(f"  [{i}] {e}"))

        self.stdout.write(self.style.SUCCESS(f"Concluído: {ok} ok, {erros} erros"))

    def _selecionar_servicos(self, options) -> list[ServicoOtimizado]:
        if options.get("servico_id"):
            return list(ServicoOtimizado.objects.filter(id=options["servico_id"]))

        if options.get("apenas_genericos"):
            qs = listar_servicos_genericos()
        else:
            qs = list(ServicoOtimizado.objects.filter(ativo=True).order_by("id"))

        if not options.get("force"):
            qs = [
                s for s in qs
                if not (s.versao_otimizacao or "").startswith("3.3")
            ]
        return qs

    def _otimizar_com_llm(self, llm: LLMService, servico: ServicoOtimizado) -> str | None:
        system = (
            "Você otimiza textos de serviços públicos municipais para busca semântica (RAG). "
            "Use linguagem coloquial do cidadão, sinônimos e situações reais. "
            "NÃO confunda com serviços parecidos de outras secretarias."
        )
        user = f"""Serviço municipal:
Título: {servico.titulo_otimizado}
Descrição: {(servico.descricao_objetiva or '')[:400]}

Gere texto RAG estruturado EXATAMENTE neste formato:

TÍTULO: (título em maiúsculas)
Intenção: (1-2 frases claras sobre para que serve)
Situações que este serviço atende:
- (bullet 1 linguagem cidadã)
- (bullet 2)
- (bullet 3)
Exemplos de como o cidadão pede:
- (frase coloquial 1)
- (frase coloquial 2)
Palavras-chave: (lista separada por vírgula)

Inclua termos que cidadãos usam no dia a dia para encontrar ESTE serviço específico."""

        raw = llm.completar_texto(system, user)
        if raw and len(raw.strip()) > 80:
            return raw.strip()
        return None

    def _texto_para_campos(self, servico: ServicoOtimizado, texto: str) -> dict:
        intencao = ""
        m = re.search(r"Intenção:\s*(.+?)(?:\n|$)", texto, re.I)
        if m:
            intencao = m.group(1).strip()

        problemas: list[str] = []
        bloco = re.search(
            r"Situações que este serviço atende:\s*(.+?)(?:\nExemplos|\nPalavras|\Z)",
            texto,
            re.I | re.S,
        )
        if bloco:
            for line in bloco.group(1).splitlines():
                line = re.sub(r"^[\-\*]\s*", "", line.strip())
                if len(line) > 10:
                    problemas.append(line)

        palavras: list[str] = []
        pk = re.search(r"Palavras-chave:\s*(.+?)(?:\n|$)", texto, re.I)
        if pk:
            palavras = _uniq_palavras([p.strip() for p in pk.group(1).split(",")])

        if not intencao:
            intencao = f"O serviço «{servico.titulo_otimizado}» atende demandas dos cidadãos."
        if not problemas:
            problemas = [f"Solicitação sobre {servico.titulo_otimizado}"]
        if not palavras:
            palavras = _uniq_palavras(
                re.findall(r"\w{3,}", f"{servico.titulo_otimizado} {texto}".lower())
            )

        return {
            "intencao_servico": intencao,
            "problemas_resolve": problemas[:6],
            "texto_rag_otimizado": texto,
            "palavras_chave": palavras[:20],
        }
