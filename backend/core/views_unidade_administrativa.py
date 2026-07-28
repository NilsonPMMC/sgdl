"""API de cadastro de setores e responsáveis."""

from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models_unidade_administrativa import (
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from core.serializers import (
    UnidadeAdministrativaResponsavelSerializer,
    UnidadeAdministrativaSerializer,
)
from core.services.tramitacao_setor_service import UnidadeAdministrativaService
from core.pagination import OptInPageNumberPagination
from core.services.gestor_escopo import (
    TIPO_SETORIAL,
    orgaos_escopo_gestor,
    pode_consultar_unidades,
    pode_gerir_responsaveis_unidade,
    pode_gerir_unidades,
    tipo_gestor,
)
from integrations import sinapse_catalog


class UnidadeAdministrativaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UnidadeAdministrativaSerializer
    queryset = UnidadeAdministrativa.objects.prefetch_related("responsaveis__usuario").order_by(
        "sinapse_orgao_id", "nome"
    )
    pagination_class = OptInPageNumberPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        orgao_id = self.request.query_params.get("sinapse_orgao_id")
        if orgao_id:
            try:
                qs = qs.filter(sinapse_orgao_id=int(orgao_id))
            except (TypeError, ValueError):
                pass
        elif getattr(self.request.user, "perfil", None) == "SECRETARIA":
            if self.request.user.sinapse_orgao_id:
                qs = qs.filter(sinapse_orgao_id=self.request.user.sinapse_orgao_id)
        elif getattr(self.request.user, "perfil", None) == "GESTOR":
            if tipo_gestor(self.request.user) == TIPO_SETORIAL:
                orgaos = orgaos_escopo_gestor(self.request.user)
                if orgaos:
                    qs = qs.filter(sinapse_orgao_id__in=orgaos)
                else:
                    qs = qs.none()
        ativo = self.request.query_params.get("ativo")
        incluir_inativos = self.request.query_params.get("incluir_inativos") in (
            "1",
            "true",
            "True",
        )
        if incluir_inativos:
            ativo_filtro = self.request.query_params.get("ativo")
            if ativo_filtro in ("1", "true", "True"):
                qs = qs.filter(ativo=True)
            elif ativo_filtro in ("0", "false", "False"):
                qs = qs.filter(ativo=False)
        elif ativo in ("0", "false", "False"):
            qs = qs.filter(ativo=False)
        elif ativo in ("1", "true", "True") or self.action == "list":
            qs = qs.filter(ativo=True)

        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(sigla__icontains=q))

        return qs

    def _negar_leitura(self):
        return Response(
            {"detail": "Acesso restrito."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def _negar_escrita(self):
        return Response(
            {"detail": "Acesso restrito a Protocolo ou Gestor administrador."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def list(self, request, *args, **kwargs):
        if not pode_consultar_unidades(request.user):
            return self._negar_leitura()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not pode_consultar_unidades(request.user):
            return self._negar_leitura()
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not pode_gerir_unidades(request.user):
            return self._negar_escrita()
        try:
            obj = UnidadeAdministrativaService().criar(
                sinapse_orgao_id=int(request.data.get("sinapse_orgao_id")),
                nome=str(request.data.get("nome") or ""),
                sigla=str(request.data.get("sigla") or ""),
                sinapse_unidade_id=request.data.get("sinapse_unidade_id"),
            )
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            UnidadeAdministrativaSerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        if not pode_gerir_unidades(request.user):
            return self._negar_escrita()
        obj = self.get_object()
        nome = request.data.get("nome")
        sigla = request.data.get("sigla")
        if nome is not None:
            obj.nome = str(nome).strip() or obj.nome
        if sigla is not None:
            obj.sigla = str(sigla).strip().upper()
        if "ativo" in request.data:
            novo_ativo = bool(request.data.get("ativo"))
            if obj.ativo and not novo_ativo:
                from core.services.carta_setor_service import CartaSetorService

                if not CartaSetorService().pode_desativar_unidade(obj):
                    return Response(
                        {
                            "detail": (
                                "Não é possível desativar: há serviços da carta "
                                "vinculados a este setor. Remova os vínculos antes."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            obj.ativo = novo_ativo
        obj.save()
        return Response(UnidadeAdministrativaSerializer(obj).data)

    def _negar_gerir_responsaveis(self):
        return Response(
            {"detail": "Sem permissão para gerir responsáveis deste setor."},
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=True, methods=["post"], url_path="responsaveis")
    def responsaveis(self, request, pk=None):
        if not pode_consultar_unidades(request.user):
            return self._negar_leitura()
        unidade = self.get_object()
        if not pode_gerir_responsaveis_unidade(request.user, unidade):
            return self._negar_gerir_responsaveis()
        usuario_id = request.data.get("usuario_id")
        if not usuario_id:
            return Response(
                {"detail": "usuario_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from core.models import Usuario

        try:
            usuario = Usuario.objects.get(pk=int(usuario_id))
        except (Usuario.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Usuário não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            vinculo = UnidadeAdministrativaService().vincular_responsavel(
                unidade,
                usuario,
                pode_tramitar=bool(request.data.get("pode_tramitar", True)),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            UnidadeAdministrativaResponsavelSerializer(vinculo).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="desvincular-responsavel")
    def desvincular_responsavel(self, request, pk=None):
        if not pode_consultar_unidades(request.user):
            return self._negar_leitura()
        unidade = self.get_object()
        if not pode_gerir_responsaveis_unidade(request.user, unidade):
            return self._negar_gerir_responsaveis()
        usuario_id = request.data.get("usuario_id")
        if not usuario_id:
            return Response(
                {"detail": "usuario_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = UnidadeAdministrativaResponsavel.objects.filter(
            unidade=unidade, usuario_id=usuario_id, ativo=True
        ).update(ativo=False)
        if not updated:
            return Response({"detail": "Vínculo não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": "desvinculado"})

    @action(detail=True, methods=["get"], url_path="vinculos")
    def vinculos(self, request, pk=None):
        if not pode_consultar_unidades(request.user):
            return self._negar_leitura()
        unidade = self.get_object()
        stats = UnidadeAdministrativaService().estatisticas_vinculos(unidade)
        return Response(
            {
                "unidade_id": unidade.pk,
                "nome": unidade.nome,
                "sigla": unidade.sigla,
                **stats,
            }
        )

    @action(detail=True, methods=["post"], url_path="excluir")
    def excluir(self, request, pk=None):
        if not pode_gerir_unidades(request.user):
            return self._negar_escrita()
        unidade = self.get_object()
        destino_raw = request.data.get("unidade_destino_id")
        destino_id = None
        if destino_raw not in (None, "", "null"):
            try:
                destino_id = int(destino_raw)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "unidade_destino_id inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            resultado = UnidadeAdministrativaService().excluir_com_redirecionamento(
                unidade,
                unidade_destino_id=destino_id,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="orgaos")
    def orgaos(self, request):
        if not pode_consultar_unidades(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        orgaos = sinapse_catalog.list_orgaos_api()
        if getattr(request.user, "perfil", None) == "GESTOR":
            if tipo_gestor(request.user) == TIPO_SETORIAL:
                ids = set(orgaos_escopo_gestor(request.user))
                orgaos = [o for o in orgaos if int(o.get("id", 0)) in ids]
        elif getattr(request.user, "perfil", None) == "SECRETARIA":
            oid = request.user.sinapse_orgao_id
            if oid:
                orgaos = [o for o in orgaos if int(o.get("id", 0)) == int(oid)]
        return Response({"results": orgaos})

    @action(detail=False, methods=["post"], url_path="importar-rm")
    def importar_rm(self, request):
        if not pode_gerir_unidades(request.user):
            return self._negar_escrita()
        from core.services.rm_unidades_import_service import RmUnidadesImportService

        dry_run = bool(request.data.get("dry_run"))
        xlsx = request.data.get("xlsx_path") or None
        try:
            resultado = RmUnidadesImportService().importar(
                xlsx_path=xlsx,
                dry_run=dry_run,
                carregar_csv=bool(request.data.get("carregar_csv", True)),
            )
        except Exception as exc:
            return Response(
                {"detail": f"Falha na importação: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(resultado.to_dict())
