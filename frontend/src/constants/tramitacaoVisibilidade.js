/** Tipos visíveis na timeline do perfil VEREADOR (P8 — marcos legislativos externos). */
export const TIPOS_TRAMITACAO_VISIVEIS_VEREADOR = new Set([
    'ENVIO_OFICIAL',
    'CONCLUSAO',
    'DEVOLUTIVA_PROTOCOLO',
    'ENCERRAMENTO_DEVOLUTIVA'
]);

/** Eventos da timeline operacional visíveis ao vereador. */
export const TIPOS_EVENTO_OPERACIONAL_VEREADOR = new Set([
    'ENVIO_OFICIAL',
    'DESPACHO',
    'CONCLUSAO',
    'CONCLUSAO_PARCIAL',
    'CONCLUSAO_TECNICA',
    'DEVOLUTIVA_PROTOCOLO',
    'CONCLUSAO_FINAL',
    'ENCERRAMENTO_DEVOLUTIVA'
]);

/** Eventos da timeline operacional visíveis ao vereador. */

export const STATUS_EXECUCAO_OPERACIONAL = new Set([
    'PROTOCOLADO',
    'EM_EXECUCAO',
    'AGUARDANDO_TRANSFERENCIA',
    'AGUARDANDO_DEVOLUTIVA_PROTOCOLO'
]);

const TEXTO_INSTITUCIONAL_VEREADOR = {
    ENVIO_OFICIAL: 'Ofício enviado oficialmente ao Protocolo.',
    DESPACHO: 'Demanda despachada pela equipe do Protocolo Legislativo.',
    CONCLUSAO: 'Serviço concluído pela secretaria responsável.',
    DEVOLUTIVA_PROTOCOLO: 'Devolutiva recebida do Protocolo.',
    CONCLUSAO_FINAL: 'Conclusão final emitida pelo Protocolo Legislativo.',
    ENCERRAMENTO_DEVOLUTIVA: 'Demanda encerrada após devolutiva ao vereador.'
};

const ROTULO_POR_TIPO = {
    ENVIO_OFICIAL: 'Gabinete Legislativo',
    DEVOLUTIVA_PROTOCOLO: 'Protocolo Legislativo',
    ENCERRAMENTO_DEVOLUTIVA: 'Gabinete Legislativo'
};

export function tramitacaoVisivelParaVereador(tipo) {
    return TIPOS_TRAMITACAO_VISIVEIS_VEREADOR.has((tipo || '').toUpperCase());
}

export function filtrarTramitacoesVereador(tramitacoes, statusDemanda) {
    if (!Array.isArray(tramitacoes)) return [];
    let items = tramitacoes.filter((t) => tramitacaoVisivelParaVereador(t.tipo));
    const status = (statusDemanda || '').toUpperCase();
    if (STATUS_EXECUCAO_OPERACIONAL.has(status)) {
        items = items.filter((t) => (t.tipo || '').toUpperCase() === 'ENVIO_OFICIAL');
    }
    return items;
}

function extrairRespostaDevolutiva(descricao) {
    const texto = (descricao || '').trim();
    const match = texto.match(/Resposta:\s*\n([\s\S]+)/i);
    return match ? match[1].trim() : texto;
}

/** Rótulo amigável para marcos legislativos no perfil vereador. */
export function labelTramitacaoVereador(item) {
    if (!item) return '';
    const tipo = (item.tipo || '').toUpperCase();
    if (tipo === 'CONCLUSAO') return 'Serviço concluído';
    if (tipo === 'DEVOLUTIVA_PROTOCOLO') return 'Devolutiva do Protocolo';
    if (tipo === 'ENCERRAMENTO_DEVOLUTIVA') return 'Encerramento';
    if (tipo === 'ENVIO_OFICIAL') return 'Envio oficial';
    return item.tipo_display || item.tipo || '';
}

/** Rótulo institucional (secretaria/setor) — defesa em profundidade no FE. */
export function rotuloInstitucionalTramitacao(item) {
    if (!item) return '';
    if (item.rotulo_institucional) return item.rotulo_institucional;
    if (item.responsavel?.username && item.responsavel.username !== 'Prefeitura') {
        return item.responsavel.username;
    }
    const tipo = (item.tipo || '').toUpperCase();
    if (ROTULO_POR_TIPO[tipo]) return ROTULO_POR_TIPO[tipo];
    if (item.orgao_nome && item.unidade_nome) {
        return `${item.orgao_nome} — ${item.unidade_nome}`;
    }
    if (item.orgao_nome) return item.orgao_nome;
    if (item.unidade_destino?.orgao_nome && item.unidade_destino?.nome) {
        return `${item.unidade_destino.orgao_nome} — ${item.unidade_destino.sigla || item.unidade_destino.nome}`;
    }
    return 'Prefeitura Municipal';
}

export function contextoExecutoraTramitacao(item) {
    if (!item) return null;
    const orgao = item.orgao_nome || item.unidade_destino?.orgao_nome;
    const unidade = item.unidade_nome || item.unidade_destino?.sigla || item.unidade_destino?.nome;
    if (!orgao && !unidade) return null;
    return { orgao, unidade };
}

