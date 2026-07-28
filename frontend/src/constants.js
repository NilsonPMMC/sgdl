import { SGDL_BRAND } from '@/theme/sgdl-preset';

/** Perfis com acesso ao Copiloto (criação de ofícios por conversa). */
export const PERFIS_COPILOTO = ['VEREADOR', 'GESTOR'];

/** Página inicial após login (Vereador → Copiloto; demais → Dashboard). */
export function rotaHomePorPerfil(perfil) {
    if (perfil === 'VEREADOR') {
        return { name: 'copiloto' };
    }
    return { name: 'dashboard' };
}

/** Rota de login conforme portal escolhido (vereador | prefeitura). */
export function loginRouteForPortal(portal) {
    return portal === 'vereador' ? '/login/vereador' : '/login';
}

export const PORTAL_AUTH = {
    vereador: {
        perfis: ['VEREADOR', 'ASSESSOR'],
        label: 'Portal do Vereador',
        loginRoute: '/login/vereador'
    },
    prefeitura: {
        perfis: ['PROTOCOLO', 'SECRETARIA', 'GESTOR'],
        label: 'Portal Operacional',
        loginRoute: '/login'
    }
};

export function portalParaPerfil(perfil) {
    if (PORTAL_AUTH.vereador.perfis.includes(perfil)) {
        return 'vereador';
    }
    return 'prefeitura';
}

export function perfilPermitidoNoPortal(perfil, portal) {
    const cfg = PORTAL_AUTH[portal];
    if (!cfg) return true;
    return cfg.perfis.includes(perfil);
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

/** Cores para gráficos (1ª série = marca institucional #213a8f). */
export const CHART_COLORS = [
    SGDL_BRAND.primary,
    '#66BB6A',
    '#FFA726',
    '#26C6DA',
    '#7E57C2',
    '#EF5350',
    '#26A69A',
    '#FFCA28'
];
