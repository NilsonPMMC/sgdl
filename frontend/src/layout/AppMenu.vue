<script setup>
import { ref } from 'vue';
import { useUserStore } from '@/stores/userStore';

import AppMenuItem from './AppMenuItem.vue';

const userStore = useUserStore(); 

const model = ref([
    {
        label: 'Home',
        items: [
            { label: 'Dashboard', icon: 'pi pi-fw pi-home', to: '/' },
            { label: 'Mapa de Calor', icon: 'pi pi-fw pi-map', to: '/mapa-calor', visible: userStore.currentUser?.perfil === 'GESTOR' },
            { label: 'Demandas', icon: 'pi pi-fw pi-book', to: '/demandas' }
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
