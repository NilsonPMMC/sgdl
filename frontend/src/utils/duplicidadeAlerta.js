/** Formatação de alertas de possível duplicidade (Copiloto e envio oficial). */

/**
 * @param {Array<Record<string, unknown>>} alertas
 */
export function temDuplicidadeEmTramite(alertas) {
    return Array.isArray(alertas) && alertas.some((a) => a?.nivel === 'em_tramite');
}

/**
 * @param {Array<Record<string, unknown>>} alertas
 */
export function resumoDuplicidadeFrontend(alertas) {
    if (!Array.isArray(alertas) || !alertas.length) {
        return null;
    }
    const emTramite = alertas.filter((a) => a?.nivel === 'em_tramite');
    const rascunhos = alertas.filter((a) => a?.nivel === 'rascunho');

    if (emTramite.length) {
        const refs = emTramite
            .slice(0, 3)
            .map((a) => `#${a.demanda_id} «${a.titulo}» (${a.status_label || a.status})`)
            .join(' · ');
        return {
            severity: 'error',
            summary: 'Possível duplicidade em tramitação',
            detail:
                `Já existe(m) processo(s) semelhante(s) aguardando protocolo ou em execução: ${refs}. ` +
                'Recomendamos não enviar este ofício e acompanhar o processo existente.',
            sugerirNaoEnviar: true
        };
    }

    const refs = rascunhos
        .slice(0, 3)
        .map((a) => `#${a.demanda_id} «${a.titulo}»`)
        .join(' · ');
    return {
        severity: 'warn',
        summary: 'Possível duplicidade de rascunho',
        detail:
            `Rascunho(s) semelhante(s) já registrado(s): ${refs}. ` +
            'Revise se não é o mesmo pedido antes de protocolar.',
        sugerirNaoEnviar: false
    };
}

/**
 * @param {Record<string, unknown>|null|undefined} resumo
 */
export function mensagemResumoBackend(resumo) {
    if (!resumo || typeof resumo !== 'object') return '';
    return String(resumo.mensagem_resumo || '');
}
