"""API — base stand-by de estudo e viabilidade."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.estudo_viabilidade_service import EstudoViabilidadeService


class EstudoViabilidadeListAPIView(APIView):
    """GET /api/estudos-viabilidade/ — fila stand-by para Protocolo, Secretarias e Gestores."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        svc = EstudoViabilidadeService()
        if not svc.usuario_ve_stand_by(request.user):
            return Response(
                {"detail": "Sem permissão para consultar a base stand-by."},
                status=403,
            )
        qs = svc.queryset_stand_by(request.user)
        q = (request.query_params.get("q") or "").strip()
        if q:
            if q.isdigit():
                qs = qs.filter(demanda_id=int(q))
            else:
                qs = qs.filter(demanda__titulo__icontains=q)
        limite = min(int(request.query_params.get("limite") or 100), 500)
        items = [
            svc.serializar_registro(reg)
            for reg in qs[:limite]
        ]
        return Response({"count": len(items), "results": items})
