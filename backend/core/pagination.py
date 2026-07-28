"""Paginação opt-in (só quando `page` ou `page_size` estão na query)."""

from rest_framework.pagination import PageNumberPagination


class OptInPageNumberPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        if "page" not in request.query_params and "page_size" not in request.query_params:
            return None
        return super().paginate_queryset(queryset, request, view)


class DemandaListPagination(OptInPageNumberPagination):
    """Alias histórico — listagem de demandas."""
