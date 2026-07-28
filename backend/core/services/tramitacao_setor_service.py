"""Tramitação operacional entre setores (intra e transversal)."""

from __future__ import annotations

import logging

from django.utils import timezone

from core.models import Demanda, Tramitacao
from core.models_unidade_administrativa import (
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)

_STATUS_OPERACIONAIS = frozenset({"PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA"})


class TramitacaoSetorService:
    def usuario_pode_gerir_unidades(self, usuario) -> bool:
        perfil = getattr(usuario, "perfil", None)
        return bool(usuario and (usuario.is_staff or perfil in ("GESTOR", "PROTOCOLO")))

    def usuario_pode_tramitar(self, usuario, unidade: UnidadeAdministrativa | None) -> bool:
        if self.usuario_pode_gerir_unidades(usuario):
            return True
        if not unidade or not usuario or not usuario.is_authenticated:
            return False
        return UnidadeAdministrativaResponsavel.objects.filter(
            unidade=unidade,
            usuario=usuario,
            ativo=True,
            pode_tramitar=True,
        ).exists()

    def encaminhar(
        self,
        demanda: Demanda,
        *,
        unidade_destino_id: int,
        usuario,
        observacao: str = "",
    ) -> Demanda:
        if demanda.status not in _STATUS_OPERACIONAIS:
            raise ValueError(
                "Apenas demandas em operação (protocoladas ou em execução) podem ser encaminhadas."
            )

        try:
            destino = UnidadeAdministrativa.objects.get(pk=int(unidade_destino_id), ativo=True)
        except (UnidadeAdministrativa.DoesNotExist, TypeError, ValueError):
            raise ValueError("Setor de destino não encontrado ou inativo.")

        origem = demanda.unidade_administrativa
        if origem and origem.pk == destino.pk:
            raise ValueError("A demanda já está neste setor.")

        if not self.usuario_pode_tramitar(usuario, origem) and not self.usuario_pode_tramitar(
            usuario, destino
        ):
            if getattr(usuario, "perfil", None) == "SECRETARIA":
                if usuario.sinapse_orgao_id != demanda.sinapse_orgao_id:
                    raise ValueError("Sem permissão para encaminhar demandas de outro órgão.")
            else:
                raise ValueError("Sem permissão para encaminhar para este setor.")

        orgao_antigo = demanda.sinapse_orgao_id
        orgao_novo = destino.sinapse_orgao_id
        if orgao_novo and not sinapse_catalog.orgao_existe(int(orgao_novo)):
            raise ValueError("Órgão do setor de destino não encontrado no catálogo Sinapse.")

        demanda.unidade_administrativa = destino
        update_fields = ["unidade_administrativa"]
        if orgao_novo and orgao_novo != orgao_antigo:
            demanda.sinapse_orgao_id = orgao_novo
            update_fields.append("sinapse_orgao_id")
        demanda.save(update_fields=update_fields)

        origem_nome = origem.sigla or origem.nome if origem else "—"
        destino_nome = destino.sigla or destino.nome
        orgao_dest_nome = sinapse_catalog.get_orgao_nome(orgao_novo) or str(orgao_novo)
        transversal = orgao_antigo and orgao_novo and int(orgao_antigo) != int(orgao_novo)
        trecho_transversal = (
            f" (tramitação transversal: {sinapse_catalog.get_orgao_nome(orgao_antigo) or orgao_antigo} → {orgao_dest_nome})"
            if transversal
            else ""
        )
        texto_obs = (observacao or "").strip()
        descricao = (
            f"Encaminhamento operacional: {origem_nome} → {destino_nome}{trecho_transversal}."
        )
        if texto_obs:
            descricao += f"\nObservação: {texto_obs}"

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="ENCAMINHAMENTO_SETOR",
            descricao=descricao,
            unidade_origem=origem,
            unidade_destino=destino,
        )

        logger.info(
            "Demanda pk=%s encaminhada setor %s → %s por usuario=%s",
            demanda.pk,
            origem.pk if origem else None,
            destino.pk,
            getattr(usuario, "pk", None),
        )
        return demanda


