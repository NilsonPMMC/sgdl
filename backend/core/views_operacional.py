"""Endpoints REST — Gestão Operacional (Portal dos Vereadores)."""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Demanda
from core.models_assinatura_eletronica import AssinaturaEletronica
from core.serializers import DemandaSerializer
from core.services.assinatura_eletronica_service import AssinaturaEletronicaService
from core.services.assinatura_etapa_executor_service import ACAO_CONCLUSAO_SECRETARIA_FLUXO_DIRETO
from core.services.demanda_visibilidade import aplicar_escopo_demanda
from core.services.operacional_estado_service import (
    OperacionalEstadoError,
    OperacionalEstadoService,
    OperacionalPermissaoError,
)
from core.services.scatter_gather_service import (
    ScatterGatherError,
    ScatterGatherPermissaoError,
    ScatterGatherDestinoDuplicadoError,
    NoOperacionalService,
)
from core.models_no_operacional import AcaoNoOperacional

logger = logging.getLogger(__name__)


def _demanda_escopo(request, demanda_pk: int) -> Demanda:
    qs = aplicar_escopo_demanda(
        Demanda.objects.select_related(
            "autor", "tendencia", "cluster", "unidade_administrativa"
        ),
        request.user,
    )
    return get_object_or_404(qs, pk=demanda_pk)


def _parse_no_ids_request(data, *, fallback_key: str = "no_id") -> list[int]:
    """Normaliza no_ids vindos de JSON, multipart ou valor escalar."""
    import json

    raw_ids = data.get("no_ids")
    if raw_ids in (None, ""):
        fallback = data.get(fallback_key)
        if fallback not in (None, ""):
            return [int(fallback)]
        return []

    if isinstance(raw_ids, int):
        return [raw_ids]

    if isinstance(raw_ids, str):
        texto = raw_ids.strip()
        if not texto:
            return []
        try:
            parsed = json.loads(texto)
        except json.JSONDecodeError:
            return [int(x) for x in texto.split(",") if x.strip()]
        if isinstance(parsed, int):
            return [parsed]
        if isinstance(parsed, list):
            return [int(x) for x in parsed if str(x).strip()]
        return []

    if isinstance(raw_ids, (list, tuple)):
        return [int(x) for x in raw_ids if str(x).strip()]

    return [int(raw_ids)]


