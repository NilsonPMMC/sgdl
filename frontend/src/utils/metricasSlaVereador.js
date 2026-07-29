import { perfilEhVereador } from '@/constants/tramitacaoVisibilidade';

/** Oculta KPIs e indicadores de atraso/SLA na UX do vereador. */
export function ocultarMetricasSla(perfil) {
    return perfilEhVereador(perfil);
}

export function isDemandaAtrasadaParaExibicao(demanda, perfil, verificarAtraso) {
    if (ocultarMetricasSla(perfil)) return false;
    return verificarAtraso(demanda);
}

export function filtrarNotificacoesSemAtraso(notificacoes, perfil) {
    if (!Array.isArray(notificacoes)) return [];
    if (!ocultarMetricasSla(perfil)) return notificacoes.filter((n) => n != null);
    return notificacoes.filter((n) => n != null && n.tipo !== 'ATRASO');
}

export function filtrarAtalhosConsultaSemSla(atalhos, perfil) {
    if (!Array.isArray(atalhos)) return [];
    if (!ocultarMetricasSla(perfil)) return atalhos;
    return atalhos.filter((a) => a?.id !== 'atrasadas');
}
