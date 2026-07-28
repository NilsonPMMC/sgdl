/** Gestão operacional — fluxos, eventos e rótulos de UI. */

import {
    labelEventoOperacionalVereador,
    rotuloInstitucionalEventoOperacional
} from '@/constants/tramitacaoVisibilidade';
import { rotuloEtapaAssinatura } from '@/constants/assinaturaEletronica';

export const FLUXO_DIRETO = 'FLUXO_DIRETO';
export const FLUXO_TRANSVERSAL = 'FLUXO_TRANSVERSAL';

export const MODO_OFICIO_UNICO = 'OFICIO_UNICO';
export const MODO_CLUSTER_SUPER_OS = 'CLUSTER_SUPER_OS';

export const ORQUESTRADOR_SECRETARIA_LIDER = 'SECRETARIA_LIDER';
export const ORQUESTRADOR_PROTOCOLO = 'PROTOCOLO';

export const PERFIL_CENARIO_1 = 'CENARIO_1';
export const PERFIL_CENARIO_2 = 'CENARIO_2';
export const PERFIL_CENARIO_3 = 'CENARIO_3';
export const PERFIL_CENARIO_4 = 'CENARIO_4';
export const PERFIL_CENARIO_5 = 'CENARIO_5';

export const ROTULO_FLUXO = {
    [FLUXO_DIRETO]: 'Fluxo direto',
    [FLUXO_TRANSVERSAL]: 'Fluxo transversal'
};

export const ROTULO_MODO_ENTRADA = {
    [MODO_OFICIO_UNICO]: 'Ofício único',
    [MODO_CLUSTER_SUPER_OS]: 'Cluster Super OS'
};

export const ROTULO_ORQUESTRADOR = {
    [ORQUESTRADOR_SECRETARIA_LIDER]: 'Secretaria responsável',
    [ORQUESTRADOR_PROTOCOLO]: 'Protocolo'
};

export const ROTULO_PERFIL_PROCESSO = {
    [PERFIL_CENARIO_1]: 'C1 — Cluster, secretaria líder',
    [PERFIL_CENARIO_2]: 'C2 — Ofício único transversal',
    [PERFIL_CENARIO_3]: 'C3 — Transversal, Protocolo',
    [PERFIL_CENARIO_4]: 'C4 — Fluxo direto',
    [PERFIL_CENARIO_5]: 'C5 — Cluster, Protocolo'
};

export const ROTULO_TIPO_ENTRADA = {
    CARTA_SERVICO: 'Carta de serviços',
    TENDENCIA: 'Tendência'
};

export const ROTULO_EVENTO = {
    ENVIO_OFICIAL: 'Envio oficial',
    TRIAGEM_PROTOCOLO: 'Triagem do Protocolo',
    RECUSA_PROTOCOLO: 'Recusa do Protocolo',
    DESPACHO: 'Despacho',
    ABERTURA_PERNAS_TRANSVERSAL: 'Despacho transversal (secretaria)',
    EXECUCAO: 'Execução operacional',
    ENCAMINHAMENTO_SETOR: 'Encaminhamento de setor',
    STATUS_UPDATE: 'Atualização de status',
    CONCLUSAO_TECNICA: 'Conclusão técnica',
    CONCLUSAO_PARCIAL: 'Conclusão parcial',
    DEVOLUCAO: 'Devolução ao Protocolo',
    CONCLUSAO_FINAL: 'Conclusão final',
    SOLICITACAO_DEVOLUTIVA: 'Solicitação de devolutiva',
    DEVOLUTIVA_PROTOCOLO: 'Devolutiva ao vereador',
    DESPACHAR: 'Despacho scatter-gather',
    DESPACHAR_ENCERRAR: 'Despacho e encerramento local',
    ENCERRAR: 'Encerramento de nó operacional',
    BOOTSTRAP: 'Abertura de nó operacional',
    CONSOLIDAR: 'Consolidação de nós equivalentes',
    ENCERRAR_LOTE: 'Encerramento unificado de nós',
    OPERACAO_NO: 'Operação scatter-gather'
};