/** Descrição institucional — oculta trânsito interno (defesa em profundidade no FE). */
export function descricaoTramitacaoVereador(item) {
    if (!item) return '';
    const tipo = (item.tipo || '').toUpperCase();
    if (tipo === 'DEVOLUTIVA_PROTOCOLO') {
        const resposta = extrairRespostaDevolutiva(item.descricao);
        return resposta || TEXTO_INSTITUCIONAL_VEREADOR[tipo];
    }
    if (tipo === 'CONCLUSAO') {
        const ctx = contextoExecutoraTramitacao(item);
        if (ctx?.orgao && ctx?.unidade) {
            return `Serviço concluído por ${ctx.orgao} — ${ctx.unidade}.`;
        }
        if (ctx?.orgao) {
            return `Serviço concluído por ${ctx.orgao}.`;
        }
    }
    return TEXTO_INSTITUCIONAL_VEREADOR[tipo] || 'Andamento registrado pela Prefeitura Municipal.';
}

export function statusPermitePacoteDevolutivaVereador(status) {
    return ['DEVOLVIDO_VEREADOR', 'FINALIZADO'].includes(status);
}

export function perfilEhVereador(perfil) {
    return (perfil || '').toUpperCase().trim() === 'VEREADOR';
}

function tipoEventoOperacional(item) {
    const acao = item?.metadata?.acao;
    if (acao === 'ABERTURA_PERNAS_TRANSVERSAL') return 'ABERTURA_PERNAS_TRANSVERSAL';
    return (item?.tipo || '').toUpperCase();
}

function dedupeDevolutivaVereador(items) {
    const temConclusaoFinal = items.some((item) => tipoEventoOperacional(item) === 'CONCLUSAO_FINAL');
    if (!temConclusaoFinal) return items;
    const instantesFinal = new Set(
        items
            .filter((item) => tipoEventoOperacional(item) === 'CONCLUSAO_FINAL')
            .map((item) => String(item?.timestamp || '').slice(0, 19))
    );
    return items.filter((item) => {
        if (tipoEventoOperacional(item) !== 'DEVOLUTIVA_PROTOCOLO') return true;
        return !instantesFinal.has(String(item?.timestamp || '').slice(0, 19));
    });
}

/** Eventos scatter/internos ocultos na timeline do vereador. */
export const TIPOS_SCATTER_OCULTOS_VEREADOR = new Set([
    'OPERACAO_NO',
    'ABERTURA_NO',
    'ENCAMINHAMENTO_NO',
    'ENCERRAR',
    'DESPACHAR',
    'DESPACHAR_ENCERRAR',
    'CONSOLIDAR',
    'ABERTURA_PERNAS_TRANSVERSAL',
    'STATUS_UPDATE',
    'TRIAGEM_PROTOCOLO'
]);

function ehTipoOcultoVereador(item) {
    return TIPOS_SCATTER_OCULTOS_VEREADOR.has(tipoEventoOperacional(item));
}

function dedupeConclusaoFinalVereador(items) {
    let visto = false;
    return items.filter((item) => {
        if (tipoEventoOperacional(item) !== 'CONCLUSAO_FINAL') return true;
        if (visto) return false;
        visto = true;
        return true;
    });
}

export function filtrarTimelineOperacionalVereador(
    timeline,
    statusDemanda,
    demandaLiderId = null,
    demandaAtualId = null
) {
    if (!Array.isArray(timeline)) return [];
    let items = timeline.filter((item) => {
        if (ehTipoOcultoVereador(item)) return false;
        const tipo = tipoEventoOperacional(item);
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
        return TIPOS_EVENTO_OPERACIONAL_VEREADOR.has(tipo);
    });
    items = dedupeDevolutivaVereador(items);
    items = dedupeConclusaoFinalVereador(items);
    const status = (statusDemanda || '').toUpperCase();
    if (STATUS_EXECUCAO_OPERACIONAL.has(status)) {
        items = items.filter((item) => {
            const tipo = tipoEventoOperacional(item);
            return tipo === 'ENVIO_OFICIAL' || tipo === 'DESPACHO';
        });
    }
    return items;
}

/** Timeline institucional do vereador: marcos + histórico técnico consolidado (opcional). */
export function montarTimelineVereador(
    timeline,
    historicoTecnico,
    statusDemanda,
    demandaAtualId,
    demandaLiderId,
    ordenarFn,
    incluirHistorico = true
) {
    let items = filtrarTimelineOperacionalVereador(
        timeline,
        statusDemanda,
        demandaLiderId,
        demandaAtualId
    );

    if (incluirHistorico) {
        const eventos = (historicoTecnico?.eventos_tecnicos || []).filter((ev) =>
            (ev?.parecer || '').trim()
        );
        if (eventos.length) {
            const idsMarcos = new Set(items.map((item) => String(item.id)));
            const fromHistorico = eventos
                .filter((ev) => ev.tramitacao_id == null || !idsMarcos.has(String(ev.tramitacao_id)))
                .map((ev) => ({
                    id: ev.tramitacao_id || `hist-${ev.no_id || ''}-${ev.timestamp}`,
                    demanda_id: ev.demanda_id,
                    tipo: 'CONCLUSAO_PARCIAL',
                    timestamp: ev.timestamp,
                    orgao_nome: ev.orgao_nome,
                    setor_nome: ev.setor_nome,
                    metadata: { parecer: ev.parecer, setor_nome: ev.setor_nome },
                    anexos: Array.isArray(ev.anexos) ? ev.anexos : [],
                    responsavel: ev.responsavel,
                    _historicoEvento: ev
                }));
            items = dedupeConclusaoFinalVereador([...items, ...fromHistorico]);
        }
    }

    return typeof ordenarFn === 'function' ? ordenarFn(items) : items;
}

