"""Configuração institucional (singleton) — modelo de ofício da Câmara Municipal."""

from __future__ import annotations

from pathlib import Path

from django.db import models


def _fmt_css_num(valor) -> str:
    """Formata número para CSS/PDF — sempre ponto decimal (locale pt ignora vírgula)."""
    return f"{float(valor):.2f}"


def _css_dinamico_oficio(
    *,
    pagina_size: str,
    margem_superior: str,
    margem_direita: str,
    margem_inferior: str,
    margem_esquerda: str,
    brasao_largura: str,
    rodape_protocolo_altura: str,
) -> str:
    """Bloco CSS gerado no backend — evita tags Django dentro de regras estáticas."""
    return (
        ":root {\n"
        f"  --oficio-brasao-largura: {brasao_largura}cm;\n"
        f"  --oficio-rodape-protocolo-altura: {rodape_protocolo_altura}cm;\n"
        "}\n"
        "@page {\n"
        f"  size: {pagina_size};\n"
        f"  margin: {margem_superior}cm {margem_direita}cm "
        f"{margem_inferior}cm {margem_esquerda}cm;\n"
        "}"
    )


class ConfiguracaoOficio(models.Model):
    """Parâmetros de layout PDF e destinatário padrão (registro único, pk=1)."""

    PAGINA_FORMATO_CHOICES = [
        ("A4", "A4"),
        ("LETTER", "Carta"),
    ]
    PAGINA_ORIENTACAO_CHOICES = [
        ("portrait", "Retrato"),
        ("landscape", "Paisagem"),
    ]

    pk_fixo = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    municipio = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Cidade usada no cabeçalho e na data do ofício (opcional).",
    )
    uf = models.CharField(max_length=2, blank=True, default="")
    orgao_destinatario = models.CharField(
        max_length=255,
        default="Prefeitura Municipal de Mogi das Cruzes",
    )
    destinatario_tratamento = models.CharField(
        max_length=80,
        default="Excelentíssima Senhora Prefeita Municipal",
        help_text="Tratamento formal (ex.: Excelentíssima Senhora Prefeita Municipal).",
    )
    destinatario_nome = models.CharField(
        max_length=200,
        default="Mara Bertaiolli",
        help_text="Nome da autoridade destinatária do ofício.",
    )
    destinatario_cargo = models.CharField(
        max_length=200,
        default="Prefeita Municipal",
        blank=True,
    )
    CABECALHO_LAYOUT_CHOICES = [
        ("BRASAO_ESQUERDA_TEXTO", "Brasão | Descrição"),
        ("TEXTO_ESQUERDA_BRASAO", "Descrição | Brasão"),
        ("BRASAO_CENTRO", "Somente brasão (centro)"),
        ("BRASAO_ACIMA_TEXTO", "Brasão acima da descrição"),
        ("TEXTO_CENTRO", "Somente descrição (centro)"),
    ]

    titulo_instituicao = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Texto institucional ao lado do brasão (opcional).",
    )
    cabecalho_layout = models.CharField(
        max_length=32,
        choices=CABECALHO_LAYOUT_CHOICES,
        default="BRASAO_ESQUERDA_TEXTO",
    )
    imagem_cabecalho = models.ImageField(
        upload_to="oficio_config/",
        blank=True,
        null=True,
        help_text="Brasão ou arte institucional do cabeçalho.",
    )
    brasao_largura_cm = models.DecimalField(max_digits=4, decimal_places=2, default=2.80)
    pagina_formato = models.CharField(
        max_length=10,
        choices=PAGINA_FORMATO_CHOICES,
        default="A4",
    )
    pagina_orientacao = models.CharField(
        max_length=10,
        choices=PAGINA_ORIENTACAO_CHOICES,
        default="portrait",
    )
    margem_superior_cm = models.DecimalField(max_digits=4, decimal_places=2, default=2.50)
    margem_inferior_cm = models.DecimalField(max_digits=4, decimal_places=2, default=2.50)
    margem_esquerda_cm = models.DecimalField(max_digits=4, decimal_places=2, default=3.00)
    margem_direita_cm = models.DecimalField(max_digits=4, decimal_places=2, default=2.00)
    rodape_protocolo_altura_cm = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=2.50,
        help_text="Área reservada no rodapé para protocolo digital.",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de ofício"
        verbose_name_plural = "Configuração de ofício"

    def save(self, *args, **kwargs):
        self.pk_fixo = 1
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        rotulo = self.titulo_instituicao or self.municipio or "Câmara Municipal"
        return f"Ofício — {rotulo}"

    @classmethod
    def carregar(cls) -> "ConfiguracaoOficio":
        obj, _ = cls.objects.get_or_create(pk_fixo=1)
        return obj

    @property
    def instituicao_nome(self) -> str:
        titulo = (self.titulo_instituicao or "").strip()
        if titulo:
            return titulo
        municipio = (self.municipio or "").strip()
        if municipio:
            return f"Câmara Municipal de {municipio}"
        return "Câmara Municipal"

    def contexto_layout_pdf(self) -> dict:
        """Variáveis de página e cabeçalho para templates WeasyPrint."""
        imagem_url: str | None = None
        if self.imagem_cabecalho:
            try:
                path = Path(self.imagem_cabecalho.path)
                if not path.is_file() and self.imagem_cabecalho.name:
                    path = Path(self.imagem_cabecalho.name)
                if path.is_file():
                    imagem_url = path.resolve().as_uri()
            except (ValueError, OSError):
                imagem_url = None

        formato = (self.pagina_formato or "A4").upper()
        orientacao = self.pagina_orientacao or "portrait"
        pagina_size = f"{formato} {orientacao}" if orientacao == "landscape" else formato

        titulo_raw = (self.titulo_instituicao or "").strip()
        municipio_raw = (self.municipio or "").strip()
        uf_raw = (self.uf or "").strip()
        layout = self.cabecalho_layout or "BRASAO_ESQUERDA_TEXTO"
        exibir_texto = bool(titulo_raw or municipio_raw or uf_raw)
        if layout in {"BRASAO_CENTRO"}:
            exibir_texto = False
        elif layout == "TEXTO_CENTRO":
            exibir_texto = bool(titulo_raw or municipio_raw or uf_raw)

        margem_superior = _fmt_css_num(self.margem_superior_cm)
        margem_inferior = _fmt_css_num(self.margem_inferior_cm)
        margem_esquerda = _fmt_css_num(self.margem_esquerda_cm)
        margem_direita = _fmt_css_num(self.margem_direita_cm)
        brasao_largura = _fmt_css_num(self.brasao_largura_cm)
        rodape_protocolo_altura = _fmt_css_num(self.rodape_protocolo_altura_cm)

        return {
            "cabecalho_imagem_url": imagem_url,
            "titulo_instituicao": titulo_raw,
            "instituicao_nome": self.instituicao_nome,
            "exibir_texto_cabecalho": exibir_texto,
            "cabecalho_layout": layout,
            "pagina_size": pagina_size,
            "margem_superior": margem_superior,
            "margem_inferior": margem_inferior,
            "margem_esquerda": margem_esquerda,
            "margem_direita": margem_direita,
            "brasao_largura": brasao_largura,
            "rodape_protocolo_altura": rodape_protocolo_altura,
            "oficio_css_dinamico": _css_dinamico_oficio(
                pagina_size=pagina_size,
                margem_superior=margem_superior,
                margem_direita=margem_direita,
                margem_inferior=margem_inferior,
                margem_esquerda=margem_esquerda,
                brasao_largura=brasao_largura,
                rodape_protocolo_altura=rodape_protocolo_altura,
            ),
        }


