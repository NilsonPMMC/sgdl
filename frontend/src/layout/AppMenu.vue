<script setup>
import { computed } from 'vue';
import { useUserStore } from '@/stores/userStore';

import AppMenuItem from './AppMenuItem.vue';
import { PERFIS_COPILOTO } from '@/constants';

const userStore = useUserStore();
const perfil = computed(() => userStore.currentUser?.perfil);
const podeCopiloto = computed(() => PERFIS_COPILOTO.includes(perfil.value));

const model = computed(() => [
    {
        label: 'Home',
        items: [
            {
                label: 'Copiloto',
                icon: 'pi pi-fw pi-comments',
                to: '/copiloto',
                visible: podeCopiloto.value
            },
            {
                label: 'Consulta rápida',
                icon: 'pi pi-fw pi-search',
                to: '/consulta',
                visible: ['VEREADOR', 'PROTOCOLO', 'SECRETARIA', 'GESTOR'].includes(perfil.value)
            },
            { label: 'Dashboard', icon: 'pi pi-fw pi-home', to: '/' },
            { label: 'Demandas', icon: 'pi pi-fw pi-book', to: '/demandas' },
            { label: 'Mapa de Calor', icon: 'pi pi-fw pi-map', to: '/mapa-calor' },
            {
                label: 'Relatórios',
                icon: 'pi pi-fw pi-chart-bar',
                to: '/relatorios',
                visible: perfil.value === 'GESTOR'
            },
            {
                label: 'Carta de Serviços',
                icon: 'pi pi-fw pi-bookmark',
                to: '/carta-servicos',
                visible: ['VEREADOR', 'GESTOR', 'PROTOCOLO', 'SECRETARIA'].includes(perfil.value)
            },
            {
                label: 'Gestão de Tendências',
                icon: 'pi pi-fw pi-chart-line',
                to: '/gestao-tendencias',
                visible: ['GESTOR', 'PROTOCOLO'].includes(perfil.value)
            },
            {
                label: 'Recusas Copiloto',
                icon: 'pi pi-fw pi-ban',
                to: '/gestao-recusas-copiloto',
                visible: ['GESTOR', 'PROTOCOLO'].includes(perfil.value)
            },
            {
                label: 'Fluxo por serviço',
                icon: 'pi pi-fw pi-directions',
                to: '/gestao-fluxo-servicos',
                visible: ['GESTOR', 'PROTOCOLO'].includes(perfil.value)
            },
            {
                label: 'Setores (UA)',
                icon: 'pi pi-fw pi-sitemap',
                to: '/gestao-setores',
                visible: ['GESTOR', 'PROTOCOLO', 'SECRETARIA'].includes(perfil.value)
            },
            {
                label: 'Gestão de usuários',
                icon: 'pi pi-fw pi-users',
                to: '/gestao-usuarios',
                visible: ['GESTOR', 'PROTOCOLO'].includes(perfil.value)
            },
            {
                label: 'Super Ordens (clusters)',
                icon: 'pi pi-fw pi-objects-column',
                to: '/clusters',
                visible: ['GESTOR', 'PROTOCOLO'].includes(perfil.value)
            },
            {
                label: 'Reconciliação Sinapse',
                icon: 'pi pi-fw pi-link',
                to: '/integracoes/sinapse/reconciliacao',
                visible: perfil.value === 'GESTOR'
            },
            {
                label: 'FAQ Copiloto',
                icon: 'pi pi-fw pi-sparkles',
                to: '/admin/faq-copiloto',
                visible: perfil.value === 'GESTOR'
            },
            {
                label: 'Modelo de ofício',
                icon: 'pi pi-fw pi-file-edit',
                to: '/admin/configuracao-oficio',
                visible: perfil.value === 'GESTOR'
            },
            {
                label: 'SLA da carta',
                icon: 'pi pi-fw pi-clock',
                to: '/admin/configuracao-carta',
                visible: perfil.value === 'GESTOR'
            },
            {
                label: 'Assuntos da carta',
                icon: 'pi pi-fw pi-tags',
                to: '/admin/assuntos-carta',
                visible: perfil.value === 'GESTOR'
            },
            { label: 'Notificações', icon: 'pi pi-fw pi-bell', to: '/notificacoes' }
        ]
    }
]);
</script>

<template>
    <ul class="layout-menu">
        <template v-for="(item, i) in model" :key="item">
            <app-menu-item v-if="!item.separator" :item="item" :index="i"></app-menu-item>
            <li v-if="item.separator" class="menu-separator"></li>
        </template>
    </ul>
</template>

<style lang="scss" scoped></style>
