/** Declarações exigidas nas assinaturas eletrônicas operacionais (A3/A4). */
export const DECLARACAO_ENVIO = 'ASSINO E ENVIO';
export const DECLARACAO_DESPACHO = 'ASSINO O DESPACHO';
export const DECLARACAO_GESTOR_PROTOCOLO = 'ASSINO COMO GESTOR DO PROTOCOLO';
export const DECLARACAO_GESTOR_SETOR = 'ASSINO COMO GESTOR DO SETOR';
export const DECLARACAO_CONCLUSAO = 'ASSINO A CONCLUSAO OPERACIONAL';
export const DECLARACAO_DEVOLUTIVA = 'ASSINO A DEVOLUTIVA';
export const DECLARACAO_CONCLUSAO_FINAL = 'ASSINO A CONCLUSAO FINAL';
export const DECLARACAO_ENCERRAMENTO_OPERACIONAL = 'ASSINO O ENCERRAMENTO OPERACIONAL';

/** Modos de exibição do painel de assinatura do Protocolo. */
export const MODO_PAINEL_ASSINATURA = {
    OPERADOR_APENAS: 'operador_apenas',
    DUAL_PROTOCOLO: 'dual_protocolo',
    GESTOR_APENAS: 'gestor_apenas'
};

/** Contextos de assinatura no fluxo operacional. */
export const CONTEXTO_ASSINATURA = {
    DESPACHO_INICIAL: 'despacho_inicial',
    CONCLUSAO_FINAL: 'conclusao_final',
    DEVOLUTIVA: 'devolutiva',
    CONCLUSAO_SECRETARIA: 'conclusao_secretaria'
};

/** Rótulos amigáveis para etapas de assinatura (painel B7). */
export const ROTULO_ETAPA_ASSINATURA = {
    ENVIO_OFICIO: 'Envio oficial do ofício',
    DESPACHO_INICIAL: 'Despacho inicial (Protocolo)',
    CONCLUSAO_SECRETARIA: 'Conclusão operacional (Secretaria)',
    DESPACHO_DEVOLUTIVA: 'Despacho de devolutiva (Protocolo)',
    CONCLUSAO_FINAL: 'Conclusão final (Protocolo)',
    OPERACAO_SCATTER: 'Operação scatter-gather'
};

export function rotuloEtapaAssinatura(etapa) {
    return ROTULO_ETAPA_ASSINATURA[etapa] || etapa;
}

/** Declaração exigida conforme a ação scatter-gather. */
export function declaracaoAssinaturaScatter(acao) {
    const a = String(acao || '').toUpperCase();
    if (a === 'DESPACHAR') return DECLARACAO_DESPACHO;
    return DECLARACAO_ENCERRAMENTO_OPERACIONAL;
}

/** Anexa campos de assinatura eletrônica ao payload scatter quando solicitado. */
export function payloadAssinaturaScatter(payload, acao, assinar) {
    if (!assinar) return payload;
    return {
        ...payload,
        assinar_eletronicamente: true,
        declaracao: declaracaoAssinaturaScatter(acao)
    };
}

export function despachoInicialAssinado(resumo) {
    return Boolean(resumo?.despacho_inicial_assinado);
}

export function despachoInicialPendenteGestor(resumo) {
    return Boolean(resumo?.despacho_inicial_pendente_gestor);
}

export function conclusaoFinalPendenteGestor(resumo) {
    return Boolean(resumo?.conclusao_final_pendente_gestor);
}

export function conclusaoSecretariaPendenteGestor(resumo) {
    return Boolean(resumo?.conclusao_secretaria_pendente_gestor);
}

export function operacaoScatterPendenteGestor(resumo) {
    return Boolean(resumo?.operacao_scatter_pendente_gestor);
}

export function demandaComValidacaoGestorPendente(resumo) {
    return (
        despachoInicialPendenteGestor(resumo) ||
        conclusaoFinalPendenteGestor(resumo) ||
        conclusaoSecretariaPendenteGestor(resumo) ||
        operacaoScatterPendenteGestor(resumo)
    );
}

/** Pendências de validação do gestor SGAC (Protocolo). */
export function pendenciaGestorProtocolo(resumo) {
    return despachoInicialPendenteGestor(resumo) || conclusaoFinalPendenteGestor(resumo);
}

/** Pendências de validação do gestor setorial (Secretaria). */
export function pendenciaGestorSecretaria(resumo) {
    return conclusaoSecretariaPendenteGestor(resumo) || operacaoScatterPendenteGestor(resumo);
}

export function usuarioEhSecretaria(user) {
    return (user?.perfil || '').toUpperCase() === 'SECRETARIA';
}