class ConfiguracaoCarta(models.Model):
    """Política de SLA operacional (prazo padrão e fallback) — singleton pk=1."""

    POLITICA_SERVICO = "SERVICO"
    POLITICA_PADRAO = "PADRAO"
    POLITICA_SERVICO_COM_FALLBACK = "SERVICO_COM_FALLBACK"
    POLITICA_CHOICES = (
        (POLITICA_SERVICO, "Somente prazo do serviço"),
        (POLITICA_PADRAO, "Sempre prazo padrão"),
        (POLITICA_SERVICO_COM_FALLBACK, "Serviço com fallback para padrão"),
    )

    pk_fixo = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    prazo_padrao_dias = models.PositiveIntegerField(
        default=30,
        help_text="Prazo operacional padrão (dias) quando política usar fallback ou PADRAO.",
    )
    politica_prazo = models.CharField(
        max_length=24,
        choices=POLITICA_CHOICES,
        default=POLITICA_SERVICO_COM_FALLBACK,
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração da carta (SLA)"
        verbose_name_plural = "Configuração da carta (SLA)"

    def save(self, *args, **kwargs):
        self.pk_fixo = 1
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Carta SLA — {self.get_politica_prazo_display()} ({self.prazo_padrao_dias}d)"

    @classmethod
    def carregar(cls) -> "ConfiguracaoCarta":
        obj, _ = cls.objects.get_or_create(pk_fixo=1)
        return obj


class NumeracaoIndicacaoCamara(models.Model):
    """Contador de indicações da Câmara — singleton pk=1; último número informado pela Câmara."""

    pk_fixo = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    ano = models.PositiveSmallIntegerField(
        default=2026,
        help_text="Ano corrente da sequência de indicações.",
    )
    ultimo_numero = models.PositiveIntegerField(
        default=0,
        help_text="Último número de indicação já utilizado no ano (informado pela Câmara).",
    )
    mascara = models.CharField(
        max_length=64,
        default="{numero}/{ano}",
        help_text="Formato exibido; use {numero} e {ano}.",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Numeração de indicações (Câmara)"
        verbose_name_plural = "Numeração de indicações (Câmara)"

    def save(self, *args, **kwargs):
        self.pk_fixo = 1
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Indicações {self.ano} — último nº {self.ultimo_numero}"

    @classmethod
    def carregar(cls) -> "NumeracaoIndicacaoCamara":
        obj, _ = cls.objects.get_or_create(pk_fixo=1)
        return obj
