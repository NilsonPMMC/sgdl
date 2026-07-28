/** Formatação de descrições na timeline (B9 — parágrafos legíveis). */

const TAG_HTML_RICO = /<\s*(p|div|br|ul|ol|li|h[1-6]|strong|em|span|blockquote)[\s>/]/i;

export function pareceHtmlRico(texto) {
    return TAG_HTML_RICO.test(String(texto || ''));
}

/**
 * @returns {{ modo: 'vazio'|'html'|'texto', html?: string, texto?: string }}
 */
export function descricaoTramitacaoParaExibicao(descricao) {
    const raw = String(descricao || '').trim();
    if (!raw) {
        return { modo: 'vazio' };
    }
    if (pareceHtmlRico(raw)) {
        return { modo: 'html', html: raw };
    }
    return { modo: 'texto', texto: raw.replace(/\r\n/g, '\n') };
}
