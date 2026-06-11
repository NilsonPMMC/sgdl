"""Models read-only do barramento Sinapse (multi-database).

Estes models refletem o schema *real* do banco Sinapse e foram gerados a
partir de `manage.py inspectdb --database=sinapse` (apenas tabelas
`catalog_*`). Todos com `managed = False`: o Django nao gera migracoes
nem cria/altera essas tabelas. O acesso e feito sempre via
`.using('sinapse')` e o router `SinapseRouter` impede escrita.

Importante: campo `embedding` em `CatalogServico`/`CatalogUnidadeAdministrativa`
e `vector(1024)` (pgvector). Use `pgvector.django.CosineDistance` para
similaridade — busca acontece *no Postgres do Sinapse*, sem fetch+numpy.
"""

from __future__ import annotations

from django.db import models
from pgvector.django import VectorField


SINAPSE_DB_ALIAS = "sinapse"


class CatalogCategoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    slug = models.CharField(max_length=150)
    nome = models.CharField(max_length=255)
    css = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "catalog_categoria"
        app_label = "integrations"

    def __str__(self) -> str:
        return self.nome


class CatalogOrgao(models.Model):
    """Órgão municipal no catálogo Sinapse (secretaria de destino no SGDL)."""
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    nome = models.CharField(max_length=255)
    tipo_orgao = models.CharField(max_length=100)
    grupo = models.CharField(max_length=100)
    slug = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = "catalog_orgao"
        app_label = "integrations"
        verbose_name = "órgão (Sinapse)"
        verbose_name_plural = "órgãos (Sinapse)"

    def __str__(self) -> str:
        return self.nome


class CatalogPublico(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    descricao = models.CharField(max_length=255)
    is_default = models.BooleanField()

    class Meta:
        managed = False
        db_table = "catalog_publico"
        app_label = "integrations"

    def __str__(self) -> str:
        return self.descricao


class CatalogTipoatendimento(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    descricao = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "catalog_tipoatendimento"
        app_label = "integrations"

    def __str__(self) -> str:
        return self.descricao


class CatalogServico(models.Model):
    """Serviço da carta municipal no catálogo Sinapse."""
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    slug = models.TextField(blank=True, null=True)
    titulo = models.TextField()
    descricao_html = models.TextField()
    departamento = models.TextField(blank=True, null=True)
    telefone = models.JSONField(blank=True, null=True)
    email = models.JSONField(blank=True, null=True)
    agendamento = models.TextField()
    solicitacao_internet = models.CharField(max_length=200)
    solicitacao_perfil = models.TextField()
    atendimento_dia_hora = models.TextField()
    documentos_necessarios = models.TextField()
    prazo = models.TextField(blank=True, null=True)
    requisitos_html = models.TextField()
    fluxo_html = models.TextField()
    observacoes_html = models.TextField()
    status = models.IntegerField()
    texto_limpo_rag = models.TextField()
    # Coluna real `vector(1024)` no Postgres do Sinapse (pgvector 0.8.1).
    embedding = VectorField(dimensions=1024, blank=True, null=True)
    id_categoria = models.ForeignKey(
        CatalogCategoria, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    id_orgao = models.ForeignKey(
        CatalogOrgao, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    id_tipo_publico = models.ForeignKey(
        CatalogPublico, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    id_tipo_atendimento = models.ForeignKey(
        CatalogTipoatendimento, on_delete=models.DO_NOTHING, blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = "catalog_servico"
        app_label = "integrations"
        verbose_name = "serviço — carta (Sinapse)"
        verbose_name_plural = "serviços — carta (Sinapse)"

    def __str__(self) -> str:
        return self.titulo[:80]


class CatalogUnidadeAdministrativa(models.Model):
    """Unidade administrativa (ponto físico / endereço) no catálogo Sinapse."""
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    slug = models.CharField(max_length=150)
    titulo = models.CharField(max_length=255)
    endereco = models.CharField(max_length=255)
    num = models.CharField(max_length=50)
    complemento = models.CharField(max_length=255)
    bairro = models.CharField(max_length=255)
    latitude = models.CharField(max_length=50)
    longitude = models.CharField(max_length=50)
    arquivo_imagem = models.CharField(max_length=255)
    categoria = models.ForeignKey(
        CatalogCategoria, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    slug_orgao = models.ForeignKey(
        CatalogOrgao,
        on_delete=models.DO_NOTHING,
        db_column="slug_orgao",
        to_field="slug",
        blank=True,
        null=True,
    )
    embedding = VectorField(dimensions=1024, blank=True, null=True)
    texto_limpo_rag = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "catalog_unidadeadministrativa"
        app_label = "integrations"
        verbose_name = "unidade administrativa (Sinapse)"
        verbose_name_plural = "unidades administrativas (Sinapse)"

    def __str__(self) -> str:
        return self.titulo