export const ICONE_EVENTO = {
    ENVIO_OFICIAL: { icon: 'pi pi-send', color: 'avatar-blue' },
    TRIAGEM_PROTOCOLO: { icon: 'pi pi-filter', color: 'avatar-orange' },
    RECUSA_PROTOCOLO: { icon: 'pi pi-times-circle', color: 'avatar-red' },
    DESPACHO: { icon: 'pi pi-share-alt', color: 'avatar-orange' },
    ABERTURA_PERNAS_TRANSVERSAL: { icon: 'pi pi-sitemap', color: 'avatar-orange' },
    EXECUCAO: { icon: 'pi pi-cog', color: 'avatar-blue' },
    ENCAMINHAMENTO_SETOR: { icon: 'pi pi-arrow-right-arrow-left', color: 'avatar-cyan' },
    STATUS_UPDATE: { icon: 'pi pi-sync', color: 'avatar-cyan' },
    CONCLUSAO_TECNICA: { icon: 'pi pi-check-square', color: 'avatar-purple' },
    CONCLUSAO_PARCIAL: { icon: 'pi pi-check', color: 'avatar-green' },
    DEVOLUCAO: { icon: 'pi pi-replay', color: 'avatar-yellow' },
    CONCLUSAO_FINAL: { icon: 'pi pi-verified', color: 'avatar-purple' },
    SOLICITACAO_DEVOLUTIVA: { icon: 'pi pi-send', color: 'avatar-purple' },
    DEVOLUTIVA_PROTOCOLO: { icon: 'pi pi-reply', color: 'avatar-blue' },
    DESPACHAR: { icon: 'pi pi-share-alt', color: 'avatar-orange' },
    DESPACHAR_ENCERRAR: { icon: 'pi pi-directions', color: 'avatar-cyan' },
    ENCERRAR: { icon: 'pi pi-check-circle', color: 'avatar-green' },
    CONSOLIDAR: { icon: 'pi pi-compress', color: 'avatar-cyan' },
    ENCERRAR_LOTE: { icon: 'pi pi-check-circle', color: 'avatar-green' },
    BOOTSTRAP: { icon: 'pi pi-sitemap', color: 'avatar-blue' },
    OPERACAO_NO: { icon: 'pi pi-sitemap', color: 'avatar-orange' }
};

export const SEVERITY_EVENTO = {
    RECUSA_PROTOCOLO: 'danger',
    DEVOLUCAO: 'warn',
    CONCLUSAO_TECNICA: 'success',
    CONCLUSAO_PARCIAL: 'success',
    CONCLUSAO_FINAL: 'success',
    TRIAGEM_PROTOCOLO: 'info',
    ABERTURA_PERNAS_TRANSVERSAL: 'help',
    EXECUCAO: 'info',
    DESPACHAR: 'info',
    DESPACHAR_ENCERRAR: 'help',
    ENCERRAR: 'success',
    CONSOLIDAR: 'info',
    ENCERRAR_LOTE: 'success',
    BOOTSTRAP: 'secondary'
};

/** Tipo de exibição — metadata.acao sobrescreve tipo bruto da tramitação. */
export function tipoEventoTimeline(item) {
    const acao = item?.metadata?.acao;
    if (acao === 'ABERTURA_PERNAS_TRANSVERSAL') return 'ABERTURA_PERNAS_TRANSVERSAL';
    if (item?.metadata?.scatter_gather) {
        const acaoNo = item?.metadata?.acao_no || item?.tipo;
        if (acaoNo) return String(acaoNo).toUpperCase();
    }
    return (item?.tipo || '').toUpperCase();
}

export function rotuloFluxo(fluxo) {
    return ROTULO_FLUXO[fluxo] || fluxo || '';
}

export function rotuloPerfilProcesso(perfil) {
    return ROTULO_PERFIL_PROCESSO[perfil] || perfil || '';
}

export function rotuloOrquestrador(orquestrador) {
    return ROTULO_ORQUESTRADOR[orquestrador] || orquestrador || '';
}

