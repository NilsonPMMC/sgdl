"""
Validação em massa da triagem da Carta de Serviços otimizada.

Gera frases-teste por serviço e verifica se o retrieval recupera o sinapse_servico_id correto.
"""

import json
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models_carta_otimizada import ServicoOtimizado
from core.services.carta_rag_builder import _detectar_categoria
from core.services.carta_triagem_validacao import (
    avaliar_frases_servico,
    gerar_frases_teste,
    limiar_triagem_carta,
    listar_servicos_genericos,
)


class Command(BaseCommand):
    help = """
    Valida retrieval da carta otimizada (frases-teste → top-K → score mínimo).

    Exemplos:
      python manage.py validar_triagem_carta --limite 20
      python manage.py validar_triagem_carta --apenas-genericos --exportar /tmp/validacao.json
      python manage.py validar_triagem_carta --sinapse-id 978
      python manage.py validar_triagem_carta --caso "proteção ao consumidor" --sinapse-id 978
    """

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=0, help="0 = todos do filtro")
        parser.add_argument("--sinapse-id", type=int, help="Validar um serviço Sinapse")
        parser.add_argument("--apenas-genericos", action="store_true")
        parser.add_argument("--apenas-procon", action="store_true")
        parser.add_argument("--com-llm", action="store_true", help="Gera frases extras via LLM")
        parser.add_argument("--limiar", type=float, default=0, help="0 = COPILOTO_CARTA_SCORE_MINIMO")
        parser.add_argument("--exportar", type=str, help="Salvar relatório JSON")
        parser.add_argument(
            "--caso",
            type=str,
            help="Validar uma frase avulsa contra sinapse-id (com --sinapse-id)",
        )

    def handle(self, *args, **options):
        limiar = options["limiar"] or limiar_triagem_carta()
        self.stdout.write(self.style.SUCCESS(f"Validação triagem carta (limiar ≥ {limiar:.4f})"))

        if options.get("caso") and options.get("sinapse_id"):
            return self._validar_caso_avulso(options["caso"], options["sinapse_id"], limiar)

        servicos = self._selecionar_servicos(options)
        total = len(servicos)
        if not total:
            self.stdout.write(self.style.WARNING("Nenhum serviço no filtro."))
            return

        self.stdout.write(f"Serviços a validar: {total}")

        aprovados = falhas = 0
        relatorio_falhas: list[dict] = []
        relatorio: dict = {
            "gerado_em": datetime.now().isoformat(),
            "limiar": limiar,
            "total": total,
            "resultados": [],
        }

        for i, servico in enumerate(servicos, 1):
            frases = gerar_frases_teste(servico, com_llm=options["com_llm"])
            res = avaliar_frases_servico(servico, frases, limiar=limiar)
            relatorio["resultados"].append(res)

            if res["aprovado"]:
                aprovados += 1
                if i <= 5 or i % 50 == 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [{i}/{total}] OK {servico.sinapse_servico_id} "
                            f"{servico.titulo_otimizado[:45]}"
                        )
                    )
            else:
                falhas += 1
                relatorio_falhas.append(res)
                self.stdout.write(
                    self.style.WARNING(
                        f"  [{i}/{total}] FALHA {servico.sinapse_servico_id} "
                        f"{servico.titulo_otimizado[:45]} "
                        f"({res['frases_ok']}/{res['frases_testadas']} frases)"
                    )
                )
                d0 = res["detalhes"][0] if res["detalhes"] else {}
                if d0.get("top1_titulo"):
                    self.stdout.write(
                        f"      top1: [{d0.get('top1_id')}] {d0['top1_titulo']} "
                        f"({d0.get('top1_score')})"
                    )

        relatorio["aprovados"] = aprovados
        relatorio["falhas"] = falhas
        relatorio["taxa_aprovacao"] = round(aprovados / total * 100, 1) if total else 0

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Aprovados: {aprovados}/{total} ({relatorio['taxa_aprovacao']}%)")
        self.stdout.write(f"Falhas: {falhas}")

        if relatorio_falhas[:10]:
            self.stdout.write("\nAmostra de falhas (até 10):")
            for f in relatorio_falhas[:10]:
                self.stdout.write(f"  - [{f['sinapse_servico_id']}] {f['titulo'][:50]}")

        if options.get("exportar"):
            path = options["exportar"]
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(relatorio, fp, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Relatório: {path}"))

    def _validar_caso_avulso(self, frase: str, sinapse_id: int, limiar: float) -> None:
        servico = ServicoOtimizado.objects.filter(sinapse_servico_id=sinapse_id).first()
        if not servico:
            self.stdout.write(self.style.ERROR(f"Serviço Sinapse {sinapse_id} não encontrado."))
            return
        res = avaliar_frases_servico(servico, [frase.lower()], limiar=limiar)
        d = res["detalhes"][0]
        self.stdout.write(f"Frase: {frase}")
        self.stdout.write(f"Esperado: {sinapse_id} — {servico.titulo_otimizado}")
        self.stdout.write(
            f"Resultado: pos={d.get('posicao')} score={d.get('score')} "
            f"top1=[{d.get('top1_id')}] {d.get('top1_titulo')}"
        )
        if d.get("ok"):
            self.stdout.write(self.style.SUCCESS("APROVADO"))
        else:
            self.stdout.write(self.style.ERROR("FALHA"))

    def _selecionar_servicos(self, options) -> list[ServicoOtimizado]:
        if options.get("sinapse_id"):
            s = ServicoOtimizado.objects.filter(sinapse_servico_id=options["sinapse_id"])
            return list(s)

        if options.get("apenas_genericos"):
            servicos = listar_servicos_genericos()
        elif options.get("apenas_procon"):
            servicos = list(
                ServicoOtimizado.objects.filter(
                    ativo=True, titulo_otimizado__icontains="PROCON"
                ).order_by("id")
            )
        else:
            servicos = list(ServicoOtimizado.objects.filter(ativo=True).order_by("id"))

        limite = options["limite"] or 0
        if limite > 0:
            servicos = servicos[:limite]
        return servicos
