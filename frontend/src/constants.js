// Em frontend/src/constants.js

export const STATUS_CHOICES_REPORTS = [
    { label: 'Aberta', value: 'ABERTA' },
    { label: 'Protocolada', value: 'PROTOCOLADA' },
    { label: 'Em Execução', value: 'EM_EXECUCAO' },
    { label: 'Concluída', value: 'CONCLUIDA' },
    { label: 'Rejeitada', value: 'REJEITADA' },
    { label: 'Aguardando Transferência', value: 'AGUARDANDO_TRANSFERENCIA' }
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
    '#FFCA28'  // yellow
];