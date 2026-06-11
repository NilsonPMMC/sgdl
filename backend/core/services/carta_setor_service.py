"""Vínculo carta otimizada → unidade administrativa (C2)."""

from __future__ import annotations

from typing import Any

from core.models_carta_otimizada import ServicoOtimizado
from core.models_unidade_administrativa import UnidadeAdministrativa
from integrations import sinapse_catalog


class CartaSetorService:
    ORIGEM_CARTA = "CARTA"
    ORIGEM_ORGAO = "ORGAO"
    ORIGEM_NENHUMA = "NENHUMA"

    def _servico_otimizado(self, sinapse_servico_id: int) -> ServicoOtimizado | None:
        return (
            ServicoOtimizado.objects.filter(
                sinapse_servico_id=int(sinapse_servico_id),
                ativo=True,
            )
            .select_related("unidade_administrativa")
            .first()
        )

    def validar_unidade_para_servico(
        self,
        sinapse_servico_id: int,
        unidade_id: int,
    ) -> UnidadeAdministrativa:
        orgao_id = sinapse_catalog.get_orgao_id_for_servico(int(sinapse_servico_id))
        if not orgao_id:
            raise ValueError("Serviço sem órgão responsável na carta Sinapse.")

        try:
            unidade = UnidadeAdministrativa.objects.get(pk=int(unidade_id), ativo=True)
        except (UnidadeAdministrativa.DoesNotExist, TypeError, ValueError):
            raise ValueError("Setor de destino não encontrado ou inativo.")

        if int(unidade.sinapse_orgao_id) != int(orgao_id):
            raise ValueError(
                "O setor informado não pertence ao órgão responsável por este serviço."
            )
        return unidade

    def vinculo_explicito(self, sinapse_servico_id: int | None) -> UnidadeAdministrativa | None:
        if not sinapse_servico_id:
            return None
        svc = self._servico_otimizado(int(sinapse_servico_id))
        if not svc or not svc.unidade_administrativa_id:
            return None
        unidade = svc.unidade_administrativa
        if unidade and unidade.ativo:
            return unidade
        return None

    def fallback_orgao(self, sinapse_servico_id: int | None) -> UnidadeAdministrativa | None:
        if not sinapse_servico_id:
            return None
        orgao_id = sinapse_catalog.get_orgao_id_for_servico(int(sinapse_servico_id))
        if not orgao_id:
            return None
        return (
            UnidadeAdministrativa.objects.filter(
                sinapse_orgao_id=int(orgao_id),
                ativo=True,
            )
            .order_by("nome")
            .first()
        )

    def resolver_unidade(self, sinapse_servico_id: int | None) -> UnidadeAdministrativa | None:
        """Prioridade: vínculo carta → fallback primeira unidade ativa do órgão."""
        explicita = self.vinculo_explicito(sinapse_servico_id)
        if explicita:
            return explicita
        return self.fallback_orgao(sinapse_servico_id)

    def resolver_unidade_demanda(self, demanda) -> UnidadeAdministrativa | None:
        return self.resolver_unidade(getattr(demanda, "sinapse_servico_id", None))

    def unidade_resumo(self, unidade: UnidadeAdministrativa | None) -> dict[str, Any] | None:
        if not unidade:
            return None
        return {
            "id": unidade.pk,
            "nome": unidade.nome,
            "sigla": unidade.sigla,
            "sinapse_orgao_id": unidade.sinapse_orgao_id,
        }

    def enriquecer_item_carta(self, item: dict[str, Any]) -> dict[str, Any]:
        sid = item.get("sinapse_servico_id") or item.get("id")
        if sid is None:
            return item
        sid_int = int(sid)
        explicita = self.vinculo_explicito(sid_int)
        sugerida = explicita or self.fallback_orgao(sid_int)
        out = dict(item)
        out["unidade_administrativa_id"] = explicita.pk if explicita else None
        out["unidade_administrativa"] = self.unidade_resumo(explicita)
        out["setor_sugerido"] = self.unidade_resumo(sugerida)
        out["setor_origem"] = (
            self.ORIGEM_CARTA
            if explicita
            else (self.ORIGEM_ORGAO if sugerida else self.ORIGEM_NENHUMA)
        )
        from core.services.carta_utilizacao_service import CartaUtilizacaoService

        return CartaUtilizacaoService().enriquecer_item_carta(out)

    def enriquecer_detalhe_servico(self, detalhe: dict[str, Any] | None) -> dict[str, Any] | None:
        if not detalhe:
            return detalhe
        sid = detalhe.get("id")
        if not sid:
            return detalhe
        return self.enriquecer_item_carta({**detalhe, "sinapse_servico_id": int(sid)})

    def vincular(
        self,
        sinapse_servico_id: int,
        unidade_administrativa_id: int | None,
    ) -> ServicoOtimizado:
        sid = int(sinapse_servico_id)
        svc = ServicoOtimizado.objects.filter(sinapse_servico_id=sid).first()
        if not svc:
            raise ValueError(
                "Serviço não encontrado na carta otimizada. "
                "Sincronize ou otimize a base antes de vincular o setor."
            )

        if unidade_administrativa_id is None:
            svc.unidade_administrativa = None
        else:
            svc.unidade_administrativa = self.validar_unidade_para_servico(
                sid, int(unidade_administrativa_id)
            )
        svc.save(update_fields=["unidade_administrativa", "atualizado_em"])
        return svc

    def pode_desativar_unidade(self, unidade: UnidadeAdministrativa) -> bool:
        return not ServicoOtimizado.objects.filter(
            unidade_administrativa=unidade,
            ativo=True,
        ).exists()