/** Gestor setorial de secretaria (não SGAC / Protocolo). */
export function usuarioEhGestorSetorialOperacional(user, userStore = null) {
    if (!user || (user.perfil || '').toUpperCase() !== 'GESTOR') return false;
    if (usuarioEhGestorProtocoloSgac(user, userStore)) return false;
    if (userStore?.isGestorSetorial) return true;
    const tipo = user.vinculo_gestor?.tipo_gestor || user.atuacao_sgdl?.tipo_gestor;
    return tipo === 'SETORIAL' || Boolean(user.sinapse_orgao_id);
}

/** Gestor que pode assinar como validador (SGAC ou setorial). */
export function usuarioPodeValidarGestorNaDemanda(user, userStore = null) {
    return (
        usuarioEhGestorProtocoloSgac(user, userStore) ||
        usuarioEhGestorSetorialOperacional(user, userStore)
    );
}

/**
 * Exibir banner / bloquear formulários conforme o perfil e a etapa pendente.
 */
export function usuarioDeveVerBannerValidacaoGestor(resumo, user, userStore = null) {
    if (!demandaComValidacaoGestorPendente(resumo)) return false;
    if (usuarioEhSecretaria(user) && pendenciaGestorSecretaria(resumo)) return true;
    if ((user?.perfil || '').toUpperCase() === 'PROTOCOLO' && pendenciaGestorProtocolo(resumo)) {
        return true;
    }
    if (usuarioEhGestorProtocoloSgac(user, userStore) && pendenciaGestorProtocolo(resumo)) {
        return true;
    }
    if (usuarioEhGestorSetorialOperacional(user, userStore) && pendenciaGestorSecretaria(resumo)) {
        return true;
    }
    return false;
}

export function usuarioDeveBloquearOperacaoAguardandoGestor(resumo, user, userStore = null) {
    return usuarioDeveVerBannerValidacaoGestor(resumo, user, userStore);
}

/** Texto do banner quando a operação só conclui após o gestor assinar. */
export function rotuloValidacaoGestorPendente(resumo) {
    if (despachoInicialPendenteGestor(resumo)) {
        return 'Despacho inicial aguardando validação do gestor do protocolo (SGAC)';
    }
    if (conclusaoFinalPendenteGestor(resumo)) {
        return 'Conclusão final aguardando validação do gestor do protocolo (SGAC)';
    }
    if (operacaoScatterPendenteGestor(resumo)) {
        return 'Encerramento/despacho scatter aguardando validação do gestor do setor';
    }
    if (conclusaoSecretariaPendenteGestor(resumo)) {
        return 'Conclusão operacional aguardando validação do gestor do setor';
    }
    return 'Assinatura aguardando validação do gestor';
}

export function devolutivaAssinada(resumo) {
    return Boolean(resumo?.devolutiva_assinada || resumo?.conclusao_final_assinada);
}

/** Badge curto na listagem do Protocolo após assinatura A4. */
export function badgeAssinaturaProtocolo(demanda) {
    const resumo = demanda?.assinaturas_resumo;
    if (!resumo) return null;
    if (despachoInicialPendenteGestor(resumo) || conclusaoFinalPendenteGestor(resumo)) {
        return { label: 'Aguardando gestor', severity: 'warn' };
    }
    if (despachoInicialAssinado(resumo)) {
        return { label: 'Despacho assinado', severity: 'success' };
    }
    if (devolutivaAssinada(resumo)) {
        return { label: 'Devolutiva assinada', severity: 'success' };
    }
    if (resumo.envio_oficio_assinado) {
        return { label: 'Ofício assinado', severity: 'info' };
    }
    return null;
}

export function formatarDataAssinatura(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('pt-BR');
}

export function formatSignatarioLinha(signatario) {
    if (!signatario) return '';
    const nome = signatario.nome || signatario.username || '';
    const cargo = (signatario.cargo || '').trim();
    return cargo ? `${nome} — ${cargo}` : nome;
}

export function gestorPorId(gestores, id) {
    if (!id || !Array.isArray(gestores)) return null;
    return gestores.find((g) => String(g.id) === String(id)) || null;
}

/** Usuário logado pode assinar como gestor do protocolo (SGAC). */
export function usuarioEhGestorProtocoloSgac(user, userStore = null) {
    if (!user) return false;
    const perfil = (user.perfil || '').toUpperCase();
    if (perfil === 'PROTOCOLO') return false;
    if (perfil !== 'GESTOR') return false;
    if (userStore?.isGestorGeral) return Number(user.sinapse_orgao_id) === 12 || !user.sinapse_orgao_id;
    const setores = user.atuacao_sgdl?.setores || user.vinculo_gestor?.setores || [];
    return setores.some((s) => String(s.sigla || '').includes('SGAC') || Number(s.id) === 754);
}

