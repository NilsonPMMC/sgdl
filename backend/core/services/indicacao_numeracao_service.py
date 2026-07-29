"""Numeração de indicações legislativas — sequência anual da Câmara (formato configurável)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.models import Demanda
from core.models_config import NumeracaoIndicacaoCamara


class IndicacaoNumeracaoService:
    def carregar_config(self) -> NumeracaoIndicacaoCamara:
        cfg = NumeracaoIndicacaoCamara.carregar()
        ano_atual = timezone.now().year
        if cfg.ano != ano_atual:
            cfg.ano = ano_atual
            cfg.ultimo_numero = 0
            cfg.save(update_fields=["ano", "ultimo_numero", "atualizado_em"])
        return cfg

    def formatar(self, numero: int, ano: int | None = None, mascara: str | None = None) -> str:
        cfg = self.carregar_config()
        ano_ref = int(ano or cfg.ano or timezone.now().year)
        tpl = (mascara or cfg.mascara or "{numero}/{ano}").strip()
        return tpl.format(numero=int(numero), ano=ano_ref)

    def proximo_numero_sugerido(self) -> dict:
        cfg = self.carregar_config()
        numero = int(cfg.ultimo_numero) + 1
        ano = int(cfg.ano)
        return {
            "ano": ano,
            "numero": numero,
            "protocolo_sugerido": self.formatar(numero, ano, cfg.mascara),
            "ultimo_numero": cfg.ultimo_numero,
            "mascara": cfg.mascara,
        }

    def _numero_ja_utilizado(self, numero: int, ano: int, *, excluir_demanda_id: int | None = None) -> bool:
        qs = Demanda.objects.filter(
            tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO,
            numero_indicacao=numero,
            ano_indicacao=ano,
        ).exclude(protocolo_legislativo__isnull=True)
        if excluir_demanda_id:
            qs = qs.exclude(pk=excluir_demanda_id)
        return qs.exists()

    def validar_numero(self, numero: int, ano: int | None = None, *, excluir_demanda_id: int | None = None) -> None:
        if numero < 1:
            raise ValueError("O número da indicação deve ser maior que zero.")
        ano_ref = int(ano or self.carregar_config().ano)
        if self._numero_ja_utilizado(numero, ano_ref, excluir_demanda_id=excluir_demanda_id):
            raise ValueError(f"Indicação nº {numero}/{ano_ref} já está registrada.")

    @transaction.atomic
    def reservar_numero(
        self,
        numero: int | None = None,
        ano: int | None = None,
        *,
        excluir_demanda_id: int | None = None,
    ) -> tuple[int, int, str]:
        cfg = self.carregar_config()
        ano_ref = int(ano or cfg.ano)
        if numero is None:
            numero = int(cfg.ultimo_numero) + 1
        numero = int(numero)
        self.validar_numero(numero, ano_ref, excluir_demanda_id=excluir_demanda_id)
        protocolo = self.formatar(numero, ano_ref, cfg.mascara)
        if Demanda.objects.filter(protocolo_legislativo=protocolo).exclude(
            pk=excluir_demanda_id or 0
        ).exists():
            raise ValueError(f"Protocolo «{protocolo}» já está em uso.")
        if ano_ref == cfg.ano and numero > cfg.ultimo_numero:
            cfg.ultimo_numero = numero
            cfg.save(update_fields=["ultimo_numero", "atualizado_em"])
        return numero, ano_ref, protocolo

    def atualizar_ultimo_informado(self, ultimo_numero: int, ano: int | None = None, mascara: str | None = None) -> dict:
        cfg = self.carregar_config()
        ultimo = int(ultimo_numero)
        if ultimo < 0:
            raise ValueError("Último número informado não pode ser negativo.")
        if ano is not None:
            cfg.ano = int(ano)
        if mascara is not None:
            cfg.mascara = str(mascara).strip() or cfg.mascara
        cfg.ultimo_numero = ultimo
        cfg.save()
        return self.proximo_numero_sugerido()


def anexo_pdf_indicacao(demanda: Demanda):
    """Primeiro anexo PDF da demanda (documento assinado pelos vereadores)."""
    for anexo in demanda.anexos.all().order_by("data_upload", "pk"):
        nome = (anexo.arquivo.name or "").lower()
        if nome.endswith(".pdf"):
            return anexo
    return None
