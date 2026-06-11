"""Encerramento legislativo — ciência do vereador e ofício ao cidadão (Fase 6)."""

from __future__ import annotations

import logging
import re
from typing import Any

from django.utils import timezone

from core.models import Demanda, Tramitacao
from core.models_encerramento_legislativo import EncerramentoLegislativo
from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService
from core.services.oficio_service import OficioService
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)

_PARECER_RE = re.compile(
    r"Parecer operacional:\s*\n(.+?)(?:\nReferência externa:|$)",
    re.DOTALL | re.IGNORECASE,
)
_RESPOSTA_RE = re.compile(r"Resposta:\s*\n(.+)", re.DOTALL | re.IGNORECASE)


class EncerramentoLegislativoService:
    def _tramitacao_por_tipo(self, demanda: Demanda, tipo: str) -> Tramitacao | None:
        return (
            demanda.tramitacoes.filter(tipo=tipo).order_by("-timestamp").first()
        )

    def _extrair_parecer_operacional(self, tram: Tramitacao | None) -> str:
        if not tram:
            return ""
        m = _PARECER_RE.search(tram.descricao or "")
        if m:
            return m.group(1).strip()
        return (tram.descricao or "").strip()

    def _extrair_resposta_protocolo(self, tram: Tramitacao | None) -> str:
        if not tram:
            return ""
        m = _RESPOSTA_RE.search(tram.descricao or "")
        if m:
            return m.group(1).strip()
        return (tram.descricao or "").strip()

    def montar_pacote_devolutiva(self, demanda: Demanda) -> dict[str, Any]:
        sol = self._tramitacao_por_tipo(demanda, "SOLICITACAO_DEVOLUTIVA")
        dev = self._tramitacao_por_tipo(demanda, "DEVOLUTIVA_PROTOCOLO")
        enc = getattr(demanda, "encerramento_legislativo", None)
        return {
            "demanda_id": demanda.pk,
            "status": demanda.status,
            "protocolo_executivo": demanda.protocolo_executivo,
            "protocolo_legislativo": demanda.protocolo_legislativo,
            "titulo": demanda.titulo,
            "relato_demanda": demanda.descricao,
            "parecer_operacional": self._extrair_parecer_operacional(sol),
            "resposta_protocolo": self._extrair_resposta_protocolo(dev),
            "orgao_nome": sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or "",
            "solicitacao_em": sol.timestamp.isoformat() if sol else None,
            "devolutiva_em": dev.timestamp.isoformat() if dev else None,
            "ciencia_em": enc.ciencia_em.isoformat() if enc and enc.ciencia_em else None,
            "texto_resposta_cidadao": enc.texto_resposta_cidadao if enc else "",
            "oficio_resposta_url": self._url_oficio_resposta(demanda),
        }

    def _url_oficio_resposta(self, demanda: Demanda) -> str | None:
        anexo = (
            demanda.anexos.filter(descricao__icontains="Resposta ao cidadão")
            .order_by("-data_upload")
            .first()
        )
        if anexo and anexo.arquivo:
            return anexo.arquivo.url
        return None

    def _get_or_create_encerramento(self, demanda: Demanda) -> EncerramentoLegislativo:
        enc, _ = EncerramentoLegislativo.objects.get_or_create(demanda=demanda)
        return enc

    def render_resposta_cidadao_pdf(
        self,
        demanda: Demanda,
        *,
        texto_resposta: str = "",
    ) -> bytes:
        if isinstance(demanda, int):
            demanda = Demanda.objects.select_related("autor").get(pk=demanda)

        pacote = self.montar_pacote_devolutiva(demanda)
        autor = demanda.autor
        from core.services.oficio_texto import montar_texto_resposta_cidadao

        corpo = montar_texto_resposta_cidadao(
            titulo_demanda=demanda.titulo,
            relato_demanda=pacote["relato_demanda"] or demanda.titulo,
            parecer_operacional=pacote["parecer_operacional"],
            resposta_protocolo=pacote["resposta_protocolo"],
            texto_resposta=texto_resposta or pacote.get("texto_resposta_cidadao") or "",
            protocolo_executivo=demanda.protocolo_executivo,
            autor_nome=autor.get_full_name() or autor.username,
            autor_cargo=getattr(autor, "cargo", None) or "",
            orgao_nome=pacote["orgao_nome"],
        )
        return OficioService().render_resposta_cidadao_pdf(demanda, corpo_texto=corpo)

    def anexar_oficio_resposta(self, demanda: Demanda, pdf_bytes: bytes) -> str | None:
        from pathlib import Path

        from django.conf import settings

        pasta = Path(settings.MEDIA_ROOT) / "oficios"
        pasta.mkdir(parents=True, exist_ok=True)
        nome = f"resposta_cidadao_demanda_{demanda.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.pdf"
        caminho = pasta / nome
        caminho.write_bytes(pdf_bytes)
        return OficioService.anexar_pdf_a_demandas(
            [demanda],
            str(caminho.resolve()),
            descricao="Resposta ao cidadão (devolutiva legislativa)",
        )

    def confirmar_ciencia(
        self,
        demanda: Demanda,
        usuario,
        *,
        texto_resposta_cidadao: str = "",
        gerar_oficio: bool = True,
        encerrar: bool = True,
    ) -> Demanda:
        if demanda.status != "DEVOLVIDO_VEREADOR":
            raise ValueError("Ciência só pode ser registrada com devolutiva pendente ao vereador.")

        perfil = getattr(usuario, "perfil", None)
        if perfil == "VEREADOR" and demanda.autor_id != usuario.pk:
            raise ValueError("Apenas o autor do ofício pode registrar ciência.")
        if perfil not in ("VEREADOR", "GESTOR") and not usuario.is_staff:
            raise ValueError("Sem permissão para registrar ciência.")

        texto = (texto_resposta_cidadao or "").strip()
        enc = self._get_or_create_encerramento(demanda)
        agora = timezone.now()
        enc.texto_resposta_cidadao = texto
        enc.ciencia_em = agora
        enc.ciencia_por = usuario
        enc.save(
            update_fields=[
                "texto_resposta_cidadao",
                "ciencia_em",
                "ciencia_por",
                "atualizado_em",
            ]
        )

        if gerar_oficio:
            pdf = self.render_resposta_cidadao_pdf(demanda, texto_resposta=texto)
            self.anexar_oficio_resposta(demanda, pdf)

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="CIENCIA_VEREADOR",
            descricao=(
                "Vereador registrou ciência da devolutiva"
                + (f" e resposta ao cidadão:\n{texto}" if texto else ".")
            ),
        )

        if encerrar:
            enc.encerrado_em = agora
            enc.save(update_fields=["encerrado_em", "atualizado_em"])
            DevolutivaProtocoloService().encerrar_devolutiva(demanda, usuario)

        logger.info(
            "Ciência registrada demanda=%s usuario=%s encerrar=%s",
            demanda.pk,
            usuario.pk,
            encerrar,
        )
        return demanda
