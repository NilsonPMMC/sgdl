"""Formulários do admin com vínculo ao catálogo Sinapse (select + validação)."""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError

from core.models import Demanda, Usuario
from core.services.usuario_vinculo_service import PROTOCOLO_SINAPSE_ORGAO_ID
from integrations import sinapse_catalog

_EMPTY = ("", "---------")


def _coerce_optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


class SinapseOrgaoChoiceField(forms.TypedChoiceField):
    def __init__(self, *, required: bool = False, include_id: int | None = None, **kwargs):
        kwargs.setdefault("coerce", _coerce_optional_int)
        kwargs.setdefault("empty_value", None)
        kwargs.setdefault("required", required)
        kwargs.setdefault("widget", forms.Select(attrs={"class": "sinapse-catalog-select"}))
        super().__init__(choices=[_EMPTY], **kwargs)
        self._include_id = include_id
        self._refresh_choices()

    def _refresh_choices(self) -> None:
        self.choices = [_EMPTY] + sinapse_catalog.choices_orgaos(
            include_id=self._include_id,
        )


class SinapseServicoChoiceField(forms.TypedChoiceField):
    def __init__(self, *, orgao_id: int | None = None, include_id: int | None = None, **kwargs):
        kwargs.setdefault("coerce", _coerce_optional_int)
        kwargs.setdefault("empty_value", None)
        kwargs.setdefault("required", False)
        kwargs.setdefault("widget", forms.Select(attrs={"class": "sinapse-catalog-select"}))
        super().__init__(choices=[_EMPTY], **kwargs)
        self.orgao_id = orgao_id
        self._include_id = include_id
        self._refresh_choices()

    def _refresh_choices(self) -> None:
        self.choices = [_EMPTY] + sinapse_catalog.choices_servicos(
            orgao_id=self.orgao_id,
            include_id=self._include_id,
        )


class DemandaAdminForm(forms.ModelForm):
    class Meta:
        model = Demanda
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        orgao_id = self._orgao_id_from_form()
        servico_id = self._servico_id_from_instance_or_form()

        self.fields["sinapse_orgao_id"] = SinapseOrgaoChoiceField(
            include_id=orgao_id,
        )
        self.fields["sinapse_servico_id"] = SinapseServicoChoiceField(
            orgao_id=orgao_id,
            include_id=servico_id,
        )

        if not sinapse_catalog.catalog_disponivel():
            for name in ("sinapse_orgao_id", "sinapse_servico_id"):
                self.fields[name].disabled = True
                self.fields[name].help_text = (
                    "Catálogo Sinapse indisponível (verifique DATABASES['sinapse'])."
                )

    def _orgao_id_from_form(self) -> int | None:
        if self.data.get("sinapse_orgao_id") not in (None, ""):
            try:
                return int(self.data["sinapse_orgao_id"])
            except (TypeError, ValueError):
                pass
        if self.instance.pk and self.instance.sinapse_orgao_id:
            return int(self.instance.sinapse_orgao_id)
        return None

    def _servico_id_from_instance_or_form(self) -> int | None:
        if self.data.get("sinapse_servico_id") not in (None, ""):
            try:
                return int(self.data["sinapse_servico_id"])
            except (TypeError, ValueError):
                pass
        if self.instance.pk and self.instance.sinapse_servico_id:
            return int(self.instance.sinapse_servico_id)
        return None

    def clean(self):
        cleaned = super().clean()
        if not sinapse_catalog.catalog_disponivel():
            return cleaned

        servico_id = cleaned.get("sinapse_servico_id")
        orgao_id = cleaned.get("sinapse_orgao_id")

        if servico_id is not None and not sinapse_catalog.servico_existe(servico_id):
            self.add_error(
                "sinapse_servico_id",
                ValidationError("Serviço não encontrado no catálogo Sinapse."),
            )

        if orgao_id is not None and not sinapse_catalog.orgao_existe(orgao_id):
            self.add_error(
                "sinapse_orgao_id",
                ValidationError("Órgão não encontrado no catálogo Sinapse."),
            )

        if servico_id and orgao_id:
            orgao_do_servico = sinapse_catalog.get_orgao_id_for_servico(servico_id)
            if orgao_do_servico and int(orgao_id) != int(orgao_do_servico):
                self.add_error(
                    "sinapse_orgao_id",
                    ValidationError(
                        "O órgão selecionado não é o responsável por este serviço na carta Sinapse."
                    ),
                )
        elif servico_id and not orgao_id:
            cleaned["sinapse_orgao_id"] = sinapse_catalog.get_orgao_id_for_servico(servico_id)

        return cleaned