export function rotuloEvento(tipo, item = null) {
    const chave = item ? tipoEventoTimeline(item) : (tipo || '').toUpperCase();
    return ROTULO_EVENTO[chave] || tipo || '';
}

export function iconeEvento(tipo, item = null) {
    const chave = item ? tipoEventoTimeline(item) : (tipo || '').toUpperCase();
    return ICONE_EVENTO[chave] || { icon: 'pi pi-info-circle', color: 'avatar-gray' };
}

export function severityEvento(tipo, item = null) {
    const chave = item ? tipoEventoTimeline(item) : (tipo || '').toUpperCase();
    return SEVERITY_EVENTO[chave] || 'secondary';
}

function dedupeConclusaoFinalOperacional(items) {
    let visto = false;
    return items.filter((item) => {
        if (tipoEventoTimeline(item) !== 'CONCLUSAO_FINAL') return true;
        if (visto) return false;
        visto = true;
        return true;
    });
}

function dedupeDevolutivaConclusaoFinal(timeline) {
    if (!Array.isArray(timeline)) return [];
    const demandasComConclusaoFinal = new Set(
        timeline
            .filter((item) => tipoEventoTimeline(item) === 'CONCLUSAO_FINAL')
            .map((item) => item.demanda_id)
    );
    return timeline.filter((item) => {
        const tipo = tipoEventoTimeline(item);
        if (tipo !== 'DEVOLUTIVA_PROTOCOLO') return true;
        return !demandasComConclusaoFinal.has(item.demanda_id);
    });
}

/** Remove espelhos de cluster, ruído scatter e duplicatas na timeline operacional. */
export function filtrarTimelineOperacional(timeline, opts = {}) {
    if (!Array.isArray(timeline)) return [];
    const demandaAtualId = opts.demandaAtualId ?? null;
    const demandaLiderId = opts.demandaLiderId ?? null;

    let items = timeline.filter((item) => {
        const meta = item?.metadata || {};
        if (meta.espelhada_do_lider) return false;
        const tipo = tipoEventoTimeline(item);
        if (tipo === 'ABERTURA_NO' || tipo === 'ENCAMINHAMENTO_NO') return false;
        if (tipo === 'ENVIO_OFICIAL') {
            return (
                demandaAtualId == null ||
                String(item?.demanda_id) === String(demandaAtualId)
            );
        }
        if (tipo === 'DESPACHO') {
            const liderId = demandaLiderId ?? demandaAtualId;
            return liderId == null || String(item?.demanda_id) === String(liderId);
        }
        return true;
    });
    items = dedupeConclusaoFinalOperacional(items);
    items = dedupeDevolutivaConclusaoFinal(items);
    return items;
}

function ordenarTimelineCronologica(timeline) {
    return [...timeline].sort((a, b) => {
        const ta = Date.parse(a?.timestamp || '') || 0;
        const tb = Date.parse(b?.timestamp || '') || 0;
        if (ta !== tb) return ta - tb;
        return String(a?.id ?? '').localeCompare(String(b?.id ?? ''));
    });
}

/** Converte tramitações da API `/demandas/{id}/` para itens da timeline operacional. */
export function tramitacoesParaTimelineOperacional(tramitacoes, demandaId) {
    if (!Array.isArray(tramitacoes)) return [];
    return tramitacoes.map((t) => {
        const acaoNo = t.acao_no || null;
        const scatter = Boolean(acaoNo);
        const responsavel = t.responsavel;
        let responsavelNome = null;
        if (typeof responsavel === 'string' && responsavel.trim()) {
            responsavelNome = responsavel.trim();
        } else if (responsavel && typeof responsavel === 'object') {
            responsavelNome =
                [responsavel.first_name, responsavel.last_name].filter(Boolean).join(' ').trim() ||
                responsavel.username ||
                null;
        }
        return {
            id: t.id,
            demanda_id: demandaId,
            tipo: t.tipo,
            descricao: t.descricao,
            metadata: {
                acao_no: acaoNo,
                orgao_id: t.orgao_id,
                orgao_nome: t.orgao_nome,
                setor_nome: t.setor_nome,
                no_id: t.no_id,
                destinos: t.destinos,
                scatter_gather: scatter
            },
            orgao_id: t.orgao_id,
            orgao_nome: t.orgao_nome,
            setor_nome: t.setor_nome,
            unidade_nome: t.setor_nome,
            no_id: t.no_id,
            responsavel: responsavelNome,
            timestamp: t.timestamp,
            anexos: Array.isArray(t.anexos) ? t.anexos : [],
            ramificacao: null
        };
    });
}

