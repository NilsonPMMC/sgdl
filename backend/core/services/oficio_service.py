"""Geração de ofícios em PDF a partir de demandas."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML

from ..models import Anexo, Demanda
from ..models_config import ConfiguracaoOficio
from integrations import sinapse_catalog
from integrations.models import SinapseServiceSync
from .assinatura_pdf import contexto_assinatura_pdf
from .oficio_corpo_pdf import preparar_corpo_pdf
from .oficio_texto import montar_texto_oficio, montar_texto_oficio_lote

logger = logging.getLogger(__name__)


class OficioService:
    """Renderiza ofício institucional em PDF (WeasyPrint)."""

    def __init__(self, config: ConfiguracaoOficio | None = None) -> None:
        self.config = config or ConfiguracaoOficio.carregar()

    def montar_descricao_oficio(
        self,
        *,
        titulo: str,
        relato: str,
        demanda: Demanda | None = None,
        endereco_formatado: str | None = None,
        servico_nome: str | None = None,
        orgao_nome: str | None = None,
        autor_nome: str | None = None,
        autor_cargo: str | None = None,
    ) -> str:
        if demanda is not None:
            endereco_formatado = endereco_formatado or self._formatar_endereco(demanda)
            catalog = sinapse_catalog.get_servico(demanda.sinapse_servico_id)
            servico_nome = servico_nome or (catalog.titulo if catalog else "")
            orgao_nome = orgao_nome or sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or ""
            autor = demanda.autor
            autor_nome = autor_nome or (autor.get_full_name() or autor.username)
            autor_cargo = autor_cargo or (getattr(autor, "cargo", None) or "")

        return montar_texto_oficio(
            titulo=titulo,
            relato=relato,
            endereco_formatado=endereco_formatado or "",
            servico_nome=servico_nome or "",
            orgao_nome=orgao_nome or "",
            autor_nome=autor_nome or "",
            autor_cargo=autor_cargo or "",
            config=self.config,
        )

    def render_amostra_pdf_bytes(self, *, autor) -> bytes:
        """PDF fictício para pré-visualizar cabeçalho, destinatário e textos institucionais."""
        autor_nome = autor.get_full_name() or getattr(autor, "username", "Vereador Exemplo")
        autor_cargo = getattr(autor, "cargo", None) or "Vereador"
        corpo_texto = self.montar_descricao_oficio(
            titulo="Solicitação de reparo em via pública",
            relato=(
                "Solicitamos a execução de serviço de tapa-buraco conforme localização "
                "indicada, em atendimento à demanda registrada no SGDL."
            ),
            endereco_formatado="Rua Exemplo, 100 — Centro",
            servico_nome="Tapa-buraco",
            orgao_nome="Secretaria de Serviços Urbanos",
            autor_nome=autor_nome,
            autor_cargo=autor_cargo,
        )
        contexto = self._contexto_pdf(
            autor=autor,
            corpo_texto=corpo_texto,
            titulo="Solicitação de reparo em via pública",
            protocolo_id="OFICIO-2026-0001",
            protocolo_legislativo="05/2026-GPe",
            endereco_formatado="Rua Exemplo, 100 — Centro",
            servico_nome="Tapa-buraco",
            orgao_nome="Secretaria de Serviços Urbanos",
            autor_nome=autor_nome,
            autor_cargo=autor_cargo,
            mostrar_marcador_protocolo=True,
        )
        html = render_to_string("oficio/demanda_oficio.html", contexto)
        return HTML(string=html, base_url=str(Path(settings.BASE_DIR))).write_pdf()

    def render_pdf_bytes(self, demanda: Demanda) -> bytes:
        """Gera bytes do PDF sem persistir (pré-visualização / hash)."""
        if isinstance(demanda, int):
            demanda = Demanda.objects.select_related("autor").get(pk=demanda)

        autor = demanda.autor
        catalog = sinapse_catalog.get_servico(demanda.sinapse_servico_id)
        corpo_texto = demanda.descricao or self.montar_descricao_oficio(
            titulo=demanda.titulo,
            relato=demanda.titulo,
            demanda=demanda,
        )
        contexto = self._contexto_pdf(
            autor=autor,
            corpo_texto=corpo_texto,
            titulo=demanda.titulo,
            protocolo_id=demanda.id,
            protocolo_executivo=demanda.protocolo_executivo,
            protocolo_legislativo=demanda.protocolo_legislativo,
            protocolo_digital=demanda.protocolo_legislativo,
            endereco_formatado=self._formatar_endereco(demanda),
            servico_nome=catalog.titulo if catalog else "",
            orgao_nome=sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or "",
            autor_nome=autor.get_full_name() or autor.username,
            autor_cargo=getattr(autor, "cargo", None) or "",
            latitude=demanda.latitude,
            longitude=demanda.longitude,
        )
        html = render_to_string("oficio/demanda_oficio.html", contexto)
        return HTML(string=html, base_url=str(Path(settings.BASE_DIR))).write_pdf()

    def render_resposta_cidadao_pdf(self, demanda: Demanda, *, corpo_texto: str) -> bytes:
        """PDF de resposta ao cidadão (devolutiva legislativa)."""
        if isinstance(demanda, int):
            demanda = Demanda.objects.select_related("autor").get(pk=demanda)

        autor = demanda.autor
        contexto = self._contexto_pdf(
            autor=autor,
            corpo_texto=corpo_texto,
            titulo=demanda.titulo,
            protocolo_id=demanda.id,
            protocolo_executivo=demanda.protocolo_executivo,
            protocolo_legislativo=demanda.protocolo_legislativo,
            autor_nome=autor.get_full_name() or autor.username,
            autor_cargo=getattr(autor, "cargo", None) or "",
        )
        html = render_to_string("oficio/oficio_resposta_cidadao.html", contexto)
        return HTML(string=html, base_url=str(Path(settings.BASE_DIR))).write_pdf()

    def gerar_pdf_oficio(self, demanda: Demanda) -> str:
        if isinstance(demanda, int):
            demanda = Demanda.objects.select_related("autor").get(pk=demanda)

        pasta = Path(settings.MEDIA_ROOT) / "oficios"
        pasta.mkdir(parents=True, exist_ok=True)
        nome_arquivo = f"oficio_demanda_{demanda.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.pdf"
        destino = pasta / nome_arquivo
        destino.write_bytes(self.render_pdf_bytes(demanda))
        logger.info("Ofício PDF gerado: %s", destino)
        return str(destino.resolve())

    def gerar_pdf_oficio_lote(self, demandas: list[Demanda]) -> str:
        if not demandas:
            raise ValueError("Lista de demandas vazia para ofício em lote.")

        demandas = list(
            Demanda.objects.select_related("autor").filter(pk__in=[d.pk for d in demandas])
        )
        ref = demandas[0]
        itens_pdf: list[dict[str, str]] = []
        itens_texto: list[dict[str, Any]] = []

        for d in demandas:
            catalog = sinapse_catalog.get_servico(d.sinapse_servico_id)
            orgao = sinapse_catalog.get_orgao_nome(d.sinapse_orgao_id) or ""
            relato_curto = (d.descricao or d.titulo or "")[:500]
            itens_pdf.append(
                {
                    "titulo": d.titulo,
                    "corpo": d.descricao or relato_curto,
                    "servico_nome": catalog.titulo if catalog else "",
                    "secretaria": orgao,
                }
            )
            itens_texto.append(
                {
                    "titulo": d.titulo,
                    "relato": relato_curto,
                    "servico_nome": catalog.titulo if catalog else "",
                    "orgao_nome": orgao,
                }
            )

        corpo_lote = montar_texto_oficio_lote(
            itens=itens_texto,
            endereco_formatado=self._formatar_endereco(ref),
            autor_nome=ref.autor.get_full_name() or ref.autor.username,
            autor_cargo=getattr(ref.autor, "cargo", None) or "",
            config=self.config,
        )

        pasta = Path(settings.MEDIA_ROOT) / "oficios"
        pasta.mkdir(parents=True, exist_ok=True)
        ids = "_".join(str(d.id) for d in demandas[:5])
        nome_arquivo = f"oficio_lote_{ids}_{timezone.now().strftime('%Y%m%d%H%M%S')}.pdf"
        destino = pasta / nome_arquivo

        coord = ""
        if ref.latitude is not None and ref.longitude is not None:
            coord = f"{ref.latitude}, {ref.longitude}"

        contexto = self._contexto_pdf(
            autor=ref.autor,
            corpo_texto=corpo_lote,
            titulo="Solicitação de serviços públicos",
            itens=itens_pdf,
            endereco_formatado=self._formatar_endereco(ref),
            coordenadas=coord,
            autor_nome=ref.autor.get_full_name() or ref.autor.username,
            autor_cargo=getattr(ref.autor, "cargo", None) or "",
            lote=True,
        )
        html = render_to_string("oficio/oficio_lote.html", contexto)
        HTML(string=html, base_url=str(Path(settings.BASE_DIR))).write_pdf(str(destino))
        logger.info("Ofício lote PDF gerado: %s (%s demandas)", destino, len(demandas))
        return str(destino.resolve())

    def _contexto_pdf(self, *, autor=None, config: ConfiguracaoOficio | None = None, **kwargs: Any) -> dict[str, Any]:
        cfg = config or self.config
        if "corpo_texto" in kwargs:
            kwargs.update(preparar_corpo_pdf(kwargs.pop("corpo_texto")))
        base = {
            "config": cfg,
            "data_emissao": timezone.localtime(timezone.now()).strftime("%d/%m/%Y"),
            "municipio": cfg.municipio,
            "destinatario_tratamento": cfg.destinatario_tratamento,
            "destinatario_nome": cfg.destinatario_nome,
            "destinatario_cargo": cfg.destinatario_cargo,
            "orgao_destinatario": cfg.orgao_destinatario,
            **cfg.contexto_layout_pdf(),
        }
        base.update(kwargs)
        if autor is not None:
            base.update(contexto_assinatura_pdf(autor))
        return base

    @staticmethod
    def anexar_pdf_a_demandas(
        demandas: list[Demanda],
        caminho_pdf: str,
        *,
        descricao: str = "Ofício copiloto (SGDL)",
    ) -> str | None:
        path = Path(caminho_pdf)
        if not path.is_file():
            return None
        conteudo = path.read_bytes()
        nome = path.name
        url_relativa: str | None = None

        for d in demandas:
            anexo = Anexo(demanda=d, descricao=descricao)
            anexo.arquivo.save(nome, ContentFile(conteudo), save=True)
            if url_relativa is None and anexo.arquivo:
                url_relativa = anexo.arquivo.url

        return url_relativa

    @staticmethod
    def _formatar_endereco(demanda: Demanda) -> str:
        partes: list[str] = []
        if demanda.logradouro:
            trecho = demanda.logradouro
            if demanda.numero:
                trecho = f"{trecho}, {demanda.numero}"
            partes.append(trecho)
        if demanda.bairro:
            partes.append(f"Bairro {demanda.bairro}")
        if demanda.cep:
            partes.append(f"CEP {demanda.cep}")
        if demanda.complemento:
            partes.append(demanda.complemento)
        return " — ".join(partes)
