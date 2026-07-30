/** Categorias e helpers de textos padrão de despacho. */

export const CATEGORIAS_TEXTO_PADRAO = [
    { label: 'Protocolo (inicial e final)', value: 'PROTOCOLO' },
    { label: 'Operacional (secretaria / setores)', value: 'OPERACIONAL' }
];

export const ESCOPO_TEXTO_PADRAO_LABEL = {
    PROTOCOLO: 'Protocolo',
    SECRETARIA: 'Secretaria',
    SETORIAL: 'Setorial',
    GERAL: 'Uso geral'
};

export const PLACEHOLDERS_TEXTO_PADRAO = [
    { chave: 'protocolo_legislativo', rotulo: 'Protocolo legislativo' },
    { chave: 'protocolo_executivo', rotulo: 'Protocolo executivo' },
    { chave: 'demanda_titulo', rotulo: 'Título da demanda' },
    { chave: 'autor_nome', rotulo: 'Nome do autor' },
    { chave: 'orgao_destino', rotulo: 'Órgão destino' },
    { chave: 'setor_destino', rotulo: 'Setor destino' },
    { chave: 'prazo_dias', rotulo: 'Prazo (dias)' }
];

export function nomeAutorDemanda(demanda) {
    if (!demanda) return '';
    if (demanda.autor_nome) return demanda.autor_nome;
    const a = demanda.autor;
    if (!a) return '';
    const nome = [a.first_name, a.last_name].filter(Boolean).join(' ').trim();
    return nome || a.username || '';
}

/** Monta contexto de placeholders a partir da demanda + extras (destinos, etc.). */
export function buildContextoPlaceholders(demanda, extras = {}) {
    if (!demanda) return { ...extras };
    return {
        protocolo_legislativo: demanda.protocolo_legislativo || '',
        protocolo_executivo: demanda.protocolo_executivo || '',
        demanda_titulo: demanda.titulo || '',
        autor_nome: nomeAutorDemanda(demanda),
        orgao_destino: extras.orgao_destino || '',
        setor_destino: extras.setor_destino || '',
        prazo_dias:
            demanda.prazo_dias != null
                ? String(demanda.prazo_dias)
                : demanda.prazo_efetivo_dias != null
                  ? String(demanda.prazo_efetivo_dias)
                  : '',
        ...extras
    };
}

/** Substitui {{chave}} no HTML pelo valor do contexto. */
export function aplicarPlaceholdersTextoPadrao(corpo, contexto = {}) {
    if (!corpo) return '';
    return corpo.replace(/\{\{\s*([a-z0-9_]+)\s*\}\}/gi, (match, chave) => {
        const val = contexto[chave.toLowerCase()];
        return val != null && val !== '' ? String(val) : match;
    });
}

export function rotuloCategoriaTextoPadrao(valor) {
    return CATEGORIAS_TEXTO_PADRAO.find((c) => c.value === valor)?.label || valor;
}

/** Insere token de placeholder no HTML do editor Quill. */
export function inserirPlaceholderNoHtml(html, token) {
    const atual = html || '';
    if (!atual.trim()) {
        return `<p>${token}</p>`;
    }
    if (/<\/p>\s*$/i.test(atual)) {
        return atual.replace(/<\/p>\s*$/i, ` ${token}</p>`);
    }
    return `${atual} ${token}`;
}

/** Extrai órgão/setor destino do formulário de tramitação para placeholders. */
export function extrairDestinosPlaceholder(destinos = [], orgaos = []) {
    const mapaOrgao = Object.fromEntries((orgaos || []).map((o) => [o.id, o.nome]));
    const linhas = [];
    let setor = '';
    for (const d of destinos || []) {
        if (!d?.secretaria_id) continue;
        const orgao = mapaOrgao[d.secretaria_id] || '';
        const rotuloSetor =
            d.unidade_labels?.[0] || d.unidade_label || (d.unidade_ids?.[0] ? `Setor #${d.unidade_ids[0]}` : '');
        if (rotuloSetor && !setor) setor = rotuloSetor;
        if (orgao) {
            linhas.push(rotuloSetor ? `${orgao} › ${rotuloSetor}` : orgao);
        }
    }
    return {
        orgao_destino: linhas.join('; ') || '',
        setor_destino: setor
    };
}
