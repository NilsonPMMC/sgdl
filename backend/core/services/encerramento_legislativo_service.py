"""Encerramento legislativo — ciência do vereador e ofício ao cidadão (Fase 6)."""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any

from django.utils import timezone
from django.utils.html import strip_tags

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

    def _html_para_texto(self, valor: str) -> str:
        texto = unescape(strip_tags(valor or "")).replace("\xa0", " ")
        return re.sub(r"\s+", " ", texto).strip()

    def _demandas_fonte_devolutiva(self, demanda: Demanda) -> list[Demanda]:
        from core.services.operacional_estado_service import OperacionalEstadoService

        ids: set[int] = {demanda.pk}
        lider = OperacionalEstadoService().demanda_processo_lider(demanda)
        ids.add(lider.pk)
        if demanda.cluster_id:
            ids.update(
                Demanda.objects.filter(cluster_id=demanda.cluster_id).values_list("pk", flat=True)
            )
        return list(Demanda.objects.filter(pk__in=ids).select_related("autor").order_by("pk"))

    def _super_os_conclusao_individual(self, demanda: Demanda) -> bool:
        from core.services.cluster_service import ClusterService

        return ClusterService().conclusao_individual_super_os_ativa(demanda)

    def _buscar_tramitacao_devolutiva_demanda(self, demanda: Demanda) -> Tramitacao | None:
        trams = list(
            demanda.tramitacoes.filter(
                tipo__in=("DEVOLUTIVA_PROTOCOLO", "CONCLUSAO_FINAL")
            ).order_by("-timestamp", "-pk")
        )
        for tram in trams:
            meta = tram.metadata if isinstance(tram.metadata, dict) else {}
            if meta.get("parecer") or _RESPOSTA_RE.search(tram.descricao or ""):
                return tram
        return trams[0] if trams else None

    def _extrair_parecer_laudo(self, tram: Tramitacao | None) -> str:
        if not tram:
            return ""
        meta = tram.metadata if isinstance(tram.metadata, dict) else {}
        parecer = (meta.get("parecer") or "").strip()
        if parecer:
            return parecer
        return self._extrair_resposta_protocolo(tram)

    def _tramitacao_devolutiva_final(self, demanda: Demanda) -> Tramitacao | None:
        propria = self._buscar_tramitacao_devolutiva_demanda(demanda)
        if propria:
            return propria
        if self._super_os_conclusao_individual(demanda):
            return None
        for fonte in self._demandas_fonte_devolutiva(demanda):
            if int(fonte.pk) == int(demanda.pk):
                continue
            tram = self._buscar_tramitacao_devolutiva_demanda(fonte)
            if tram:
                return tram
        return None

    def _laudo_despacho_final(self, demanda: Demanda, dev: Tramitacao | None) -> str:
        if dev and int(dev.demanda_id) == int(demanda.pk):
            return self._extrair_parecer_laudo(dev)

        propria = self._buscar_tramitacao_devolutiva_demanda(demanda)
        if propria:
            return self._extrair_parecer_laudo(propria)

        if self._super_os_conclusao_individual(demanda):
            return ""

        candidatos: list[Tramitacao] = []
        if dev:
            candidatos.append(dev)
        for fonte in self._demandas_fonte_devolutiva(demanda):
            candidatos.extend(
                list(
                    fonte.tramitacoes.filter(
                        tipo__in=("DEVOLUTIVA_PROTOCOLO", "CONCLUSAO_FINAL")
                    ).order_by("-timestamp", "-pk")
                )
            )
        vistos: set[int] = set()
        for tram in candidatos:
            if tram.pk in vistos:
                continue
            vistos.add(tram.pk)
            texto = self._extrair_parecer_laudo(tram)
            if texto:
                return texto
        return ""

    def _anexos_despacho_final(self, demanda: Demanda) -> list[dict[str, Any]]:
        from core.services.tramitacao_anexo_service import serializar_anexos_tramitacao

        if self._super_os_conclusao_individual(demanda):
            fontes = [demanda]
        else:
            fontes = self._demandas_fonte_devolutiva(demanda)

        vistos: set[int] = set()
        anexos: list[dict[str, Any]] = []
        for fonte in fontes:
            for tram in fonte.tramitacoes.filter(
                tipo__in=("DEVOLUTIVA_PROTOCOLO", "CONCLUSAO_FINAL")
            ).order_by("-timestamp", "-pk"):
                for item in serializar_anexos_tramitacao(tram):
                    aid = item.get("id")
                    if aid in vistos:
                        continue
                    vistos.add(aid)
                    anexos.append(item)
        return anexos

    def _signatarios_despacho_final(
        self, assinaturas: list[dict[str, Any]]
    ) -> tuple[str | None, str | None]:
        """Operador e gestor do protocolo na devolutiva/conclusão final assinada eletronicamente."""
        etapas = {"DESPACHO_DEVOLUTIVA", "CONCLUSAO_FINAL"}
        operador: str | None = None
        gestor: str | None = None
        for item in assinaturas:
            if (item.get("etapa") or "") not in etapas:
                continue
            papel = item.get("papel") or ""
            nome = (item.get("signatario") or "").strip()
            if not nome:
                continue
            if papel == "OPERADOR":
                operador = nome
            elif papel == "GESTOR_PROTOCOLO":
                gestor = nome
        return operador, gestor

    def _assinaturas_processo(
        self, demanda: Demanda, historico_tecnico: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        svc = AssinaturaEletronicaService()
        assinaturas: list[dict[str, Any]] = []
        vistos: set[tuple[str, ...]] = set()

        def add(item: dict[str, Any], *, chave: tuple[str, ...] | None = None) -> None:
            key = chave or (
                item.get("etapa") or "",
                item.get("papel") or "",
                item.get("codigo_validacao") or item.get("signatario") or "",
            )
            if key in vistos:
                return
            vistos.add(key)
            assinaturas.append(item)

        for item in svc.serializar_assinaturas_demanda(demanda):
            add(item)

        dev = self._tramitacao_devolutiva_final(demanda)
        if dev and dev.demanda_id != demanda.pk:
            from core.models import Demanda as DemandaModel

            fonte_dev = DemandaModel.objects.filter(pk=dev.demanda_id).first()
            if fonte_dev:
                for item in svc.serializar_assinaturas_demanda(fonte_dev):
                    if item.get("etapa") in ("DESPACHO_DEVOLUTIVA", "CONCLUSAO_FINAL"):
                        add(item)

        eletronicas_conclusao = {
            (a.get("signatario") or "", a.get("etapa") or "")
            for a in assinaturas
            if a.get("etapa") == "CONCLUSAO_SECRETARIA"
        }

        for ev in (historico_tecnico or {}).get("eventos_tecnicos") or []:
            if not isinstance(ev, dict):
                continue
            signatario = (ev.get("responsavel") or "").strip() or "—"
            if ("CONCLUSAO_SECRETARIA", signatario) in eletronicas_conclusao:
                continue
            orgao = ev.get("orgao_nome") or "Secretaria"
            parcial = ev.get("parcial") or ev.get("tipo") == "CONCLUSAO_PARCIAL"
            add(
                {
                    "etapa": "CONCLUSAO_PARCIAL" if parcial else "CONCLUSAO_SECRETARIA",
                    "etapa_display": f"Conclusão operacional — {orgao}",
                    "papel": "CHEFIA_SETOR",
                    "papel_display": "Gestor / chefia da secretaria",
                    "signatario": signatario,
                    "cargo": ev.get("setor_nome") or orgao,
                    "assinado_em": ev.get("timestamp"),
                    "codigo_validacao": None,
                    "declaracao": None,
                },
                chave=("HISTORICO", str(ev.get("tramitacao_id") or ""), signatario),
            )

        def _ts(item: dict[str, Any]) -> str:
            raw = item.get("assinado_em")
            if raw is None:
                return ""
            if hasattr(raw, "isoformat"):
                return raw.isoformat()
            return str(raw)

        assinaturas.sort(key=_ts)
        return assinaturas

    def _sanitizar_historico_tecnico(self, historico: dict[str, Any] | None) -> dict[str, Any] | None:
        if not historico:
            return historico
        eventos = []
        for ev in historico.get("eventos_tecnicos") or []:
            if not isinstance(ev, dict):
                continue
            limpo = dict(ev)
            limpo["parecer"] = self._html_para_texto(limpo.get("parecer") or "")
            eventos.append(limpo)
        return {**historico, "eventos_tecnicos": eventos}

    def montar_pacote_devolutiva(self, demanda: Demanda) -> dict[str, Any]:
        dev = self._tramitacao_devolutiva_final(demanda)
        enc = getattr(demanda, "encerramento_legislativo", None)

        laudo_final = self._laudo_despacho_final(demanda, dev)

        historico_tecnico = None
        if dev and isinstance(dev.metadata, dict):
            historico_tecnico = dev.metadata.get("historico_tecnico")
        if not (historico_tecnico or {}).get("eventos_tecnicos") and demanda.fluxo_roteamento:
            from core.services.operacional_estado_service import OperacionalEstadoService

            historico_tecnico = OperacionalEstadoService().compilar_historico_tecnico(demanda)
        historico_tecnico = self._sanitizar_historico_tecnico(historico_tecnico)

        assinaturas = self._assinaturas_processo(demanda, historico_tecnico)

        conclusao_em = dev.timestamp.isoformat() if dev and dev.timestamp else None
        operador_ass, gestor_ass = self._signatarios_despacho_final(assinaturas)
        if gestor_ass:
            conclusao_responsavel = gestor_ass
        elif dev and dev.responsavel:
            conclusao_responsavel = dev.responsavel.get_full_name() or dev.responsavel.username
        else:
            conclusao_responsavel = operador_ass

        return {
            "demanda_id": demanda.pk,
            "status": demanda.status,
            "protocolo_executivo": demanda.protocolo_executivo,
            "protocolo_legislativo": demanda.protocolo_legislativo,
            "titulo": demanda.titulo,
            "oficio_original": demanda.descricao or "",
            "laudo_final": laudo_final,
            "anexos_devolutiva": self._anexos_despacho_final(demanda),
            "orgao_nome": sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or "",
            "conclusao_em": conclusao_em,
            "conclusao_responsavel": conclusao_responsavel,
            "conclusao_operador": operador_ass,
            "conclusao_gestor_protocolo": gestor_ass,
            "historico_tecnico": historico_tecnico,
            "assinaturas": assinaturas,
            "pesquisa_satisfacao_habilitada": False,
            # Campos legados (API interna / PDF futuro)
            "relato_demanda": demanda.descricao,
            "parecer_operacional": "",
            "resposta_protocolo": self._html_para_texto(laudo_final),
            "devolutiva_em": conclusao_em,
            "devolutiva_responsavel": conclusao_responsavel,
            "solicitacao_em": None,
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
        if demanda.status == "FINALIZADO":
            encerrar = False
        elif demanda.status != "DEVOLVIDO_VEREADOR":
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
