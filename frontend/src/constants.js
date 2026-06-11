// Em frontend/src/constants.js

/** Perfis com acesso ao Copiloto (criação de ofícios por conversa). */
export const PERFIS_COPILOTO = ['VEREADOR', 'GESTOR'];

/** Página inicial após login (Vereador → Copiloto; demais → Dashboard). */
export function rotaHomePorPerfil(perfil) {
    if (perfil === 'VEREADOR') {
        return { name: 'copiloto' };
    }
    return { name: 'dashboard' };
}

export const STATUS_CHOICES_REPORTS = [
    { label: 'Rascunho', value: 'RASCUNHO' },
    { label: 'Aberta', value: 'AGUARDANDO_PROTOCOLO' },
    { label: 'Protocolado', value: 'PROTOCOLADO' },
    { label: 'Em Execução', value: 'EM_EXECUCAO' },
    { label: 'Finalizada', value: 'FINALIZADO' },
    { label: 'Cancelada', value: 'CANCELADO' },
    { label: 'Aguardando Transferência', value: 'AGUARDANDO_TRANSFERENCIA' },
    { label: 'Aguardando devolutiva', value: 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO' },
    { label: 'Devolutiva ao vereador', value: 'DEVOLVIDO_VEREADOR' }
];

// Cores para os gráficos (padrão PrimeVue)
export const CHART_COLORS = [
    '#42A5F5', // blue
    '#66BB6A', // green
    '#FFA726', // orange
    '#26C6DA', // cyan
    '#7E57C2', // purple
    '#EF5350', // red
    '#26A69A', // teal
    '#FFCA28' // yellow
];
