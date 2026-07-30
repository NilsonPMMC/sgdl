"""API de textos padrão para despachos e tramitações."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Demanda
from core.models_texto_padrao_despacho import TextoPadraoDespacho
from core.serializers import TextoPadraoDespachoSerializer
from core.services.texto_padrao_despacho_service import (
    aplicar_placeholders,
    categoria_padrao_criacao,
    categorias_visiveis_usuario,
    contexto_demanda,
    exige_selecao_setores,
    normalizar_categoria_legada,
    pode_editar,
    queryset_visivel,
    resolver_escopo_criacao,
    resolver_unidades_criacao,
    setores_disponiveis_usuario,
    usuario_pode_acessar_modulo,
)


def _extrair_unidades_ids(data) -> list[int] | None:
    if "unidades_administrativas_ids" in data:
        raw = data.pop("unidades_administrativas_ids")
        if raw is None:
            return None
        if isinstance(raw, (list, tuple)):
            return [int(x) for x in raw if x is not None and str(x).strip() != ""]
        return None
    legado = data.pop("unidade_administrativa_id", None)
    if legado is not None and legado != "":
        try:
            return [int(legado)]
        except (TypeError, ValueError):
            return None
    return None


class TextoPadraoDespachoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TextoPadraoDespachoSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def _negado(self):
        return Response(
            {"detail": "Acesso restrito a Protocolo, Secretaria ou Gestor."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def get_queryset(self):
        user = self.request.user
        categoria = self.request.query_params.get("categoria")
        if categoria:
            categoria = normalizar_categoria_legada(categoria)
        incluir_inativos = self.request.query_params.get("todos") == "1"
        return queryset_visivel(
            user,
            categoria=categoria or None,
            incluir_inativos=incluir_inativos,
        )

    def list(self, request, *args, **kwargs):
        if not usuario_pode_acessar_modulo(request.user):
            return self._negado()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not usuario_pode_acessar_modulo(request.user):
            return self._negado()
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not usuario_pode_acessar_modulo(request.user):
            return self._negado()
        try:
            escopo = resolver_escopo_criacao(request.user)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        unidades_ids = _extrair_unidades_ids(data)
        try:
            unidades_resolvidas = resolver_unidades_criacao(
                request.user, escopo, unidades_ids=unidades_ids
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        escopo_save = {
            k: v
            for k, v in escopo.items()
            if k in ("escopo_tipo", "sinapse_orgao_id")
        }
        cat_payload = data.get("categoria")
        if cat_payload:
            cat_norm = normalizar_categoria_legada(str(cat_payload))
            if cat_norm not in categorias_visiveis_usuario(request.user):
                return Response(
                    {"detail": "Categoria não permitida para o seu perfil."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            escopo_save["categoria"] = cat_norm
        else:
            escopo_save["categoria"] = categoria_padrao_criacao(request.user)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        instancia = serializer.save(criado_por=request.user, **escopo_save)
        if unidades_resolvidas:
            instancia.unidades.set(unidades_resolvidas)
        return Response(
            self.get_serializer(instancia).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        if not usuario_pode_acessar_modulo(request.user):
            return self._negado()
        instancia = self.get_object()
        if not pode_editar(request.user, instancia):
            return Response(
                {"detail": "Sem permissão para editar este modelo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = dict(request.data) if isinstance(request.data, dict) else request.data.copy()
        unidades_ids = _extrair_unidades_ids(data)
        serializer = self.get_serializer(instancia, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if unidades_ids is not None:
            try:
                escopo = {
                    "escopo_tipo": instancia.escopo_tipo,
                    "sinapse_orgao_id": instancia.sinapse_orgao_id,
                    "unidade_padrao_id": None,
                }
                unidades_resolvidas = resolver_unidades_criacao(
                    request.user, escopo, unidades_ids=unidades_ids
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            instancia.unidades.set(unidades_resolvidas)

        return Response(self.get_serializer(instancia).data)

    def destroy(self, request, *args, **kwargs):
        if not usuario_pode_acessar_modulo(request.user):
            return self._negado()
        instancia = self.get_object()
        if not pode_editar(request.user, instancia):
            return Response(
                {"detail": "Sem permissão para excluir este modelo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instancia.ativo = False
        instancia.save(update_fields=["ativo", "atualizado_em"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="aplicar")
    def aplicar(self, request, pk=None):
        if not usuario_pode_acessar_modulo(request.user):
            return self._negado()
        instancia = self.get_object()
        ctx_extra = dict(request.data.get("contexto") or {})
        demanda_id = request.data.get("demanda_id")
        if demanda_id:
            try:
                demanda = Demanda.objects.select_related("autor").get(pk=int(demanda_id))
                ctx = contexto_demanda(demanda, ctx_extra)
            except (Demanda.DoesNotExist, TypeError, ValueError):
                return Response(
                    {"detail": "demanda_id inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            ctx = contexto_demanda(None, ctx_extra)
        corpo = aplicar_placeholders(instancia.corpo, ctx)
        return Response(
            {
                "id": instancia.pk,
                "titulo": instancia.titulo,
                "corpo": corpo,
                "categoria": instancia.categoria,
            }
        )

    @action(detail=False, methods=["get"], url_path="meta-criacao")
    def meta_criacao(self, request):
        if not usuario_pode_acessar_modulo(request.user):
            return self._negado()
        try:
            escopo = resolver_escopo_criacao(request.user)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        setores = setores_disponiveis_usuario(request.user)
        cats = categorias_visiveis_usuario(request.user)
        return Response(
            {
                "escopo": {
                    k: v for k, v in escopo.items() if k != "unidade_padrao_id"
                },
                "setores_disponiveis": setores,
                "exige_selecao_setores": exige_selecao_setores(request.user, escopo),
                "categoria_padrao": categoria_padrao_criacao(request.user),
                "categorias_disponiveis": cats,
            }
        )
