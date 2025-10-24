import AppLayout from '@/layout/AppLayout.vue';
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
                    component: () => import('@/views/DashboardView.vue')
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
                    path: '/demandas/novo',
                    name: 'demandas-novo',
                    component: () => import('@/views/DemandaForm.vue')
                },
                {
                    path: '/demandas/editar/:id',
                    name: 'demandas-editar',
                    component: () => import('@/views/DemandaForm.vue'),
                    props: true
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
                }
            ]
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

    // --- INÍCIO DA CORREÇÃO ---
    // 1. Define uma lista de rotas públicas
    const publicPages = ['login', 'resetar-senha']; 
    const authRequired = !publicPages.includes(to.name);
    // --- FIM DA CORREÇÃO ---

    // 2. Modifica a condição
    if (authRequired && !isAuthenticated) {
        // Se a rota exige login e o usuário não está logado, vai para /login
        next({ name: 'login' });
    } else if (isAuthenticated && to.name === 'login') {
        // Se já está logado e tenta ir para /login, vai para /
        next({ path: '/' }); 
    } else {
        // Em todos os outros casos (logado, ou indo para uma página pública), permite o acesso
        next();
    }
});

export default router;