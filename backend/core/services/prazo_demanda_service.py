"""Resolução centralizada de prazo (SLA) por demanda ou serviço Sinapse (C1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models import Demanda
from core.models_config import ConfiguracaoCarta
from integrations import sinapse_catalog


@dataclass(frozen=True)
class PrazoResolvido:
    dias: int | None
    origem: str
    origem_detalhe: str
    servico_dias: int | None = None

    ORIGEM_LABELS = {
        "CARTA": "Carta otimizada",
        "SINAPSE": "Sinapse",
        "METADADO": "Metadados enriquecidos",
        "PADRAO": "Padrão institucional",
        "INDEFINIDO": "Sem prazo",
    }

    def as_dict(self) -> dict[str, Any]:
        return {
            "dias": self.dias,
            "origem": self.origem,
            "origem_detalhe": self.origem_detalhe,
            "origem_label": self.ORIGEM_LABELS.get(self.origem_detalhe, self.origem_detalhe),
            "servico_dias": self.servico_dias,
        }


class PrazoDemandaService:
    def _config(self) -> ConfiguracaoCarta:
        return ConfiguracaoCarta.carregar()

    def prazo_servico_bruto(self, sinapse_servico_id: int | None) -> tuple[int | None, str]:
        """Prioridade: ServicoOtimizado → Sinapse → ServicoMetadataRico."""
        if not sinapse_servico_id:
            return None, "INDEFINIDO"

        sid = int(sinapse_servico_id)

        from core.models_carta_otimizada import ServicoOtimizado

        otimizado = (
            ServicoOtimizado.objects.filter(sinapse_servico_id=sid, ativo=True)
            .only("prazo_dias")
            .first()
        )
        if otimizado and otimizado.prazo_dias is not None:
            return int(otimizado.prazo_dias), "CARTA"

        prazo_sinapse = sinapse_catalog.prazo_dias(sid)
        if prazo_sinapse is not None:
            return int(prazo_sinapse), "SINAPSE"

        from core.models_carta_metadata import ServicoMetadataRico

        meta = (
            ServicoMetadataRico.objects.filter(sinapse_servico_id=sid)
            .only("prazo_dias_numericos")
            .first()
        )
        if meta and meta.prazo_dias_numericos is not None:
            return int(meta.prazo_dias_numericos), "METADADO"

        return None, "INDEFINIDO"

    def _aplicar_politica(
        self,
        *,
        servico_dias: int | None,
        origem_detalhe: str,
        politica: str,
        prazo_padrao: int | None,
    ) -> PrazoResolvido:
        if politica == ConfiguracaoCarta.POLITICA_PADRAO:
            if prazo_padrao is not None:
                return PrazoResolvido(
                    int(prazo_padrao),
                    Demanda.PRAZO_ORIGEM_PADRAO,
                    "PADRAO",
                    servico_dias,
                )
            return PrazoResolvido(None, Demanda.PRAZO_ORIGEM_INDEFINIDO, "INDEFINIDO", servico_dias)

        if politica == ConfiguracaoCarta.POLITICA_SERVICO:
            if servico_dias is not None:
                return PrazoResolvido(
                    servico_dias,
                    Demanda.PRAZO_ORIGEM_SERVICO,
                    origem_detalhe,
                    servico_dias,
                )
            return PrazoResolvido(None, Demanda.PRAZO_ORIGEM_INDEFINIDO, "INDEFINIDO", None)

        # SERVICO_COM_FALLBACK (default homologação)
        if servico_dias is not None:
            return PrazoResolvido(
                servico_dias,
                Demanda.PRAZO_ORIGEM_SERVICO,
                origem_detalhe,
                servico_dias,
            )
        if prazo_padrao is not None:
            return PrazoResolvido(
                int(prazo_padrao),
                Demanda.PRAZO_ORIGEM_PADRAO,
                "PADRAO",
                None,
            )
        return PrazoResolvido(None, Demanda.PRAZO_ORIGEM_INDEFINIDO, "INDEFINIDO", None)

    def resolver_servico(self, sinapse_servico_id: int | None) -> PrazoResolvido:
        cfg = self._config()
        servico_dias, origem_detalhe = self.prazo_servico_bruto(sinapse_servico_id)
        return self._aplicar_politica(
            servico_dias=servico_dias,
            origem_detalhe=origem_detalhe,
            politica=cfg.politica_prazo,
            prazo_padrao=cfg.prazo_padrao_dias,
        )

    def resolver_demanda(self, demanda: Demanda) -> PrazoResolvido:
        if demanda.prazo_efetivo_dias is not None and demanda.prazo_origem:
            origem_detalhe = "INDEFINIDO"
            if demanda.prazo_origem == Demanda.PRAZO_ORIGEM_PADRAO:
                origem_detalhe = "PADRAO"
            elif (
                demanda.prazo_origem == Demanda.PRAZO_ORIGEM_SERVICO
                and demanda.sinapse_servico_id
            ):
                _, origem_detalhe = self.prazo_servico_bruto(demanda.sinapse_servico_id)
            return PrazoResolvido(
                int(demanda.prazo_efetivo_dias),
                demanda.prazo_origem,
                origem_detalhe,
            )

        servico_dias, origem_detalhe = self.prazo_servico_bruto(demanda.sinapse_servico_id)
        cfg = self._config()
        return self._aplicar_politica(
            servico_dias=servico_dias,
            origem_detalhe=origem_detalhe,
            politica=cfg.politica_prazo,
            prazo_padrao=cfg.prazo_padrao_dias,
        )

    def aplicar_snapshot_protocolo(self, demanda: Demanda) -> None:
        """Persiste prazo efetivo ao iniciar contagem (protocolado)."""
        resolvido = self.resolver_demanda(demanda)
        demanda.prazo_efetivo_dias = resolvido.dias
        demanda.prazo_origem = resolvido.origem or Demanda.PRAZO_ORIGEM_INDEFINIDO

    def enriquecer_detalhe_servico(self, detalhe: dict[str, Any] | None) -> dict[str, Any] | None:
        if not detalhe:
            return detalhe
        sid = detalhe.get("id")
        resolvido = self.resolver_servico(int(sid) if sid else None)
        out = dict(detalhe)
        out["prazo_efetivo_dias"] = resolvido.dias
        out["prazo_origem"] = resolvido.origem
        out["prazo_origem_detalhe"] = resolvido.origem_detalhe
        out["prazo_origem_label"] = resolvido.as_dict()["origem_label"]
        if resolvido.dias is not None:
            out["prazo_dias"] = resolvido.dias
        return out
