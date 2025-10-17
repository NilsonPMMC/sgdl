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
    // Se a rota não for a de login E o usuário não estiver autenticado
    if (to.name !== 'login' && !userStore.isAuthenticated) {
        next({ name: 'login' }); // Redireciona para o login
    } else {
        next(); // Permite a navegação
    }
});

export default router;
