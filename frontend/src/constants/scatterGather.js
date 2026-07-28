/** Scatter-gather — nós operacionais na etapa EM_OPERACAO. */

export const ACAO_SCATTER_DESPACHAR = 'DESPACHAR';
export const ACAO_SCATTER_DESPACHAR_ENCERRAR = 'DESPACHAR_ENCERRAR';
export const ACAO_SCATTER_ENCERRAR = 'ENCERRAR';
export const ACAO_SCATTER_BOOTSTRAP = 'BOOTSTRAP';

export const ROTULO_ACAO_SCATTER = {
    [ACAO_SCATTER_DESPACHAR]: 'Despachar (nó permanece aberto)',
    [ACAO_SCATTER_DESPACHAR_ENCERRAR]: 'Despachar e encerrar participação',
    [ACAO_SCATTER_ENCERRAR]: 'Encerrar participação',
    [ACAO_SCATTER_BOOTSTRAP]: 'Abertura de nó operacional'
};

export const STATUS_NO_ABERTO = 'ABERTO';
export const STATUS_NO_CONCLUIDO = 'CONCLUIDO';

export function acaoScatterRequerDestino(acao) {
    return acao === ACAO_SCATTER_DESPACHAR || acao === ACAO_SCATTER_DESPACHAR_ENCERRAR;
}

export function opcoesAcaoScatter(acoesDisponiveis = []) {
    const lista = Array.isArray(acoesDisponiveis) ? acoesDisponiveis : [];
    const opcoes = [];
    if (lista.includes('scatter_despachar')) {
        opcoes.push({
            label: ROTULO_ACAO_SCATTER[ACAO_SCATTER_DESPACHAR],
            value: ACAO_SCATTER_DESPACHAR
        });
    }
    if (lista.includes('scatter_despachar_encerrar')) {
        opcoes.push({
            label: ROTULO_ACAO_SCATTER[ACAO_SCATTER_DESPACHAR_ENCERRAR],
            value: ACAO_SCATTER_DESPACHAR_ENCERRAR
        });
    }
    if (lista.includes('scatter_encerrar')) {
        opcoes.push({
            label: ROTULO_ACAO_SCATTER[ACAO_SCATTER_ENCERRAR],
            value: ACAO_SCATTER_ENCERRAR
        });
    }
    return opcoes;
}

export function rotuloNoOperacional(no) {
    if (!no) return '';
    const org = no.orgao_nome || (no.orgao_id ? `Órgão #${no.orgao_id}` : 'Órgão');
    const setor = no.setor_nome ? ` › ${no.setor_nome}` : '';
    const origem = no.origem_label ? `${no.origem_label} — ` : '';
    const quando = no.aberto_em
        ? ` (${new Date(no.aberto_em).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })})`
        : '';
    return `${origem}${org}${setor}${quando}`;
}

/** Verifica se órgão × setor já possui nó operacional aberto. */
export function destinoScatterOcupado(destinosOcupados, secretariaId, unidadeId = null) {
    if (!secretariaId || !Array.isArray(destinosOcupados)) return null;
    const sid = Number(secretariaId);
    const uid = unidadeId != null && unidadeId !== '' ? Number(unidadeId) : null;
    return (
        destinosOcupados.find((item) => {
            if (Number(item.secretaria_id) !== sid) return false;
            const itemUid =
                item.unidade_administrativa_id != null && item.unidade_administrativa_id !== ''
                    ? Number(item.unidade_administrativa_id)
                    : null;
            return itemUid === uid;
        }) || null
    );
}

export function rotuloDestinoOcupado(item) {
    if (!item) return '';
    const org = item.orgao_nome || `Órgão #${item.secretaria_id}`;
    const setor = item.setor_nome ? ` › ${item.setor_nome}` : '';
    return `${org}${setor}`;
}

/** Fallback FE quando API ainda não devolveu grupos — mesma secretaria, 2+ nós abertos. */
function orgaoIdNo(no) {
    const id = no?.orgao_id ?? no?.secretaria_id;
    if (id == null || id === '') return null;
    const n = Number(id);
    return Number.isNaN(n) ? null : n;
}

