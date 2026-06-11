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
