/** H3-17 / H3-18 — formulário padrão de tramitação (Despacho + Andamentos). */

export const MODO_DESPACHO = 'despacho';
export const MODO_ANDAMENTO = 'andamento';

export const MAX_DESTINOS_DESPACHO = 5;
export const MAX_INTEGRADOS_DESPACHO = 4;
export const MAX_PERNAS_DESPACHO = 30;

/** Matriz H3-18 — regras de assinatura por contexto. */
export const REGRAS_ASSINATURA = {
    [MODO_DESPACHO]: {
        obrigatoria: false,
        opcionalCheckbox: false,
        perguntaConfirmacao: false,
        rotulo: 'Despacho inicial'
    },
    [MODO_ANDAMENTO]: {
        obrigatoria: false,
        opcionalCheckbox: true,
        perguntaConfirmacao: true,
        rotulo: 'Andamento'
    },
    CONCLUSAO: {
        obrigatoria: true,
        opcionalCheckbox: false,
        perguntaConfirmacao: false,
        rotulo: 'Conclusão do serviço'
    },
    DEVOLUTIVA: {
        obrigatoria: true,
        opcionalCheckbox: false,
        perguntaConfirmacao: false,
        rotulo: 'Devolutiva ao vereador'
    }
};

/** Scatter-gather — assinatura por ação operacional (Secretaria / Gestor setorial). */
export const REGRAS_ASSINATURA_SCATTER = {
    DESPACHAR: {
        obrigatoria: false,
        opcionalCheckbox: true,
        perguntaConfirmacao: true,
        rotulo: 'Despacho operacional'
    },
    DESPACHAR_ENCERRAR: {
        obrigatoria: true,
        opcionalCheckbox: false,
        perguntaConfirmacao: true,
        rotulo: 'Despachar e encerrar'
    },
    ENCERRAR: {
        obrigatoria: true,
        opcionalCheckbox: false,
        perguntaConfirmacao: true,
        rotulo: 'Encerrar participação'
    }
};

/** Resolve regras de assinatura para formulário de tramitação/andamento. */
export function regrasAssinaturaAndamento(tipoAndamento) {
    if (tipoAndamento === 'CONCLUSAO') return REGRAS_ASSINATURA.CONCLUSAO;
    return REGRAS_ASSINATURA[MODO_ANDAMENTO];
}

/** Resolve regras scatter a partir da ação (DESPACHAR, DESPACHAR_ENCERRAR, ENCERRAR). */
export function regrasAssinaturaScatter(acao) {
    return REGRAS_ASSINATURA_SCATTER[acao] || REGRAS_ASSINATURA_SCATTER.DESPACHAR;
}

export const TIPOS_ANDAMENTO_PADRAO = [
    { label: 'Comentário', value: 'COMENTARIO' },
    { label: 'Análise Técnica', value: 'ANALISE_TECNICA' },
    { label: 'Execução', value: 'EXECUCAO' },
    { label: 'Conclusão', value: 'CONCLUSAO' }
];

let _seqDestino = 0;

export function novoDestino(partial = {}) {
    _seqDestino += 1;
    const ids = partial.unidade_administrativa_ids
        ? [...partial.unidade_administrativa_ids]
        : partial.unidade_administrativa_id
          ? [partial.unidade_administrativa_id]
          : [];
    return {
        _key: `d-${_seqDestino}`,
        secretaria_id: null,
        unidade_administrativa_id: ids[0] ?? null,
        unidade_administrativa_ids: ids,
        unidade_labels: partial.unidade_labels ? [...partial.unidade_labels] : [],
        fixo: false,
        ...partial,
        unidade_administrativa_ids: ids
    };
}

export function estadoFormularioTramitacao(overrides = {}) {
    return {
        tipo: null,
        /** Lista: [{ secretaria_id, unidade_administrativa_ids[], fixo? }] */
        destinos: [],
        descricao: '',
        anexos: [],
        assinar_eletronicamente: false,
        ...overrides
    };
}

/** Despacho com 2+ órgãos distintos → fluxo transversal (C2/C3/C5). */
export function despachoEhTransversal(destinos = []) {
    const orgaos = new Set(
        (destinos || []).map((d) => d?.secretaria_id).filter(Boolean).map(Number)
    );
    return orgaos.size > 1;
}

export function inicializarDestinosDespacho(orgaoCompetenteId) {
    if (!orgaoCompetenteId) return [];
    return [novoDestino({ secretaria_id: Number(orgaoCompetenteId), fixo: true })];
}

export function inicializarDestinosAndamento(orgaoId) {
    if (!orgaoId) return [novoDestino()];
    return [novoDestino({ secretaria_id: Number(orgaoId), fixo: true })];
}

function setoresDestino(destino) {
    if (destino?.unidade_administrativa_ids?.length) {
        return destino.unidade_administrativa_ids.map(Number).filter(Boolean);
    }
    if (destino?.unidade_administrativa_id) {
        return [Number(destino.unidade_administrativa_id)];
    }
    return [];
}

