/** Resultado operacional e base stand-by (estudo/viabilidade). */

export const RESULTADO_EXECUTADO = 'EXECUTADO';
export const RESULTADO_SEM_EXECUCAO = 'RESPONDIDO_SEM_EXECUCAO';
export const RESULTADO_ORIENTACAO = 'ORIENTACAO';
export const RESULTADO_PARCIAL = 'PARCIAL';

export const OPCOES_RESULTADO_OPERACIONAL = [
    { label: 'Executado', value: RESULTADO_EXECUTADO },
    { label: 'Respondido sem execução', value: RESULTADO_SEM_EXECUCAO },
    { label: 'Somente orientação', value: RESULTADO_ORIENTACAO },
    { label: 'Parcialmente executado', value: RESULTADO_PARCIAL }
];

export const MOTIVO_ESTUDO_VIABILIDADE = 'ESTUDO_VIABILIDADE';
export const MOTIVO_INVESTIMENTO = 'DEPENDE_INVESTIMENTO';
export const MOTIVO_LICITACAO = 'DEPENDE_LICITACAO';
export const MOTIVO_NORMATIVO = 'DEPENDE_NORMATIVO';
export const MOTIVO_INVIAVEL = 'INVIAVEL_TECNICO';
export const MOTIVO_INFORMACIONAL = 'INFORMACIONAL';

export const OPCOES_MOTIVO_NAO_EXECUCAO = [
    { label: 'Estudo / viabilidade técnica', value: MOTIVO_ESTUDO_VIABILIDADE },
    { label: 'Depende de investimento', value: MOTIVO_INVESTIMENTO },
    { label: 'Depende de licitação / contratação', value: MOTIVO_LICITACAO },
    { label: 'Depende de norma / legislação', value: MOTIVO_NORMATIVO },
    { label: 'Inviável técnico no momento', value: MOTIVO_INVIAVEL },
    { label: 'Registro informativo', value: MOTIVO_INFORMACIONAL }
];

export function estadoInicialResultadoOperacional() {
    return {
        resultado_operacional: RESULTADO_EXECUTADO,
        motivo_nao_execucao: null,
        escopo_geografico: '',
        registrar_stand_by: false
    };
}

export function resultadoPermiteStandBy(resultado) {
    return [RESULTADO_SEM_EXECUCAO, RESULTADO_ORIENTACAO].includes(resultado);
}

export function validarResultadoOperacional(form) {
    const resultado = form?.resultado_operacional;
    if (!resultado) {
        return 'Informe como o processo foi encerrado.';
    }
    if (resultado === RESULTADO_SEM_EXECUCAO && !form.motivo_nao_execucao) {
        return 'Informe o motivo quando o pedido não foi executado.';
    }
    if (form.registrar_stand_by) {
        if (!resultadoPermiteStandBy(resultado)) {
            return 'A base stand-by só se aplica a encerramentos sem execução ou orientação.';
        }
        if (!(form.escopo_geografico || '').trim() || form.escopo_geografico.trim().length < 3) {
            return 'Informe o escopo geográfico (ex.: município inteiro, bairro, trecho da via).';
        }
    }
    return null;
}

export function payloadResultadoOperacional(form) {
    const out = {
        resultado_operacional: form.resultado_operacional
    };
    if (form.motivo_nao_execucao) {
        out.motivo_nao_execucao = form.motivo_nao_execucao;
    }
    if ((form.escopo_geografico || '').trim()) {
        out.escopo_geografico = form.escopo_geografico.trim();
    }
    if (form.registrar_stand_by) {
        out.registrar_stand_by = true;
    }
    return out;
}

export function anexarResultadoOperacional(alvo, form) {
    const payload = payloadResultadoOperacional(form);
    Object.entries(payload).forEach(([chave, valor]) => {
        alvo[chave] = valor;
    });
    return alvo;
}
