"""Router de banco para o barramento Sinapse.

Regras:
- Models do Sinapse (`CatalogServico`, `CatalogCategoria`, ...) sao
  *somente leitura*; toda escrita pelo SGDL e bloqueada.
- Nenhuma migracao do projeto roda contra a base `sinapse` (managed=False).
- Demais models continuam usando `default`.
"""

from __future__ import annotations

SINAPSE_DB_ALIAS = "sinapse"

_SINAPSE_MODELS = {
    "catalogcategoria",
    "catalogorgao",
    "catalogpublico",
    "catalogtipoatendimento",
    "catalogservico",
    "catalogunidadeadministrativa",
}


def _is_sinapse_model(model) -> bool:
    return (
        getattr(model._meta, "app_label", "") == "integrations"
        and model._meta.model_name in _SINAPSE_MODELS
    )


class SinapseRouter:
    """Direciona leitura de tabelas `catalog_*` para o DB `sinapse`.

    Sem `DATABASE_ROUTERS` configurado, `using('sinapse')` precisa ser
    chamado manualmente — este router torna o roteamento implicito e,
    sobretudo, impede escrita acidental no Sinapse.
    """

    def db_for_read(self, model, **hints):
        if _is_sinapse_model(model):
            return SINAPSE_DB_ALIAS
        return None

    def db_for_write(self, model, **hints):
        if _is_sinapse_model(model):
            # Bloqueia escrita: SGDL nunca grava no barramento.
            return None
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Permite relacoes intra-Sinapse e intra-SGDL; nao mistura.
        sinapse1 = _is_sinapse_model(type(obj1))
        sinapse2 = _is_sinapse_model(type(obj2))
        if sinapse1 and sinapse2:
            return True
        if not sinapse1 and not sinapse2:
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Nenhuma migracao roda no DB do Sinapse.
        if db == SINAPSE_DB_ALIAS:
            return False
        # Os models do Sinapse nao migram em nenhum DB.
        if model_name and model_name in _SINAPSE_MODELS and app_label == "integrations":
            return False
        return None
