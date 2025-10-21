<script setup>
import { ref, computed } from 'vue';
import { useLayout } from '@/layout/composables/layout';
import { useUserStore } from '@/stores/userStore';
import { useRouter } from 'vue-router';

import Button from 'primevue/button';
import Avatar from 'primevue/avatar';
import OverlayPanel from 'primevue/overlaypanel';

const { toggleMenu, toggleDarkMode, isDarkTheme } = useLayout();
const userStore = useUserStore();
const router = useRouter();

const op = ref();

const toggle = (event) => {
    op.value.toggle(event);
};

const userInitial = computed(() => {
    const user = userStore.currentUser;
    if (user?.first_name) {
        return user.first_name[0].toUpperCase();
    }
    if (user?.username) {
        return user.username[0].toUpperCase();
    }
    return '?';
});
</script>

<template>
    <div class="layout-topbar">
        <div class="layout-topbar-logo-container">
            <button class="layout-menu-button layout-topbar-action" @click="toggleMenu">
                <i class="pi pi-bars"></i>
            </button>
            <router-link to="/" class="layout-topbar-logo">
                <img src="/layout/images/brasao_pmmc.png" alt="Brasão da Prefeitura" style="height:40px" />
                <span>SGDL</span>
            </router-link>
        </div>

        <div class="layout-topbar-actions">
            <div class="layout-config-menu">
                <button type="button" class="layout-topbar-action" @click="toggleDarkMode">
                    <i :class="['pi', { 'pi-moon': isDarkTheme, 'pi-sun': !isDarkTheme }]"></i>
                </button>
            </div>

            <div v-if="userStore.isAuthenticated" class="flex items-center">
                <Avatar 
                    :key="userStore.currentUser?.avatar"
                    :image="userStore.currentUser?.avatar" 
                    :label="userStore.currentUser?.avatar ? null : userInitial"
                    class="cursor-pointer" 
                    shape="circle"
                    @click="toggle" 
                    aria-haspopup="true" 
                    aria-controls="overlay_panel"
                />
                </div>

            <OverlayPanel ref="op" id="overlay_panel">
                <div class="flex flex-col items-center gap-4 p-4" style="min-width: 250px;">
                    <Avatar 
                        :key="userStore.currentUser?.avatar"
                        :image="userStore.currentUser?.avatar" 
                        :label="userStore.currentUser?.avatar ? null : userInitial"
                        size="xlarge"
                        shape="circle" 
                    />
                    <div class="text-center">
                        <span class="font-bold">{{ userStore.currentUser?.first_name }} {{ userStore.currentUser?.last_name }}</span>
                        <div class="text-sm text-muted-color">{{ userStore.currentUser?.username }}</div>
                    </div>

                    <div class="flex flex-col gap-2 w-full">
                        <Button 
                            label="Meu Perfil" 
                            icon="pi pi-user" 
                            class="p-button-text"
                            @click="router.push('/perfil'); toggle($event);"
                        />
                        <Button 
                            label="Sair" 
                            icon="pi pi-sign-out" 
                            class="p-button-text p-button-danger"
                            @click="userStore.logout()"
                        />
                    </div>
                </div>
            </OverlayPanel>
        </div>
    </div>
</template>