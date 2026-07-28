"""Vínculos institucionais de usuários por perfil (U2 Protocolo, U3 Secretaria)."""

from __future__ import annotations

import logging

from django.db import transaction

from core.models import Usuario
from core.models_unidade_administrativa import (
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from core.services.tramitacao_setor_service import UnidadeAdministrativaService
from core.services.gestor_escopo import (
    TIPO_GERAL,
    TIPO_SETORIAL,
    orgaos_escopo_gestor,
    privilegios_django_gestor,
    tipo_gestor,
)
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)

# Secretaria de Governo e Transparência — Protocolo Geral (spec U2)
PROTOCOLO_SINAPSE_ORGAO_ID = 12
PROTOCOLO_UNIDADE_PK = 754
PROTOCOLO_UNIDADE_SIGLA = "MCRUZ-SMGOV-SGAC"
PROTOCOLO_UNIDADE_SINAPSE_ID = 110004543


class UsuarioVinculoService:
    def ids_unidades_ativas(self, usuario: Usuario) -> list[int]:
        return UnidadeAdministrativaService().ids_unidades_do_usuario(usuario)

    def _setores_do_usuario(self, usuario: Usuario) -> list[dict]:
        ids = self.ids_unidades_ativas(usuario)
        if not ids:
            return []
        return [
            {
                "id": u.pk,
                "sigla": u.sigla,
                "nome": u.nome,
                "rotulo": (u.sigla or u.nome).strip(),
                "sinapse_orgao_id": u.sinapse_orgao_id,
            }
            for u in UnidadeAdministrativa.objects.filter(pk__in=ids).order_by("nome")
        ]

    @staticmethod
    def _resumo_orgao_setor(orgao_nome: str | None, setores: list[dict], *, fallback: str = "—") -> str:
        if not orgao_nome:
            return fallback
        if not setores:
            return orgao_nome
        if len(setores) == 1:
            return f"{orgao_nome} › {setores[0]['rotulo']}"
        rotulos = ", ".join(s["rotulo"] for s in setores[:3])
        extra = f" (+{len(setores) - 3})" if len(setores) > 3 else ""
        return f"{orgao_nome} › {rotulos}{extra}"

    def atuacao_sgdl(self, usuario: Usuario) -> dict:
        """Perfil + Órgão (Sinapse) + Setor (UA) = onde o usuário atua no SGDL."""
        perfil = getattr(usuario, "perfil", None) or ""
        setores = self._setores_do_usuario(usuario) if perfil != "VEREADOR" else []

        if perfil == "VEREADOR":
            return {
                "perfil": perfil,
                "requer_orgao": False,
                "requer_setor": False,
                "orgao_id": None,
                "orgao_nome": None,
                "setores": [],
                "resumo": "Legislativo — sem órgão/setor",
                "escopo": "Copiloto e demandas próprias (autor)",
                "completa": True,
            }

        if perfil == "PROTOCOLO":
            org_id = PROTOCOLO_SINAPSE_ORGAO_ID
            org_nome = sinapse_catalog.get_orgao_nome(org_id) or f"Órgão {org_id}"
            ua = self.resolver_unidade_protocolo()
            setor_ref = (
                [{"id": ua.pk, "sigla": ua.sigla, "nome": ua.nome, "rotulo": ua.sigla or ua.nome}]
                if ua
                else []
            )
            setores_exibir = setores or setor_ref
            st = self.status_vinculo_protocolo(usuario)
            return {
                "perfil": perfil,
                "requer_orgao": True,
                "requer_setor": True,
                "orgao_id": org_id,
                "orgao_nome": org_nome,
                "setores": setores_exibir,
                "resumo": self._resumo_orgao_setor(org_nome, setores_exibir, fallback=org_nome),
                "escopo": "Protocolo geral — triagem, clusters e filas institucionais",
                "completa": bool(st.get("completo")),
            }

        if perfil == "SECRETARIA":
            org_id = usuario.sinapse_orgao_id
            org_nome = sinapse_catalog.get_orgao_nome(org_id) if org_id else None
            st = self.status_vinculo_secretaria(usuario)
            return {
                "perfil": perfil,
                "requer_orgao": True,
                "requer_setor": True,
                "orgao_id": org_id,
                "orgao_nome": org_nome,
                "setores": setores,
                "resumo": self._resumo_orgao_setor(
                    org_nome,
                    setores,
                    fallback="Definir órgão › setor",
                ),
                "escopo": "Operação da secretaria — fila do setor e demandas do órgão",
                "completa": bool(st.get("completo")),
            }

        if perfil == "GESTOR":
            org_id = usuario.sinapse_orgao_id
            org_nome = sinapse_catalog.get_orgao_nome(org_id) if org_id else None
            st = self.status_vinculo_gestor(usuario)
            tipo = st.get("tipo_gestor") or TIPO_GERAL
            if tipo == TIPO_GERAL:
                resumo = "Todo o sistema"
                escopo = "Gestor Geral — acesso pleno e CRUD administrativo"
            else:
                resumo = self._resumo_orgao_setor(
                    org_nome,
                    setores,
                    fallback="Escopo setorial",
                )
                escopo = "Gestor Setorial — dados e tramitações do escopo vinculado"
            return {
                "perfil": perfil,
                "tipo_gestor": tipo,
                "requer_orgao": False,
                "requer_setor": False,
                "orgao_id": org_id,
                "orgao_nome": org_nome,
                "setores": setores,
                "resumo": resumo,
                "escopo": escopo,
                "completa": bool(st.get("admin_pleno") or tipo == TIPO_SETORIAL),
                "referencia_institucional": tipo == TIPO_SETORIAL,
            }

        return {
            "perfil": perfil,
            "requer_orgao": False,
            "requer_setor": False,
            "orgao_id": usuario.sinapse_orgao_id,
            "orgao_nome": sinapse_catalog.get_orgao_nome(usuario.sinapse_orgao_id)
            if usuario.sinapse_orgao_id
            else None,
            "setores": setores,
            "resumo": "—",
            "escopo": "",
            "completa": True,
        }

    def status_vinculo_secretaria(self, usuario: Usuario) -> dict:
        if getattr(usuario, "perfil", None) != "SECRETARIA":
            return {
                "aplicavel": False,
                "completo": True,
                "falta_orgao": False,
                "falta_setores": False,
                "unidade_ids": [],
                "avisos": [],
            }

        avisos: list[str] = []
        falta_orgao = not usuario.sinapse_orgao_id
        unidade_ids = self.ids_unidades_ativas(usuario)
        falta_setores = not unidade_ids

        if falta_orgao:
            avisos.append("Órgão (secretaria) não vinculado ao usuário.")
        if falta_setores:
            avisos.append("Nenhum setor vinculado ao usuário.")

        return {
            "aplicavel": True,
            "completo": not avisos,
            "falta_orgao": falta_orgao,
            "falta_setores": falta_setores,
            "unidade_ids": unidade_ids,
            "avisos": avisos,
        }

    def status_vinculo_protocolo(self, usuario: Usuario) -> dict:
        if getattr(usuario, "perfil", None) != "PROTOCOLO":
            return {
                "aplicavel": False,
                "completo": True,
                "unidade_ids": [],
                "avisos": [],
            }

        unidade_ids = self.ids_unidades_ativas(usuario)
        ua = self.resolver_unidade_protocolo()
        avisos: list[str] = []
        if usuario.sinapse_orgao_id != PROTOCOLO_SINAPSE_ORGAO_ID:
            avisos.append(f"Órgão esperado: {PROTOCOLO_SINAPSE_ORGAO_ID} (SMGOV).")
        if ua and ua.pk not in unidade_ids:
            avisos.append("Responsável UA SGAC (754) não vinculado.")

        return {
            "aplicavel": True,
            "completo": not avisos,
            "unidade_ids": unidade_ids,
            "ua_referencia_id": ua.pk if ua else None,
            "avisos": avisos,
        }

    def resolver_unidade_protocolo(self) -> UnidadeAdministrativa | None:
        """Localiza a UA SGAC (Protocolo Geral) na base importada RM."""
        try:
            ua = UnidadeAdministrativa.objects.get(pk=PROTOCOLO_UNIDADE_PK)
            if int(ua.sinapse_orgao_id) == PROTOCOLO_SINAPSE_ORGAO_ID:
                return ua
            logger.warning(
                "UA pk=%s existe mas sinapse_orgao_id=%s (esperado %s).",
                PROTOCOLO_UNIDADE_PK,
                ua.sinapse_orgao_id,
                PROTOCOLO_SINAPSE_ORGAO_ID,
            )
        except UnidadeAdministrativa.DoesNotExist:
            pass

        ua = (
            UnidadeAdministrativa.objects.filter(
                sinapse_orgao_id=PROTOCOLO_SINAPSE_ORGAO_ID,
                sigla__iexact=PROTOCOLO_UNIDADE_SIGLA,
            )
            .order_by("pk")
            .first()
        )
        if ua:
            return ua

        return (
            UnidadeAdministrativa.objects.filter(
                sinapse_unidade_id=PROTOCOLO_UNIDADE_SINAPSE_ID,
            )
            .order_by("pk")
            .first()
        )

    @transaction.atomic
    def sincronizar_protocolo(self, usuario: Usuario) -> dict:
        """Garante órgão 12 e responsável na UA SGAC para perfil PROTOCOLO."""
        if getattr(usuario, "perfil", None) != "PROTOCOLO":
            return {
                "orgao_atualizado": False,
                "responsavel_criado": False,
                "unidade_encontrada": False,
            }

        orgao_atualizado = False
        if usuario.sinapse_orgao_id != PROTOCOLO_SINAPSE_ORGAO_ID:
            Usuario.objects.filter(pk=usuario.pk).update(
                sinapse_orgao_id=PROTOCOLO_SINAPSE_ORGAO_ID
            )
            orgao_atualizado = True

        unidade = self.resolver_unidade_protocolo()
        responsavel_criado = False
        if unidade:
            _, created = UnidadeAdministrativaResponsavel.objects.update_or_create(
                unidade=unidade,
                usuario_id=usuario.pk,
                defaults={"ativo": True, "pode_tramitar": True},
            )
            responsavel_criado = created
        else:
            logger.warning(
                "UA Protocolo (SGAC) não encontrada; usuário pk=%s ficou só com órgão %s.",
                usuario.pk,
                PROTOCOLO_SINAPSE_ORGAO_ID,
            )

        return {
            "orgao_atualizado": orgao_atualizado,
            "responsavel_criado": responsavel_criado,
            "unidade_encontrada": unidade is not None,
            "unidade_id": unidade.pk if unidade else None,
        }

    def sincronizar_todos_protocolo(self) -> list[dict]:
        """Aplica vínculo em todos os usuários PROTOCOLO existentes."""
        resultados = []
        for usuario in Usuario.objects.filter(perfil="PROTOCOLO").order_by("pk"):
            info = self.sincronizar_protocolo(usuario)
            info["usuario_id"] = usuario.pk
            info["username"] = usuario.username
            resultados.append(info)
        return resultados

    @transaction.atomic
    def sincronizar_gestor(
        self,
        usuario: Usuario,
        *,
        sinapse_orgao_id: int | None = None,
        unidade_ids: list[int] | None = None,
        limpar_referencia: bool = False,
    ) -> dict:
        """Garante privilégios Django e metadados institucionais (U4/U7)."""
        if getattr(usuario, "perfil", None) != "GESTOR":
            raise ValueError("Vínculo de gestor aplica-se apenas ao perfil GESTOR.")

        updates: dict = {}
        if limpar_referencia:
            updates["sinapse_orgao_id"] = None
        elif sinapse_orgao_id is not None:
            updates["sinapse_orgao_id"] = (
                self._validar_orgao_secretaria(sinapse_orgao_id) if sinapse_orgao_id else None
            )

        if updates:
            Usuario.objects.filter(pk=usuario.pk).update(**updates)
            usuario.refresh_from_db()

        if unidade_ids is not None:
            if unidade_ids:
                orgao_ref = sinapse_orgao_id if sinapse_orgao_id is not None else usuario.sinapse_orgao_id
                if not orgao_ref:
                    raise ValueError(
                        "Informe o órgão de referência antes de vincular setor(es) ao gestor."
                    )
                unidades = self._validar_unidades_secretaria(int(orgao_ref), unidade_ids)
                ids_finais = [u.pk for u in unidades]
                for unidade in unidades:
                    UnidadeAdministrativaResponsavel.objects.update_or_create(
                        unidade=unidade,
                        usuario_id=usuario.pk,
                        defaults={"ativo": True, "pode_tramitar": True},
                    )
                UnidadeAdministrativaResponsavel.objects.filter(
                    usuario_id=usuario.pk,
                    ativo=True,
                ).exclude(unidade_id__in=ids_finais).update(ativo=False)
            else:
                UnidadeAdministrativaResponsavel.objects.filter(
                    usuario_id=usuario.pk,
                    ativo=True,
                ).update(ativo=False)

        usuario.refresh_from_db()
        priv = privilegios_django_gestor(usuario)
        priv_updates = {}
        if usuario.is_staff != priv["is_staff"]:
            priv_updates["is_staff"] = priv["is_staff"]
        if usuario.is_superuser != priv["is_superuser"]:
            priv_updates["is_superuser"] = priv["is_superuser"]
        if priv_updates:
            Usuario.objects.filter(pk=usuario.pk).update(**priv_updates)
            usuario.refresh_from_db()

        return self.status_vinculo_gestor(usuario)

    def status_vinculo_gestor(self, usuario: Usuario) -> dict:
        if getattr(usuario, "perfil", None) != "GESTOR":
            return {
                "aplicavel": False,
                "admin_pleno": False,
                "referencia_orgao": False,
                "referencia_unidades": False,
                "recomendado_pendente": False,
                "unidade_ids": [],
                "avisos": [],
            }

        unidade_ids = self.ids_unidades_ativas(usuario)
        tipo = tipo_gestor(usuario) or TIPO_GERAL
        admin_pleno = bool(
            tipo == TIPO_GERAL and usuario.is_staff and usuario.is_superuser
        )
        avisos: list[str] = []
        if tipo == TIPO_GERAL and not admin_pleno:
            avisos.append("Privilégios Django Admin incompletos (is_staff/is_superuser).")
        if tipo == TIPO_SETORIAL and usuario.is_superuser:
            avisos.append("Gestor setorial não deve ter superuser — será corrigido na sincronização.")
        if tipo == TIPO_GERAL and (usuario.sinapse_orgao_id or unidade_ids):
            avisos.append(
                "Gestor com vínculo org/setor é classificado como Setorial — remova vínculos para Geral."
            )

        return {
            "aplicavel": True,
            "tipo_gestor": tipo,
            "admin_pleno": admin_pleno,
            "referencia_orgao": bool(usuario.sinapse_orgao_id),
            "referencia_unidades": bool(unidade_ids),
            "orgaos_escopo": orgaos_escopo_gestor(usuario),
            "recomendado_pendente": False,
            "unidade_ids": unidade_ids,
            "avisos": avisos,
        }

    def sincronizar_todos_gestor(self) -> list[dict]:
        resultados = []
        for usuario in Usuario.objects.filter(perfil="GESTOR").order_by("pk"):
            info = self.sincronizar_gestor(usuario)
            info["usuario_id"] = usuario.pk
            info["username"] = usuario.username
            resultados.append(info)
        return resultados

    def _validar_orgao_secretaria(self, sinapse_orgao_id: int) -> int:
        orgao_id = int(sinapse_orgao_id)
        if sinapse_catalog.catalog_disponivel() and not sinapse_catalog.orgao_existe(orgao_id):
            raise ValueError("Órgão não encontrado no catálogo Sinapse.")
        return orgao_id

    def _validar_unidades_secretaria(
        self,
        sinapse_orgao_id: int,
        unidade_ids: list[int],
    ) -> list[UnidadeAdministrativa]:
        if not unidade_ids:
            raise ValueError("Informe ao menos um setor para o usuário de secretaria.")
        ids_unicos = sorted({int(x) for x in unidade_ids})
        unidades = list(
            UnidadeAdministrativa.objects.filter(pk__in=ids_unicos, ativo=True)
        )
        if len(unidades) != len(ids_unicos):
            raise ValueError("Um ou mais setores não foram encontrados ou estão inativos.")
        orgao_id = int(sinapse_orgao_id)
        for unidade in unidades:
            if int(unidade.sinapse_orgao_id) != orgao_id:
                rotulo = unidade.sigla or unidade.nome
                raise ValueError(
                    f"O setor «{rotulo}» não pertence ao órgão selecionado."
                )
        return unidades

    @transaction.atomic
    def sincronizar_secretaria(
        self,
        usuario: Usuario,
        *,
        sinapse_orgao_id: int,
        unidade_ids: list[int],
    ) -> dict:
        """Define órgão e setores responsáveis para perfil SECRETARIA."""
        if getattr(usuario, "perfil", None) != "SECRETARIA":
            raise ValueError("Vínculo de secretaria aplica-se apenas ao perfil SECRETARIA.")

        orgao_id = self._validar_orgao_secretaria(sinapse_orgao_id)
        unidades = self._validar_unidades_secretaria(orgao_id, unidade_ids)
        ids_finais = [u.pk for u in unidades]

        if usuario.sinapse_orgao_id != orgao_id:
            Usuario.objects.filter(pk=usuario.pk).update(sinapse_orgao_id=orgao_id)

        for unidade in unidades:
            UnidadeAdministrativaResponsavel.objects.update_or_create(
                unidade=unidade,
                usuario_id=usuario.pk,
                defaults={"ativo": True, "pode_tramitar": True},
            )

        UnidadeAdministrativaResponsavel.objects.filter(
            usuario_id=usuario.pk,
            ativo=True,
        ).exclude(unidade_id__in=ids_finais).update(ativo=False)

        usuario.refresh_from_db()
        return self.status_vinculo_secretaria(usuario)
