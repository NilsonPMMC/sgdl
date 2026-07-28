# /var/www/sgdl/backend/core/signals.py

import logging
import threading

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Demanda, Usuario
from .services.cluster_service import (
    DEMANDA_STATUS_ELEGIVEIS,
    ClusterService,
    embedding_presente,
)
from .services.vector_service import VectorService
from .services.llm_service import LLMService
from .services.triagem_service import TriagemService

# Score minimo de cosseno (Carta de Servicos Sinapse) para preencher
# `ia_categoria` quando o LLM Groq nao tiver dado um valor — modo assistivo
# conforme regra `evolucao-sinapse-mova`: sugestao com validacao humana.
SINAPSE_AUTOFILL_THRESHOLD = 0.6

logger = logging.getLogger(__name__)


def _montar_texto_embedding_demanda(demanda: Demanda) -> str:
    partes: list[str] = []
    if demanda.titulo:
        t = demanda.titulo.strip()
        if t:
            partes.append(t)
    if demanda.descricao:
        d = demanda.descricao.strip()
        if d:
            partes.append(d)
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]}\n\n{partes[1]}"


def _aplicar_embedding_demanda_async(demanda_pk: int) -> None:
    """Pipeline de IA pós-commit: embedding (Kernel) + triagem (Groq).

    Idempotente: cada etapa só roda se o respectivo campo ainda estiver vazio.
    `ia_processado` só vira True se *pelo menos uma* etapa preencheu algo,
    permitindo retry automático no próximo save quando o serviço estiver de volta.
    """
    try:
        demanda = Demanda.objects.get(pk=demanda_pk)
    except Demanda.DoesNotExist:
        logger.warning("Demanda pk=%s não encontrada para pipeline IA.", demanda_pk)
        return

    precisa_embedding = demanda.embedding is None
    precisa_triagem = not (demanda.ia_categoria or "").strip()

    if not precisa_embedding and not precisa_triagem:
        return

    texto = _montar_texto_embedding_demanda(demanda)
    if not texto:
        logger.debug("Demanda pk=%s sem texto utilizável; pulando pipeline IA.", demanda_pk)
        return

    update_fields: list[str] = []

    if precisa_embedding:
        vetor = VectorService().generate_embedding(texto)
        if vetor:
            demanda.embedding = vetor
            update_fields.append("embedding")
        else:
            logger.info("Embedding indisponível agora para demanda pk=%s; retry futuro.", demanda_pk)

    if precisa_triagem:
        dados = LLMService().extrair_entidades(demanda.titulo or "", demanda.descricao or "")
        if dados:
            categoria = (dados.get("categoria_principal") or "").strip()
            sentimento = (dados.get("sentimento_municipe") or "").strip()
            if categoria:
                demanda.ia_categoria = categoria[:100]
                update_fields.append("ia_categoria")
            if sentimento:
                demanda.ia_sentimento = sentimento[:20]
                update_fields.append("ia_sentimento")
        else:
            logger.info("Triagem indisponível agora para demanda pk=%s; retry futuro.", demanda_pk)

    # 3. Triagem cruzada com a Carta de Servicos do Sinapse (modo assistivo).
    #    Roda quando temos um vetor: o resultado fica no log de auditoria;
    #    so preenche `ia_categoria` se ela ainda estiver vazia e o top
    #    score for confiante (>= SINAPSE_AUTOFILL_THRESHOLD).
    vetor_para_triagem = demanda.embedding if demanda.embedding is not None else None
    if vetor_para_triagem is not None:
        try:
            sinapse_top = TriagemService().buscar_servico_sinapse(
                list(vetor_para_triagem), top_k=3
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Triagem Sinapse falhou para demanda pk=%s: %s", demanda_pk, exc
            )
            sinapse_top = []

        if sinapse_top:
            logger.info(
                "Triagem Sinapse demanda pk=%s top=%s",
                demanda_pk,
                [
                    (item["servico_id"], item["titulo"][:40], item["score"])
                    for item in sinapse_top
                ],
            )
            top1 = sinapse_top[0]
            categoria_sinapse = (top1.get("categoria") or "").strip()
            if (
                categoria_sinapse
                and not (demanda.ia_categoria or "").strip()
                and float(top1.get("score", 0.0)) >= SINAPSE_AUTOFILL_THRESHOLD
            ):
                demanda.ia_categoria = categoria_sinapse[:100]
                if "ia_categoria" not in update_fields:
                    update_fields.append("ia_categoria")

    if not update_fields:
        return

    demanda.ia_processado = True
    update_fields.append("ia_processado")
    demanda.save(update_fields=update_fields)

    demanda.refresh_from_db(fields=["status", "sinapse_servico_id", "embedding"])
    if demanda.embedding is not None and demanda.status not in (
        "RASCUNHO",
        "CANCELADO",
    ):
        try:
            ClusterService().atribuir_demanda_pk(int(demanda.pk))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Clusterização falhou para demanda pk=%s: %s", demanda_pk, exc
            )
        try:
            from core.services.fluxo_protocolo_service import FluxoProtocoloService

            if demanda.sinapse_servico_id and demanda.status == "AGUARDANDO_PROTOCOLO":
                FluxoProtocoloService().processar_cohorte_servico(
                    int(demanda.sinapse_servico_id)
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Fluxo automático pós-IA falhou demanda pk=%s: %s", demanda_pk, exc
            )