function filtrarNosEquivalentesParalelos(nos) {
    if (nos.length < 2) return [];
    const ids = new Set(nos.map((n) => Number(n.id)));
    const nosMap = new Map(nos.map((n) => [Number(n.id), n]));

    function temAncestralNoConjunto(no) {
        let pid = no.parent_id ?? no.parentId ?? null;
        while (pid != null && pid !== '') {
            const id = Number(pid);
            if (ids.has(id)) return true;
            const ancestral = nosMap.get(id);
            if (!ancestral) break;
            pid = ancestral.parent_id ?? ancestral.parentId ?? null;
        }
        return false;
    }

    const paralelos = nos.filter((n) => !temAncestralNoConjunto(n));
    return paralelos.length >= 2 ? paralelos : [];
}

function chaveSetorNo(no) {
    const ua = no?.setor_id ?? no?.unidade_administrativa_id;
    if (ua == null || ua === '') return null;
    const n = Number(ua);
    return Number.isNaN(n) ? null : n;
}

function particionarNosPorSetor(nos) {
    const map = new Map();
    for (const no of nos) {
        const key = chaveSetorNo(no);
        const bucketKey = key == null ? '__null__' : String(key);
        if (!map.has(bucketKey)) map.set(bucketKey, []);
        map.get(bucketKey).push(no);
    }
    return [...map.values()];
}

function montarGrupoNos(nos, { equivalentes = false } = {}) {
    const setores = [...new Set(nos.map((n) => n.setor_nome).filter(Boolean))];
    const orgaoNome = nos[0]?.orgao_nome || '';
    const canon =
        nos.find((n) => (n.origem_label || '').toLowerCase().includes('protocolo')) || nos[0];
    const setorNome =
        setores.length === 1 ? setores[0] : setores.length > 1 ? setores.join(', ') : '';

    return {
        secretaria_id: orgaoIdNo(nos[0]),
        unidade_administrativa_id: canon?.setor_id ?? null,
        orgao_nome: orgaoNome,
        setor_nome: setorNome,
        setores_nomes: setores,
        quantidade: nos.length,
        no_canonico_id: canon?.id,
        no_ids: nos.map((n) => n.id),
        nos,
        equivalentes
    };
}

/** Painel de gestão — 2+ nós abertos no mesmo setor (redundantes). */
export function montarGruposNosOperador(nosUsuario = [], gruposApiPainel = []) {
    const nos = Array.isArray(nosUsuario) ? nosUsuario : [];
    const painelApi = Array.isArray(gruposApiPainel) ? gruposApiPainel : [];
    const minNoPainel = (g) => (g.quantidade || g.no_ids?.length || g.nos?.length || 0) >= 2;

    if (painelApi.length) {
        return painelApi.filter(minNoPainel);
    }

    if (!nos.length || nos.length === 1) {
        return [];
    }

    const orgaos = new Set(nos.map(orgaoIdNo).filter((id) => id != null));
    if (orgaos.size !== 1) return [];

    return particionarNosPorSetor(nos)
        .map((subset) => {
            const paralelos = filtrarNosEquivalentesParalelos(subset);
            const equivalentes = paralelos.length >= 2;
            const base = equivalentes ? paralelos : subset;
            if (base.length < 2) return null;
            return montarGrupoNos(base, { equivalentes });
        })
        .filter((g) => g && minNoPainel(g));
}

export function montarGruposNosEquivalentes(nosUsuario = [], gruposApi = []) {
    const painelApi = Array.isArray(gruposApi) ? gruposApi : [];
    if (painelApi.length) {
        return painelApi.filter((g) => (g.quantidade || 0) >= 2);
    }

    const nos = Array.isArray(nosUsuario) ? nosUsuario : [];
    const orgaos = new Set(nos.map(orgaoIdNo).filter((id) => id != null));
    if (orgaos.size !== 1) {
        return [];
    }

    return particionarNosPorSetor(nos)
        .map((subset) => {
            const paralelos = filtrarNosEquivalentesParalelos(subset);
            if (paralelos.length < 2) return null;
            return montarGrupoNos(paralelos, { equivalentes: true });
        })
        .filter((g) => g && (g.quantidade || 0) >= 2);
}

export function severityStatusNo(status) {
    if (status === STATUS_NO_ABERTO) return 'warn';
    if (status === STATUS_NO_CONCLUIDO) return 'success';
    return 'secondary';
}

