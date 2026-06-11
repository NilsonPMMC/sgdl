"""Política de utilização da carta no SGDL — assunto + override por serviço (C5)."""

from __future__ import annotations

import logging
from typing import Any

from core.models_assunto_carta import AssuntoCarta, ModoUtilizacaoSgdl
from core.models_carta_otimizada import ServicoOtimizado

logger = logging.getLogger(__name__)

MODO_DEFAULT = ModoUtilizacaoSgdl.PROTOCOLAVEL


class CartaUtilizacaoService:
    def _servico(self, sinapse_servico_id: int | None) -> ServicoOtimizado | None:
        if not sinapse_servico_id:
            return None
        return (
            ServicoOtimizado.objects.filter(
                sinapse_servico_id=int(sinapse_servico_id),
                ativo=True,
            )
            .select_related("assunto")
            .first()
        )

    def resolver(self, sinapse_servico_id: int | None) -> dict[str, Any]:
        svc = self._servico(sinapse_servico_id)
        assunto = svc.assunto if svc else None
        modo_servico = (svc.modo_utilizacao_sgdl or "").strip() if svc else ""
        modo_assunto = (
            assunto.modo_utilizacao_sgdl if assunto else MODO_DEFAULT
        )

        if modo_servico:
            modo_efetivo = modo_servico
            heranca = "SERVICO"
        elif assunto:
            modo_efetivo = modo_assunto
            heranca = "ASSUNTO"
        else:
            modo_efetivo = MODO_DEFAULT
            heranca = "GLOBAL"

        mensagem = ""
        if svc and svc.mensagem_orientacao:
            mensagem = svc.mensagem_orientacao.strip()
        elif assunto and assunto.mensagem_orientacao:
            mensagem = assunto.mensagem_orientacao.strip()

        return {
            "sinapse_servico_id": int(sinapse_servico_id) if sinapse_servico_id else None,
            "modo_efetivo": modo_efetivo,
            "modo_servico": modo_servico or None,
            "modo_assunto": modo_assunto if assunto else None,
            "heranca": heranca,
            "assunto_id": assunto.pk if assunto else None,
            "assunto_nome": assunto.nome if assunto else None,
            "assunto_slug": assunto.slug if assunto else None,
            "mensagem_orientacao": mensagem,
            "somente_orientacao": modo_efetivo == ModoUtilizacaoSgdl.INFORMATIVO,
            "requer_condicao": modo_efetivo == ModoUtilizacaoSgdl.PROTOCOLAVEL_CONDICIONAL,
        }

    def pode_protocolar(self, sinapse_servico_id: int | None) -> bool:
        info = self.resolver(sinapse_servico_id)
        return info["modo_efetivo"] != ModoUtilizacaoSgdl.INFORMATIVO

    def validar_protocolo(self, sinapse_servico_id: int | None, *, contexto: str = "") -> None:
        info = self.resolver(sinapse_servico_id)
        if info["modo_efetivo"] == ModoUtilizacaoSgdl.INFORMATIVO:
            msg = info.get("mensagem_orientacao") or (
                "Este serviço é somente informativo no SGDL e não gera ofício pelo gabinete."
            )
            logger.info(
                "Bloqueio protocolo serviço informativo id=%s contexto=%s assunto=%s",
                sinapse_servico_id,
                contexto,
                info.get("assunto_nome"),
            )
            raise ValueError(msg)

    def enriquecer_candidato(self, candidato: dict[str, Any]) -> dict[str, Any]:
        sid = candidato.get("servico_id")
        if sid is None:
            return candidato
        info = self.resolver(int(sid))
        out = dict(candidato)
        out.update(
            {
                "modo_utilizacao_sgdl": info["modo_efetivo"],
                "modo_heranca": info["heranca"],
                "assunto_nome": info["assunto_nome"],
                "somente_orientacao": info["somente_orientacao"],
                "mensagem_orientacao": info["mensagem_orientacao"],
            }
        )
        return out

    def enriquecer_item_carta(self, item: dict[str, Any]) -> dict[str, Any]:
        sid = item.get("sinapse_servico_id") or item.get("id")
        if sid is None:
            return item
        info = self.resolver(int(sid))
        out = dict(item)
        out["utilizacao_sgdl"] = info
        return out

    def vincular(
        self,
        sinapse_servico_id: int,
        *,
        assunto_id: int | None = None,
        modo_utilizacao_sgdl: str | None = None,
        mensagem_orientacao: str | None = None,
    ) -> ServicoOtimizado:
        sid = int(sinapse_servico_id)
        svc = ServicoOtimizado.objects.filter(sinapse_servico_id=sid).first()
        if not svc:
            raise ValueError(
                "Serviço não encontrado na carta otimizada. "
                "Sincronize ou otimize a base antes de classificar."
            )

        if assunto_id is not None:
            if assunto_id == 0 or assunto_id == "":
                svc.assunto = None
            else:
                try:
                    svc.assunto = AssuntoCarta.objects.get(pk=int(assunto_id), ativo=True)
                except (AssuntoCarta.DoesNotExist, TypeError, ValueError):
                    raise ValueError("Assunto temático não encontrado.")

        if modo_utilizacao_sgdl is not None:
            modo = str(modo_utilizacao_sgdl).strip().upper()
            if modo in ("", "NULL", "HERDAR"):
                svc.modo_utilizacao_sgdl = ""
            elif modo in ModoUtilizacaoSgdl.values:
                svc.modo_utilizacao_sgdl = modo
            else:
                raise ValueError("modo_utilizacao_sgdl inválido.")

        if mensagem_orientacao is not None:
            svc.mensagem_orientacao = str(mensagem_orientacao).strip()

        svc.save(
            update_fields=[
                "assunto",
                "modo_utilizacao_sgdl",
                "mensagem_orientacao",
                "atualizado_em",
            ]
        )
        return svc