def _resposta_erro(exc: Exception) -> Response:
    if isinstance(exc, (OperacionalPermissaoError, ScatterGatherPermissaoError)):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ScatterGatherDestinoDuplicadoError):
        return Response(
            {
                "detail": str(exc),
                "codigo": "NO_DESTINO_DUPLICADO",
                "conflitos": exc.conflitos,
                "permite_prosseguir": True,
            },
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, (OperacionalEstadoError, ScatterGatherError, ValueError)):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    logger.exception("Falha operacional")
    return Response(
        {"detail": "Erro interno na operação."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _resposta_demanda(request, demanda: Demanda, extra: dict | None = None) -> Response:
    data = DemandaSerializer(demanda, context={"request": request}).data
    if extra:
        data.update(extra)
    return Response(data)


class DemandaOperacionalEstadoAPIView(APIView):
    """GET /api/demandas/{id}/operacional/estado/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        payload = OperacionalEstadoService().montar_estado_operacional(
            demanda, request.user
        )
        return Response(payload)


class DemandaOperacionalHistoricoTecnicoAPIView(APIView):
    """GET /api/demandas/{id}/operacional/historico-tecnico/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        historico = OperacionalEstadoService().compilar_historico_tecnico(demanda)
        return Response(historico)


class DemandaOperacionalVincularServicoAPIView(APIView):
    """POST /api/demandas/{id}/operacional/vincular-servico/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        sid = request.data.get("sinapse_servico_id") or request.data.get("servico_id")
        if not sid:
            return Response(
                {"detail": "sinapse_servico_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            demanda = OperacionalEstadoService().aplicar_vincular_servico_tendencia(
                demanda, request.user, sinapse_servico_id=int(sid)
            )
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)
        return _resposta_demanda(request, demanda)


class DemandaOperacionalRecusaProtocoloAPIView(APIView):
    """POST /api/demandas/{id}/operacional/recusa-protocolo/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        parecer = str(
            request.data.get("parecer")
            or request.data.get("parecer_recusa")
            or request.data.get("descricao")
            or ""
        )
        try:
            demanda = OperacionalEstadoService().aplicar_recusa_protocolo(
                demanda, request.user, parecer=parecer
            )
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)
        return _resposta_demanda(request, demanda)


class DemandaOperacionalConclusaoParcialAPIView(APIView):
    """POST /api/demandas/{id}/operacional/conclusao-parcial/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        parecer = str(
            request.data.get("parecer_operacional")
            or request.data.get("parecer")
            or request.data.get("descricao")
            or ""
        )
        arquivos = request.FILES.getlist("arquivos_anexos") or request.FILES.getlist("anexos")
        perna_raw = request.data.get("perna_id")
        perna_id = int(perna_raw) if perna_raw not in (None, "") else None
        try:
            resultado = OperacionalEstadoService().aplicar_conclusao_parcial(
                demanda,
                request.user,
                parecer=parecer,
                perna_id=perna_id,
                arquivos_anexos=arquivos or None,
            )
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)
        demanda = resultado["demanda"]
        return _resposta_demanda(
            request,
            demanda,
            extra={
                "operacional": {
                    "processo_avancou": resultado["processo_avancou"],
                    "ultima_conclusao_parcial": resultado.get("ultima_conclusao_parcial", False),
                    "pendencias_parciais": resultado["pendencias_parciais"],
                    "historico_tecnico": resultado["historico_tecnico"],
                    "lider_id": resultado["lider"].pk,
                }
            },
        )


class DemandaOperacionalIniciarExecucaoAPIView(APIView):
    """POST /api/demandas/{id}/operacional/iniciar-execucao/ — C1, C2, C4."""

    permission_classes = [IsAuthenticated]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        try:
            demanda = OperacionalEstadoService().aplicar_inicio_execucao(
                demanda, request.user
            )
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)
        return _resposta_demanda(request, demanda)


class DemandaOperacionalAbrirPernasTransversalAPIView(APIView):
    """POST /api/demandas/{id}/operacional/abrir-pernas-transversal/ — C1/C2."""

    permission_classes = [IsAuthenticated]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        observacao = str(
            request.data.get("observacao")
            or request.data.get("descricao")
            or ""
        )
        try:
            resultado = OperacionalEstadoService().aplicar_abertura_pernas_transversal(
                demanda,
                request.user,
                destinos_raw=dict(request.data),
                observacao=observacao,
            )
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)
        return _resposta_demanda(
            request,
            resultado["demanda"],
            extra={
                "operacional": {
                    "pernas_criadas": resultado["pernas_criadas"],
                    "total_pernas": resultado["total_pernas"],
                }
            },
        )


class DemandaOperacionalConclusaoTecnicaAPIView(APIView):
    """POST /api/demandas/{id}/operacional/conclusao-tecnica/ — fluxo direto + assinatura."""

    permission_classes = [IsAuthenticated]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        parecer = str(
            request.data.get("parecer_operacional")
            or request.data.get("parecer")
            or request.data.get("descricao")
            or ""
        )
        assinatura_svc = AssinaturaEletronicaService()
        try:
            operacional = OperacionalEstadoService()
            operacional.validar_conclusao_tecnica(demanda, request.user, parecer=parecer)
            pending = assinatura_svc._validar_hash_pending(
                int(demanda.pk),
                AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA,
                request.data.get("hash_documento"),
            )
            from core.services.estudo_viabilidade_service import EstudoViabilidadeService

            estudo_payload = EstudoViabilidadeService.parse_payload_request(
                dict(request.data) if hasattr(request.data, "items") else {}
            )
            contexto = {
                "parecer_operacional": parecer,
                "acao_executiva": ACAO_CONCLUSAO_SECRETARIA_FLUXO_DIRETO,
            }
            if estudo_payload is not None:
                contexto["resultado_operacional"] = estudo_payload

            assinatura = assinatura_svc.registrar_assinatura_conclusao_secretaria(
                demanda,
                request.user,
                hash_documento=pending["hash_documento"],
                declaracao=request.data.get("declaracao"),
                contexto_operacao=contexto,
                request=request,
            )
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)

        return _resposta_demanda(
            request,
            demanda,
            extra={
                "assinatura_registrada": {
                    "codigo_validacao": assinatura.codigo_validacao,
                },
                "aguardando_validacao_gestor": True,
                "mensagem": (
                    "Assinatura registrada. A conclusão só será aplicada após validação "
                    "do gestor do setor em Assinaturas pendentes."
                ),
            },
        )


class DemandaOperacionalDevolverProtocoloAPIView(APIView):
    """POST /api/demandas/{id}/operacional/devolver-protocolo/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        justificativa = str(
            request.data.get("justificativa")
            or request.data.get("parecer")
            or request.data.get("descricao")
            or ""
        )
        try:
            demanda = OperacionalEstadoService().aplicar_devolucao(
                demanda, request.user, justificativa=justificativa
            )
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)
        return _resposta_demanda(request, demanda)


