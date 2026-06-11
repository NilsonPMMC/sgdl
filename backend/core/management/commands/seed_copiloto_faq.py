"""Carrega a FAQ inicial do Copiloto (Mogi das Cruzes) — idempotente."""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models_copiloto_faq import CopilotoFaqOrientacao, CopilotoFaqPadraoRegex
from core.services.copiloto_faq_service import invalidar_cache_faq

SEED_ENTRADAS = (
    {
        "slug": "energia-mogi",
        "categoria_orientacao": "ENERGIA_CONCESSIONARIA",
        "titulo": "Fornecimento de energia elétrica",
        "mensagem": (
            "Interrupções ou problemas no fornecimento de energia elétrica na rede da "
            "concessionária (conta de luz, medidor, queda de energia na residência/comércio) "
            "devem ser tratados diretamente com a companhia responsável pelo serviço em Mogi das Cruzes."
        ),
        "orgao_hint": "Concessionária de energia (ex.: CPFL Piratininga na região)",
        "ordem": 10,
        "padroes": (
            r"\bconta\s+de\s+luz\b",
            r"\bfatura\s+(?:de\s+)?(?:luz|energia)\b",
            r"\bconcession[aá]ria\s+de\s+energia\b",
            r"\b(?:cpfl|enel|eletropaulo|light|cemig|copel)\b",
            r"\bmedidor\s+de\s+(?:luz|energia)\b",
            r"\bfalta\s+de\s+energia\s+(?:em\s+casa|na\s+resid[eê]ncia|no\s+im[oó]vel)\b",
            r"\benergia\s+el[eé]trica\s+(?:residencial|domiciliar)\b",
            r"\bqueda\s+de\s+energia\s+(?:em\s+casa|na\s+casa)\b",
        ),
    },
    {
        "slug": "agua-mogi",
        "categoria_orientacao": "AGUA_SANEAMENTO",
        "titulo": "Abastecimento de água e esgoto (concessionária)",
        "mensagem": (
            "Falta de água, vazamentos na rede da concessionária, conta de água ou esgoto "
            "domiciliar costumam ser atendidos pela companhia de saneamento — não pelo gabinete "
            "como ofício de zeladoria municipal."
        ),
        "orgao_hint": "SABESP ou serviço de saneamento da região",
        "ordem": 20,
        "padroes": (
            r"\bconta\s+de\s+[aá]gua\b",
            r"\bfalta\s+d[e']?\s*[aá]gua\s+(?:em\s+casa|na\s+resid[eê]ncia|no\s+im[oó]vel)\b",
            r"\b(?:sabesp|sanepar|cedae|copasa)\b",
            r"\besgoto\s+(?:domiciliar|residencial|da\s+casa)\b",
            r"\bagua\s+na\s+torneira\b",
        ),
    },
    {
        "slug": "telefonia-mogi",
        "categoria_orientacao": "TELEFONIA_INTERNET",
        "titulo": "Telefonia, internet e TV por assinatura",
        "mensagem": (
            "Reclamações sobre telefone fixo, internet banda larga, celular ou TV por assinatura "
            "devem ser direcionadas à operadora contratada ou aos canais de defesa do consumidor "
            "(Procon / Anatel), conforme o caso."
        ),
        "orgao_hint": "Operadora contratada ou Procon / Anatel",
        "ordem": 30,
        "padroes": (
            r"\b(?:anatel|procon)\b",
            r"\binternet\s+(?:lenta|fora|caiu)\b",
            r"\btelefonia\s+fixa\b",
            r"\boperadora\s+de\s+(?:celular|telefonia|internet)\b",
            r"\b(?:vivo|claro|tim|oi)\s+(?:internet|fibra|celular)\b",
        ),
    },
    {
        "slug": "consumidor-mogi",
        "categoria_orientacao": "DEFESA_CONSUMIDOR",
        "titulo": "Relações de consumo (comércio e serviços privados)",
        "mensagem": (
            "Questões com lojas, bancos, planos de saúde privados ou produtos/serviços comerciais "
            "em geral não são tratadas como ofício de serviço público municipal. O Procon pode "
            "orientar em casos de consumo."
        ),
        "orgao_hint": "Procon Mogi das Cruzes ou órgão regulador do setor",
        "ordem": 40,
        "padroes": (
            r"\bprocon\b",
            r"\bestabelecimento\s+comercial\b",
            r"\bloja\s+(?:n[aã]o|nao)\b",
            r"\bplano\s+de\s+sa[uú]de\s+privad",
        ),
    },
)


class Command(BaseCommand):
    help = "Popula a base FAQ do Copiloto (orientações fora da competência municipal)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria criado sem gravar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options["dry_run"]
        criadas = 0
        padroes_novos = 0

        for entrada in SEED_ENTRADAS:
            cat = entrada["categoria_orientacao"]
            if dry:
                self.stdout.write(f"[dry-run] FAQ {cat}")
                continue

            faq, created = CopilotoFaqOrientacao.objects.get_or_create(
                categoria_orientacao=cat,
                defaults={
                    "slug": entrada["slug"],
                    "titulo": entrada["titulo"],
                    "mensagem": entrada["mensagem"],
                    "orgao_hint": entrada["orgao_hint"],
                    "municipio_referencia": "Mogi das Cruzes",
                    "ordem": entrada["ordem"],
                    "fonte": CopilotoFaqOrientacao.FONTE_MIGRACAO,
                    "ativo": True,
                },
            )
            if created:
                criadas += 1
            else:
                faq.titulo = entrada["titulo"]
                faq.mensagem = entrada["mensagem"]
                faq.orgao_hint = entrada["orgao_hint"]
                faq.ordem = entrada["ordem"]
                faq.ativo = True
                faq.save(update_fields=["titulo", "mensagem", "orgao_hint", "ordem", "ativo"])

            for i, expr in enumerate(entrada["padroes"]):
                if not faq.padroes.filter(expressao=expr).exists():
                    CopilotoFaqPadraoRegex.objects.create(
                        faq=faq,
                        expressao=expr,
                        ordem=10 + i,
                        fonte=CopilotoFaqOrientacao.FONTE_MIGRACAO,
                    )
                    padroes_novos += 1

        if not dry:
            invalidar_cache_faq()
        self.stdout.write(
            self.style.SUCCESS(
                f"FAQ Copiloto: {criadas} entradas novas, {padroes_novos} padrões regex adicionados."
            )
        )