/**
 * Filas centralizadas do Protocolo: protocolados, devolutivas, finalizados, stand-by.
 * Protocolo, gestor SGAC ou gestor geral (sem vínculo setorial).
 */
export function usuarioPodePainelProtocoloCentral(user, userStore = null) {
    if (!user) return false;
    const perfil = (user.perfil || '').toUpperCase();
    if (perfil === 'PROTOCOLO') return true;
    if (perfil === 'GESTOR') {
        if (usuarioEhGestorProtocoloSgac(user, userStore)) return true;
        if (userStore?.isGestorGeral) return true;
        const tipo = user.vinculo_gestor?.tipo_gestor || user.atuacao_sgdl?.tipo_gestor;
        if (tipo === 'GERAL') return true;
    }
    return false;
}

/**
 * Modo do painel de assinatura para fluxos do Protocolo (despacho inicial / conclusão final / devolutiva).
 * @param {string} contexto — CONTEXTO_ASSINATURA.*
 * @param {{ perfil?: string, id?: number }} user
 * @param {{ isGestorGeral?: boolean }} [userStore]
 */
export function modoPainelAssinaturaProtocolo(contexto, user, userStore = null) {
    const perfil = (user?.perfil || '').toUpperCase();
    const ehGestorSgac = usuarioEhGestorProtocoloSgac(user, userStore);

    if (contexto === CONTEXTO_ASSINATURA.DEVOLUTIVA || contexto === CONTEXTO_ASSINATURA.CONCLUSAO_FINAL) {
        if (ehGestorSgac && perfil === 'GESTOR') {
            return MODO_PAINEL_ASSINATURA.GESTOR_APENAS;
        }
        if (perfil === 'PROTOCOLO' || (perfil === 'GESTOR' && userStore?.isGestorGeral)) {
            return MODO_PAINEL_ASSINATURA.OPERADOR_APENAS;
        }
        return MODO_PAINEL_ASSINATURA.OPERADOR_APENAS;
    }

    if (ehGestorSgac && perfil === 'GESTOR') {
        return MODO_PAINEL_ASSINATURA.GESTOR_APENAS;
    }

    return MODO_PAINEL_ASSINATURA.OPERADOR_APENAS;
}

/** Valida formulário de assinatura conforme o modo do painel. */
export function validarAssinaturaFormulario(modo, form, gestores = []) {
    const erros = [];
    if (!form?.hashPreview && !form?.hash_documento) {
        erros.push('Gere a prévia de assinatura antes de confirmar.');
        return erros;
    }

    if (modo === MODO_PAINEL_ASSINATURA.OPERADOR_APENAS) {
        if (!form.declaracaoOperador) {
            erros.push('Marque a declaração de assinatura eletrônica.');
        }
        return erros;
    }

    if (modo === MODO_PAINEL_ASSINATURA.GESTOR_APENAS) {
        if (!form.declaracaoGestor) {
            erros.push('Marque a declaração de assinatura como gestor do protocolo.');
        }
        return erros;
    }

    if (!form.declaracaoOperador) {
        erros.push('Marque a declaração do operador do protocolo.');
    }
    if (!form.gestor_protocolo_id) {
        erros.push('Selecione o gestor setorial do SGAC.');
    } else if (!gestorPorId(gestores, form.gestor_protocolo_id)) {
        erros.push('Gestor selecionado inválido.');
    }
    if (!form.declaracaoGestor) {
        erros.push('Marque a declaração do gestor do protocolo.');
    }
    return erros;
}

/** Monta payload de assinatura para endpoints do Protocolo. */
export function payloadAssinaturaProtocolo(modo, form, hashDocumento, declaracoes = {}) {
    const opText = declaracoes.declaracaoOperadorText || DECLARACAO_DESPACHO;
    const gestText = declaracoes.declaracaoGestorText || DECLARACAO_GESTOR_PROTOCOLO;
    const base = { hash_documento: hashDocumento };

    if (modo === MODO_PAINEL_ASSINATURA.OPERADOR_APENAS) {
        return { ...base, declaracao: opText, declaracao_operador: opText };
    }

    if (modo === MODO_PAINEL_ASSINATURA.GESTOR_APENAS) {
        return {
            ...base,
            declaracao_gestor: gestText,
            assinatura_apenas_gestor: true
        };
    }

    return {
        ...base,
        declaracao: opText,
        declaracao_operador: opText,
        declaracao_gestor: gestText,
        gestor_protocolo_id: form.gestor_protocolo_id
    };
}

/** Mensagem amigável a partir da lista de erros de validação. */
export function mensagemErroAssinatura(erros) {
    if (!erros?.length) return '';
    return erros[0];
}
