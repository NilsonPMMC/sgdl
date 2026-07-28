/** Helpers compartilhados para DataTable lazy + paginação DRF. */

export function extrairPaginaResposta(response) {
    const data = response?.data;
    const rows = data?.results ?? (Array.isArray(data) ? data : []);
    const total = data?.count ?? data?.total ?? rows.length;
    return { rows, total };
}

export function indicePagina(tablePagination) {
    return Math.floor(tablePagination.first / tablePagination.rows) + 1;
}

export function paramsPagina(tablePagination, extra = {}) {
    return {
        ...extra,
        page: indicePagina(tablePagination),
        page_size: tablePagination.rows
    };
}