export function timelineOperacionalOrdenada(timeline, opts = {}) {
    if (opts.completa) {
        return ordenarTimelineCronologica(timeline);
    }
    return ordenarTimelineCronologica(filtrarTimelineOperacional(timeline, opts));
}

/** Cronológica (mais antigo → mais recente) para o perfil vereador. */
export function timelineOperacionalVereadorOrdenada(timeline) {
    return ordenarTimelineCronologica(dedupeDevolutivaConclusaoFinal(timeline));
}

/** Secretaria e setor — conector literal " e " conforme layout da timeline. */
export function secretariaESetorEvento(item) {
    const meta = item?.metadata || {};
    const orgao = item?.orgao_nome || meta.orgao_nome || '';
    const setor = item?.setor_nome || item?.unidade_nome || meta.setor_nome || '';
    const tipo = tipoEventoTimeline(item);

    if (
        ['DESPACHO', 'TRIAGEM_PROTOCOLO', 'DEVOLUTIVA_PROTOCOLO', 'CONCLUSAO_FINAL'].includes(
            tipo
        ) &&
        !orgao &&
        !setor
    ) {
        return 'Protocolo Legislativo';
    }
    if (tipo === 'ENVIO_OFICIAL' && !orgao && !setor) {
        return 'Gabinete Legislativo';
    }
    if (orgao && setor) return `${orgao} e ${setor}`;
    return orgao || setor || '';
}

export function responsavelEventoOperacional(item, modoVereador) {
    if (modoVereador) return null;
    const r = item?.responsavel;
    if (typeof r === 'string' && r.trim()) return r.trim();
    if (r && typeof r === 'object') {
        const nome = [r.first_name, r.last_name].filter(Boolean).join(' ').trim();
        return nome || r.username || null;
    }
    return null;
}

/** Marcos com rótulo de etapa de assinatura no cabeçalho (evita confundir origem/destino). */
const ETAPA_ASSINATURA_POR_TIPO = {
    ENVIO_OFICIAL: 'ENVIO_OFICIO',
    DESPACHO: 'DESPACHO_INICIAL',
    TRIAGEM_PROTOCOLO: 'DESPACHO_INICIAL',
    DEVOLUTIVA_PROTOCOLO: 'DESPACHO_DEVOLUTIVA',
    CONCLUSAO_FINAL: 'CONCLUSAO_FINAL',
    DESPACHAR: 'OPERACAO_SCATTER',
    DESPACHAR_ENCERRAR: 'OPERACAO_SCATTER',
    ENCERRAR: 'OPERACAO_SCATTER'
};

/** Texto em negrito no cabeçalho: etapa institucional ou setor executor. */
export function rotuloSetorEventoOperacional(item) {
    const tipo = tipoEventoTimeline(item);
    const etapa = ETAPA_ASSINATURA_POR_TIPO[tipo];
    if (etapa) {
        return rotuloEtapaAssinatura(etapa);
    }

    const meta = item?.metadata || {};
    const setor = item?.setor_nome || item?.unidade_nome || meta.setor_nome || '';
    if (setor) return setor;

    const orgao = item?.orgao_nome || meta.orgao_nome || '';
    if (['CONCLUSAO_PARCIAL', 'CONCLUSAO_TECNICA', 'CONCLUSAO'].includes(tipo) && orgao) {
        return orgao;
    }
    return orgao || 'Prefeitura Municipal';
}

