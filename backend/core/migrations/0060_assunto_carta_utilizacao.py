from django.db import migrations, models
import django.db.models.deletion


ASSUNTOS_INICIAIS = [
    (1, "alvara-certidoes-licencas", "Alvará, Certidões e Licenças", "INFORMATIVO",
     "Este assunto é de orientação ao cidadão. Indique ColabGov, portal ou atendimento presencial."),
    (2, "animais", "Animais", "PROTOCOLAVEL", ""),
    (3, "cultura-turismo", "Cultura e Turismo", "PROTOCOLAVEL", ""),
    (4, "educacao", "Educação", "PROTOCOLAVEL", ""),
    (5, "emprego-profissionalizacao", "Emprego e Profissionalização", "PROTOCOLAVEL", ""),
    (6, "esporte-lazer", "Esporte e Lazer", "PROTOCOLAVEL", ""),
    (7, "impostos-taxas", "Impostos e Taxas", "INFORMATIVO",
     "Muitos serviços fiscais são autoatendimento. Oriente o munícipe ao canal correto."),
    (8, "procon-transparencia-ouvidoria", "Procon, Transparência e Ouvidoria", "INFORMATIVO",
     "Encaminhe ao Procon, ouvidoria ou portal de transparência conforme o caso."),
    (9, "protecao-social-habitacao", "Proteção Social e Habitação", "PROTOCOLAVEL", ""),
    (10, "saneamento", "Saneamento", "PROTOCOLAVEL", ""),
    (11, "saude", "Saúde", "PROTOCOLAVEL", ""),
    (12, "seguranca-fiscalizacao", "Segurança e Fiscalização", "PROTOCOLAVEL", ""),
    (13, "sustentabilidade-agricultura", "Sustentabilidade e Agricultura", "PROTOCOLAVEL", ""),
    (14, "transporte-transito", "Transporte e Trânsito", "PROTOCOLAVEL", ""),
    (15, "zeladoria-obras-publicas", "Zeladoria e Obras Públicas", "PROTOCOLAVEL", ""),
]


def seed_assuntos(apps, schema_editor):
    AssuntoCarta = apps.get_model("core", "AssuntoCarta")
    for ordem, slug, nome, modo, msg in ASSUNTOS_INICIAIS:
        AssuntoCarta.objects.update_or_create(
            slug=slug,
            defaults={
                "nome": nome,
                "ordem": ordem,
                "modo_utilizacao_sgdl": modo,
                "mensagem_orientacao": msg,
                "ativo": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0059_depara_rm_unidade_campos"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssuntoCarta",
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
                ("nome", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("ordem", models.PositiveSmallIntegerField(default=0)),
                (
                    "modo_utilizacao_sgdl",
                    models.CharField(
                        choices=[
                            ("PROTOCOLAVEL", "Protocolável"),
                            ("INFORMATIVO", "Somente orientação"),
                            ("PROTOCOLAVEL_CONDICIONAL", "Protocolável com condição"),
                        ],
                        default="PROTOCOLAVEL",
                        max_length=32,
                    ),
                ),
                (
                    "mensagem_orientacao",
                    models.TextField(
                        blank=True,
                        help_text="Texto exibido no Copiloto quando o modo efetivo for informativo.",
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Assunto temático (carta)",
                "verbose_name_plural": "Assuntos temáticos (carta)",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.AddField(
            model_name="servicootimizado",
            name="assunto",
            field=models.ForeignKey(
                blank=True,
                help_text="Assunto temático de gestão (C5).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="servicos_otimizados",
                to="core.assuntocarta",
            ),
        ),
        migrations.AddField(
            model_name="servicootimizado",
            name="mensagem_orientacao",
            field=models.TextField(
                blank=True,
                help_text="Orientação específica deste serviço (quando informativo).",
            ),
        ),
        migrations.AddField(
            model_name="servicootimizado",
            name="modo_utilizacao_sgdl",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PROTOCOLAVEL", "Protocolável"),
                    ("INFORMATIVO", "Somente orientação"),
                    ("PROTOCOLAVEL_CONDICIONAL", "Protocolável com condição"),
                ],
                help_text="Override do modo do assunto; vazio = herda do assunto.",
                max_length=32,
            ),
        ),
        migrations.RunPython(seed_assuntos, migrations.RunPython.noop),
    ]
