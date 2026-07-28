"""Corpus de aprendizado a partir do CSV legado (não importa Demandas operacionais)."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

_EIXOS_TEMATICOS: tuple[tuple[str, str], ...] = (
    (
        "vias_buracos_nivelamento",
        r"manuten[cç][aã]o de estrada|manuten[cç][aã]o estrada|nivelamento|cascalh|conserva[cç][aã]o de via",
    ),
    ("vias_buracos", r"burac|tapa|recap|paviment|asfalt"),
    ("limpeza_rocada", r"limpeza|roçag|rocag|entulho|lixo|bueiro|boca de lobo|drenagem"),
    ("iluminacao", r"ilumina|luminária|luminaria|poste"),
    ("poda_arvore", r"poda|árvore|arvore"),
    ("educacao", r"escola|creche|transferência|transferencia|aluno|professor"),
    ("seguranca", r"gcm|ronda|policiamento|segurança|seguranca"),
    ("saude", r"ubs|upa|hospital|saúde|saude"),
    ("eventos", r"evento|empréstimo|emprestimo|campo"),
    ("sinalizacao", r"sinaliza|faixa|lombada|semáforo|semaforo"),
    ("terreno_zeladoria", r"terreno|muro|limpeza do terreno"),
)

_ROTULO_EIXO = {
    "vias_buracos_nivelamento": "Manutenção de estrada",
    "vias_buracos": "Vias e buracos",
    "limpeza_rocada": "Limpeza e roçada",
    "iluminacao": "Iluminação pública",
    "poda_arvore": "Poda de árvore",
    "educacao": "Educação",
    "seguranca": "Segurança e rondas",
    "saude": "Saúde",
    "eventos": "Eventos e empréstimo de espaço",
    "sinalizacao": "Sinalização e lombadas",
    "terreno_zeladoria": "Terrenos e zeladoria",
}

# Pedidos frequentes do Copiloto — agrupados por eixo (sem «Outros»), com busca na carta otimizada.
_PEDIDOS_FREQUENTES_META: tuple[dict[str, Any], ...] = (
    {
        "eixo_id": "limpeza_rocada",
        "rotulo": "Limpeza e roçada de via",
        "consulta_carta": "Varrição",
        "filtro_titulo": re.compile(r"varri|limpez|roçag|rocag|entulho|coleta de lixo", re.I),
        "excluir_titulo": re.compile(r"fossa|valeta|córrego|corrego|bueiro", re.I),
        "servico_padrao_id": 176,
        "texto_sugerido": "Solicito limpeza e roçagem de via.",
    },
    {
        "eixo_id": "vias_buracos",
        "rotulo": "Tapa buraco na via",
        "consulta_carta": "tapa buraco",
        "filtro_titulo": re.compile(r"tapa|burac|recap|paviment", re.I),
        "servico_padrao_id": 80,
        "texto_sugerido": "Solicito tapa buraco na via.",
    },
    {
        "eixo_id": "iluminacao",
        "rotulo": "Iluminação pública",
        "consulta_carta": "Iluminação Pública",
        "filtro_titulo": re.compile(r"^Iluminação Pública:", re.I),
        "excluir_titulo": re.compile(r"CIP|Consumo de Energia|Contribuição", re.I),
        "servico_padrao_id": 14,
        "texto_sugerido": "Solicito iluminação pública.",
    },
    {
        "eixo_id": "poda_arvore",
        "rotulo": "Poda de árvore",
        "consulta_carta": "poda árvores área pública",
        "filtro_titulo": re.compile(r"poda|árvore|arvore|galho|corte", re.I),
        "excluir_titulo": re.compile(r"autorização para corte acima|supressão|transplante", re.I),
        "servico_padrao_id": 982,
        "texto_sugerido": "Solicito poda de árvore.",
    },
    {
        "eixo_id": "sinalizacao",
        "rotulo": "Sinalização e lombadas",
        "consulta_carta": "Trânsito Sinalização",
        "filtro_titulo": re.compile(r"sinaliz|lombad|redutor|trânsito|transito", re.I),
        "servico_padrao_id": 133,
        "texto_sugerido": "Solicito sinalização ou lombada na via.",
    },
    {
        "eixo_id": "terreno_zeladoria",
        "rotulo": "Limpeza de terreno",
        "consulta_carta": "limpeza terreno particular zeladoria",
        "filtro_titulo": re.compile(r"terreno|zelador|limpez", re.I),
        "texto_sugerido": "Solicito limpeza de terreno.",
    },
    {
        "eixo_id": "seguranca",
        "rotulo": "Ronda da GCM",
        "consulta_carta": "Ronda",
        "filtro_titulo": re.compile(r"ronda|gcm|guarda|patrimônio|patrimonio", re.I),
        "servico_padrao_id": 143,
        "texto_sugerido": "Solicito ronda da GCM no bairro.",
    },
    {
        "eixo_id": "vias_buracos_nivelamento",
        "rotulo": "Manutenção de estrada",
        "consulta_carta": "Nivelamento",
        "filtro_titulo": re.compile(r"nivelamento|cascalh|estrada|conservação de via", re.I),
        "servico_padrao_id": 86,
        "texto_sugerido": "Solicito manutenção de estrada.",
    },
)


def _repo_root() -> Path:
    return Path(getattr(settings, "BASE_DIR", Path.cwd())).parent


def corpus_legado_csv_path() -> Path:
    rel = getattr(
        settings,
        "CORPUS_LEGADO_CSV_PATH",
        "docs/bd-legado-demandas-vereadores.csv",
    )
    p = Path(rel)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def corpus_legado_json_path() -> Path:
    rel = getattr(
        settings,
        "CORPUS_LEGADO_JSON_PATH",
        "docs/insights/corpus-legado.json",
    )
    p = Path(rel)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def corpus_legado_depara_path() -> Path:
    rel = getattr(
        settings,
        "CORPUS_LEGADO_DEPARA_PATH",
        "docs/insights/depara-legado-sinapse.json",
    )
    p = Path(rel)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _slug_ascii(texto: str) -> str:
    bruto = (texto or "").strip().lower()
    nfkd = unicodedata.normalize("NFKD", bruto)
    ascii_txt = nfkd.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_txt).strip("-")
    return slug[:120] or "trend"


def _parse_detalhamento(detalhamento: str) -> tuple[str, str | None]:
    det = (detalhamento or "").strip()
    if " - " in det:
        serv, setor = det.rsplit(" - ", 1)
        return serv.strip(), setor.strip()
    return det, None


def _extrair_bairro(assunto: str) -> str | None:
    m = re.search(r'Bairro\s*[–\-]\s*([^\.,"]+)', assunto or "", re.I)
    if m:
        return m.group(1).strip()[:120]
    return None


def _checksum_arquivo(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def carregar_linhas_csv(path: Path | None = None) -> list[dict[str, str]]:
    csv_path = path or corpus_legado_csv_path()
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV legado não encontrado: {csv_path}")
    with csv_path.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        required = {"Assunto", "Tipo de pedido", "Detalhamento"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV legado deve conter colunas: Assunto, Tipo de pedido, Detalhamento")
        return [
            {
                "assunto": (row.get("Assunto") or "").strip(),
                "tipo_pedido": (row.get("Tipo de pedido") or "").strip(),
                "detalhamento": (row.get("Detalhamento") or "").strip(),
            }
            for row in reader
            if (row.get("Assunto") or "").strip()
        ]


def analisar_corpus(linhas: list[dict[str, str]], *, checksum: str = "") -> dict[str, Any]:
    """Agrega estatísticas e top trends a partir das linhas normalizadas."""
    from collections import Counter, defaultdict

    n = len(linhas)
    tipos = Counter()
    servicos = Counter()
    setores = Counter()
    servico_setor = Counter()
    bairros = Counter()
    eixos = Counter()
    exemplos_por_trend: dict[tuple[str, str | None], list[str]] = defaultdict(list)

    for row in linhas:
        tipos[row["tipo_pedido"]] += 1
        serv, setor = _parse_detalhamento(row["detalhamento"])
        servicos[serv] += 1
        if setor:
            setores[setor] += 1
        servico_setor[(serv, setor)] += 1

        b = _extrair_bairro(row["assunto"])
        if b:
            bairros[b] += 1

        blob = f"{row['assunto']} {row['detalhamento']}".lower()
        for eixo_id, pat in _EIXOS_TEMATICOS:
            if re.search(pat, blob):
                eixos[eixo_id] += 1

        chave = (serv, setor)
        if len(exemplos_por_trend[chave]) < 3:
            exemplos_por_trend[chave].append(row["assunto"][:200])

    top_trends: list[dict[str, Any]] = []
    for (serv, setor), volume in servico_setor.most_common(50):
        titulo = serv if not setor else f"{serv} ({setor})"
        top_trends.append(
            {
                "id": _slug_ascii(f"{serv}-{setor or 'geral'}"),
                "titulo": titulo,
                "servico_legado": serv,
                "setor_legado": setor,
                "volume": volume,
                "percentual": round(100 * volume / max(n, 1), 2),
                "exemplos_assunto": exemplos_por_trend[(serv, setor)],
                "atalho_sugerido": _atalho_curto(serv),
            }
        )

    return {
        "versao": 1,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "checksum_csv": checksum,
        "total_registros": n,
        "periodo_referencia_meses": 17,
        "nota": (
            "Corpus de aprendizado — não substitui Demandas operacionais nem altera o fluxo do Copiloto."
        ),
        "tipos_pedido": [
            {"tipo": k, "volume": v, "percentual": round(100 * v / max(n, 1), 2)}
            for k, v in tipos.most_common()
        ],
        "top_trends": top_trends,
        "top_setores": [
            {
                "setor": k,
                "volume": v,
                "percentual": round(100 * v / max(n, 1), 2),
            }
            for k, v in setores.most_common(20)
        ],
        "top_servicos": [
            {"servico": k, "volume": v, "percentual": round(100 * v / max(n, 1), 2)}
            for k, v in servicos.most_common(25)
        ],
        "eixos_tematicos": [
            {
                "eixo": eixo_id,
                "rotulo": _ROTULO_EIXO.get(eixo_id, eixo_id),
                "volume": v,
                "percentual": round(100 * v / max(n, 1), 2),
            }
            for eixo_id, v in eixos.most_common()
        ],
        "top_bairros": [
            {"bairro": k, "volume": v} for k, v in bairros.most_common(30)
        ],
    }


def _atalho_curto(servico: str) -> str:
    """Rótulo curto para atalho no Copiloto (linguagem do cidadão)."""
    mapa = {
        "Limpeza Pública": "Limpeza e roçada de via",
        "Recapeamento/Tapa Buraco": "Tapa buraco na via",
        "Manutenção Estradas Rurais/Urbanas": "Manutenção de estrada",
        "Manutenção Iluminação Pública": "Iluminação pública",
        "Poda de Árvore": "Poda de árvore",
        "Implantação de Lombada": "Lombada na via",
        "Implantação de Sinalização viária": "Sinalização de trânsito",
        "Rondas Ostensivas/Intensificação": "Ronda da GCM",
        "Coleta de Lixo/Entulho": "Coleta de entulho",
    }
    return mapa.get(servico, servico)


def gerar_relatorio_corpus(
    *,
    csv_path: Path | None = None,
    json_path: Path | None = None,
) -> dict[str, Any]:
    csv_p = csv_path or corpus_legado_csv_path()
    json_p = json_path or corpus_legado_json_path()
    checksum = _checksum_arquivo(csv_p)
    linhas = carregar_linhas_csv(csv_p)
    relatorio = analisar_corpus(linhas, checksum=checksum)
    json_p.parent.mkdir(parents=True, exist_ok=True)
    json_p.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Corpus legado gerado: %s registros → %s",
        relatorio["total_registros"],
        json_p,
    )
    return relatorio


class CorpusLegadoService:
    """Leitura do JSON gerado — camada opcional, sem efeito colateral no fluxo principal."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] | None = None
        self._depara_cache: dict[str, Any] | None = None
        self._depara_index: dict[str, dict[str, Any]] | None = None

    def relatorio(self, *, force_reload: bool = False) -> dict[str, Any] | None:
        from core.services.copiloto_config import corpus_legado_habilitado

        if not corpus_legado_habilitado():
            return None
        if self._cache is not None and not force_reload:
            return self._cache
        path = corpus_legado_json_path()
        if not path.is_file():
            return None
        try:
            self._cache = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Falha ao ler corpus legado: %s", path)
            return None
        return self._cache

    def top_trends(self, *, limite: int = 20) -> list[dict[str, Any]]:
        rel = self.relatorio()
        if not rel:
            return []
        return list(rel.get("top_trends") or [])[:limite]

    def top_setores(self, *, limite: int = 15) -> list[dict[str, Any]]:
        rel = self.relatorio()
        if not rel:
            return []
        return list(rel.get("top_setores") or [])[:limite]

    def sugerir_por_texto(self, texto: str, *, limite: int = 3) -> list[dict[str, Any]]:
        """
        Sugestão assistiva por sobreposição lexical — não altera triagem Sinapse.
        Retorna trends do histórico com score simples.
        """
        rel = self.relatorio()
        if not rel or not (texto or "").strip():
            return []

        tokens = set(re.findall(r"[a-záàâãéêíóôõúç]{4,}", (texto or "").lower()))
        if len(tokens) < 2:
            return []

        candidatos: list[tuple[float, dict[str, Any]]] = []
        for trend in rel.get("top_trends") or []:
            blob = " ".join(
                [
                    trend.get("titulo") or "",
                    trend.get("servico_legado") or "",
                    trend.get("atalho_sugerido") or "",
                    " ".join(trend.get("exemplos_assunto") or []),
                ]
            ).lower()
            tb = set(re.findall(r"[a-záàâãéêíóôõúç]{4,}", blob))
            if not tb:
                continue
            inter = tokens & tb
            if len(inter) < 2:
                continue
            score = len(inter) / max(len(tokens), len(tb), 1)
            candidatos.append((score, {**trend, "score_sugestao": round(score, 3)}))

        candidatos.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in candidatos[:limite]]

    def depara_legado_sinapse(self, *, force_reload: bool = False) -> dict[str, Any] | None:
        from core.services.copiloto_config import corpus_legado_habilitado

        if not corpus_legado_habilitado():
            return None
        if self._depara_cache is not None and not force_reload:
            return self._depara_cache
        path = corpus_legado_depara_path()
        if not path.is_file():
            return None
        try:
            self._depara_cache = json.loads(path.read_text(encoding="utf-8"))
            self._depara_index = None
        except (OSError, json.JSONDecodeError):
            logger.exception("Falha ao ler de-para legado→Sinapse: %s", path)
            return None
        return self._depara_cache

    def _index_depara(self) -> dict[str, dict[str, Any]]:
        if self._depara_index is not None:
            return self._depara_index
        rel = self.depara_legado_sinapse() or {}
        idx: dict[str, dict[str, Any]] = {}
        for row in rel.get("mapeamentos") or []:
            if not isinstance(row, dict):
                continue
            chave = (row.get("servico_legado") or "").strip()
            if chave:
                idx[chave] = row
        self._depara_index = idx
        return idx

    def resolver_depara_legado(self, servico_legado: str) -> dict[str, Any] | None:
        """Resolve mapeamento curado legado → Sinapse (assistivo)."""
        chave = (servico_legado or "").strip()
        if not chave:
            return None
        row = self._index_depara().get(chave)
        if not row:
            return None
        out = dict(row)
        sid = out.get("sinapse_servico_id")
        if sid is None and out.get("consulta_sinapse"):
            try:
                from integrations import sinapse_catalog

                resolvido = sinapse_catalog.resolver_servico_por_titulo(
                    str(out["consulta_sinapse"])
                )
                if resolvido:
                    out["sinapse_servico_id"] = int(resolvido)
                    catalog = sinapse_catalog.get_servico(int(resolvido))
                    if catalog:
                        out["titulo_sinapse"] = (catalog.titulo or "").strip()
            except Exception:
                logger.debug("De-para: falha ao resolver Sinapse para %s", chave, exc_info=True)
        elif sid is not None and not out.get("titulo_sinapse"):
            try:
                from integrations import sinapse_catalog

                catalog = sinapse_catalog.get_servico(int(sid))
                if catalog:
                    out["titulo_sinapse"] = (catalog.titulo or "").strip()
            except Exception:
                pass
        return out

    def enriquecer_sugestao_depara(self, sugestao: dict[str, Any]) -> dict[str, Any]:
        """Anexa de-para Sinapse à sugestão do histórico (sem alterar triagem)."""
        serv = (sugestao.get("servico_legado") or "").strip()
        if not serv:
            return sugestao
        depara = self.resolver_depara_legado(serv)
        if not depara:
            return sugestao
        out = {**sugestao}
        if depara.get("sinapse_servico_id") is not None:
            out["sinapse_servico_id_sugerido_historico"] = int(depara["sinapse_servico_id"])
        if depara.get("titulo_sinapse"):
            out["titulo_sinapse_historico"] = depara["titulo_sinapse"]
        if depara.get("confianca"):
            out["confianca_depara"] = depara["confianca"]
        if depara.get("atalho") and not out.get("atalho_sugerido"):
            out["atalho_sugerido"] = depara["atalho"]
        return out

    def hints_pos_triagem(
        self,
        texto: str,
        *,
        limite: int = 3,
        servico_legado_prioritario: str | None = None,
    ) -> list[dict[str, Any]]:
        """Sugestões da carta por tema — substitui overlap lexical irrelevante."""
        opcoes = self.hints_carta_por_texto(texto, limite=limite)
        if opcoes:
            return opcoes
        sugestoes = self.sugerir_por_texto(texto, limite=limite)
        if servico_legado_prioritario:
            dep = self.resolver_depara_legado(servico_legado_prioritario)
            if dep:
                injetada = {
                    "id": _slug_ascii(servico_legado_prioritario),
                    "servico_legado": servico_legado_prioritario,
                    "atalho_sugerido": dep.get("atalho") or servico_legado_prioritario,
                    "score_sugestao": 1.0,
                    "fonte": "depara_curado",
                }
                sugestoes = [self.enriquecer_sugestao_depara(injetada)] + sugestoes
        vistos: set[str] = set()
        out: list[dict[str, Any]] = []
        for s in sugestoes:
            chave = (s.get("servico_legado") or s.get("id") or "").strip()
            if chave in vistos:
                continue
            vistos.add(chave)
            out.append(self.enriquecer_sugestao_depara(s))
            if len(out) >= limite:
                break
        return out

    def meta_pedido_frequente(self, eixo_id: str) -> dict[str, Any] | None:
        for meta in _PEDIDOS_FREQUENTES_META:
            if meta.get("eixo_id") == eixo_id:
                return meta
        return None

    def _volumes_eixos(self) -> dict[str, int]:
        rel = self.relatorio() or {}
        return {
            (row.get("eixo") or ""): int(row.get("volume") or 0)
            for row in (rel.get("eixos_tematicos") or [])
            if isinstance(row, dict)
        }

    def _ordenar_metas_por_volume(self) -> list[dict[str, Any]]:
        vols = self._volumes_eixos()
        metas = list(_PEDIDOS_FREQUENTES_META)
        metas.sort(key=lambda m: vols.get(m["eixo_id"], 0), reverse=True)
        return metas

    def opcoes_carta_para_eixo(
        self, meta: dict[str, Any], *, limite: int = 8
    ) -> list[dict[str, Any]]:
        """Busca serviços na carta Sinapse filtrados por eixo (mesma lógica do Explorer)."""
        consulta = (meta.get("consulta_carta") or meta.get("rotulo") or "").strip()
        if not consulta:
            return []
        try:
            from integrations import sinapse_catalog

            if not sinapse_catalog.catalog_disponivel():
                return []
            hits = sinapse_catalog.buscar_servicos_catalogo(
                q=consulta,
                limit=max(limite * 3, 12),
            )
        except Exception:
            logger.debug("Falha ao buscar carta para eixo %s", meta.get("eixo_id"), exc_info=True)
            return []

        filtro = meta.get("filtro_titulo")
        excluir = meta.get("excluir_titulo")
        padrao_id = meta.get("servico_padrao_id")
        opcoes: list[dict[str, Any]] = []
        for row in hits.get("results") or []:
            sid = row.get("id")
            titulo = (row.get("nome") or row.get("titulo") or "").strip()
            if not sid or not titulo:
                continue
            if filtro and not filtro.search(titulo):
                continue
            if excluir and excluir.search(titulo):
                continue
            orgao = (row.get("secretaria_responsavel") or {}).get("nome") or row.get("orgao")
            opcoes.append(
                {
                    "servico_id": int(sid),
                    "titulo": titulo,
                    "orgao": orgao,
                    "padrao": int(sid) == int(padrao_id) if padrao_id else False,
                    "score": 0.95 if padrao_id and int(sid) == int(padrao_id) else 0.88,
                }
            )

        opcoes.sort(key=lambda o: (not o.get("padrao"), -float(o.get("score") or 0)))
        if opcoes:
            return opcoes[:limite]

        padrao_id = meta.get("servico_padrao_id")
        if padrao_id:
            try:
                from integrations import sinapse_catalog

                catalog = sinapse_catalog.get_servico(int(padrao_id))
                if catalog:
                    titulo = (catalog.titulo or "").strip()
                    if not filtro or filtro.search(titulo):
                        if not excluir or not excluir.search(titulo):
                            return [
                                {
                                    "servico_id": int(padrao_id),
                                    "titulo": titulo,
                                    "orgao": sinapse_catalog.get_orgao_nome(catalog.id_orgao_id),
                                    "padrao": True,
                                    "score": 0.95,
                                }
                            ]
            except Exception:
                pass

        try:
            from core.services.triagem_otimizada_service import TriagemOtimizadaService
            from core.services.vector_service import VectorService

            emb = VectorService().generate_embedding(consulta)
            if emb:
                cands = TriagemOtimizadaService().buscar_servico_sinapse(
                    emb, top_k=max(limite * 2, 8), texto_consulta=consulta
                )
                for c in cands:
                    sid = c.get("servico_id")
                    titulo = (c.get("titulo") or "").strip()
                    if not sid or not titulo:
                        continue
                    if filtro and not filtro.search(titulo):
                        continue
                    if excluir and excluir.search(titulo):
                        continue
                    opcoes.append(
                        {
                            "servico_id": int(sid),
                            "titulo": titulo,
                            "orgao": c.get("orgao"),
                            "padrao": padrao_id and int(sid) == int(padrao_id),
                            "score": max(float(c.get("score") or 0), 0.88),
                        }
                    )
                opcoes.sort(key=lambda o: (not o.get("padrao"), -float(o.get("score") or 0)))
        except Exception:
            logger.debug("Fallback triagem falhou para eixo %s", meta.get("eixo_id"), exc_info=True)

        return opcoes[:limite]

    def detectar_eixo_por_texto(self, texto: str) -> dict[str, Any] | None:
        blob = (texto or "").lower()
        if len(blob) < 6:
            return None
        # Padrões explícitos antes do match genérico (evita «manutenção de estrada» → tapa buraco).
        prioridade: tuple[tuple[str, str], ...] = (
            (
                "vias_buracos_nivelamento",
                r"manuten[cç][aã]o de estrada|manuten[cç][aã]o estrada|nivelamento|cascalh",
            ),
            ("iluminacao", r"ilumina"),
            ("sinalizacao", r"sinaliza|lombad|semáforo|semaforo"),
            ("vias_buracos", r"tapa|burac"),
            ("limpeza_rocada", r"limpeza|roçag|rocag|varri"),
            ("poda_arvore", r"poda|árvore|arvore|galho"),
            ("seguranca", r"gcm|ronda"),
        )
        for eixo_id, pat in prioridade:
            if re.search(pat, blob):
                meta = self.meta_pedido_frequente(eixo_id)
                if meta:
                    return meta
        melhor: tuple[int, dict[str, Any]] | None = None
        for meta in _PEDIDOS_FREQUENTES_META:
            eixo_id = meta.get("eixo_id") or ""
            pat = next((p for eid, p in _EIXOS_TEMATICOS if eid == eixo_id), None)
            if not pat:
                continue
            if re.search(pat, blob):
                peso = len(re.findall(pat, blob))
                if melhor is None or peso > melhor[0]:
                    melhor = (peso, meta)
        return melhor[1] if melhor else None

    def hints_carta_por_texto(self, texto: str, *, limite: int = 5) -> list[dict[str, Any]]:
        """Hints pós-triagem: opções reais da carta para o tema do pedido."""
        meta = self.detectar_eixo_por_texto(texto)
        if not meta:
            return []
        opcoes = self.opcoes_carta_para_eixo(meta, limite=limite)
        out: list[dict[str, Any]] = []
        for i, op in enumerate(opcoes, 1):
            out.append(
                {
                    "id": f"{meta['eixo_id']}-{op['servico_id']}",
                    "ranking": i,
                    "rotulo": meta.get("rotulo"),
                    "atalho_sugerido": meta.get("rotulo"),
                    "servico_legado": meta.get("rotulo"),
                    "titulo_sinapse_historico": op.get("titulo"),
                    "sinapse_servico_id_sugerido_historico": op.get("servico_id"),
                    "orgao": op.get("orgao"),
                    "padrao": op.get("padrao"),
                    "fonte": "carta_eixo",
                }
            )
        return out

    def atalhos_copiloto(self, *, limite: int = 12) -> list[dict[str, Any]]:
        """Pedidos frequentes agrupados por eixo — sem «Outros», com ranking."""
        metas = self._ordenar_metas_por_volume()[:limite]
        out: list[dict[str, Any]] = []
        for ranking, meta in enumerate(metas, 1):
            opcoes = self.opcoes_carta_para_eixo(meta, limite=6)
            eixo_id = meta["eixo_id"]
            out.append(
                {
                    "id": eixo_id,
                    "ranking": ranking,
                    "rotulo": meta["rotulo"],
                    "texto_sugerido": meta.get("texto_sugerido")
                    or f"Solicito {meta['rotulo'].lower()}.",
                    "eixo_id": eixo_id,
                    "tem_detalhamento": len(opcoes) > 1,
                    "qtd_opcoes_carta": len(opcoes),
                    "servico_padrao_id": meta.get("servico_padrao_id"),
                    "opcoes_carta": opcoes if len(opcoes) <= 6 else opcoes[:6],
                }
            )
        return out

    def detalhe_atalho_copiloto(self, eixo_id: str) -> dict[str, Any] | None:
        meta = self.meta_pedido_frequente(eixo_id)
        if not meta:
            return None
        opcoes = self.opcoes_carta_para_eixo(meta, limite=10)
        return {
            "id": eixo_id,
            "rotulo": meta["rotulo"],
            "texto_sugerido": meta.get("texto_sugerido"),
            "tem_detalhamento": len(opcoes) > 1,
            "opcoes_carta": opcoes,
        }


def _texto_atalho_copiloto(trend: dict[str, Any]) -> str:
    exemplo = (trend.get("exemplos_assunto") or [""])[0]
    atalho = trend.get("atalho_sugerido") or trend.get("titulo") or "Solicitação"
    if len(exemplo) > 40:
        return f"Solicito {atalho.lower()}."
    return exemplo or f"Solicito {atalho.lower()}."