@receiver(post_save, sender=Demanda)
def demanda_gerar_embedding_post_save(sender, instance, created, **kwargs):
    """Agenda pipeline IA pós-commit em thread daemon (não bloqueia o request)."""
    if not instance.pk:
        return

    precisa_embedding = instance.embedding is None
    precisa_triagem = not (instance.ia_categoria or "").strip()
    if not created and not precisa_embedding and not precisa_triagem:
        return

    demanda_pk = int(instance.pk)

    def _start_worker() -> None:
        threading.Thread(
            target=_aplicar_embedding_demanda_async,
            args=(demanda_pk,),
            daemon=True,
            name=f"demanda-ia-{demanda_pk}",
        ).start()

    transaction.on_commit(_start_worker)


def _clusterizar_demanda_async(demanda_pk: int) -> None:
    try:
        ClusterService().atribuir_demanda_pk(demanda_pk)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Clusterização async demanda pk=%s: %s", demanda_pk, exc)


def _despacho_automatico_async(demanda_pk: int) -> None:
    try:
        from core.services.fluxo_protocolo_service import FluxoProtocoloService

        demanda = Demanda.objects.filter(pk=demanda_pk).values(
            "sinapse_servico_id", "status"
        ).first()
        if (
            demanda
            and demanda["sinapse_servico_id"]
            and demanda["status"] == "AGUARDANDO_PROTOCOLO"
        ):
            FluxoProtocoloService().processar_cohorte_servico(
                int(demanda["sinapse_servico_id"])
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Despacho automático demanda pk=%s: %s", demanda_pk, exc)


@receiver(post_save, sender=Demanda)
def demanda_fluxo_automatico_pos_save(sender, instance, created, **kwargs):
    """Fluxo automático só após embedding (evita protocolar antes do cluster)."""
    if not getattr(instance, "pk", None):
        return
    status_antigo = getattr(instance, "_status_antigo", None)
    if instance.status != "AGUARDANDO_PROTOCOLO":
        return
    if status_antigo == "AGUARDANDO_PROTOCOLO":
        return
    if not embedding_presente(instance.embedding):
        return

    pk = int(instance.pk)
    transaction.on_commit(lambda: _despacho_automatico_async(pk))


@receiver(post_save, sender=Demanda)
def demanda_rascunho_limpa_cluster(sender, instance, **kwargs):
    """Garante desvinculação mesmo em save(update_fields=[...])."""
    if instance.status != "RASCUNHO":
        return
    cluster_id = (
        instance.cluster_id
        or Demanda.objects.filter(pk=instance.pk).values_list("cluster_id", flat=True).first()
    )
    if not cluster_id:
        return
    Demanda.objects.filter(pk=instance.pk).update(cluster=None)
    try:
        ClusterService()._dissolver_cluster_insuficiente(int(cluster_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Falha ao reavaliar cluster pk=%s após rascunho pk=%s: %s",
            cluster_id,
            instance.pk,
            exc,
        )


@receiver(post_save, sender=Demanda)
def demanda_cluster_pos_save(sender, instance, created, **kwargs):
    """Agrupa demandas elegíveis após mudança de status; reavalia fechamento do cluster."""
    if not getattr(instance, "pk", None):
        return

    status_antigo = getattr(instance, "_status_antigo", None)
    status_mudou = status_antigo is not None and status_antigo != instance.status

    if instance.cluster_id:
        cluster_id = int(instance.cluster_id)
        pk = int(instance.pk)
        propagar = status_mudou and not getattr(
            instance, "_propagando_cluster_status", False
        )

        def _pos_cluster() -> None:
            try:
                demanda = Demanda.objects.get(pk=pk)
            except Demanda.DoesNotExist:
                return
            svc = ClusterService()
            if propagar:
                svc.propagar_status_no_cluster(demanda)
            svc.reavaliar_fechamento_cluster(cluster_id)

        transaction.on_commit(_pos_cluster)

    if not embedding_presente(instance.embedding):
        return

    if instance.cluster_id:
        return

    if instance.status not in DEMANDA_STATUS_ELEGIVEIS:
        return

    if not created and not status_mudou:
        return

    pk = int(instance.pk)
    transaction.on_commit(
        lambda: threading.Thread(
            target=_clusterizar_demanda_async,
            args=(pk,),
            daemon=True,
            name=f"demanda-cluster-{pk}",
        ).start()
    )


@receiver(pre_save, sender=Demanda)
def atualizar_dados_demanda_on_status_change(sender, instance, **kwargs):
    """
    Este sinal é executado ANTES de salvar.
    Usamos ele para capturar o status antigo e para definir
    a data de início do prazo.
    """
    status_antigo = None
    if instance.pk:  # Se o objeto já existe (não é uma criação)
        try:
            status_antigo = Demanda.objects.get(pk=instance.pk).status
        except Demanda.DoesNotExist:
            pass  # Deixa status_antigo como None
    
    # Armazena o status antigo na instância para o post_save usar
    instance._status_antigo = status_antigo

    # REGRA DE NEGÓCIO: Se o status está mudando PARA 'PROTOCOLADO',
    # e ele não era 'PROTOCOLADO' antes, iniciamos o relógio do prazo.
    if instance.status == 'PROTOCOLADO' and status_antigo != 'PROTOCOLADO':
        instance.data_inicio_prazo = timezone.now()
        from core.services.prazo_demanda_service import PrazoDemandaService

        PrazoDemandaService().aplicar_snapshot_protocolo(instance)
        logger.debug("Data de início de prazo definida para demanda %s", instance.id)

    if status_antigo != instance.status or not instance.data_entrada_etapa:
        instance.data_entrada_etapa = timezone.now()

    if instance.status == "RASCUNHO":
        instance.cluster = None


@receiver(post_save, sender=Demanda)
def notificar_eventos_demanda(sender, instance, created, **kwargs):
    """
    Este sinal é executado DEPOIS de salvar.
    Usamos ele apenas para ENVIAR NOTIFICAÇÕES.
    """
    from core.services.notificacao_service import NotificacaoService

    svc = NotificacaoService()
    status_antigo = getattr(instance, '_status_antigo', None)

    # 1. FLUXO DE CRIAÇÃO (Rascunho)
    # Não faz nada, pois o 'envio' é uma atualização de status.
    if created:
        return

    # Se o status não mudou, não faz nada.
    if status_antigo is None or status_antigo == instance.status:
        return

    # --- SÓ EXECUTAMOS NOTIFICAÇÕES SE O STATUS MUDOU ---
    # 1. NOVO OFÍCIO: Vereador envia para o Protocolo
    if instance.status == 'AGUARDANDO_PROTOCOLO':
        from core.services.fluxo_protocolo_service import FluxoProtocoloService

        if FluxoProtocoloService().despacho_automatico_habilitado(instance):
            return

        svc.notificar_oficio_enviado(instance)

    # 2. OFÍCIO PROTOCOLADO: despacho inicial → vereador + setores envolvidos
    elif instance.status == 'PROTOCOLADO':
        from integrations import sinapse_catalog

        orgao_nome = ""
        if instance.sinapse_orgao_id:
            orgao_nome = (
                sinapse_catalog.get_orgao_nome(int(instance.sinapse_orgao_id))
                or str(instance.sinapse_orgao_id)
            )
        if not getattr(instance, "_notificacao_super_os_lote", False):
            svc.notificar_despacho_inicial(instance, orgao_nome=orgao_nome)
        svc.notificar_despacho_inicial_setores(instance)

    # 3–6: demais transições não disparam notificação automática nesta matriz
    # (vereador só recebe conclusão em FINALIZADO; protocolo via gather/SLA/cluster)

    elif instance.status == 'FINALIZADO':
        svc.notificar_conclusao_final(instance)
        from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

        AcompanhamentoDemandaService().encerrar_acompanhamentos_demanda(instance)

    elif instance.status == 'DEVOLVIDO_VEREADOR':
        from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

        AcompanhamentoDemandaService().encerrar_acompanhamentos_demanda(instance)


@receiver(post_save, sender=Usuario)
def sincronizar_vinculo_usuario_por_perfil(sender, instance: Usuario, **kwargs):
    """U2/U4: vínculos automáticos por perfil (Protocolo, Gestor)."""
    from core.services.usuario_vinculo_service import UsuarioVinculoService

    service = UsuarioVinculoService()
    if instance.perfil == "PROTOCOLO":
        service.sincronizar_protocolo(instance)
    elif instance.perfil == "GESTOR":
        service.sincronizar_gestor(instance)