/** Tag 1 — "{Secretaria e Setor} | {responsável} - {data e hora}". */
export function tagContextoEventoOperacional(item, modoVereador, formatarData) {
    const local = secretariaESetorEvento(item);
    const data = formatarData(item?.timestamp);
    const resp = responsavelEventoOperacional(item, modoVereador);

    if (local && resp && data) return `${local} | ${resp} - ${data}`;
    if (local && resp) return `${local} | ${resp}`;
    if (local && data) return `${local} - ${data}`;
    if (resp && data) return `${resp} - ${data}`;
    return local || resp || data || '';
}

/** Tag — rótulo institucional (Gabinete, Protocolo, secretaria executora). */
export function tagRotuloInstitucionalEvento(item, modoVereador) {
    if (modoVereador) {
        return rotuloInstitucionalEventoOperacional(item);
    }
    const tipo = tipoEventoTimeline(item);
    if (tipo === 'ENVIO_OFICIAL') return 'Gabinete Legislativo';
    if (
        [
            'DESPACHO',
            'TRIAGEM_PROTOCOLO',
            'DEVOLUTIVA_PROTOCOLO',
            'CONCLUSAO_FINAL',
            'SOLICITACAO_DEVOLUTIVA'
        ].includes(tipo)
    ) {
        return 'Protocolo Legislativo';
    }
    const orgao = item?.orgao_nome || item?.metadata?.orgao_nome;
    if (orgao) return orgao;
    if (item?.rotulo_institucional) return item.rotulo_institucional;
    return 'Prefeitura Municipal';
}

const ETAPAS_ASSINATURA_POR_EVENTO = {
    ENVIO_OFICIAL: ['ENVIO_OFICIO'],
    ENTRADA_VEREADOR: ['ENVIO_OFICIO'],
    DESPACHO: ['DESPACHO_INICIAL'],
    TRIAGEM_PROTOCOLO: ['DESPACHO_INICIAL'],
    CONCLUSAO_PARCIAL: ['CONCLUSAO_SECRETARIA'],
    CONCLUSAO_TECNICA: ['CONCLUSAO_SECRETARIA'],
    CONCLUSAO: ['CONCLUSAO_SECRETARIA'],
    DEVOLUTIVA_PROTOCOLO: ['CONCLUSAO_FINAL'],
    CONCLUSAO_FINAL: ['CONCLUSAO_FINAL']
};

export function assinaturasParaEventoOperacional(item, assinaturas) {
    if (!Array.isArray(assinaturas) || !assinaturas.length) return [];
    const tramId = item?.id != null ? Number(item.id) : null;
    if (tramId != null) {
        const porTramitacao = assinaturas.filter(
            (a) =>
                (a.etapa || '').toUpperCase() === 'OPERACAO_SCATTER' &&
                Number(a.tramitacao_id) === tramId
        );
        if (porTramitacao.length) return porTramitacao;
    }
    const chave = tipoEventoTimeline(item);
    const etapas = ETAPAS_ASSINATURA_POR_EVENTO[chave] || [];
    if (!etapas.length) return [];
    return assinaturas.filter((a) => etapas.includes((a.etapa || '').toUpperCase()));
}

export function anexosEventoOperacional(item, modoVereador, historicoPorTramitacao = null) {
    if (modoVereador) {
        const fromItem = Array.isArray(item?.anexos) ? item.anexos : [];
        if (fromItem.length) return fromItem;
        const hist =
            item?._historicoEvento ||
            (historicoPorTramitacao && item?.id != null
                ? historicoPorTramitacao.get(String(item.id))
                : null);
        return Array.isArray(hist?.anexos) ? hist.anexos : [];
    }
    const anexos = item?.anexos;
    return Array.isArray(anexos) ? anexos : [];
}

export function rotuloTipoEventoOperacional(item, modoVereador) {
    if (modoVereador) return labelEventoOperacionalVereador(item);
    return rotuloEvento(item?.tipo, item);
}
