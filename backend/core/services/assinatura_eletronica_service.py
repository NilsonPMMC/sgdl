"""Registro de assinatura eletrônica nativa (envio oficial do ofício)."""

from __future__ import annotations

import hashlib
import logging
import secrets
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from core.models import Demanda
from core.models_assinatura_eletronica import AssinaturaEletronica
from core.services.oficio_service import OficioService

logger = logging.getLogger(__name__)

DECLARACAO_ENVIO = "ASSINO E ENVIO"


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


def _preview_pdf_path(demanda_id: int) -> Path:
    """Arquivo compartilhado entre workers (evita LocMemCache por processo)."""
    return Path(settings.MEDIA_ROOT) / "oficios" / f"oficio_demanda_{demanda_id}_preview.pdf"


class AssinaturaEletronicaService:
    def render_pdf_bytes(self, demanda: Demanda) -> bytes:
        return OficioService().render_pdf_bytes(demanda)

    def hash_documento_pdf(self, pdf_bytes: bytes) -> str:
        return hashlib.sha256(pdf_bytes).hexdigest()

    def _limpar_anexos_oficio(self, demanda: Demanda) -> None:
        """Remove PDFs de ofício anteriores (preview, copiloto, assinatura, legado)."""
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

    def invalidar_preview_envio(self, demanda_id: int) -> None:
        """Descarta preview após edição do rascunho (força nova pré-visualização)."""
        self._remover_preview_arquivo(demanda_id)

    def preparar_preview_envio(self, demanda: Demanda) -> dict[str, Any]:
        """Gera hash do PDF sem anexo na demanda (preview em disco compartilhado)."""
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

    def registrar_assinatura(
        self,
        demanda: Demanda,
        usuario,
        *,
        hash_documento_informado: str,
        declaracao: str,
        request=None,
    ) -> AssinaturaEletronica:
        if AssinaturaEletronica.objects.filter(demanda=demanda).exists():
            raise ValueError("Esta demanda já possui assinatura eletrônica registrada.")

        decl = (declaracao or "").strip().upper()
        if decl != DECLARACAO_ENVIO:
            raise ValueError(
                f'Declaração inválida. Informe exatamente: "{DECLARACAO_ENVIO}".'
            )

        if demanda.autor_id != usuario.pk and getattr(usuario, "perfil", None) not in (
            "GESTOR",
        ):
            raise ValueError("Apenas o autor do ofício (ou gestor) pode assinar o envio.")

        pdf_preview = self._ler_preview_arquivo(int(demanda.pk))
        if pdf_preview is not None:
            pdf_bytes = pdf_preview
        else:
            logger.warning(
                "Preview em disco ausente para demanda %s; regenerando PDF para assinatura.",
                demanda.pk,
            )
            pdf_bytes = self.render_pdf_bytes(demanda)
        hash_doc = self.hash_documento_pdf(pdf_bytes)
        informado = (hash_documento_informado or "").strip().lower()
        if informado and informado != hash_doc:
            logger.warning(
                "Hash divergente demanda %s: informado=%s… calculado=%s… preview_em_disco=%s",
                demanda.pk,
                informado[:12],
                hash_doc[:12],
                pdf_preview is not None,
            )
            raise ValueError(
                "O conteúdo do ofício mudou desde a pré-visualização. "
                "Feche o diálogo, abra novamente a pré-visualização e tente enviar."
            )

        agora = timezone.now()
        pepper = (settings.SECRET_KEY or "")[:32]
        material = f"{hash_doc}|{usuario.pk}|{demanda.pk}|{agora.isoformat()}|{pepper}"
        hash_assinatura = hashlib.sha256(material.encode("utf-8")).hexdigest()
        codigo = secrets.token_hex(16)

        self._limpar_anexos_oficio(demanda)
        self._remover_preview_arquivo(int(demanda.pk))

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

        assinatura = AssinaturaEletronica.objects.create(
            demanda=demanda,
            usuario=usuario,
            hash_documento=hash_doc,
            hash_assinatura=hash_assinatura,
            codigo_validacao=codigo,
            ip_origem=_client_ip(request),
            user_agent=_client_user_agent(request),
            declaracao=decl,
        )
        logger.info(
            "Assinatura eletrônica registrada demanda=%s usuario=%s codigo=%s",
            demanda.pk,
            usuario.pk,
            codigo[:8],
        )
        return assinatura

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
            "protocolo_legislativo": demanda.protocolo_legislativo,
            "protocolo_executivo": demanda.protocolo_executivo,
            "demanda_id": demanda.pk,
            "demanda_titulo": demanda.titulo,
            "vereador": autor.get_full_name() or autor.username,
            "signatario": signatario.get_full_name() or signatario.username,
            "status_demanda": demanda.status,
            "url_validacao": f"{base_url}/validar-assinatura/{assinatura.codigo_validacao}",
        }

    def url_qr_validacao(self, codigo: str) -> str:
        base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
        return f"{base}/validar-assinatura/{codigo}"

    def gerar_qr_png_bytes(self, codigo: str) -> bytes:
        import qrcode

        img = qrcode.make(self.url_qr_validacao(codigo))
        from io import BytesIO

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