class DemandaOperacionalPreviewConclusaoFinalAPIView(APIView):
    """POST /api/demandas/{id}/operacional/preview-conclusao-final/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        from core.services.gestor_escopo import usuario_pode_painel_protocolo_central

        if not usuario_pode_painel_protocolo_central(request.user) and not request.user.is_staff:
            return Response(
                {"detail": "Apenas o Protocolo pode preparar a conclusão final."},
                status=status.HTTP_403_FORBIDDEN,
            )
        parecer = str(
            request.data.get("parecer_resposta")
            or request.data.get("parecer")
            or request.data.get("descricao")
            or ""
        )
        try:
            operacional = OperacionalEstadoService()
            operacional.validar_conclusao_final(demanda, request.user, parecer=parecer)
            historico = operacional.compilar_historico_tecnico(demanda)
            preview = AssinaturaEletronicaService().preparar_assinatura_conclusao_final(
                demanda,
                parecer_resposta=parecer,
                historico_tecnico=historico,
            )
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)

        preview["gestores_protocolo"] = AssinaturaEletronicaService().listar_gestores_protocolo()
        preview["signatario_operador"] = AssinaturaEletronicaService().resumo_signatario(
            request.user, AssinaturaEletronica.PAPEL_OPERADOR
        )
        preview["modo_assinatura"] = AssinaturaEletronicaService().modo_assinatura_protocolo(
            request.user, contexto="conclusao_final"
        )
        if preview["modo_assinatura"] == "gestor_apenas":
            preview["signatario_gestor"] = AssinaturaEletronicaService().resumo_signatario(
                request.user, AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO
            )
        return Response(preview)


class DemandaOperacionalConclusaoFinalAPIView(APIView):
    """POST /api/demandas/{id}/operacional/conclusao-final/"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, demanda_pk: int):
        demanda = _demanda_escopo(request, demanda_pk)
        from core.services.gestor_escopo import usuario_pode_painel_protocolo_central

        if not usuario_pode_painel_protocolo_central(request.user) and not request.user.is_staff:
            return Response(
                {"detail": "Apenas o Protocolo ou gestor central pode emitir a conclusão final."},
                status=status.HTTP_403_FORBIDDEN,
            )

        parecer = str(
            request.data.get("parecer_resposta")
            or request.data.get("parecer")
            or request.data.get("descricao")
            or ""
        )
        arquivos = request.FILES.getlist("arquivos_anexos") or request.FILES.getlist("anexos")

        from django.db import transaction

        from core.services.devolutiva_protocolo_service import (
            _parse_destinos,
            _parse_ids,
        )

        anexos_ids = _parse_ids(request.data.get("anexos_tramitacao_ids"))
        alerta_destinos = _parse_destinos(request.data.get("alerta_destinos"))
        assinatura_apenas_gestor = bool(request.data.get("assinatura_apenas_gestor"))

        try:
            with transaction.atomic():
                assinatura_svc = AssinaturaEletronicaService()
                operacional = OperacionalEstadoService()
                operacional.validar_conclusao_final(demanda, request.user, parecer=parecer)
                historico = operacional.compilar_historico_tecnico(demanda)
                contexto = {
                    "parecer_resposta": parecer,
                    "historico_tecnico": historico,
                    "anexos_tramitacao_ids": anexos_ids,
                    "alerta_destinos": alerta_destinos,
                }
                staging_id = assinatura_svc._criar_tramitacao_staging_anexos(
                    demanda, request.user, arquivos or None
                )
                if staging_id:
                    contexto["tramitacao_staging_id"] = staging_id

                assinaturas = assinatura_svc.registrar_assinaturas_conclusao_final(
                    demanda,
                    request.user,
                    hash_documento=request.data.get("hash_documento"),
                    declaracao_operador=request.data.get("declaracao")
                    or request.data.get("declaracao_operador"),
                    gestor_usuario_id=request.data.get("gestor_protocolo_id"),
                    declaracao_gestor=request.data.get("declaracao_gestor"),
                    assinatura_apenas_gestor=assinatura_apenas_gestor,
                    validacao_id=request.data.get("validacao_id"),
                    contexto_operacao=contexto,
                    request=request,
                )
                if assinatura_apenas_gestor and not request.data.get("validacao_id"):
                    from core.models import Tramitacao
                    from core.services.devolutiva_protocolo_service import (
                        DevolutivaProtocoloService,
                    )
                    from core.services.tramitacao_janela_edicao_service import (
                        TramitacaoJanelaEdicaoService,
                    )

                    demanda = operacional.aplicar_conclusao_final(
                        demanda,
                        request.user,
                        parecer=parecer,
                        historico_compilado=historico,
                    )
                    tram = (
                        demanda.tramitacoes.filter(tipo="CONCLUSAO_FINAL")
                        .order_by("-timestamp")
                        .first()
                    )
                    if tram is not None:
                        arquivos_staging = None
                        if staging_id:
                            staging = Tramitacao.objects.filter(pk=int(staging_id)).first()
                            if staging:
                                arquivos_staging = list(staging.anexos.all())
                        DevolutivaProtocoloService().complementar_tramitacao_devolutiva(
                            tram,
                            demanda,
                            request.user,
                            arquivos_anexos=arquivos or arquivos_staging,
                            anexos_tramitacao_ids=anexos_ids or None,
                            alerta_destinos=alerta_destinos or None,
                        )
                        DevolutivaProtocoloService().remover_devolutiva_redundante(demanda)
                        if staging_id:
                            Tramitacao.objects.filter(pk=int(staging_id)).delete()
                        TramitacaoJanelaEdicaoService.abrir_janela(tram)
                        if assinaturas:
                            assinaturas[0].tramitacao = tram
                            assinaturas[0].save(update_fields=["tramitacao"])
        except (OperacionalEstadoError, OperacionalPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)

        demanda.refresh_from_db()
        return _resposta_demanda(
            request,
            demanda,
            extra={
                "historico_tecnico": historico,
                "assinaturas_registradas": [
                    {"codigo_validacao": a.codigo_validacao, "papel": a.papel}
                    for a in assinaturas
                ],
                "aguardando_validacao_gestor": not assinatura_apenas_gestor,
                "mensagem": (
                    "Assinatura registrada. A conclusão final só será enviada ao vereador "
                    "após validação do gestor do protocolo em Assinaturas pendentes."
                    if not assinatura_apenas_gestor
                    else None
                ),
            },
        )