export function labelEventoOperacionalVereador(item) {
    const tipo = tipoEventoOperacional(item);
    if (tipo === 'DESPACHO') return 'Despacho inicial (Protocolo)';
    if (['CONCLUSAO_PARCIAL', 'CONCLUSAO_TECNICA', 'CONCLUSAO'].includes(tipo)) {
        if (item?._historicoEvento || item?.setor_nome || item?.metadata?.setor_nome) {
            return 'Encerramento no setor';
        }
        return 'Serviço concluído';
    }
    if (['DEVOLUTIVA_PROTOCOLO', 'CONCLUSAO_FINAL'].includes(tipo)) {
        return 'Despacho de devolutiva (Protocolo)';
    }
    if (tipo === 'ENVIO_OFICIAL') return 'Envio oficial';
    if (tipo === 'ENCERRAMENTO_DEVOLUTIVA') return 'Encerramento';
    return labelTramitacaoVereador({ tipo });
}

export function rotuloInstitucionalEventoOperacional(item) {
    const tipo = tipoEventoOperacional(item);
    if (tipo === 'ENVIO_OFICIAL') return 'Gabinete Legislativo';
    if (['DESPACHO', 'DEVOLUTIVA_PROTOCOLO', 'CONCLUSAO_FINAL'].includes(tipo)) {
        return 'Protocolo Legislativo';
    }
    if (['CONCLUSAO_PARCIAL', 'CONCLUSAO_TECNICA', 'CONCLUSAO'].includes(tipo)) {
        return item?.orgao_nome || item?.metadata?.orgao_nome || 'Secretaria Municipal';
    }
    return item?.orgao_nome || 'Prefeitura Municipal';
}

function extrairParecerEvento(item) {
    const meta = item?.metadata || {};
    const parecer = (meta.parecer || '').trim();
    if (parecer) return parecer.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    return extrairRespostaDevolutiva(item?.descricao || '');
}

const TEXTO_ENCERRAMENTO_SETOR_VEREADOR = 'Processo encerrado no setor.';

/** Encerramento de nó operacional (scatter-gather) — vereador não vê parecer técnico. */
export function ehEncerramentoNoSetorVereador(item) {
    const tipo = tipoEventoOperacional(item);
    if (!['CONCLUSAO_PARCIAL', 'CONCLUSAO_TECNICA', 'CONCLUSAO'].includes(tipo)) return false;
    return Boolean(
        item?._historicoEvento ||
            item?.setor_nome ||
            item?.metadata?.setor_nome
    );
}

export function descricaoEncerramentoNoSetorVereador() {
    return TEXTO_ENCERRAMENTO_SETOR_VEREADOR;
}

export function descricaoEventoOperacionalVereador(item) {
    const tipo = tipoEventoOperacional(item);
    const orgao = item?.orgao_nome || item?.metadata?.orgao_nome || 'Secretaria Municipal';
    const setor = item?.metadata?.setor_nome || '';

    if (tipo === 'ENVIO_OFICIAL') {
        return TEXTO_INSTITUCIONAL_VEREADOR.ENVIO_OFICIAL;
    }
    if (tipo === 'DESPACHO') {
        return TEXTO_INSTITUCIONAL_VEREADOR.DESPACHO;
    }
    if (['CONCLUSAO_PARCIAL', 'CONCLUSAO_TECNICA', 'CONCLUSAO'].includes(tipo)) {
        if (orgao && setor) return `Serviço concluído por ${orgao} — ${setor}.`;
        if (orgao) return `Serviço concluído por ${orgao}.`;
        return TEXTO_INSTITUCIONAL_VEREADOR.CONCLUSAO;
    }
    if (['DEVOLUTIVA_PROTOCOLO', 'CONCLUSAO_FINAL'].includes(tipo)) {
        const parecer = extrairParecerEvento(item);
        if (parecer) return parecer;
        return TEXTO_INSTITUCIONAL_VEREADOR.CONCLUSAO_FINAL;
    }
    if (tipo === 'ENCERRAMENTO_DEVOLUTIVA') {
        return TEXTO_INSTITUCIONAL_VEREADOR.ENCERRAMENTO_DEVOLUTIVA;
    }
    return 'Andamento registrado pela Prefeitura Municipal.';
}
