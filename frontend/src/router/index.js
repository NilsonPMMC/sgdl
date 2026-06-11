import AppLayout from '@/layout/AppLayout.vue';
import { rotaHomePorPerfil } from '@/constants';
import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/stores/userStore';

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            component: AppLayout,
            children: [
                {
                    path: '/',
                    name: 'dashboard',
                    component: () => import('@/views/DashboardView.vue'),
                    meta: { requiresAuth: true }
                },
                {
                    path: '/consulta',
                    name: 'consulta',
                    component: () => import('@/views/ConsultaHubView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['VEREADOR', 'PROTOCOLO', 'SECRETARIA', 'GESTOR']
                    }
                },
                {
                    path: '/relatorios',
                    name: 'relatorios',
                    component: () => import('@/views/RelatoriosView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR']
                    }
                },
                {
                    path: '/notificacoes',
                    name: 'notificacoes',
                    component: () => import('@/views/NotificacoesView.vue'),
                    meta: { requiresAuth: true }
                },
                {
                    path: '/mapa-calor',
                    name: 'mapa-calor',
                    component: () => import('@/views/MapaCalorView.vue')
                },
                {
                    path: '/demandas',
                    name: 'demandas',
                    component: () => import('@/views/DemandasView.vue')
                },
                {
                    path: '/copiloto',
                    name: 'copiloto',
                    component: () => import('@/views/CopilotoView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['VEREADOR', 'GESTOR']
                    }
                },
                {
                    path: '/demandas/novo',
                    redirect: { name: 'copiloto' }
                },
                {
                    path: '/demandas/editar/:id',
                    name: 'demandas-editar',
                    component: () => import('@/views/DemandaForm.vue'),
                    props: true,
                    meta: {
                        requiresAuth: true,
                        perfis: ['VEREADOR', 'GESTOR'],
                        somenteRascunho: true
                    }
                },
                {
                    path: '/demandas/detalhes/:id',
                    name: 'demandas-detalhes',
                    component: () => import('@/views/DemandaDetailView.vue'),
                    props: true
                },
                {
                    path: '/perfil',
                    name: 'perfil',
                    component: () => import('@/views/pages/ProfileView.vue')
                },
                {
                    path: '/integracoes/sinapse/reconciliacao',
                    name: 'sinapse-reconciliacao',
                    component: () => import('@/views/SinapseReconciliacaoView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR']
                    }
                },
                {
                    path: '/carta-servicos',
                    name: 'carta-servicos',
                    component: () => import('@/views/CartaExplorerView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['VEREADOR', 'GESTOR', 'PROTOCOLO', 'SECRETARIA']
                    }
                },
                {
                    path: '/gestao-tendencias',
                    name: 'gestao-tendencias',
                    component: () => import('@/views/TendenciasGestaoView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR', 'PROTOCOLO']
                    }
                },
                {
                    path: '/gestao-recusas-copiloto',
                    name: 'gestao-recusas-copiloto',
                    component: () => import('@/views/RecusasCopilotoView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR', 'PROTOCOLO']
                    }
                },
                {
                    path: '/gestao-fluxo-servicos',
                    name: 'gestao-fluxo-servicos',
                    component: () => import('@/views/FluxoServicosView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR', 'PROTOCOLO']
                    }
                },
                {
                    path: '/gestao-setores',
                    name: 'gestao-setores',
                    component: () => import('@/views/SetoresView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR', 'PROTOCOLO', 'SECRETARIA']
                    }
                },
                {
                    path: '/gestao-usuarios',
                    name: 'gestao-usuarios',
                    component: () => import('@/views/GestaoUsuariosView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR', 'PROTOCOLO']
                    }
                },
                {
                    path: '/gestao-usuarios-secretaria',
                    redirect: { name: 'gestao-usuarios', query: { perfil: 'SECRETARIA' } }
                },
                {
                    path: '/gestao-usuarios-gestor',
                    redirect: { name: 'gestao-usuarios', query: { perfil: 'GESTOR' } }
                },
                {
                    path: '/clusters',
                    name: 'clusters',
                    component: () => import('@/views/ClustersView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR', 'PROTOCOLO']
                    }
                },
                {
                    path: '/admin/faq-copiloto',
                    name: 'admin-faq-copiloto',
                    component: () => import('@/views/AdminFaqView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR']
                    }
                },
                {
                    path: '/admin/configuracao-oficio',
                    name: 'configuracao-oficio',
                    component: () => import('@/views/ConfiguracaoOficioView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR']
                    }
                },
                {
                    path: '/admin/configuracao-carta',
                    name: 'configuracao-carta',
                    component: () => import('@/views/ConfiguracaoCartaView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR']
                    }
                },
                {
                    path: '/admin/assuntos-carta',
                    name: 'assuntos-carta',
                    component: () => import('@/views/AssuntosCartaView.vue'),
                    meta: {
                        requiresAuth: true,
                        perfis: ['GESTOR']
                    }
                }
            ]
        },
        {
            path: '/validar-assinatura/:codigo',
            name: 'validar-assinatura',
            component: () => import('@/views/ValidarAssinaturaView.vue')
        },
        {
            path: '/pages/notfound',
            name: 'notfound',
            component: () => import('@/views/pages/NotFound.vue')
        },

        {
            path: '/login',
            name: 'login',
            component: () => import('@/views/pages/Login.vue')
        },
        {
            path: '/resetar-senha/:uidb64/:token',
            name: 'resetar-senha',
            component: () => import('@/views/pages/ResetPasswordConfirm.vue'),
            props: true
        },
        {
            path: '/auth/access',
            name: 'accessDenied',
            component: () => import('@/views/pages/auth/Access.vue')
        },
        {
            path: '/auth/error',
            name: 'error',
            component: () => import('@/views/pages/auth/Error.vue')
        }
    ]
});

router.beforeEach((to, from, next) => {
    const userStore = useUserStore();
    const isAuthenticated = userStore.accessToken;
    const perfil = userStore.currentUser?.perfil;

    // --- INÍCIO DA CORREÇÃO ---
    // 1. Define uma lista de rotas públicas
    const publicPages = ['login', 'resetar-senha', 'validar-assinatura'];
    const authRequired = !publicPages.includes(to.name);
    // --- FIM DA CORREÇÃO ---

    // 2. Modifica a condição
    if (authRequired && !isAuthenticated) {
        // Se a rota exige login e o usuário não está logado, vai para /login
        next({ name: 'login' });
    } else if (to.meta?.perfis && Array.isArray(to.meta.perfis) && !to.meta.perfis.includes(perfil)) {
        next({ name: 'accessDenied' });
    } else if (isAuthenticated && to.name === 'login') {
        next(rotaHomePorPerfil(perfil));
    } else {
        // Em todos os outros casos (logado, ou indo para uma página pública), permite o acesso
        next();
    }
});

export default router;