class DemandaOperacionalScatterGatherAPIView(APIView):
    """
    POST /api/demandas/{id}/operacional/scatter-gather/

    Ações scatter-gather na etapa EM_OPERACAO:
    - DESPACHAR: abre nó(s) filho(s); nó atual permanece aberto
    - DESPACHAR_ENCERRAR: abre nó(s) filho(s) e encerra o nó atual
    - ENCERRAR: encerra o nó atual (sem filhos abertos)
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, demanda_pk: int):
        from core.services.scatter_gather_service import _parse_destinos_scatter

        demanda = _demanda_escopo(request, demanda_pk)
        lider = OperacionalEstadoService().demanda_processo_lider(demanda)
        acao = str(request.data.get("acao") or "").upper()
        no_raw = request.data.get("no_id")
        if no_raw in (None, ""):
            return Response(
                {"detail": "Informe no_id do nó operacional."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        no_id = int(no_raw)
        observacao = str(
            request.data.get("observacao") or request.data.get("descricao") or ""
        )
        arquivos = request.FILES.getlist("arquivos_anexos") or request.FILES.getlist("anexos")
        destinos = _parse_destinos_scatter(dict(request.data))
        destino_orgao = request.data.get("destino_orgao_id") or request.data.get(
            "secretaria_id"
        )
        destino_setor = request.data.get("destino_setor_id") or request.data.get(
            "unidade_administrativa_id"
        )
        destino_setor_id = int(destino_setor) if destino_setor not in (None, "") else None
        confirmar_duplicado = str(
            request.data.get("confirmar_destino_duplicado") or ""
        ).lower() in ("1", "true", "yes", "sim")

        assinatura_svc = AssinaturaEletronicaService()
        assinatura_ctx = assinatura_svc.parse_assinatura_scatter_request(dict(request.data), acao)
        from core.services.estudo_viabilidade_service import EstudoViabilidadeService

        estudo_payload = EstudoViabilidadeService.parse_payload_request(
            dict(request.data) if hasattr(request.data, "items") else {}
        )
        if estudo_payload is not None:
            assinatura_ctx["resultado_operacional"] = estudo_payload
        try:
            assinatura_svc.validar_assinatura_scatter_contexto(assinatura_ctx)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        svc = NoOperacionalService()
        try:
            if acao == AcaoNoOperacional.DESPACHAR:
                if not destinos and destino_orgao in (None, ""):
                    return Response(
                        {"detail": "Informe ao menos um destino para despachar."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if len(destinos) > 1 or (destinos and not destino_orgao):
                    resultado = svc.aplicar_despachar_destinos(
                        lider,
                        no_id,
                        request.user,
                        destinos=destinos,
                        observacao=observacao,
                        arquivos_anexos=arquivos or None,
                        confirmar_destino_duplicado=confirmar_duplicado,
                        assinatura_ctx=assinatura_ctx,
                        request=request,
                    )
                else:
                    oid = int(destinos[0]["secretaria_id"]) if destinos else int(destino_orgao)
                    setor = destinos[0].get("unidade_administrativa_id") if destinos else destino_setor_id
                    setor_id = int(setor) if setor not in (None, "") else None
                    resultado = svc.aplicar_despachar(
                        lider,
                        no_id,
                        request.user,
                        destino_orgao_id=oid,
                        destino_setor_id=setor_id,
                        observacao=observacao,
                        arquivos_anexos=arquivos or None,
                        confirmar_destino_duplicado=confirmar_duplicado,
                        assinatura_ctx=assinatura_ctx,
                        request=request,
                    )
            elif acao == AcaoNoOperacional.DESPACHAR_ENCERRAR:
                if not destinos and destino_orgao in (None, ""):
                    return Response(
                        {"detail": "Informe ao menos um destino para despachar e encerrar."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                resultado = svc.aplicar_despachar_encerrar(
                    lider,
                    no_id,
                    request.user,
                    destino_orgao_id=int(destino_orgao) if destino_orgao not in (None, "") else None,
                    destino_setor_id=destino_setor_id,
                    destinos=destinos or None,
                    observacao=observacao,
                    arquivos_anexos=arquivos or None,
                    confirmar_destino_duplicado=confirmar_duplicado,
                    assinatura_ctx=assinatura_ctx,
                    request=request,
                )
            elif acao == AcaoNoOperacional.ENCERRAR:
                resultado = svc.aplicar_encerrar(
                    lider,
                    no_id,
                    request.user,
                    observacao=observacao,
                    arquivos_anexos=arquivos or None,
                    assinatura_ctx=assinatura_ctx,
                    request=request,
                )
            else:
                return Response(
                    {
                        "detail": (
                            "Ação inválida. Use DESPACHAR, DESPACHAR_ENCERRAR ou ENCERRAR."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ScatterGatherError, ScatterGatherPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)

        from core.services.estudo_viabilidade_service import (
            registrar_resultado_operacional_se_processo_avancou,
        )

        lider.refresh_from_db()
        if not resultado.get("aguardando_validacao_gestor"):
            registrar_resultado_operacional_se_processo_avancou(
                request,
                lider,
                request.user,
                parecer=observacao,
                processo_avancou=bool(resultado.get("processo_avancou")),
            )
        sg = NoOperacionalService()
        no_filho = resultado.get("no_filho")
        nos_filhos = resultado.get("nos_filhos") or []
        return _resposta_scatter_ok(request, lider, resultado, sg, no_filho, nos_filhos)


def _resposta_scatter_ok(request, lider, resultado, sg, no_filho=None, nos_filhos=None):
    return Response(
        {
            "demanda_id": lider.pk,
            "status": lider.status,
            "nos_ativos": lider.nos_ativos,
            "acao": resultado["acao"],
            "no": sg.serializar_no(resultado["no"]) if resultado.get("no") else None,
            "no_filho": sg.serializar_no(no_filho) if no_filho else None,
            "nos_filhos": [sg.serializar_no(n) for n in (nos_filhos or [])],
            "no_canonico": (
                sg.serializar_no(resultado["no_canonico"])
                if resultado.get("no_canonico")
                else None
            ),
            "nos_encerrados": [
                sg.serializar_no(n) for n in (resultado.get("nos_encerrados") or [])
            ],
            "nos_bloqueados": resultado.get("nos_bloqueados") or [],
            "encerramento_parcial": bool(resultado.get("encerramento_parcial")),
            "processo_avancou": resultado.get("processo_avancou", False),
            "aguardando_validacao_gestor": bool(resultado.get("aguardando_validacao_gestor")),
            "assinatura_registrada": resultado.get("assinatura_registrada"),
            "assinaturas_registradas": resultado.get("assinaturas_registradas"),
            "arvore_nos": sg.montar_arvore_nos(lider),
            "operacional": OperacionalEstadoService().montar_estado_operacional(
                lider, request.user
            ),
        }
    )


class DemandaOperacionalNosUnificadosAPIView(APIView):
    """
    POST /api/demandas/{id}/operacional/nos-unificados/

    Ações sobre nós operacionais equivalentes (mesmo órgão × setor):
    - CONSOLIDAR: mantém nó canônico e encerra redundantes
    - ENCERRAR_LOTE: encerra todos os nós do grupo
    - DESPACHAR / DESPACHAR_ENCERRAR: consolida e despacha uma vez pelo nó canônico
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, demanda_pk: int):
        from core.services.scatter_gather_service import _parse_destinos_scatter

        demanda = _demanda_escopo(request, demanda_pk)
        lider = OperacionalEstadoService().demanda_processo_lider(demanda)
        acao = str(request.data.get("acao") or "").upper()
        observacao = str(
            request.data.get("observacao") or request.data.get("descricao") or ""
        )
        arquivos = request.FILES.getlist("arquivos_anexos") or request.FILES.getlist("anexos")
        confirmar_duplicado = str(
            request.data.get("confirmar_destino_duplicado") or ""
        ).lower() in ("1", "true", "yes", "sim")

        no_ids = _parse_no_ids_request(request.data)

        no_canonico_raw = request.data.get("no_canonico_id")
        no_canonico_id = int(no_canonico_raw) if no_canonico_raw not in (None, "") else None

        assinatura_ctx = None
        if acao in (
            "ENCERRAR_LOTE",
            AcaoNoOperacional.DESPACHAR,
            AcaoNoOperacional.DESPACHAR_ENCERRAR,
        ):
            assinatura_svc = AssinaturaEletronicaService()
            assinatura_ctx = assinatura_svc.parse_assinatura_scatter_request(
                dict(request.data), acao
            )
            try:
                assinatura_svc.validar_assinatura_scatter_contexto(assinatura_ctx)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        svc = NoOperacionalService()
        try:
            if acao == "CONSOLIDAR":
                resultado = svc.consolidar_nos_equivalentes(
                    lider,
                    request.user,
                    no_ids=no_ids,
                    no_canonico_id=no_canonico_id,
                    observacao=observacao,
                )
            elif acao == "ENCERRAR_LOTE":
                resultado = svc.encerrar_nos_lote(
                    lider,
                    request.user,
                    no_ids=no_ids,
                    observacao=observacao,
                    arquivos_anexos=arquivos or None,
                    assinatura_ctx=assinatura_ctx,
                    request=request,
                )
            elif acao in (AcaoNoOperacional.DESPACHAR, AcaoNoOperacional.DESPACHAR_ENCERRAR):
                destinos = _parse_destinos_scatter(dict(request.data))
                if not destinos:
                    return Response(
                        {"detail": "Informe ao menos um destino para o despacho unificado."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                resultado = svc.despachar_nos_unificado(
                    lider,
                    request.user,
                    no_ids=no_ids,
                    destinos=destinos,
                    acao_scatter=acao,
                    observacao=observacao,
                    arquivos_anexos=arquivos or None,
                    confirmar_destino_duplicado=confirmar_duplicado,
                    no_canonico_id=no_canonico_id,
                    assinatura_ctx=assinatura_ctx,
                    request=request,
                )
            else:
                return Response(
                    {
                        "detail": (
                            "Ação inválida. Use CONSOLIDAR, ENCERRAR_LOTE, DESPACHAR "
                            "ou DESPACHAR_ENCERRAR."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ScatterGatherError, ScatterGatherPermissaoError, ValueError) as exc:
            return _resposta_erro(exc)

        from core.services.estudo_viabilidade_service import (
            registrar_resultado_operacional_se_processo_avancou,
        )

        lider.refresh_from_db()
        if not resultado.get("aguardando_validacao_gestor"):
            registrar_resultado_operacional_se_processo_avancou(
                request,
                lider,
                request.user,
                parecer=observacao,
                processo_avancou=bool(resultado.get("processo_avancou")),
            )
        sg = NoOperacionalService()
        return _resposta_scatter_ok(
            request,
            lider,
            resultado,
            sg,
            resultado.get("no_filho"),
            resultado.get("nos_filhos"),
        )