class UnidadeAdministrativaService:
    def listar_por_orgao(self, sinapse_orgao_id: int | None = None, *, ativo: bool | None = True):
        qs = UnidadeAdministrativa.objects.all().order_by("nome")
        if sinapse_orgao_id is not None:
            qs = qs.filter(sinapse_orgao_id=int(sinapse_orgao_id))
        if ativo is not None:
            qs = qs.filter(ativo=ativo)
        return qs

    def criar(
        self,
        *,
        sinapse_orgao_id: int,
        nome: str,
        sigla: str = "",
        sinapse_unidade_id: int | None = None,
    ) -> UnidadeAdministrativa:
        orgao_id = int(sinapse_orgao_id)
        if not sinapse_catalog.orgao_existe(orgao_id):
            raise ValueError("Órgão não encontrado no catálogo Sinapse.")
        nome_limpo = (nome or "").strip()
        if not nome_limpo:
            raise ValueError("Nome do setor é obrigatório.")
        sigla_l = (sigla or "").strip().upper()
        if sigla_l and UnidadeAdministrativa.objects.filter(
            sinapse_orgao_id=orgao_id, sigla__iexact=sigla_l
        ).exists():
            raise ValueError("Já existe setor com esta sigla neste órgão.")
        return UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=orgao_id,
            nome=nome_limpo,
            sigla=sigla_l,
            sinapse_unidade_id=sinapse_unidade_id,
        )

    def vincular_responsavel(
        self,
        unidade: UnidadeAdministrativa,
        usuario,
        *,
        pode_tramitar: bool = True,
    ) -> UnidadeAdministrativaResponsavel:
        if not unidade.ativo:
            raise ValueError("Setor inativo.")
        if getattr(usuario, "perfil", None) not in ("SECRETARIA", "GESTOR", "PROTOCOLO"):
            raise ValueError("Usuário deve ter perfil operacional (Secretaria, Protocolo ou Gestor).")
        if (
            getattr(usuario, "perfil", None) == "SECRETARIA"
            and usuario.sinapse_orgao_id
            and int(usuario.sinapse_orgao_id) != int(unidade.sinapse_orgao_id)
        ):
            raise ValueError("Usuário de secretaria deve pertencer ao mesmo órgão do setor.")
        obj, _ = UnidadeAdministrativaResponsavel.objects.update_or_create(
            unidade=unidade,
            usuario=usuario,
            defaults={"ativo": True, "pode_tramitar": pode_tramitar},
        )
        return obj

    def unidade_principal_usuario(self, usuario) -> UnidadeAdministrativa | None:
        ids = self.ids_unidades_do_usuario(usuario)
        if not ids:
            return None
        return UnidadeAdministrativa.objects.filter(pk=ids[0]).first()

    def ids_unidades_do_usuario(self, usuario) -> list[int]:
        return list(
            UnidadeAdministrativaResponsavel.objects.filter(
                usuario=usuario,
                ativo=True,
            ).values_list("unidade_id", flat=True)
        )

    def estatisticas_vinculos(self, unidade: UnidadeAdministrativa) -> dict[str, int]:
        from core.models import Demanda
        from core.models_carta_otimizada import ServicoOtimizado

        demandas_qs = Demanda.objects.filter(unidade_administrativa=unidade)
        status_aberto = [
            "AGUARDANDO_PROTOCOLO",
            "PROTOCOLADO",
            "EM_EXECUCAO",
            "AGUARDANDO_TRANSFERENCIA",
            "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
            "DEVOLVIDO_VEREADOR",
        ]
        return {
            "demandas": demandas_qs.count(),
            "demandas_abertas": demandas_qs.filter(status__in=status_aberto).count(),
            "servicos_carta": ServicoOtimizado.objects.filter(
                unidade_administrativa=unidade, ativo=True
            ).count(),
            "responsaveis": unidade.responsaveis.filter(ativo=True).count(),
        }

    def excluir_com_redirecionamento(
        self,
        unidade: UnidadeAdministrativa,
        *,
        unidade_destino_id: int | None = None,
    ) -> dict[str, int | str | None]:
        from core.models import Demanda
        from core.models_carta_otimizada import ServicoOtimizado

        stats = self.estatisticas_vinculos(unidade)
        precisa_destino = stats["demandas"] > 0 or stats["servicos_carta"] > 0
        destino: UnidadeAdministrativa | None = None

        if precisa_destino:
            if not unidade_destino_id:
                raise ValueError(
                    "Informe o setor de destino para redirecionar demandas e vínculos da carta."
                )
            try:
                destino = UnidadeAdministrativa.objects.get(
                    pk=int(unidade_destino_id), ativo=True
                )
            except (UnidadeAdministrativa.DoesNotExist, TypeError, ValueError):
                raise ValueError("Setor de destino não encontrado ou inativo.")
            if destino.pk == unidade.pk:
                raise ValueError("O setor de destino deve ser diferente do setor excluído.")

        demandas_movidas = 0
        servicos_movidos = 0
        if destino:
            demandas_movidas = Demanda.objects.filter(unidade_administrativa=unidade).update(
                unidade_administrativa=destino
            )
            servicos_movidos = ServicoOtimizado.objects.filter(
                unidade_administrativa=unidade
            ).update(unidade_administrativa=destino)

        UnidadeAdministrativaResponsavel.objects.filter(unidade=unidade).update(ativo=False)
        excluido_id = unidade.pk
        nome = unidade.nome
        destino_id = destino.pk if destino else None
        destino_nome = (destino.sigla or destino.nome) if destino else None
        unidade.delete()

        return {
            "excluido_id": excluido_id,
            "nome": nome,
            "demandas_redirecionadas": demandas_movidas,
            "servicos_carta_redirecionados": servicos_movidos,
            "unidade_destino_id": destino_id,
            "unidade_destino_nome": destino_nome,
        }
