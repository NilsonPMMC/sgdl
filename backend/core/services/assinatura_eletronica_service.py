"""Registro de assinatura eletrônica nativa (ofício e etapas operacionais)."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from core.models import Demanda, Tramitacao, Usuario
from core.services.assinatura_etapa_executor_service import (
    ACAO_CONCLUSAO_FINAL,
    ACAO_CONCLUSAO_SECRETARIA,
    ACAO_CONCLUSAO_SECRETARIA_FLUXO_DIRETO,
    ACAO_DESPACHO_INICIAL,
    ACAO_SCATTER_DESPACHAR_ENCERRAR,
    ACAO_SCATTER_ENCERRAR,
    AssinaturaEtapaExecutorService,
)
from core.models_assinatura_eletronica import (
    AssinaturaEletronica,
    AssinaturaPendingAcao,
    AssinaturaValidacaoGestor,
)
from core.models_unidade_administrativa import UnidadeAdministrativaResponsavel
from core.services.oficio_service import OficioService

logger = logging.getLogger(__name__)

DECLARACAO_ENVIO = "ASSINO E ENVIO"
DECLARACAO_DESPACHO = "ASSINO O DESPACHO"
DECLARACAO_DESPACHO_AUTOMATICO = "DESPACHO AUTOMATICO DO SISTEMA"
DECLARACAO_GESTOR_PROTOCOLO = "ASSINO COMO GESTOR DO PROTOCOLO"
DECLARACAO_GESTOR_SETOR = "ASSINO COMO GESTOR DO SETOR"
DECLARACAO_CONCLUSAO = "ASSINO A CONCLUSAO OPERACIONAL"
DECLARACAO_DEVOLUTIVA = "ASSINO A DEVOLUTIVA"
DECLARACAO_CONCLUSAO_FINAL = "ASSINO A CONCLUSAO FINAL"
DECLARACAO_ENCERRAMENTO_OPERACIONAL = "ASSINO O ENCERRAMENTO OPERACIONAL"

ACOES_SCATTER_ASSINATURA_OBRIGATORIA = frozenset(
    {"DESPACHAR_ENCERRAR", "ENCERRAR", "ENCERRAR_LOTE"}
)

PROTOCOLO_ORGAO_ID = 12

CARGO_PADRAO_POR_PAPEL = {
    AssinaturaEletronica.PAPEL_OPERADOR: "Operador do Protocolo",
    AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO: "Gestor do Protocolo",
    AssinaturaEletronica.PAPEL_GESTOR_SETOR: "Gestor do setor",
    AssinaturaEletronica.PAPEL_CHEFIA_SETOR: "Chefia do setor",
}

ETAPAS_VALIDACAO_GESTOR_PROTOCOLO = frozenset(
    {
        AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
        AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
    }
)

ETAPAS_VALIDACAO_GESTOR_SETOR = frozenset(
    {
        AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA,
        AssinaturaEletronica.ETAPA_OPERACAO_SCATTER,
    }
)

PAPEL_GESTOR_POR_ETAPA = {
    AssinaturaEletronica.ETAPA_DESPACHO_INICIAL: AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO,
    AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL: AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO,
    AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA: AssinaturaEletronica.PAPEL_GESTOR_SETOR,
    AssinaturaEletronica.ETAPA_OPERACAO_SCATTER: AssinaturaEletronica.PAPEL_GESTOR_SETOR,
}

DECLARACAO_GESTOR_POR_ETAPA = {
    AssinaturaEletronica.ETAPA_DESPACHO_INICIAL: DECLARACAO_GESTOR_PROTOCOLO,
    AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL: DECLARACAO_GESTOR_PROTOCOLO,
    AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA: DECLARACAO_GESTOR_SETOR,
    AssinaturaEletronica.ETAPA_OPERACAO_SCATTER: DECLARACAO_GESTOR_SETOR,
}


def cargo_signatario(usuario, papel: str | None = None) -> str:
    """Cargo institucional do signatário (B6 — preferir `Usuario.cargo`)."""
    cargo = (getattr(usuario, "cargo", None) or "").strip()
    if cargo:
        return cargo
    if papel:
        return CARGO_PADRAO_POR_PAPEL.get(papel, "")
    return ""


def resumo_signatario(usuario, papel: str | None = None) -> dict[str, Any]:
    return {
        "id": usuario.pk,
        "nome": usuario.get_full_name() or usuario.username,
        "username": usuario.username,
        "cargo": cargo_signatario(usuario, papel),
        "papel": papel,
        "papel_display": (
            dict(AssinaturaEletronica.PAPEL_CHOICES).get(papel, "") if papel else ""
        ),
    }


def _client_ip(request) -> str | None:
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR")


def _client_user_agent(request) -> str:
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT") or "")[:500]


def _scalar_request_value(val) -> str:
    """Normaliza valor de request (QueryDict multipart pode retornar listas)."""
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        if not val:
            return ""
        val = val[0]
    return str(val).strip()


def _preview_pdf_path(demanda_id: int) -> Path:
    return Path(settings.MEDIA_ROOT) / "oficios" / f"oficio_demanda_{demanda_id}_preview.pdf"


def _pending_acao_path(demanda_id: int, etapa: str) -> Path:
    return Path(settings.MEDIA_ROOT) / "assinaturas" / "pending" / f"{demanda_id}_{etapa}.json"


class AssinaturaEletronicaService:
    USUARIO_SISTEMA_USERNAME = "sgdl_sistema"

    def obter_usuario_sistema(self) -> Usuario:
        usuario, created = Usuario.objects.get_or_create(
            username=self.USUARIO_SISTEMA_USERNAME,
            defaults={
                "perfil": "PROTOCOLO",
                "is_active": True,
                "first_name": "SGDL",
                "last_name": "Sistema",
                "cargo": "Despacho automático (fluxo configurado)",
            },
        )
        if created:
            usuario.set_unusable_password()
            usuario.save(update_fields=["password"])
        return usuario

    def hash_despacho_automatico(self, demanda: Demanda) -> str:
        payload = {
            "demanda_id": int(demanda.pk),
            "etapa": AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            "protocolo_executivo": demanda.protocolo_executivo,
            "protocolo_legislativo": demanda.protocolo_legislativo,
            "sinapse_orgao_id": demanda.sinapse_orgao_id,
            "automatico": True,
        }
        return self.hash_canonical(payload)

    def registrar_assinatura_despacho_automatico(
        self, demanda: Demanda
    ) -> AssinaturaEletronica | None:
        """H3-01/H3-18 — trilha auditável para fluxo AUTO (sem operador humano)."""
        if self._assinatura_existe(
            demanda,
            AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            AssinaturaEletronica.PAPEL_OPERADOR,
        ):
            return None
        usuario = self.obter_usuario_sistema()
        hash_doc = self.hash_despacho_automatico(demanda)
        return self._criar_assinatura(
            demanda,
            usuario,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento=hash_doc,
            declaracao=DECLARACAO_DESPACHO_AUTOMATICO,
            request=None,
        )

    def hash_canonical(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def render_pdf_bytes(self, demanda: Demanda) -> bytes:
        return OficioService().render_pdf_bytes(demanda)

    def hash_documento_pdf(self, pdf_bytes: bytes) -> str:
        return hashlib.sha256(pdf_bytes).hexdigest()

    def _assinatura_existe(self, demanda: Demanda, etapa: str, papel: str) -> bool:
        return AssinaturaEletronica.objects.filter(
            demanda=demanda, etapa=etapa, papel=papel, tramitacao__isnull=True
        ).exists()

    def _limpar_assinaturas_orfas_etapa(self, demanda: Demanda, etapa: str) -> None:
        """Remove assinaturas incompletas ao gerar nova prévia (retry seguro)."""
        if demanda.status in ("DEVOLVIDO_VEREADOR", "FINALIZADO"):
            return
        AssinaturaEletronica.objects.filter(demanda=demanda, etapa=etapa).delete()
        AssinaturaValidacaoGestor.objects.filter(
            demanda=demanda, etapa=etapa, status=AssinaturaValidacaoGestor.STATUS_PENDENTE
        ).update(status=AssinaturaValidacaoGestor.STATUS_CANCELADA)

    def _tipo_gestor_para_etapa(self, etapa: str) -> str:
        if etapa in ETAPAS_VALIDACAO_GESTOR_PROTOCOLO:
            return AssinaturaValidacaoGestor.TIPO_GESTOR_PROTOCOLO
        if etapa in ETAPAS_VALIDACAO_GESTOR_SETOR:
            return AssinaturaValidacaoGestor.TIPO_GESTOR_SETOR
        raise ValueError(f"Etapa sem validação de gestor: {etapa}")

    def _papel_operador_para_etapa(self, etapa: str) -> str:
        if etapa in (
            AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
        ):
            return AssinaturaEletronica.PAPEL_OPERADOR
        if etapa in (
            AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA,
            AssinaturaEletronica.ETAPA_OPERACAO_SCATTER,
        ):
            return AssinaturaEletronica.PAPEL_CHEFIA_SETOR
        raise ValueError(f"Etapa sem operador de primeira fase: {etapa}")

    def listar_gestores_setor(
        self,
        *,
        unidade_administrativa_id: int | None = None,
        sinapse_orgao_id: int | None = None,
    ) -> list[dict[str, Any]]:
        from core.services.notificacao_service import NotificacaoService

        gestores_ids: set[int] = set()
        unidades: set[int] = set()
        orgaos: set[int] = set()
        if unidade_administrativa_id:
            unidades.add(int(unidade_administrativa_id))
        if sinapse_orgao_id:
            orgaos.add(int(sinapse_orgao_id))
        if unidades and not orgaos:
            from core.models_unidade_administrativa import UnidadeAdministrativa

            for oid in UnidadeAdministrativa.objects.filter(pk__in=unidades).values_list(
                "sinapse_orgao_id", flat=True
            ):
                if oid is not None:
                    orgaos.add(int(oid))

        for usuario in NotificacaoService()._gestores_setoriais_envolvidos(
            orgaos, unidades, unidades_destino=unidades or None
        ):
            gestores_ids.add(int(usuario.pk))

        if unidade_administrativa_id:
            for uid in UnidadeAdministrativaResponsavel.objects.filter(
                unidade_id=int(unidade_administrativa_id),
                ativo=True,
                usuario__perfil="GESTOR",
                usuario__is_active=True,
            ).values_list("usuario_id", flat=True):
                gestores_ids.add(int(uid))

        gestores: list[dict[str, Any]] = []
        for u in Usuario.objects.filter(pk__in=gestores_ids, is_active=True, perfil="GESTOR").order_by(
            "first_name", "username"
        ):
            gestores.append(
                {
                    "id": u.pk,
                    "nome": u.get_full_name() or u.username,
                    "username": u.username,
                    "perfil": u.perfil,
                    "cargo": cargo_signatario(u, AssinaturaEletronica.PAPEL_GESTOR_SETOR),
                }
            )
        return gestores

    def _criar_validacao_gestor_pendente(
        self,
        demanda: Demanda,
        operador,
        *,
        etapa: str,
        hash_documento: str,
        payload: dict[str, Any],
        tramitacao=None,
        unidade_administrativa_id: int | None = None,
        sinapse_orgao_id: int | None = None,
    ) -> AssinaturaValidacaoGestor:
        tipo_gestor = self._tipo_gestor_para_etapa(etapa)
        AssinaturaValidacaoGestor.objects.filter(
            demanda=demanda,
            etapa=etapa,
            tramitacao=tramitacao,
            status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
        ).update(status=AssinaturaValidacaoGestor.STATUS_CANCELADA)

        validacao = AssinaturaValidacaoGestor.objects.create(
            demanda=demanda,
            tramitacao=tramitacao,
            etapa=etapa,
            tipo_gestor=tipo_gestor,
            hash_documento=hash_documento,
            payload=payload,
            operador=operador,
            unidade_administrativa_id=unidade_administrativa_id,
            sinapse_orgao_id=sinapse_orgao_id,
            status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
        )
        from core.services.notificacao_service import NotificacaoService

        NotificacaoService().notificar_assinatura_pendente_gestor(validacao)
        return validacao

    def usuario_pode_validar_assinatura_gestor(
        self, usuario, validacao: AssinaturaValidacaoGestor
    ) -> bool:
        if validacao.status != AssinaturaValidacaoGestor.STATUS_PENDENTE:
            return False
        if validacao.tipo_gestor == AssinaturaValidacaoGestor.TIPO_GESTOR_PROTOCOLO:
            return self._usuario_eh_gestor_protocolo_sgac(usuario)
        from core.models_unidade_administrativa import UnidadeAdministrativa
        from core.services.gestor_escopo import gestor_pode_gerir_unidade_no_escopo

        if getattr(usuario, "perfil", None) != "GESTOR":
            return False
        if validacao.unidade_administrativa_id:
            ua = UnidadeAdministrativa.objects.filter(
                pk=validacao.unidade_administrativa_id
            ).first()
            if gestor_pode_gerir_unidade_no_escopo(usuario, ua):
                return True
        gestores = self.listar_gestores_setor(
            unidade_administrativa_id=validacao.unidade_administrativa_id,
            sinapse_orgao_id=validacao.sinapse_orgao_id,
        )
        return any(int(g["id"]) == int(usuario.pk) for g in gestores)

    def listar_validacoes_pendentes(self, usuario) -> list[dict[str, Any]]:
        qs = (
            AssinaturaValidacaoGestor.objects.filter(status=AssinaturaValidacaoGestor.STATUS_PENDENTE)
            .select_related("demanda", "operador", "tramitacao", "unidade_administrativa")
            .order_by("-criado_em")
        )
        itens: list[dict[str, Any]] = []
        for row in qs:
            if not self.usuario_pode_validar_assinatura_gestor(usuario, row):
                continue
            demanda = row.demanda
            itens.append(
                {
                    "id": row.pk,
                    "demanda_id": demanda.pk,
                    "etapa": row.etapa,
                    "etapa_display": dict(AssinaturaEletronica.ETAPA_CHOICES).get(row.etapa, row.etapa),
                    "tipo_gestor": row.tipo_gestor,
                    "hash_documento": row.hash_documento,
                    "tramitacao_id": row.tramitacao_id,
                    "protocolo_executivo": demanda.protocolo_executivo,
                    "protocolo_legislativo": demanda.protocolo_legislativo,
                    "demanda_titulo": demanda.titulo,
                    "operador": resumo_signatario(row.operador, self._papel_operador_para_etapa(row.etapa)),
                    "criado_em": row.criado_em,
                    "declaracao_gestor": DECLARACAO_GESTOR_POR_ETAPA.get(row.etapa, DECLARACAO_GESTOR_PROTOCOLO),
                    "unidade_sigla": (
                        row.unidade_administrativa.sigla if row.unidade_administrativa else None
                    ),
                }
            )
        return itens

    def obter_preview_validacao_gestor(
        self, validacao: AssinaturaValidacaoGestor, gestor
    ) -> dict[str, Any]:
        if validacao.status != AssinaturaValidacaoGestor.STATUS_PENDENTE:
            raise ValueError("Esta validação não está mais pendente.")
        if not self.usuario_pode_validar_assinatura_gestor(gestor, validacao):
            raise ValueError("Você não tem permissão para validar esta assinatura.")

        papel_gestor = PAPEL_GESTOR_POR_ETAPA.get(
            validacao.etapa, AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO
        )
        return {
            "validacao_id": validacao.pk,
            "demanda_id": validacao.demanda_id,
            "etapa": validacao.etapa,
            "etapa_display": dict(AssinaturaEletronica.ETAPA_CHOICES).get(
                validacao.etapa, validacao.etapa
            ),
            "hash_documento": validacao.hash_documento,
            "declaracao_gestor": DECLARACAO_GESTOR_POR_ETAPA.get(
                validacao.etapa, DECLARACAO_GESTOR_PROTOCOLO
            ),
            "signatario_operador": resumo_signatario(
                validacao.operador, self._papel_operador_para_etapa(validacao.etapa)
            ),
            "signatario_gestor": resumo_signatario(gestor, papel_gestor),
            "modo_assinatura": "gestor_apenas",
            "tramitacao_id": validacao.tramitacao_id,
            "payload": validacao.payload,
        }

    def registrar_validacao_gestor(
        self,
        validacao: AssinaturaValidacaoGestor,
        gestor,
        *,
        hash_documento: str,
        declaracao_gestor: str,
        request=None,
    ) -> AssinaturaEletronica:
        if validacao.status != AssinaturaValidacaoGestor.STATUS_PENDENTE:
            raise ValueError("Esta validação já foi concluída ou cancelada.")
        if not self.usuario_pode_validar_assinatura_gestor(gestor, validacao):
            raise ValueError("Você não tem permissão para validar esta assinatura.")

        hash_doc = (validacao.hash_documento or "").lower()
        informado = (hash_documento or "").strip().lower()
        if not informado or informado != hash_doc:
            raise ValueError(
                "O conteúdo da ação mudou desde a assinatura do operador. Solicite nova prévia."
            )

        decl_esperada = DECLARACAO_GESTOR_POR_ETAPA.get(
            validacao.etapa, DECLARACAO_GESTOR_PROTOCOLO
        )
        if (declaracao_gestor or "").strip().upper() != decl_esperada:
            raise ValueError(f'Declaração do gestor inválida. Use: "{decl_esperada}".')

        if validacao.operador_id == gestor.pk:
            raise ValueError(
                "O gestor responsável deve assinar em conta própria, diferente do operador."
            )

        papel_gestor = PAPEL_GESTOR_POR_ETAPA.get(
            validacao.etapa, AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO
        )
        if validacao.tramitacao_id:
            assinatura = self._criar_assinatura_tramitacao(
                validacao.demanda,
                validacao.tramitacao,
                gestor,
                etapa=validacao.etapa,
                papel=papel_gestor,
                hash_documento=validacao.hash_documento,
                declaracao=declaracao_gestor,
                request=request,
            )
        else:
            assinatura = self._criar_assinatura(
                validacao.demanda,
                gestor,
                etapa=validacao.etapa,
                papel=papel_gestor,
                hash_documento=validacao.hash_documento,
                declaracao=declaracao_gestor,
                request=request,
            )

        from django.db import transaction

        with transaction.atomic():
            validacao = AssinaturaValidacaoGestor.objects.select_for_update().get(
                pk=validacao.pk
            )
            if validacao.status != AssinaturaValidacaoGestor.STATUS_PENDENTE:
                raise ValueError("Esta validação já foi concluída ou cancelada.")

            AssinaturaEtapaExecutorService().executar_apos_validacao_gestor(
                validacao, request=request
            )

            agora = timezone.now()
            atualizados = AssinaturaValidacaoGestor.objects.filter(
                pk=validacao.pk,
                status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
            ).update(
                status=AssinaturaValidacaoGestor.STATUS_CONCLUIDA,
                gestor_validador=gestor,
                concluido_em=agora,
            )
            if atualizados != 1:
                raise ValueError(
                    "Não foi possível concluir a validação. Solicite nova prévia ao operador."
                )
            validacao.refresh_from_db()
        return assinatura

    def _etapa_totalmente_assinada(self, demanda: Demanda, etapa: str) -> bool:
        pares = set(demanda.assinaturas_eletronicas.values_list("etapa", "papel"))
        operador = self._papel_operador_para_etapa(etapa)
        gestor = PAPEL_GESTOR_POR_ETAPA.get(etapa)
        if not gestor:
            return (etapa, operador) in pares
        return (etapa, operador) in pares and (etapa, gestor) in pares

    def _limpar_anexos_oficio(self, demanda: Demanda) -> None:
        prefixo = f"oficio_demanda_{demanda.id}"
        demanda.anexos.filter(
            Q(descricao__icontains="Pré-visualização do ofício")
            | Q(descricao__icontains="Ofício copiloto")
            | Q(descricao__icontains="Ofício assinado eletronicamente")
            | Q(arquivo__icontains=prefixo)
        ).delete()

        pasta = Path(settings.MEDIA_ROOT) / "oficios"
        if pasta.is_dir():
            for caminho in pasta.glob(f"{prefixo}*.pdf"):
                try:
                    caminho.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Não foi possível remover arquivo órfão: %s", caminho)

    def _ler_preview_arquivo(self, demanda_id: int) -> bytes | None:
        caminho = _preview_pdf_path(demanda_id)
        if not caminho.is_file():
            return None
        return caminho.read_bytes()

    def _gravar_preview_arquivo(self, demanda_id: int, pdf_bytes: bytes) -> None:
        caminho = _preview_pdf_path(demanda_id)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(pdf_bytes)

    def _remover_preview_arquivo(self, demanda_id: int) -> None:
        try:
            _preview_pdf_path(demanda_id).unlink(missing_ok=True)
        except OSError:
            logger.warning("Não foi possível remover preview demanda %s", demanda_id)

    def _vincular_staging_a_tramitacao(
        self,
        staging_id: int | None,
        tramitacao: Tramitacao,
    ) -> None:
        if not staging_id:
            return
        from core.models import AnexoTramitacao

        staging = Tramitacao.objects.filter(pk=int(staging_id)).first()
        if not staging:
            return
        AnexoTramitacao.objects.filter(tramitacao=staging).update(tramitacao=tramitacao)
        staging.delete()

    def _criar_tramitacao_pendente_gestor(
        self,
        demanda: Demanda,
        operador,
        *,
        tipo: str,
        descricao: str,
        etapa: str,
        metadata_extra: dict[str, Any] | None = None,
        staging_id: int | None = None,
        unidade_destino_id: int | None = None,
    ) -> Tramitacao:
        from core.services.tramitacao_setor_service import UnidadeAdministrativaService

        meta = {
            "etapa": etapa,
            "aguardando_validacao_gestor": True,
            **(metadata_extra or {}),
        }
        unidade_origem = UnidadeAdministrativaService().unidade_principal_usuario(operador)
        tram = Tramitacao.objects.create(
            demanda=demanda,
            responsavel=operador,
            tipo=tipo,
            descricao=(descricao or "").strip(),
            unidade_origem=unidade_origem,
            unidade_destino_id=unidade_destino_id,
            metadata=meta,
        )
        self._vincular_staging_a_tramitacao(staging_id, tram)
        from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService

        tram.refresh_from_db()
        TramitacaoJanelaEdicaoService.abrir_janela(tram)
        return tram

    def _criar_tramitacao_staging_anexos(
        self,
        demanda: Demanda,
        usuario,
        arquivos: list | None,
    ) -> int | None:
        if not arquivos:
            return None
        from core.services.tramitacao_anexo_service import anexar_arquivos_tramitacao

        tram = Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="STAGING_ASSINATURA",
            descricao="Anexos aguardando validação do gestor",
            metadata={"staging": True},
        )
        anexar_arquivos_tramitacao(tram, arquivos, copiar=False)
        return tram.pk

    def _gravar_pending_acao(self, demanda_id: int, etapa: str, payload: dict) -> str:
        hash_doc = self.hash_canonical(payload)
        AssinaturaPendingAcao.objects.update_or_create(
            demanda_id=demanda_id,
            etapa=etapa,
            defaults={"payload": payload, "hash_documento": hash_doc},
        )
        self._remover_pending_arquivo_legado(demanda_id, etapa)
        return hash_doc

    def _ler_pending_acao(self, demanda_id: int, etapa: str) -> dict | None:
        row = (
            AssinaturaPendingAcao.objects.filter(demanda_id=demanda_id, etapa=etapa)
            .order_by("-criado_em")
            .first()
        )
        if row:
            return {"hash_documento": row.hash_documento, "payload": row.payload}

        caminho = _pending_acao_path(demanda_id, etapa)
        if not caminho.is_file():
            return None
        try:
            legacy = json.loads(caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if legacy:
            AssinaturaPendingAcao.objects.update_or_create(
                demanda_id=demanda_id,
                etapa=etapa,
                defaults={
                    "payload": legacy.get("payload") or {},
                    "hash_documento": legacy.get("hash_documento") or "",
                },
            )
            self._remover_pending_arquivo_legado(demanda_id, etapa)
        return legacy

    def _remover_pending_arquivo_legado(self, demanda_id: int, etapa: str) -> None:
        try:
            _pending_acao_path(demanda_id, etapa).unlink(missing_ok=True)
        except OSError:
            pass

    def _remover_pending_acao(self, demanda_id: int, etapa: str) -> None:
        AssinaturaPendingAcao.objects.filter(demanda_id=demanda_id, etapa=etapa).delete()
        self._remover_pending_arquivo_legado(demanda_id, etapa)

    def possui_assinatura_despacho_inicial(self, demanda: Demanda) -> bool:
        return self._etapa_totalmente_assinada(
            demanda, AssinaturaEletronica.ETAPA_DESPACHO_INICIAL
        )

    def liberar_assinaturas_despacho_inicial(self, demanda: Demanda) -> int:
        """Remove assinaturas de despacho inicial para permitir novo ciclo na fila do Protocolo."""
        count, _ = AssinaturaEletronica.objects.filter(
            demanda=demanda,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
        ).delete()
        self._remover_pending_acao(
            int(demanda.pk), AssinaturaEletronica.ETAPA_DESPACHO_INICIAL
        )
        AssinaturaValidacaoGestor.objects.filter(
            demanda=demanda,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
        ).delete()
        if count:
            logger.info(
                "Assinaturas DESPACHO_INICIAL liberadas demanda=%s count=%s",
                demanda.pk,
                count,
            )
        return count

    def liberar_assinaturas_conclusao_final(self, demanda: Demanda) -> int:
        """Remove assinaturas de conclusão final para permitir novo ciclo."""
        count, _ = AssinaturaEletronica.objects.filter(
            demanda=demanda,
            etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
        ).delete()
        self._remover_pending_acao(
            int(demanda.pk), AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL
        )
        AssinaturaValidacaoGestor.objects.filter(
            demanda=demanda,
            etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
        ).delete()
        if count:
            logger.info(
                "Assinaturas CONCLUSAO_FINAL liberadas demanda=%s count=%s",
                demanda.pk,
                count,
            )
        return count

    def invalidar_preview_envio(self, demanda_id: int) -> None:
        self._remover_preview_arquivo(demanda_id)

    def preparar_preview_envio(self, demanda: Demanda) -> dict[str, Any]:
        from core.services.indicacao_numeracao_service import anexo_pdf_indicacao
        from core.services.indicacao_service import demanda_eh_indicacao

        if demanda_eh_indicacao(demanda):
            anexo = anexo_pdf_indicacao(demanda)
            if not anexo or not anexo.arquivo:
                raise ValueError("Anexe o PDF da indicação antes de protocolar.")
            pdf_bytes = anexo.arquivo.read()
            if hasattr(anexo.arquivo, "seek"):
                anexo.arquivo.seek(0)
            hash_doc = self.hash_documento_pdf(pdf_bytes)
            self._gravar_preview_arquivo(int(demanda.pk), pdf_bytes)
            return {
                "hash_documento": hash_doc,
                "preview_pdf_disponivel": True,
                "declaracao_exigida": DECLARACAO_ENVIO,
                "origem_documento": "anexo_indicacao",
            }

        pdf_bytes = self.render_pdf_bytes(demanda)
        hash_doc = self.hash_documento_pdf(pdf_bytes)
        self._gravar_preview_arquivo(int(demanda.pk), pdf_bytes)
        return {
            "hash_documento": hash_doc,
            "preview_pdf_disponivel": True,
            "declaracao_exigida": DECLARACAO_ENVIO,
        }

    def obter_preview_pdf_bytes(self, demanda: Demanda) -> bytes | None:
        salvo = self._ler_preview_arquivo(int(demanda.pk))
        if salvo:
            return salvo
        pdf_bytes = self.render_pdf_bytes(demanda)
        self._gravar_preview_arquivo(int(demanda.pk), pdf_bytes)
        return pdf_bytes

    def preparar_assinatura_despacho_inicial(
        self,
        demanda: Demanda,
        *,
        secretaria_id: int,
        unidade_administrativa_id: int | None,
        protocolo_executivo: str,
        destinos: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "demanda_id": demanda.pk,
            "etapa": AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            "acao_executiva": ACAO_DESPACHO_INICIAL,
            "secretaria_id": int(secretaria_id),
            "unidade_administrativa_id": unidade_administrativa_id,
            "protocolo_executivo": protocolo_executivo,
            "protocolo_legislativo": demanda.protocolo_legislativo,
            "destinos": destinos or [{"secretaria_id": int(secretaria_id), "unidade_administrativa_id": unidade_administrativa_id}],
        }
        hash_doc = self._gravar_pending_acao(
            int(demanda.pk), AssinaturaEletronica.ETAPA_DESPACHO_INICIAL, payload
        )
        return {
            "hash_documento": hash_doc,
            "declaracao_operador": DECLARACAO_DESPACHO,
            "requer_gestor_protocolo": True,
            "requer_validacao_gestor": True,
        }

    def preparar_assinatura_conclusao_secretaria(
        self,
        demanda: Demanda,
        *,
        parecer_operacional: str,
    ) -> dict[str, Any]:
        texto = (parecer_operacional or "").strip()
        if len(texto) < 10:
            raise ValueError("Informe o parecer operacional (mínimo 10 caracteres).")
        payload = {
            "demanda_id": demanda.pk,
            "etapa": AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA,
            "acao_executiva": ACAO_CONCLUSAO_SECRETARIA,
            "parecer_operacional": texto,
            "unidade_administrativa_id": demanda.unidade_administrativa_id,
            "sinapse_orgao_id": demanda.sinapse_orgao_id,
        }
        hash_doc = self._gravar_pending_acao(
            int(demanda.pk), AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA, payload
        )
        return {
            "hash_documento": hash_doc,
            "declaracao_exigida": DECLARACAO_CONCLUSAO,
            "requer_validacao_gestor": True,
        }

    def preparar_assinatura_despacho_devolutiva(
        self,
        demanda: Demanda,
        *,
        parecer_resposta: str,
    ) -> dict[str, Any]:
        from django.utils.html import strip_tags

        if len(strip_tags(parecer_resposta or "").strip()) < 10:
            raise ValueError(
                "Informe a resposta de devolutiva ao vereador (mínimo 10 caracteres)."
            )
        if demanda.status == "AGUARDANDO_DEVOLUTIVA_PROTOCOLO":
            self._limpar_assinaturas_orfas_etapa(
                demanda, AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA
            )
        payload = {
            "demanda_id": demanda.pk,
            "etapa": AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
            "parecer_resposta": parecer_resposta.strip(),
            "protocolo_executivo": demanda.protocolo_executivo,
        }
        hash_doc = self._gravar_pending_acao(
            int(demanda.pk), AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA, payload
        )
        return {
            "hash_documento": hash_doc,
            "declaracao_operador": DECLARACAO_DEVOLUTIVA,
            "declaracao_gestor": DECLARACAO_GESTOR_PROTOCOLO,
            "requer_gestor_protocolo": True,
        }

    def preparar_assinatura_conclusao_final(
        self,
        demanda: Demanda,
        *,
        parecer_resposta: str,
        historico_tecnico: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from core.services.operacional_estado_service import OperacionalEstadoService

        texto = (parecer_resposta or "").strip()
        if len(texto) < 10:
            raise ValueError(
                "Informe o parecer de conclusão final (mínimo 10 caracteres)."
            )
        historico = historico_tecnico or OperacionalEstadoService().compilar_historico_tecnico(
            demanda
        )
        if not historico.get("pronto_conclusao_final"):
            raise ValueError(
                "Histórico técnico incompleto — aguarde as conclusões das secretarias."
            )
        if demanda.status == "AGUARDANDO_DEVOLUTIVA_PROTOCOLO":
            self._limpar_assinaturas_orfas_etapa(
                demanda, AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL
            )
        payload = {
            "demanda_id": demanda.pk,
            "etapa": AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
            "acao_executiva": ACAO_CONCLUSAO_FINAL,
            "parecer_resposta": texto,
            "protocolo_executivo": demanda.protocolo_executivo,
            "protocolo_legislativo": demanda.protocolo_legislativo,
            "historico_tecnico": historico,
        }
        hash_doc = self._gravar_pending_acao(
            int(demanda.pk), AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL, payload
        )
        return {
            "hash_documento": hash_doc,
            "declaracao_operador": DECLARACAO_CONCLUSAO_FINAL,
            "declaracao_gestor": DECLARACAO_GESTOR_PROTOCOLO,
            "requer_gestor_protocolo": True,
            "requer_validacao_gestor": True,
            "historico_tecnico": historico,
        }

    def _validar_hash_pending(
        self, demanda_id: int, etapa: str, hash_informado: str
    ) -> dict:
        pending = self._ler_pending_acao(demanda_id, etapa)
        if not pending:
            raise ValueError(
                "Prévia de assinatura expirada ou ausente. Gere a prévia novamente antes de confirmar."
            )
        hash_doc = (pending.get("hash_documento") or "").lower()
        informado = (hash_informado or "").strip().lower()
        if not informado or informado != hash_doc:
            raise ValueError(
                "O conteúdo da ação mudou desde a prévia. Gere a prévia e assine novamente."
            )
        return pending

    def _criar_assinatura(
        self,
        demanda: Demanda,
        usuario,
        *,
        etapa: str,
        papel: str,
        hash_documento: str,
        declaracao: str,
        request=None,
    ) -> AssinaturaEletronica:
        existente = AssinaturaEletronica.objects.filter(
            demanda=demanda, etapa=etapa, papel=papel, tramitacao__isnull=True
        ).first()
        if existente:
            if demanda.status in ("DEVOLVIDO_VEREADOR", "FINALIZADO"):
                raise ValueError(
                    f"Assinatura já registrada para esta etapa ({etapa}/{papel})."
                )
            if (existente.hash_documento or "").lower() != (hash_documento or "").lower():
                raise ValueError(
                    "Assinatura pendente com conteúdo diferente. Gere a prévia novamente."
                )
            if existente.usuario_id != usuario.pk:
                raise ValueError(
                    f"Assinatura já registrada por outro usuário ({etapa}/{papel})."
                )
            return existente

        decl = (declaracao or "").strip().upper()
        agora = timezone.now()
        pepper = (settings.SECRET_KEY or "")[:32]
        material = f"{hash_documento}|{usuario.pk}|{demanda.pk}|{etapa}|{papel}|{agora.isoformat()}|{pepper}"
        hash_assinatura = hashlib.sha256(material.encode("utf-8")).hexdigest()
        codigo = secrets.token_hex(16)

        assinatura = AssinaturaEletronica.objects.create(
            demanda=demanda,
            usuario=usuario,
            etapa=etapa,
            papel=papel,
            hash_documento=hash_documento,
            hash_assinatura=hash_assinatura,
            codigo_validacao=codigo,
            ip_origem=_client_ip(request),
            user_agent=_client_user_agent(request),
            declaracao=decl,
        )
        logger.info(
            "Assinatura etapa=%s papel=%s demanda=%s usuario=%s codigo=%s",
            etapa,
            papel,
            demanda.pk,
            usuario.pk,
            codigo[:8],
        )
        return assinatura

    def hash_documento_operacao_scatter(
        self,
        demanda: Demanda,
        tramitacao,
        *,
        acao: str,
    ) -> str:
        meta = tramitacao.metadata if isinstance(tramitacao.metadata, dict) else {}
        payload = {
            "demanda_id": demanda.pk,
            "tramitacao_id": tramitacao.pk,
            "acao": str(acao or meta.get("acao_no") or "").upper(),
            "no_id": meta.get("no_id"),
            "observacao": (meta.get("observacao") or tramitacao.descricao or "").strip(),
            "destinos": meta.get("destinos") or [],
        }
        return self.hash_canonical(payload)

    def parse_assinatura_scatter_request(self, data: dict[str, Any], acao: str) -> dict[str, Any]:
        acao_norm = str(acao or "").upper()
        obrigatoria = acao_norm in ACOES_SCATTER_ASSINATURA_OBRIGATORIA
        raw = _scalar_request_value(data.get("assinar_eletronicamente"))
        if obrigatoria:
            assinar = True
        elif not raw:
            assinar = False
        else:
            assinar = raw.lower() in ("1", "true", "yes", "sim", "on")

        decl = _scalar_request_value(data.get("declaracao")).upper()
        if assinar and not decl:
            if acao_norm == "DESPACHAR":
                decl = DECLARACAO_DESPACHO
            else:
                decl = DECLARACAO_ENCERRAMENTO_OPERACIONAL
        return {"assinar": assinar, "declaracao": decl, "obrigatoria": obrigatoria, "acao": acao_norm}

    def validar_assinatura_scatter_contexto(self, ctx: dict[str, Any]) -> None:
        if ctx.get("obrigatoria") and not ctx.get("assinar"):
            rotulo = ctx.get("acao") or "esta operação"
            raise ValueError(
                f"Assinatura eletrônica obrigatória para {rotulo.replace('_', ' ').lower()}."
            )
        if not ctx.get("assinar"):
            return
        decl = ctx.get("declaracao") or ""
        acao = ctx.get("acao") or ""
        if acao == "DESPACHAR":
            if decl != DECLARACAO_DESPACHO:
                raise ValueError(f'Declaração inválida. Use: "{DECLARACAO_DESPACHO}".')
        elif decl != DECLARACAO_ENCERRAMENTO_OPERACIONAL:
            raise ValueError(
                f'Declaração inválida. Use: "{DECLARACAO_ENCERRAMENTO_OPERACIONAL}".'
            )

    def _usuario_pode_assinar_operacao_scatter(self, usuario, tramitacao) -> bool:
        from core.models import NoOperacional
        from core.services import operacional_permissions as perm

        meta = tramitacao.metadata if isinstance(tramitacao.metadata, dict) else {}
        no_id = meta.get("no_id")
        if no_id in (None, ""):
            return False
        no = NoOperacional.objects.filter(pk=int(no_id)).first()
        if not no:
            return False
        return perm.usuario_pode_operar_no_scatter(usuario, no)

    def registrar_assinatura_operacao_scatter(
        self,
        demanda: Demanda,
        tramitacao,
        usuario,
        *,
        acao: str,
        declaracao: str,
        contexto_extra: dict[str, Any] | None = None,
        request=None,
    ) -> AssinaturaEletronica:
        if not self._usuario_pode_assinar_operacao_scatter(usuario, tramitacao):
            raise ValueError(
                "Apenas o gestor ou a secretaria responsável pelo nó pode assinar esta operação."
            )
        ctx = {
            "assinar": True,
            "declaracao": (declaracao or "").strip().upper(),
            "acao": str(acao or "").upper(),
            "obrigatoria": str(acao or "").upper() in ACOES_SCATTER_ASSINATURA_OBRIGATORIA,
        }
        self.validar_assinatura_scatter_contexto(ctx)

        hash_doc = self.hash_documento_operacao_scatter(
            demanda, tramitacao, acao=ctx["acao"]
        )
        assinatura = self._criar_assinatura_tramitacao(
            demanda,
            tramitacao,
            usuario,
            etapa=AssinaturaEletronica.ETAPA_OPERACAO_SCATTER,
            papel=AssinaturaEletronica.PAPEL_CHEFIA_SETOR,
            hash_documento=hash_doc,
            declaracao=ctx["declaracao"],
            request=request,
        )
        if ctx["acao"] in ACOES_SCATTER_ASSINATURA_OBRIGATORIA:
            meta = tramitacao.metadata if isinstance(tramitacao.metadata, dict) else {}
            from core.models_no_operacional import NoOperacional

            no_id = meta.get("no_id")
            unidade_id = None
            orgao_id = None
            if no_id not in (None, ""):
                no = NoOperacional.objects.filter(pk=int(no_id)).first()
                if no:
                    unidade_id = no.unidade_administrativa_id
                    orgao_id = no.sinapse_orgao_id
            payload = {
                "demanda_id": demanda.pk,
                "tramitacao_id": tramitacao.pk,
                "acao": ctx["acao"],
                "no_id": no_id,
                "observacao": meta.get("observacao") or "",
            }
            if ctx["acao"] == "ENCERRAR":
                payload["acao_executiva"] = ACAO_SCATTER_ENCERRAR
            elif ctx["acao"] == "DESPACHAR_ENCERRAR":
                payload["acao_executiva"] = ACAO_SCATTER_DESPACHAR_ENCERRAR
            if ctx.get("resultado_operacional"):
                payload["resultado_operacional"] = ctx["resultado_operacional"]
            if contexto_extra:
                if contexto_extra.get("resultado_operacional"):
                    payload["resultado_operacional"] = contexto_extra["resultado_operacional"]
            self._criar_validacao_gestor_pendente(
                demanda,
                usuario,
                etapa=AssinaturaEletronica.ETAPA_OPERACAO_SCATTER,
                hash_documento=hash_doc,
                payload=payload,
                tramitacao=tramitacao,
                unidade_administrativa_id=unidade_id,
                sinapse_orgao_id=orgao_id,
            )
        return assinatura

    def _criar_assinatura_tramitacao(
        self,
        demanda: Demanda,
        tramitacao,
        usuario,
        *,
        etapa: str,
        papel: str,
        hash_documento: str,
        declaracao: str,
        request=None,
    ) -> AssinaturaEletronica:
        existente = AssinaturaEletronica.objects.filter(
            tramitacao=tramitacao, papel=papel
        ).first()
        if existente:
            if (existente.hash_documento or "").lower() != (hash_documento or "").lower():
                raise ValueError(
                    "Assinatura já registrada para esta tramitação com conteúdo diferente."
                )
            if existente.usuario_id != usuario.pk:
                raise ValueError("Assinatura já registrada por outro usuário nesta tramitação.")
            return existente

        decl = (declaracao or "").strip().upper()
        agora = timezone.now()
        pepper = (settings.SECRET_KEY or "")[:32]
        material = (
            f"{hash_documento}|{usuario.pk}|{demanda.pk}|{tramitacao.pk}|"
            f"{etapa}|{papel}|{agora.isoformat()}|{pepper}"
        )
        hash_assinatura = hashlib.sha256(material.encode("utf-8")).hexdigest()
        codigo = secrets.token_hex(16)

        assinatura = AssinaturaEletronica.objects.create(
            demanda=demanda,
            tramitacao=tramitacao,
            usuario=usuario,
            etapa=etapa,
            papel=papel,
            hash_documento=hash_documento,
            hash_assinatura=hash_assinatura,
            codigo_validacao=codigo,
            ip_origem=_client_ip(request),
            user_agent=_client_user_agent(request),
            declaracao=decl,
        )
        logger.info(
            "Assinatura scatter tram=%s demanda=%s usuario=%s codigo=%s",
            tramitacao.pk,
            demanda.pk,
            usuario.pk,
            codigo[:8],
        )
        return assinatura

    def registrar_assinatura(
        self,
        demanda: Demanda,
        usuario,
        *,
        hash_documento_informado: str,
        declaracao: str,
        request=None,
    ) -> AssinaturaEletronica:
        if self._assinatura_existe(demanda, AssinaturaEletronica.ETAPA_ENVIO_OFICIO, AssinaturaEletronica.PAPEL_OPERADOR):
            raise ValueError("Esta demanda já possui assinatura eletrônica de envio registrada.")

        decl = (declaracao or "").strip().upper()
        if decl != DECLARACAO_ENVIO:
            raise ValueError(f'Declaração inválida. Informe exatamente: "{DECLARACAO_ENVIO}".')

        from core.services.indicacao_service import demanda_eh_indicacao

        if demanda_eh_indicacao(demanda):
            if getattr(usuario, "perfil", None) not in ("CAMARA", "GESTOR"):
                raise ValueError("Apenas usuário da Câmara (ou gestor) pode assinar o protocolo da indicação.")
            if demanda.autor_id != usuario.pk and getattr(usuario, "perfil", None) != "GESTOR":
                raise ValueError("Apenas o usuário da Câmara autor da indicação (ou gestor) pode assinar.")
        elif demanda.autor_id != usuario.pk and getattr(usuario, "perfil", None) not in ("GESTOR",):
            raise ValueError("Apenas o autor do ofício (ou gestor) pode assinar o envio.")

        pdf_preview = self._ler_preview_arquivo(int(demanda.pk))
        if pdf_preview is not None:
            pdf_bytes = pdf_preview
        else:
            logger.warning(
                "Preview em disco ausente para demanda %s; regenerando PDF para assinatura.",
                demanda.pk,
            )
            if demanda_eh_indicacao(demanda):
                from core.services.indicacao_numeracao_service import anexo_pdf_indicacao

                anexo = anexo_pdf_indicacao(demanda)
                if not anexo or not anexo.arquivo:
                    raise ValueError("Anexo PDF da indicação não encontrado.")
                pdf_bytes = anexo.arquivo.read()
                if hasattr(anexo.arquivo, "seek"):
                    anexo.arquivo.seek(0)
            else:
                pdf_bytes = self.render_pdf_bytes(demanda)
        hash_doc = self.hash_documento_pdf(pdf_bytes)
        informado = (hash_documento_informado or "").strip().lower()
        if informado and informado != hash_doc:
            raise ValueError(
                "O conteúdo do ofício mudou desde a pré-visualização. "
                "Feche o diálogo, abra novamente a pré-visualização e tente enviar."
            )

        self._remover_preview_arquivo(int(demanda.pk))

        if not demanda_eh_indicacao(demanda):
            self._limpar_anexos_oficio(demanda)
            pasta = Path(settings.MEDIA_ROOT) / "oficios"
            pasta.mkdir(parents=True, exist_ok=True)
            nome_final = f"oficio_demanda_{demanda.id}_assinado.pdf"
            caminho_final = pasta / nome_final
            caminho_final.write_bytes(pdf_bytes)
            OficioService.anexar_pdf_a_demandas(
                [demanda],
                str(caminho_final.resolve()),
                descricao="Ofício assinado eletronicamente (SGDL)",
            )

        return self._criar_assinatura(
            demanda,
            usuario,
            etapa=AssinaturaEletronica.ETAPA_ENVIO_OFICIO,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento=hash_doc,
            declaracao=decl,
            request=request,
        )

    def registrar_assinaturas_despacho_inicial(
        self,
        demanda: Demanda,
        operador,
        *,
        hash_documento: str,
        declaracao_operador: str,
        gestor_usuario_id: int | None = None,
        declaracao_gestor: str | None = None,
        contexto_operacao: dict[str, Any] | None = None,
        request=None,
    ) -> list[AssinaturaEletronica]:
        """Despacho inicial — operador assina; gestor valida antes da execução."""
        pending = self._validar_hash_pending(
            int(demanda.pk), AssinaturaEletronica.ETAPA_DESPACHO_INICIAL, hash_documento
        )
        hash_doc = pending["hash_documento"]
        payload = dict(pending.get("payload") or {})
        if contexto_operacao:
            payload.update(contexto_operacao)
        payload["acao_executiva"] = ACAO_DESPACHO_INICIAL

        if (declaracao_operador or "").strip().upper() != DECLARACAO_DESPACHO:
            raise ValueError(f'Declaração do operador inválida. Use: "{DECLARACAO_DESPACHO}".')

        texto_despacho = str(payload.get("texto_despacho") or "").strip()
        tram_pendente = self._criar_tramitacao_pendente_gestor(
            demanda,
            operador,
            tipo="DESPACHO",
            descricao=texto_despacho,
            etapa="DESPACHO_PROTOCOLO",
            metadata_extra={
                "protocolo_executivo": payload.get("protocolo_executivo"),
                "total_pernas": len(payload.get("destinos") or []),
            },
            staging_id=payload.get("tramitacao_staging_id"),
            unidade_destino_id=payload.get("unidade_administrativa_id"),
        )

        assinatura = self._criar_assinatura(
            demanda,
            operador,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento=hash_doc,
            declaracao=declaracao_operador,
            request=request,
        )
        assinatura.tramitacao = tram_pendente
        assinatura.save(update_fields=["tramitacao"])
        self._criar_validacao_gestor_pendente(
            demanda,
            operador,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            hash_documento=hash_doc,
            payload=payload,
            tramitacao=tram_pendente,
            unidade_administrativa_id=payload.get("unidade_administrativa_id"),
            sinapse_orgao_id=PROTOCOLO_ORGAO_ID,
        )
        self._remover_pending_acao(int(demanda.pk), AssinaturaEletronica.ETAPA_DESPACHO_INICIAL)
        return [assinatura]

    def registrar_assinatura_conclusao_secretaria(
        self,
        demanda: Demanda,
        usuario,
        *,
        hash_documento: str,
        declaracao: str,
        contexto_operacao: dict[str, Any] | None = None,
        request=None,
    ) -> AssinaturaEletronica:
        if not self._usuario_eh_chefia_conclusao(usuario, demanda):
            raise ValueError(
                "Apenas a chefia responsável pelo setor da demanda pode assinar a conclusão."
            )
        pending = self._validar_hash_pending(
            int(demanda.pk), AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA, hash_documento
        )
        if (declaracao or "").strip().upper() != DECLARACAO_CONCLUSAO:
            raise ValueError(f'Declaração inválida. Use: "{DECLARACAO_CONCLUSAO}".')

        assinatura = self._criar_assinatura(
            demanda,
            usuario,
            etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA,
            papel=AssinaturaEletronica.PAPEL_CHEFIA_SETOR,
            hash_documento=pending["hash_documento"],
            declaracao=declaracao,
            request=request,
        )
        payload = dict(pending.get("payload") or {})
        if contexto_operacao:
            payload.update(contexto_operacao)
        if not payload.get("acao_executiva"):
            payload["acao_executiva"] = ACAO_CONCLUSAO_SECRETARIA
        self._criar_validacao_gestor_pendente(
            demanda,
            usuario,
            etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA,
            hash_documento=pending["hash_documento"],
            payload=payload,
            unidade_administrativa_id=payload.get("unidade_administrativa_id")
            or demanda.unidade_administrativa_id,
            sinapse_orgao_id=payload.get("sinapse_orgao_id") or demanda.sinapse_orgao_id,
        )
        self._remover_pending_acao(int(demanda.pk), AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA)
        return assinatura

    def registrar_assinaturas_despacho_devolutiva(
        self,
        demanda: Demanda,
        operador,
        *,
        hash_documento: str,
        declaracao_operador: str | None = None,
        gestor_usuario_id: int | None = None,
        declaracao_gestor: str | None = None,
        assinatura_apenas_gestor: bool = False,
        request=None,
    ) -> list[AssinaturaEletronica]:
        pending = self._validar_hash_pending(
            int(demanda.pk), AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA, hash_documento
        )
        hash_doc = pending["hash_documento"]
        assinaturas: list[AssinaturaEletronica] = []

        if assinatura_apenas_gestor:
            if (declaracao_gestor or "").strip().upper() != DECLARACAO_GESTOR_PROTOCOLO:
                raise ValueError(
                    f'Declaração do gestor inválida. Use: "{DECLARACAO_GESTOR_PROTOCOLO}".'
                )
            if not self._usuario_eh_gestor_protocolo_sgac(operador):
                raise ValueError("Apenas o gestor setorial do SGAC pode assinar nesta etapa.")
            assinaturas.append(
                self._criar_assinatura(
                    demanda,
                    operador,
                    etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
                    papel=AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO,
                    hash_documento=hash_doc,
                    declaracao=declaracao_gestor,
                    request=request,
                )
            )
        else:
            if (declaracao_operador or "").strip().upper() != DECLARACAO_DEVOLUTIVA:
                raise ValueError(
                    f'Declaração do operador inválida. Use: "{DECLARACAO_DEVOLUTIVA}".'
                )
            if (declaracao_gestor or "").strip().upper() != DECLARACAO_GESTOR_PROTOCOLO:
                raise ValueError(
                    f'Declaração do gestor inválida. Use: "{DECLARACAO_GESTOR_PROTOCOLO}".'
                )
            try:
                gestor = Usuario.objects.get(pk=int(gestor_usuario_id))
            except (Usuario.DoesNotExist, TypeError, ValueError):
                raise ValueError("Gestor do protocolo inválido.")
            if not self._usuario_eh_gestor_protocolo_sgac(gestor):
                raise ValueError("O gestor indicado não é gestor setorial do SGAC.")
            if gestor.pk == operador.pk:
                raise ValueError("O gestor do protocolo deve ser diferente do operador.")
            assinaturas = [
                self._criar_assinatura(
                    demanda,
                    operador,
                    etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
                    papel=AssinaturaEletronica.PAPEL_OPERADOR,
                    hash_documento=hash_doc,
                    declaracao=declaracao_operador,
                    request=request,
                ),
                self._criar_assinatura(
                    demanda,
                    gestor,
                    etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
                    papel=AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO,
                    hash_documento=hash_doc,
                    declaracao=declaracao_gestor,
                    request=request,
                ),
            ]

        self._remover_pending_acao(int(demanda.pk), AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA)
        return assinaturas

    def registrar_assinaturas_conclusao_final(
        self,
        demanda: Demanda,
        operador,
        *,
        hash_documento: str,
        declaracao_operador: str | None = None,
        gestor_usuario_id: int | None = None,
        declaracao_gestor: str | None = None,
        assinatura_apenas_gestor: bool = False,
        validacao_id: int | None = None,
        contexto_operacao: dict[str, Any] | None = None,
        request=None,
    ) -> list[AssinaturaEletronica]:
        if assinatura_apenas_gestor and validacao_id:
            try:
                validacao = AssinaturaValidacaoGestor.objects.get(
                    pk=int(validacao_id),
                    demanda=demanda,
                    etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
                    status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
                )
            except (AssinaturaValidacaoGestor.DoesNotExist, TypeError, ValueError):
                raise ValueError("Validação pendente inválida.")
            assinatura = self.registrar_validacao_gestor(
                validacao,
                operador,
                hash_documento=hash_documento,
                declaracao_gestor=declaracao_gestor or "",
                request=request,
            )
            return [assinatura]

        pending = self._validar_hash_pending(
            int(demanda.pk), AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL, hash_documento
        )
        hash_doc = pending["hash_documento"]
        payload = dict(pending.get("payload") or {})
        if contexto_operacao:
            payload.update(contexto_operacao)
        payload["acao_executiva"] = ACAO_CONCLUSAO_FINAL

        if (declaracao_operador or "").strip().upper() != DECLARACAO_CONCLUSAO_FINAL:
            raise ValueError(
                f'Declaração do operador inválida. Use: "{DECLARACAO_CONCLUSAO_FINAL}".'
            )

        texto = str(payload.get("parecer_resposta") or "").strip()
        tram_pendente = self._criar_tramitacao_pendente_gestor(
            demanda,
            operador,
            tipo="CONCLUSAO_FINAL",
            descricao=f"Conclusão final do Protocolo.\nParecer:\n{texto}",
            etapa="CONCLUSAO_FINAL",
            metadata_extra={
                "parecer": texto,
                "historico_tecnico": payload.get("historico_tecnico"),
            },
            staging_id=payload.get("tramitacao_staging_id"),
        )

        assinatura = self._criar_assinatura(
            demanda,
            operador,
            etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento=hash_doc,
            declaracao=declaracao_operador,
            request=request,
        )
        assinatura.tramitacao = tram_pendente
        assinatura.save(update_fields=["tramitacao"])
        self._criar_validacao_gestor_pendente(
            demanda,
            operador,
            etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
            hash_documento=hash_doc,
            payload=payload,
            tramitacao=tram_pendente,
            sinapse_orgao_id=PROTOCOLO_ORGAO_ID,
        )
        self._remover_pending_acao(int(demanda.pk), AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL)
        return [assinatura]

    def _usuario_eh_gestor_protocolo(self, usuario) -> bool:
        """Legado — perfil Protocolo ou Gestor vinculado ao órgão 12."""
        perfil = getattr(usuario, "perfil", None)
        if perfil not in ("PROTOCOLO", "GESTOR") and not getattr(usuario, "is_staff", False):
            return False
        orgao = getattr(usuario, "sinapse_orgao_id", None)
        return orgao is None or int(orgao) == PROTOCOLO_ORGAO_ID

    def _usuario_eh_gestor_protocolo_sgac(self, usuario) -> bool:
        """Gestor setorial responsável pela UA SGAC (754) ou Gestor Geral."""
        from core.services.gestor_escopo import gestor_admin_pleno
        from core.services.usuario_vinculo_service import (
            PROTOCOLO_UNIDADE_PK,
            UsuarioVinculoService,
        )

        if getattr(usuario, "perfil", None) != "GESTOR":
            return False
        if gestor_admin_pleno(usuario):
            return True
        ids = UsuarioVinculoService().ids_unidades_ativas(usuario)
        if PROTOCOLO_UNIDADE_PK in ids:
            return True
        return UnidadeAdministrativaResponsavel.objects.filter(
            unidade_id=PROTOCOLO_UNIDADE_PK,
            usuario=usuario,
            ativo=True,
        ).exists()

    def usuario_pode_assinar_conclusao(self, usuario, demanda: Demanda) -> bool:
        return self._usuario_eh_chefia_conclusao(usuario, demanda)

    def _usuario_eh_chefia_conclusao(self, usuario, demanda: Demanda) -> bool:
        from core.models_unidade_administrativa import UnidadeAdministrativa
        from core.services.gestor_escopo import (
            TIPO_GERAL,
            gestor_pode_gerir_unidade_no_escopo,
            orgaos_escopo_gestor,
            tipo_gestor,
        )

        perfil = getattr(usuario, "perfil", None)
        if perfil == "SECRETARIA":
            if not usuario.sinapse_orgao_id or demanda.sinapse_orgao_id != usuario.sinapse_orgao_id:
                return False
            if demanda.unidade_administrativa_id:
                return UnidadeAdministrativaResponsavel.objects.filter(
                    unidade_id=demanda.unidade_administrativa_id,
                    usuario=usuario,
                    ativo=True,
                ).exists()
            return True

        if perfil == "GESTOR":
            if tipo_gestor(usuario) == TIPO_GERAL:
                return True
            if demanda.unidade_administrativa_id:
                ua = UnidadeAdministrativa.objects.filter(
                    pk=demanda.unidade_administrativa_id
                ).first()
                return gestor_pode_gerir_unidade_no_escopo(usuario, ua)
            orgao_demanda = demanda.sinapse_orgao_id
            if orgao_demanda is None:
                return False
            return int(orgao_demanda) in orgaos_escopo_gestor(usuario)

        return False

    def listar_gestores_protocolo(self) -> list[dict[str, Any]]:
        from core.services.gestor_escopo import gestor_admin_pleno
        from core.services.usuario_vinculo_service import PROTOCOLO_UNIDADE_PK

        resp_ids = set(
            UnidadeAdministrativaResponsavel.objects.filter(
                unidade_id=PROTOCOLO_UNIDADE_PK,
                ativo=True,
            ).values_list("usuario_id", flat=True)
        )
        qs = (
            Usuario.objects.filter(is_active=True, perfil="GESTOR")
            .filter(
                Q(pk__in=resp_ids)
                | Q(
                    unidades_responsaveis__unidade_id=PROTOCOLO_UNIDADE_PK,
                    unidades_responsaveis__ativo=True,
                )
            )
            .distinct()
        )
        gestores = []
        for u in qs.order_by("first_name", "username"):
            if not self._usuario_eh_gestor_protocolo_sgac(u) and not gestor_admin_pleno(u):
                continue
            gestores.append(
                {
                    "id": u.pk,
                    "nome": u.get_full_name() or u.username,
                    "username": u.username,
                    "perfil": u.perfil,
                    "cargo": cargo_signatario(u, AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO),
                }
            )
        return gestores

    def resumo_signatario(self, usuario, papel: str | None = None) -> dict[str, Any]:
        return resumo_signatario(usuario, papel)

    def modo_assinatura_protocolo(self, usuario, *, contexto: str | None = None) -> str:
        """operador_apenas | gestor_apenas | dual_protocolo (somente devolutiva legada)."""
        from core.services.gestor_escopo import gestor_admin_pleno

        if contexto == "devolutiva":
            perfil = getattr(usuario, "perfil", None)
            if perfil == "PROTOCOLO":
                return "dual_protocolo"
            if perfil == "GESTOR":
                if gestor_admin_pleno(usuario):
                    return "dual_protocolo"
                if self._usuario_eh_gestor_protocolo_sgac(usuario):
                    return "gestor_apenas"
            return "dual_protocolo"

        perfil = getattr(usuario, "perfil", None)
        if perfil == "GESTOR" and self._usuario_eh_gestor_protocolo_sgac(usuario):
            return "gestor_apenas"
        if perfil == "GESTOR" and gestor_admin_pleno(usuario):
            return "gestor_apenas"
        return "operador_apenas"

    def validar_codigo(self, codigo: str) -> dict[str, Any] | None:
        cod = (codigo or "").strip().lower()
        if not cod:
            return None
        try:
            assinatura = AssinaturaEletronica.objects.select_related(
                "demanda", "demanda__autor", "usuario"
            ).get(codigo_validacao__iexact=cod)
        except AssinaturaEletronica.DoesNotExist:
            return None

        demanda = assinatura.demanda
        autor = demanda.autor
        signatario = assinatura.usuario
        base_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
        return {
            "valido": True,
            "codigo_validacao": assinatura.codigo_validacao,
            "hash_documento": assinatura.hash_documento,
            "hash_assinatura": assinatura.hash_assinatura,
            "assinado_em": assinatura.assinado_em,
            "declaracao": assinatura.declaracao,
            "etapa": assinatura.etapa,
            "etapa_display": assinatura.get_etapa_display(),
            "papel": assinatura.papel,
            "papel_display": assinatura.get_papel_display(),
            "protocolo_legislativo": demanda.protocolo_legislativo,
            "protocolo_executivo": demanda.protocolo_executivo,
            "demanda_id": demanda.pk,
            "demanda_titulo": demanda.titulo,
            "vereador": autor.get_full_name() or autor.username,
            "signatario": signatario.get_full_name() or signatario.username,
            "cargo": cargo_signatario(signatario, assinatura.papel),
            "status_demanda": demanda.status,
            "url_validacao": f"{base_url}/validar-assinatura/{assinatura.codigo_validacao}",
        }

    def url_qr_validacao(self, codigo: str) -> str:
        base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
        return f"{base}/validar-assinatura/{codigo}"

    def gerar_qr_png_bytes(self, codigo: str) -> bytes:
        import qrcode
        from io import BytesIO

        img = qrcode.make(self.url_qr_validacao(codigo))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def serializar_assinaturas_demanda(self, demanda: Demanda) -> list[dict[str, Any]]:
        return [
            {
                "etapa": a.etapa,
                "etapa_display": a.get_etapa_display(),
                "papel": a.papel,
                "papel_display": a.get_papel_display(),
                "codigo_validacao": a.codigo_validacao,
                "declaracao": a.declaracao,
                "assinado_em": a.assinado_em,
                "signatario": a.usuario.get_full_name() or a.usuario.username,
                "cargo": cargo_signatario(a.usuario, a.papel),
                "tramitacao_id": a.tramitacao_id,
            }
            for a in demanda.assinaturas_eletronicas.select_related("usuario").order_by(
                "assinado_em"
            )
        ]

    def resumo_assinaturas_demanda(self, demanda: Demanda) -> dict[str, bool]:
        """Flags de conclusão por etapa (B7 — feedback Protocolo/Secretaria)."""
        pares = set(
            demanda.assinaturas_eletronicas.values_list("etapa", "papel")
        )

        def etapa_completa(etapa: str, papeis: tuple[str, ...]) -> bool:
            return all((etapa, papel) in pares for papel in papeis)

        def pendente_gestor(etapa: str) -> bool:
            return AssinaturaValidacaoGestor.objects.filter(
                demanda=demanda,
                etapa=etapa,
                status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
            ).exists()

        return {
            "envio_oficio_assinado": (
                AssinaturaEletronica.ETAPA_ENVIO_OFICIO,
                AssinaturaEletronica.PAPEL_OPERADOR,
            ) in pares,
            "despacho_inicial_assinado": etapa_completa(
                AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
                (
                    AssinaturaEletronica.PAPEL_OPERADOR,
                    AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO,
                ),
            ),
            "despacho_inicial_pendente_gestor": pendente_gestor(
                AssinaturaEletronica.ETAPA_DESPACHO_INICIAL
            ),
            "conclusao_secretaria_assinada": etapa_completa(
                AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA,
                (
                    AssinaturaEletronica.PAPEL_CHEFIA_SETOR,
                    AssinaturaEletronica.PAPEL_GESTOR_SETOR,
                ),
            ),
            "conclusao_secretaria_pendente_gestor": pendente_gestor(
                AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA
            ),
            "operacao_scatter_assinada": etapa_completa(
                AssinaturaEletronica.ETAPA_OPERACAO_SCATTER,
                (
                    AssinaturaEletronica.PAPEL_CHEFIA_SETOR,
                    AssinaturaEletronica.PAPEL_GESTOR_SETOR,
                ),
            ),
            "operacao_scatter_pendente_gestor": pendente_gestor(
                AssinaturaEletronica.ETAPA_OPERACAO_SCATTER
            ),
            "devolutiva_assinada": etapa_completa(
                AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
                (
                    AssinaturaEletronica.PAPEL_OPERADOR,
                    AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO,
                ),
            ),
            "conclusao_final_assinada": etapa_completa(
                AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
                (
                    AssinaturaEletronica.PAPEL_OPERADOR,
                    AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO,
                ),
            ),
            "conclusao_final_pendente_gestor": pendente_gestor(
                AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL
            ),
        }
