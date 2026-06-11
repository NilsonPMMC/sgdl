# Generated manually — FAQ Copiloto em banco

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_tendencia_demanda_origem_vinculo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CopilotoFaqOrientacao",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="Identificador estável (ex.: energia-mogi).",
                        max_length=80,
                        unique=True,
                    ),
                ),
                (
                    "categoria_orientacao",
                    models.CharField(
                        db_index=True,
                        help_text="Código usado pelo LLM em categoria_orientacao (ex.: ENERGIA_CONCESSIONARIA).",
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("titulo", models.CharField(max_length=200)),
                (
                    "mensagem",
                    models.TextField(
                        help_text="Texto exibido ao cidadão na recusa do Copiloto."
                    ),
                ),
                (
                    "orgao_hint",
                    models.CharField(
                        help_text="Para onde encaminhar (ex.: CPFL, SABESP, Procon).",
                        max_length=255,
                    ),
                ),
                (
                    "municipio_referencia",
                    models.CharField(
                        default="Mogi das Cruzes",
                        help_text="Contexto local usado pela automação de IA ao enriquecer entradas.",
                        max_length=120,
                    ),
                ),
                (
                    "ativo",
                    models.BooleanField(
                        default=True,
                        help_text="Somente entradas ativas entram na detecção do Copiloto.",
                    ),
                ),
                (
                    "ordem",
                    models.PositiveSmallIntegerField(
                        default=100,
                        help_text="Menor = maior prioridade na detecção por regex.",
                    ),
                ),
                (
                    "fonte",
                    models.CharField(
                        choices=[
                            ("MANUAL", "Cadastro manual (Admin)"),
                            ("LLM", "Sugestão / enriquecimento por IA"),
                            ("MIGRACAO", "Migração ou seed inicial"),
                        ],
                        default="MANUAL",
                        max_length=16,
                    ),
                ),
                (
                    "notas_internas",
                    models.TextField(
                        blank=True,
                        help_text="Notas para Protocolo / curadoria (não exibidas ao cidadão).",
                    ),
                ),
                (
                    "ultima_sincronizacao_llm",
                    models.DateTimeField(
                        blank=True,
                        help_text="Última vez que a automação de IA alterou este registro.",
                        null=True,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "revisado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="faq_copiloto_revisadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "FAQ Copiloto (orientação)",
                "verbose_name_plural": "FAQ Copiloto — base de conhecimento",
                "ordering": ["ordem", "titulo"],
            },
        ),
        migrations.CreateModel(
            name="CopilotoFaqPadraoRegex",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "expressao",
                    models.CharField(
                        help_text="Expressão regular (Python), flag IGNORECASE aplicada automaticamente.",
                        max_length=500,
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                ("ordem", models.PositiveSmallIntegerField(default=100)),
                (
                    "fonte",
                    models.CharField(
                        choices=[
                            ("MANUAL", "Cadastro manual (Admin)"),
                            ("LLM", "Sugestão / enriquecimento por IA"),
                            ("MIGRACAO", "Migração ou seed inicial"),
                        ],
                        default="MANUAL",
                        max_length=16,
                    ),
                ),
                ("notas", models.CharField(blank=True, max_length=255)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "faq",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="padroes",
                        to="core.copilotofaqorientacao",
                    ),
                ),
            ],
            options={
                "verbose_name": "Padrão regex (FAQ)",
                "verbose_name_plural": "Padrões regex (FAQ)",
                "ordering": ["ordem", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="copilotofaqorientacao",
            index=models.Index(
                fields=["ativo", "ordem"], name="core_copilo_ativo_i_6e8f0a_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="copilotofaqorientacao",
            index=models.Index(
                fields=["municipio_referencia", "ativo"],
                name="core_copilo_municip_2a1b9c_idx",
            ),
        ),
    ]