export function calcularTemposNo(no, agoraMs = Date.now()) {
    if (!no?.aberto_em) {
        return { totalSegundos: null, paradoSegundos: null };
    }
    const inicio = new Date(no.aberto_em).getTime();
    if (Number.isNaN(inicio)) {
        return { totalSegundos: null, paradoSegundos: null };
    }
    const fim = no.concluido_em ? new Date(no.concluido_em).getTime() : agoraMs;
    const totalSegundos = Math.max(0, Math.floor((fim - inicio) / 1000));
    const paradoSegundos =
        no.status === STATUS_NO_ABERTO
            ? Math.max(0, Math.floor((agoraMs - inicio) / 1000))
            : 0;
    return { totalSegundos, paradoSegundos };
}

export function formatarDuracaoSegundos(segundos) {
    if (segundos == null) return '—';
    const dias = Math.floor(segundos / 86400);
    const horas = Math.floor((segundos % 86400) / 3600);
    const minutos = Math.floor((segundos % 3600) / 60);
    if (dias > 0) return `${dias}d ${horas}h`;
    if (horas > 0) return `${horas}h ${minutos}min`;
    if (minutos > 0) return `${minutos}min`;
    return `${segundos}s`;
}

export function severidadeTempoNo(segundos, aberto = true) {
    if (!aberto || segundos == null) return 'secondary';
    if (segundos >= 72 * 3600) return 'danger';
    if (segundos >= 24 * 3600) return 'warn';
    return 'info';
}

export function rotuloStatusNo(status) {
    if (status === STATUS_NO_ABERTO) return 'Aberto';
    if (status === STATUS_NO_CONCLUIDO) return 'Concluído';
    if (status === 'CANCELADO') return 'Cancelado';
    return status || '—';
}

export function contarNosArvore(nos = []) {
    let total = 0;
    let abertos = 0;
    for (const no of nos) {
        total += 1;
        if (no.status === STATUS_NO_ABERTO) abertos += 1;
        if (no.filhos?.length) {
            const sub = contarNosArvore(no.filhos);
            total += sub.total;
            abertos += sub.abertos;
        }
    }
    return { total, abertos };
}

export function buscarNoOperacionalPorId(noId, gruposPainel = [], nosUsuario = []) {
    const id = Number(noId);
    if (!id) return null;
    for (const grupo of gruposPainel || []) {
        const no = (grupo.nos || []).find((n) => Number(n.id) === id);
        if (no) return no;
    }
    return (nosUsuario || []).find((n) => Number(n.id) === id) || null;
}

export function nosPodemEncerrar(ids = [], gruposPainel = [], nosUsuario = []) {
    return (ids || []).every((noId) => {
        const no = buscarNoOperacionalPorId(noId, gruposPainel, nosUsuario);
        return !no || no.pode_encerrar !== false;
    });
}

export function mensagemEncerramentoBloqueado(ids = [], gruposPainel = [], nosUsuario = []) {
    const bloqueados = (ids || [])
        .map((noId) => buscarNoOperacionalPorId(noId, gruposPainel, nosUsuario))
        .filter((no) => no && no.pode_encerrar === false);
    if (!bloqueados.length) return '';
    const partes = bloqueados.map((no) => {
        const filhos = filhosInternosBloqueantesNo(no)
            .map((f) => {
                const org = f.orgao_nome || `Órgão #${f.id}`;
                return `#${f.id} (${org}${f.setor_nome ? ` › ${f.setor_nome}` : ''})`;
            })
            .join('; ');
        return filhos ? `#${no.id}: pendentes ${filhos}` : `#${no.id}`;
    });
    return (
        'Não é possível encerrar este nó enquanto houver encaminhamento(s) pendente(s) ' +
        `no mesmo setor: ${partes.join(' | ')}. Encerre o(s) nó(s) filho(s) ou aguarde a conclusão.`
    );
}

function filhosInternosBloqueantesNo(no) {
    if (!no) return [];
    if (Array.isArray(no.filhos_abertos_internos) && no.filhos_abertos_internos.length) {
        return no.filhos_abertos_internos;
    }
    return no.pode_encerrar === false ? no.filhos_abertos_externos || [] : [];
}