def _validar_orgao_id(orgao_id: int | None) -> int | None:
    if orgao_id is None:
        return None
    if not sinapse_catalog.catalog_disponivel():
        return orgao_id
    if not sinapse_catalog.orgao_existe(orgao_id):
        raise ValidationError("Órgão não encontrado no catálogo Sinapse.")
    return orgao_id


def _attach_orgao_select(form: forms.ModelForm) -> None:
    include_id = None
    if form.instance.pk and form.instance.sinapse_orgao_id:
        include_id = int(form.instance.sinapse_orgao_id)
    elif form.data.get("sinapse_orgao_id") not in (None, ""):
        try:
            include_id = int(form.data["sinapse_orgao_id"])
        except (TypeError, ValueError):
            pass

    form.fields["sinapse_orgao_id"] = SinapseOrgaoChoiceField(include_id=include_id)
    if not sinapse_catalog.catalog_disponivel():
        form.fields["sinapse_orgao_id"].disabled = True
        form.fields["sinapse_orgao_id"].help_text = (
            "Catálogo Sinapse indisponível (verifique DATABASES['sinapse'])."
        )


        form.fields["sinapse_orgao_id"].help_text = (
            "Catálogo Sinapse indisponível (verifique DATABASES['sinapse'])."
        )


class UsuarioAdminForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _attach_orgao_select(self)
        perfil = getattr(self.instance, "perfil", None)
        if perfil == "PROTOCOLO" and "sinapse_orgao_id" in self.fields:
            self.fields["sinapse_orgao_id"].disabled = True
            self.fields["sinapse_orgao_id"].help_text = (
                f"Definido automaticamente para órgão {PROTOCOLO_SINAPSE_ORGAO_ID} (Protocolo Geral)."
            )
        elif perfil == "GESTOR" and "sinapse_orgao_id" in self.fields:
            self.fields["sinapse_orgao_id"].help_text = (
                "Opcional — metadado institucional; não limita o escopo do gestor."
            )
            if "is_staff" in self.fields:
                self.fields["is_staff"].disabled = True
            if "is_superuser" in self.fields:
                self.fields["is_superuser"].disabled = True
        elif perfil == "SECRETARIA" and "sinapse_orgao_id" in self.fields:
            self.fields["sinapse_orgao_id"].help_text = (
                "Obrigatório — vincule setor(es) na seção abaixo após salvar."
            )

    def clean_sinapse_orgao_id(self):
        return _validar_orgao_id(self.cleaned_data.get("sinapse_orgao_id"))

    def clean(self):
        cleaned = super().clean()
        perfil = cleaned.get("perfil")
        if perfil == "PROTOCOLO":
            cleaned["sinapse_orgao_id"] = PROTOCOLO_SINAPSE_ORGAO_ID
        elif perfil == "SECRETARIA" and not cleaned.get("sinapse_orgao_id"):
            raise ValidationError(
                {"sinapse_orgao_id": "Usuário de secretaria deve ter órgão Sinapse vinculado."}
            )
        elif perfil == "GESTOR":
            cleaned["is_staff"] = True
            cleaned["is_superuser"] = True
        return cleaned


class UsuarioCreationAdminForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = Usuario
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _attach_orgao_select(self)

    def clean_sinapse_orgao_id(self):
        return _validar_orgao_id(self.cleaned_data.get("sinapse_orgao_id"))

    def clean(self):
        cleaned = super().clean()
        perfil = cleaned.get("perfil")
        if perfil == "PROTOCOLO":
            cleaned["sinapse_orgao_id"] = PROTOCOLO_SINAPSE_ORGAO_ID
        elif perfil == "SECRETARIA" and not cleaned.get("sinapse_orgao_id"):
            raise ValidationError(
                {"sinapse_orgao_id": "Usuário de secretaria deve ter órgão Sinapse vinculado."}
            )
        elif perfil == "GESTOR":
            cleaned["is_staff"] = True
            cleaned["is_superuser"] = True
        return cleaned
