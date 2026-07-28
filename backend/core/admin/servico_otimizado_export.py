"""Exportação CSV de ServicoOtimizado para o Django Admin."""

from __future__ import annotations

import csv
import json
from typing import Any, Iterable

from django.http import HttpResponse
from django.utils import timezone

from core.models_carta_otimizada import ServicoOtimizado

CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "id"),
    ("titulo_otimizado", "titulo_otimizado"),
    ("descricao_objetiva", "descricao_objetiva"),
    ("intencao_servico", "intencao_servico"),
    ("problemas_resolve", "problemas_resolve"),
    ("texto_rag_otimizado", "texto_rag_otimizado"),
    ("tipo_processo", "tipo_processo"),
    ("prazo_dias", "prazo_dias"),
    ("prazo_categoria", "prazo_categoria"),
    ("dependencias_documentos", "dependencias_documentos"),
    ("dependencias_realizacao", "dependencias_realizacao"),
    ("dependencias_pagamentos", "dependencias_pagamentos"),
    ("tipos_atendimento", "tipos_atendimento"),
    ("sistema_solicitacao", "sistema_solicitacao"),
    ("link_sistema", "link_sistema"),
    ("palavras_chave", "palavras_chave"),
    ("unidade_administrativa_id", "unidade_administrativa_id"),
    ("unidade_administrativa_nome", "unidade_administrativa_nome"),
    ("assunto_id", "assunto_id"),
    ("assunto_nome", "assunto_nome"),
    ("otimizado_em", "otimizado_em"),
    ("atualizado_em", "atualizado_em"),
)


def _json_cell(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _datetime_cell(value) -> str:
    if value is None:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _row_dict(obj: ServicoOtimizado) -> dict[str, Any]:
    unidade = obj.unidade_administrativa
    assunto = obj.assunto
    return {
        "id": obj.pk,
        "titulo_otimizado": obj.titulo_otimizado or "",
        "descricao_objetiva": obj.descricao_objetiva or "",
        "intencao_servico": obj.intencao_servico or "",
        "problemas_resolve": _json_cell(obj.problemas_resolve),
        "texto_rag_otimizado": obj.texto_rag_otimizado or "",
        "tipo_processo": obj.tipo_processo or "",
        "prazo_dias": obj.prazo_dias if obj.prazo_dias is not None else "",
        "prazo_categoria": obj.prazo_categoria or "",
        "dependencias_documentos": _json_cell(obj.dependencias_documentos),
        "dependencias_realizacao": _json_cell(obj.dependencias_realizacao),
        "dependencias_pagamentos": _json_cell(obj.dependencias_pagamentos),
        "tipos_atendimento": _json_cell(obj.tipos_atendimento),
        "sistema_solicitacao": obj.sistema_solicitacao or "",
        "link_sistema": obj.link_sistema or "",
        "palavras_chave": _json_cell(obj.palavras_chave),
        "unidade_administrativa_id": unidade.pk if unidade else "",
        "unidade_administrativa_nome": (unidade.nome if unidade else "") or "",
        "assunto_id": assunto.pk if assunto else "",
        "assunto_nome": (assunto.nome if assunto else "") or "",
        "otimizado_em": _datetime_cell(obj.otimizado_em),
        "atualizado_em": _datetime_cell(obj.atualizado_em),
    }


def queryset_exportavel(queryset):
    return queryset.select_related("unidade_administrativa", "assunto").order_by(
        "sinapse_servico_id"
    )


def servico_otimizado_csv_response(
    queryset,
    *,
    filename: str = "servicos_otimizados.csv",
) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([label for label, _ in CSV_COLUMNS])

    for obj in queryset_exportavel(queryset):
        row = _row_dict(obj)
        writer.writerow([row[key] for _, key in CSV_COLUMNS])

    return response


def iter_csv_rows(queryset) -> Iterable[list[Any]]:
    yield [label for label, _ in CSV_COLUMNS]
    for obj in queryset_exportavel(queryset):
        row = _row_dict(obj)
        yield [row[key] for _, key in CSV_COLUMNS]
