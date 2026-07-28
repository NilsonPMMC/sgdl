/** Remove tags HTML e normaliza espaços — exibição em timeline e rótulos. */
export function htmlParaTexto(html) {
    const t = (html || '').trim();
    if (!t) return '';
    if (!/<[a-z][\s\S]*>/i.test(t)) return t.replace(/\s+/g, ' ').trim();
    return t
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/p>/gi, '\n')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/gi, ' ')
        .replace(/&amp;/gi, '&')
        .replace(/&lt;/gi, '<')
        .replace(/&gt;/gi, '>')
        .replace(/\u00a0/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

/** Converte texto do ofício (parágrafos por linha em branco) para HTML legível. Idempotente se já for HTML. */
export function descricaoParaHtml(texto) {
    const t = (texto || '').trim();
    if (!t) return '';
    if (/<p[\s>]/i.test(t) || /<div[\s>]/i.test(t)) {
        return t;
    }
    return t
        .split(/\n\s*\n/)
        .map((bloco) => bloco.trim())
        .filter(Boolean)
        .map((bloco) => {
            const linhas = bloco
                .split('\n')
                .map((l) => l.trim())
                .filter(Boolean)
                .map((l) => l.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'))
                .join('<br>');
            return `<p>${linhas}</p>`;
        })
        .join('');
}
