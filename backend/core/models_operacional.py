"""Constantes da máquina de estados — Gestão Operacional (Portal dos Vereadores)."""

from __future__ import annotations


class TipoEntrada:
    """Classificação na etapa de entrada do vereador."""

    CARTA_SERVICO = "CARTA_SERVICO"
    TENDENCIA = "TENDENCIA"


class FluxoRoteamento:
    """Rota definida pelo Protocolo na triagem (TRIAGEM_PROTOCOLO)."""

    FLUXO_DIRETO = "FLUXO_DIRETO"
    FLUXO_TRANSVERSAL = "FLUXO_TRANSVERSAL"

    CHOICES = (
        (FLUXO_DIRETO, "Fluxo direto (secretaria líder)"),
        (FLUXO_TRANSVERSAL, "Fluxo transversal (multi-secretaria)"),
    )


class ModoEntradaProcesso:
    """Agrupamento na entrada — diagrama SGDL-fluxo_tramitacoes.png."""

    OFICIO_UNICO = "OFICIO_UNICO"
    CLUSTER_SUPER_OS = "CLUSTER_SUPER_OS"

    CHOICES = (
        (OFICIO_UNICO, "Ofício único"),
        (CLUSTER_SUPER_OS, "Cluster Super OS (multi-vereador)"),
    )


class OrquestradorConclusao:
    """Quem conduz início/consolidação operacional antes da conclusão final."""

    SECRETARIA_LIDER = "SECRETARIA_LIDER"
    PROTOCOLO = "PROTOCOLO"

    CHOICES = (
        (SECRETARIA_LIDER, "Secretaria responsável (líder)"),
        (PROTOCOLO, "Protocolo"),
    )

    VALID = frozenset({SECRETARIA_LIDER, PROTOCOLO})


class PerfilProcesso:
    """Cenários 1–5 do diagrama de tramitações."""

    CENARIO_1 = "CENARIO_1"
    CENARIO_2 = "CENARIO_2"
    CENARIO_3 = "CENARIO_3"
    CENARIO_4 = "CENARIO_4"
    CENARIO_5 = "CENARIO_5"

    CHOICES = (
        (CENARIO_1, "C1 — Cluster, secretaria líder orquestra"),
        (CENARIO_2, "C2 — Ofício único transversal, secretaria líder"),
        (CENARIO_3, "C3 — Ofício único transversal, Protocolo"),
        (CENARIO_4, "C4 — Fluxo direto, secretaria líder"),
        (CENARIO_5, "C5 — Cluster transversal, Protocolo"),
    )

    @classmethod
    def resolver(
        cls,
        *,
        modo_entrada: str,
        fluxo_roteamento: str,
        orquestrador_conclusao: str,
    ) -> str:
        if fluxo_roteamento == FluxoRoteamento.FLUXO_DIRETO:
            return cls.CENARIO_4
        if modo_entrada == ModoEntradaProcesso.CLUSTER_SUPER_OS:
            if orquestrador_conclusao == OrquestradorConclusao.PROTOCOLO:
                return cls.CENARIO_5
            return cls.CENARIO_1
        if orquestrador_conclusao == OrquestradorConclusao.PROTOCOLO:
            return cls.CENARIO_3
        return cls.CENARIO_2


class EventoOperacional:
    """Eventos de domínio persistidos como Tramitacao.tipo (+ metadata JSON)."""

    ENTRADA_VEREADOR = "ENVIO_OFICIAL"
    TRIAGEM_PROTOCOLO = "TRIAGEM_PROTOCOLO"
    RECUSA_PROTOCOLO = "RECUSA_PROTOCOLO"
    DESPACHO = "DESPACHO"
    INICIO_EXECUCAO = "STATUS_UPDATE"
    CONCLUSAO_TECNICA = "CONCLUSAO_TECNICA"
    CONCLUSAO_PARCIAL = "CONCLUSAO_PARCIAL"
    DEVOLUCAO = "DEVOLUCAO"
    CONCLUSAO_FINAL = "CONCLUSAO_FINAL"
    SOLICITACAO_DEVOLUTIVA = "SOLICITACAO_DEVOLUTIVA"
    DEVOLUTIVA_PROTOCOLO = "DEVOLUTIVA_PROTOCOLO"
    OPERACAO_NO = "OPERACAO_NO"

    TIPOS_TRAMITACAO = frozenset(
        {
            ENTRADA_VEREADOR,
            TRIAGEM_PROTOCOLO,
            RECUSA_PROTOCOLO,
            DESPACHO,
            INICIO_EXECUCAO,
            CONCLUSAO_TECNICA,
            CONCLUSAO_PARCIAL,
            DEVOLUCAO,
            CONCLUSAO_FINAL,
            SOLICITACAO_DEVOLUTIVA,
            DEVOLUTIVA_PROTOCOLO,
            OPERACAO_NO,
        }
    )


class AcaoTriagemProtocolo:
    """Ações disponíveis na triagem de tendências."""

    VINCULAR_SERVICO = "VINCULAR_SERVICO"
    DESPACHO_MANUAL = "DESPACHO_MANUAL"
    RECUSA_VEREADOR = "RECUSA_VEREADOR"


# Alias semântico: conclusão técnica aguardando despacho final do Protocolo.
ESTADO_AGUARDANDO_CONCLUSAO_FINAL = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"

# Alias: etapa livre scatter-gather (valor persistido permanece EM_EXECUCAO).
ESTADO_EM_OPERACAO = "EM_EXECUCAO"


class AcaoNoOperacional:
    DESPACHAR = "DESPACHAR"
    DESPACHAR_ENCERRAR = "DESPACHAR_ENCERRAR"
    ENCERRAR = "ENCERRAR"
