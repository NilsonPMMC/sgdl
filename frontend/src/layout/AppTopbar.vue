<script setup>
import { ref, computed, onMounted } from 'vue';
import { useLayout } from '@/layout/composables/layout';
import { useUserStore } from '@/stores/userStore';
import { useRouter } from 'vue-router';
import ApiService from '@/service/ApiService';

import Button from 'primevue/button';
import Avatar from 'primevue/avatar';
import OverlayPanel from 'primevue/overlaypanel';
import ScrollPanel from 'primevue/scrollpanel';
import OverlayBadge from 'primevue/overlaybadge';
import Divider from 'primevue/divider';

const { toggleMenu, toggleDarkMode, isDarkTheme } = useLayout();
const userStore = useUserStore();
const router = useRouter();

const op = ref();
const on = ref();

const notificacoes = ref([]);
const unreadCount = ref(0);

const toggle = (event) => {
    op.value.toggle(event);
};

const toggleNotificacoes = (event) => {
    on.value.toggle(event);
    fetchNotificacoes();
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

const fetchNotificacoes = async () => {
    try {
        const response = await ApiService.getNotificacoes();
        notificacoes.value = response.data;
        // Calcula o número de não lidas e atualiza o badge
        unreadCount.value = notificacoes.value.filter((n) => !n.lida).length;
    } catch (error) {
        console.error('Erro ao buscar notificações:', error);
    }
    if (notificacoes.value.length > 0) {
        // Adiciona um separador
        notificacoes.value.push({ separator: true });
    }
    notificacoes.value.push({
        label: 'Ver todas as notificações',
        icon: 'pi pi-list',
        command: () => {
            router.push('/notificacoes');
        }
    });
};

const handleNotificacaoClick = async (notificacao) => {
    try {
        if (!notificacao.lida) {
            await ApiService.marcarNotificacaoComoLida(notificacao.id);
            fetchNotificacoes();
        }
        router.push(notificacao.link);
        on.value.hide();
    } catch (error) {
        console.error('Erro ao marcar notificação como lida:', error);
    }
};

const marcarTodasComoLidas = async () => {
    try {
        await ApiService.marcarTodasNotificacoesComoLidas();
        fetchNotificacoes(); // Apenas atualiza a lista, que agora virá com tudo lido
    } catch (error) {
        console.error('Erro ao marcar todas as notificações como lidas:', error);
    }
};

const getNotificacaoIcon = (tipo) => {
    switch (tipo) {
        case 'ATRASO':
            return 'pi pi-exclamation-triangle'; // Ícone de Alerta
        case 'NOVO_OFICIO':
            return 'pi pi-file-plus';
        case 'CONCLUSAO':
            return 'pi pi-check-circle';
        case 'TRANSFERENCIA':
            return 'pi pi-arrow-right-arrow-left';
        case 'DESPACHO':
            return 'pi pi-send';
        default:
            return 'pi pi-bell'; // Padrão
    }
};

const getNotificacaoClass = (notificacao) => {
    if (!notificacao.lida) {
        switch (notificacao.tipo) {
            case 'ATRASO':
                return 'avatar-atraso text-white'; // Classe vermelha
            case 'NOVO_OFICIO':
            case 'DESPACHO':
                return 'avatar-novo text-white'; // Classe azul
            default:
                return 'avatar-nao-lida text-white'; // Classe verde (padrão)
        }
    }
    return 'avatar-lida text-color-secondary'; // Classe cinza (lida)
};

onMounted(() => {
    if (userStore.isAuthenticated) {
        fetchNotificacoes(); // Busca as notificações na primeira vez
        // Configura o polling para verificar a cada 30 segundos
        setInterval(fetchNotificacoes, 30000);
    }
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

                <button type="button" class="layout-topbar-action" @click="toggleNotificacoes">
    
                    <OverlayBadge v-if="unreadCount > 0" :value="unreadCount" severity="danger">
                        <i class="pi pi-bell" />
                    </OverlayBadge>
                    
                    <i v-else class="pi pi-bell" />

                    <span>Notificações</span>
                </button>

                <OverlayPanel ref="on" appendTo="body" :pt="{ content: { class: 'p-0' } }">
                    <div class="flex flex-col" style="width: 25rem;">
                        <div class="flex justify-between items-center py-3 px-4">
                            <span class="font-bold text-lg">Notificações</span>
                            <Button v-if="unreadCount > 0" label="Marcar todas como lidas" class="p-button-text p-button-sm" @click="marcarTodasComoLidas"></Button>
                        </div>
                        <Divider class="m-0" />

                        <ScrollPanel style="height: 250px;" class="px-4">
                            <div class="flex flex-col gap-1">
                                <div v-for="notificacao in notificacoes" :key="notificacao.id" @click="handleNotificacaoClick(notificacao)"
                                    :class="['flex align-items-center gap-3 p-3 border-round-md cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700', 
                                    { 
                                        'bg-gray-100 dark:bg-gray-800': !notificacao.lida,  
                                        'opacity-60': notificacao.lida 
                                    }]">
                                    
                                    <Avatar :class="['flex-shrink-0', getNotificacaoClass(notificacao)]"
                                        :icon="getNotificacaoIcon(notificacao.tipo)" 
                                        shape="circle" />
                                    
                                    <div class="flex flex-col">
                                        <p :class="['m-0 text-sm', { 'font-bold': !notificacao.lida, 'font-normal': notificacao.lida }]">
                                            {{ notificacao.mensagem }}
                                        </p>
                                    </div>

                                </div>
                                <div v-if="!notificacoes.length" class="text-center text-color-secondary p-4">
                                    Nenhuma notificação por aqui.
                                </div>
                            </div>
                        </ScrollPanel>
                        <Divider class="m-0" />

                        <div class="px-4 py-3">
                            <Button label="Ver todas as notificações" icon="pi pi-arrow-right" iconPos="right" class="p-button-outlined w-full" @click="router.push('/notificacoes'); on.hide()"></Button>
                        </div>
                    </div>
                </OverlayPanel>
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

<style>
.p-overlaybadge span{
    display: inline-flex !important;
    font-size: .75rem !important;
    min-width: 1.25rem !important;
    height: 1.25rem !important;
    align-items: center;
    justify-content: center;
}
.avatar-atraso {
    background: var(--p-red-500) !important;
    color: white !important;
}
.avatar-novo {
    background: var(--p-blue-500) !important;
    color: white !important;
}
.avatar-nao-lida {
    background: var(--p-emerald-500) !important;
    color: white !important;
}
.avatar-lida {
    background: var(--p-gray-400) !important;
}
.dark .avatar-lida {
    background: var(--p-gray-600) !important;
    color: white !important;
}
</style>