/** Órgão com UAs carregadas no editor (lista de objetos ou {id, label}). */
export function orgaoExigeSetor(orgaoId, unidadesPorOrgao = {}) {
    const lista = unidadesPorOrgao[Number(orgaoId)];
    return Array.isArray(lista) && lista.length > 0;
}

/** Valida destinos de despacho — setor obrigatório quando o órgão tem UAs ativas. */
export function validarSetoresObrigatoriosDestinos(destinos = [], unidadesPorOrgao = {}, orgaos = []) {
    const mapaNomes = Object.fromEntries((orgaos || []).map((o) => [Number(o.id), o.nome]));
    const erros = [];
    for (const d of destinos) {
        if (!d?.secretaria_id) continue;
        const sid = Number(d.secretaria_id);
        if (!orgaoExigeSetor(sid, unidadesPorOrgao)) continue;
        if (!setoresDestino(d).length) {
            const nome = mapaNomes[sid] || `Órgão #${sid}`;
            erros.push({
                secretaria_id: sid,
                mensagem: `Selecione ao menos um setor do órgão ${nome}.`
            });
        }
    }
    return erros;
}

export function mensagemSetoresObrigatoriosDestinos(destinos = [], unidadesPorOrgao = {}, orgaos = []) {
    const erros = validarSetoresObrigatoriosDestinos(destinos, unidadesPorOrgao, orgaos);
    return erros[0]?.mensagem || null;
}

/** Conta pernas órgão × setor. Com mapa de UAs, órgão sem setor selecionado não conta. */
export function contarPernasDestinos(destinos = [], unidadesPorOrgao = null) {
    let total = 0;
    for (const d of destinos) {
        if (!d?.secretaria_id) continue;
        const setores = setoresDestino(d);
        if (unidadesPorOrgao && orgaoExigeSetor(d.secretaria_id, unidadesPorOrgao)) {
            total += setores.length;
        } else {
            total += setores.length || 1;
        }
    }
    return total;
}

/** Payload API despacho — competente + integrados, multi-setor por órgão. */
export function destinosParaPayload(form, orgaoCompetenteId = null) {
    const linhas = (form?.destinos || []).filter((d) => d.secretaria_id);
    if (linhas.length) {
        return {
            destinos: linhas.map((d) => {
                const item = { secretaria_id: Number(d.secretaria_id) };
                const ids = setoresDestino(d);
                if (ids.length === 1) {
                    item.unidade_administrativa_id = ids[0];
                } else if (ids.length > 1) {
                    item.unidade_administrativa_ids = ids;
                }
                return item;
            })
        };
    }
    const integrados = (form?.orgao_ids || []).filter(Boolean);
    if (integrados.length) {
        return {
            destinos: integrados.map((secretaria_id) => ({
                secretaria_id: Number(secretaria_id)
            }))
        };
    }
    if (orgaoCompetenteId) {
        const item = { secretaria_id: Number(orgaoCompetenteId) };
        const ids = setoresDestino(form || {});
        if (ids.length === 1) item.unidade_administrativa_id = ids[0];
        else if (ids.length > 1) item.unidade_administrativa_ids = ids;
        return { destinos: [item] };
    }
    return {};
}

/** Há órgãos integrados além do competente/líder (tramitação transversal). */
export function temIntegradosDestinos(destinos = [], orgaoLiderId = null) {
    return (destinos || []).some((d) => {
        if (!d?.secretaria_id) return false;
        if (orgaoLiderId == null) return !d.fixo;
        return Number(d.secretaria_id) !== Number(orgaoLiderId);
    });
}

export function destinoAndamentoPayload(form) {
    const linha = (form?.destinos || []).find((d) => d.secretaria_id) || form?.destinos?.[0];
    const ids = linha ? setoresDestino(linha) : [];
    return {
        unidade_destino_id: ids[0] ?? form?.unidade_destino_id ?? null,
        secretaria_id: linha?.secretaria_id ?? null
    };
}

export function resumoDestinosTexto(destinos = [], orgaos = []) {
    const mapa = Object.fromEntries(orgaos.map((o) => [o.id, o.nome]));
    const linhas = [];
    let idx = 0;
    for (const d of destinos) {
        if (!d.secretaria_id) continue;
        idx += 1;
        const nome = mapa[d.secretaria_id] || `Órgão #${d.secretaria_id}`;
        const setores = setoresDestino(d);
        const prefix = d.fixo ? 'Competente' : `Integrado ${idx}`;
        if (!setores.length) {
            linhas.push(`${prefix}: ${nome} › — setor não informado`);
            continue;
        }
        const labels = d.unidade_labels?.length
            ? d.unidade_labels
            : setores.map((id) => d.unidade_label || `Setor #${id}`);
        if (setores.length === 1) {
            linhas.push(`${prefix}: ${nome} › ${labels[0]}`);
        } else {
            linhas.push(`${prefix}: ${nome} › ${setores.length} setores (${labels.join('; ')})`);
        }
    }
    return linhas;
}

export function legacyDespachoFromForm(form) {
    const payload = destinosParaPayload(form);
    return {
        destinos: payload.destinos,
        secretaria_ids: (form.destinos || [])
            .filter((d) => d.secretaria_id && !d.fixo)
            .map((d) => d.secretaria_id)
    };
}
