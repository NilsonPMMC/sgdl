"""Explorer da Carta de Serviços Sinapse + simulação de triagem vetorial."""

from __future__ import annotations

import time
from typing import Any

from integrations import sinapse_catalog
from integrations.sinapse_catalog import catalog_disponivel


class CartaExplorerService:
    """Consulta ao catálogo e prova de triagem (mesmo motor do Copiloto)."""

    def buscar(
        self,
        *,
        q: str = "",
        orgao_id: int | None = None,
        limit: int = 40,
        offset: int = 0,
    ) -> dict[str, Any]:
        data = sinapse_catalog.buscar_servicos_catalogo(
            q=q,
            orgao_id=orgao_id,
            limit=min(max(limit, 1), 100),
            offset=max(offset, 0),
        )
        from core.services.prazo_demanda_service import PrazoDemandaService

        prazo_svc = PrazoDemandaService()
        from core.services.carta_setor_service import CartaSetorService

        setor_svc = CartaSetorService()
        results = []
        for item in data.get("results") or []:
            sid = item.get("id")
            if not sid:
                results.append(item)
                continue
            resolvido = prazo_svc.resolver_servico(int(sid))
            item["prazo_efetivo_dias"] = resolvido.dias
            item["prazo_origem_label"] = resolvido.as_dict()["origem_label"]
            if resolvido.dias is not None:
                item["prazo_dias"] = resolvido.dias
            results.append(setor_svc.enriquecer_item_carta({**item, "sinapse_servico_id": int(sid)}))
        data["results"] = results
        return data

    def detalhe(self, servico_id: int) -> dict[str, Any] | None:
        from core.services.prazo_demanda_service import PrazoDemandaService
        from core.services.carta_setor_service import CartaSetorService

        raw = sinapse_catalog.servico_detalhe_dict(servico_id)
        raw = PrazoDemandaService().enriquecer_detalhe_servico(raw)
        return CartaSetorService().enriquecer_detalhe_servico(raw)

    def simular_triagem(self, texto: str, *, top_k: int = 5) -> dict[str, Any]:
        texto_limpo = (texto or "").strip()
        if len(texto_limpo) < 4:
            return {
                "ok": False,
                "erro": "Informe pelo menos 4 caracteres para simular a triagem.",
                "candidatos": [],
            }
        if not catalog_disponivel():
            return {
                "ok": False,
                "erro": "Catálogo Sinapse indisponível (DATABASES['sinapse']).",
                "candidatos": [],
            }

        from core.services.triagem_service import TriagemService
        from core.services.vector_service import VectorService

        t_embed = time.perf_counter()
        embedding = VectorService().generate_embedding(texto_limpo)
        latencia_embed_ms = round((time.perf_counter() - t_embed) * 1000, 1)

        if not embedding:
            return {
                "ok": False,
                "erro": "Não foi possível gerar embedding (Kernel AI indisponível ou texto vazio).",
                "candidatos": [],
                "latencia_embed_ms": latencia_embed_ms,
            }

        t_triagem = time.perf_counter()
        candidatos = TriagemService().buscar_servico_sinapse(
            embedding,
            top_k=min(max(top_k, 1), 10),
            texto_consulta=texto_limpo,
        )
        latencia_triagem_ms = round((time.perf_counter() - t_triagem) * 1000, 1)

        enriquecidos: list[dict[str, Any]] = []
        from core.services.prazo_demanda_service import PrazoDemandaService

        prazo_svc = PrazoDemandaService()
        for item in candidatos:
            sid = item.get("servico_id")
            det = sinapse_catalog.servico_detalhe_dict(int(sid)) if sid else None
            if det:
                det = prazo_svc.enriquecer_detalhe_servico(det)
            enriquecidos.append(
                {
                    **item,
                    "prazo_dias": det.get("prazo_efetivo_dias") if det else None,
                    "prazo_efetivo_dias": det.get("prazo_efetivo_dias") if det else None,
                    "prazo_origem_label": det.get("prazo_origem_label") if det else None,
                    "prazo_texto": det.get("prazo_texto") if det else None,
                    "documentos_resumo": (
                        (det.get("documentos_necessarios") or "")[:240] if det else ""
                    ),
                }
            )

        return {
            "ok": True,
            "texto": texto_limpo,
            "top_k": len(enriquecidos),
            "latencia_embed_ms": latencia_embed_ms,
            "latencia_triagem_ms": latencia_triagem_ms,
            "latencia_total_ms": round(latencia_embed_ms + latencia_triagem_ms, 1),
            "candidatos": enriquecidos,
        }
