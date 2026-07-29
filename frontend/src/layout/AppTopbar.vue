<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useLayout } from '@/layout/composables/layout';
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService';
import { filtrarNotificacoesSemAtraso } from '@/utils/metricasSlaVereador';

import Button from 'primevue/button';
import Avatar from 'primevue/avatar';
import OverlayPanel from 'primevue/overlaypanel';
import ScrollPanel from 'primevue/scrollpanel';
import OverlayBadge from 'primevue/overlaybadge';
import Divider from 'primevue/divider';

const QUICK_LINKS_POR_PERFIL = {
    VEREADOR: [
        { label: 'Copiloto', icon: 'pi pi-comments', to: '/copiloto' },
        { label: 'Demandas', icon: 'pi pi-book', to: '/demandas' },
        { label: 'Consulta', icon: 'pi pi-search', to: '/consulta' },
        { label: 'Carta', icon: 'pi pi-bookmark', to: '/carta-servicos' }
    ],
    CAMARA: [
        { label: 'Copiloto', icon: 'pi pi-comments', to: '/copiloto' },
        { label: 'Indicações', icon: 'pi pi-book', to: '/demandas' },
        { label: 'Consulta', icon: 'pi pi-search', to: '/consulta' },
        { label: 'Notificações', icon: 'pi pi-bell', to: '/notificacoes' }
    ],
    GESTOR: [
        { label: 'Dashboard', icon: 'pi pi-home', to: '/' },
        { label: 'Demandas', icon: 'pi pi-book', to: '/demandas' },
        { label: 'Relatórios', icon: 'pi pi-chart-bar', to: '/relatorios' },
        { label: 'Mapa', icon: 'pi pi-map', to: '/mapa-calor' },
        { label: 'Consulta', icon: 'pi pi-search', to: '/consulta' }
    ],
    PROTOCOLO: [
        { label: 'Dashboard', icon: 'pi pi-home', to: '/' },
        { label: 'Demandas', icon: 'pi pi-book', to: '/demandas' },
        { label: 'Super OS', icon: 'pi pi-objects-column', to: '/clusters' },
        { label: 'Tendências', icon: 'pi pi-chart-line', to: '/gestao-tendencias' },
        { label: 'Consulta', icon: 'pi pi-search', to: '/consulta' }
    ],
    SECRETARIA: [
        { label: 'Demandas', icon: 'pi pi-book', to: '/demandas' },
        { label: 'Carta', icon: 'pi pi-bookmark', to: '/carta-servicos' },
        { label: 'Setores', icon: 'pi pi-sitemap', to: '/gestao-setores' },
        { label: 'Mapa', icon: 'pi pi-map', to: '/mapa-calor' }
    ],
    ASSESSOR: [
        { label: 'Dashboard', icon: 'pi pi-home', to: '/' },
        { label: 'Demandas', icon: 'pi pi-book', to: '/demandas' },
        { label: 'Consulta', icon: 'pi pi-search', to: '/consulta' }
    ]
};

const PADRAO_QUICK_LINKS = [
    { label: 'Dashboard', icon: 'pi pi-home', to: '/' },
    { label: 'Demandas', icon: 'pi pi-book', to: '/demandas' }
];

const { toggleMenu, toggleDarkMode, isDarkTheme } = useLayout();
const userStore = useUserStore();
const router = useRouter();
const route = useRoute();

const op = ref();
const on = ref();
const notificacoes = ref([]);
const unreadCount = ref(0);
let pollingId = null;

const perfil = computed(() => userStore.currentUser?.perfil);

const quickLinks = computed(() => QUICK_LINKS_POR_PERFIL[perfil.value] || PADRAO_QUICK_LINKS);

const isQuickLinkActive = (to) => {
    if (to === '/') return route.path === '/';
    return route.path === to || route.path.startsWith(`${to}/`);
};

const toggle = (event) => {
    op.value.toggle(event);
};

const toggleNotificacoes = (event) => {
    on.value.toggle(event);
    fetchNotificacoes();
};

const userInitial = computed(() => {
    const user = userStore.currentUser;
    if (user?.first_name) return user.first_name[0].toUpperCase();
    if (user?.username) return user.username[0].toUpperCase();
    return '?';
});

const fetchNotificacoes = async () => {
    try {
        const response = await ApiService.getNotificacoes();
        const lista =
            response.data && Array.isArray(response.data.results)
                ? response.data.results
                : Array.isArray(response.data)
                  ? response.data
                  : [];
        notificacoes.value = filtrarNotificacoesSemAtraso(lista, perfil.value);
        unreadCount.value = notificacoes.value.filter((n) => n && !n.lida).length;
    } catch (error) {
        console.error('Erro ao buscar notificações:', error);
        notificacoes.value = [];
        unreadCount.value = 0;
    }
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
        fetchNotificacoes();
    } catch (error) {
        console.error('Erro ao marcar todas as notificações como lidas:', error);
    }
};

const getNotificacaoIcon = (tipo) => {
    switch (tipo) {
        case 'ATRASO':
            return 'pi pi-exclamation-triangle';
        case 'NOVO_OFICIO':
            return 'pi pi-file-plus';
        case 'CONCLUSAO':
            return 'pi pi-check-circle';
        case 'TRANSFERENCIA':
            return 'pi pi-arrow-right-arrow-left';
        case 'DESPACHO':
            return 'pi pi-send';
        case 'ASSINATURA_PENDENTE':
            return 'pi pi-verified';
        default:
            return 'pi pi-bell';
    }
};

const getNotificacaoClass = (notificacao) => {
    if (!notificacao.lida) {
        switch (notificacao.tipo) {
            case 'ATRASO':
                return 'avatar-atraso text-white';
            case 'NOVO_OFICIO':
            case 'DESPACHO':
            case 'ASSINATURA_PENDENTE':
                return 'avatar-novo text-white';
            default:
                return 'avatar-nao-lida text-white';
        }
    }
    return 'avatar-lida text-color-secondary';
};

onMounted(() => {
    if (userStore.isAuthenticated) {
        fetchNotificacoes();
        pollingId = setInterval(fetchNotificacoes, 30000);
    }
});

onUnmounted(() => {
    if (pollingId) clearInterval(pollingId);
});
</script>

<template>
    <div class="layout-topbar">
        <div class="layout-topbar-logo-container">
            <button type="button" class="layout-menu-button layout-topbar-action" aria-label="Alternar menu" @click="toggleMenu">
                <i class="pi pi-bars" />
            </button>
            <router-link to="/" class="layout-topbar-logo">
                <img src="/layout/images/brasao_pmmc.png" alt="Brasão da Prefeitura" style="height: 40px" />
                <span>Portal dos Vereadores</span>
            </router-link>
        </div>

        <nav v-if="userStore.isAuthenticated" class="layout-topbar-quicklinks hidden lg:flex" aria-label="Acessos rápidos">
            <router-link
                v-for="item in quickLinks"
                :key="item.to"
                :to="item.to"
                class="layout-topbar-quicklink"
                :class="{ 'layout-topbar-quicklink--active': isQuickLinkActive(item.to) }"
                :title="item.label"
                :aria-label="item.label"
            >
                <i :class="item.icon" />
                <span class="layout-topbar-quicklink-label">{{ item.label }}</span>
            </router-link>
        </nav>

        <div class="layout-topbar-actions">
            <div class="layout-config-menu">
                <button type="button" class="layout-topbar-action" aria-label="Alternar tema" @click="toggleDarkMode">
                    <i :class="['pi', { 'pi-moon': isDarkTheme, 'pi-sun': !isDarkTheme }]" />
                </button>

                <button type="button" class="layout-topbar-action" aria-label="Notificações" @click="toggleNotificacoes">
                    <OverlayBadge v-if="unreadCount > 0" :value="unreadCount" severity="danger">
                        <i class="pi pi-bell" />
                    </OverlayBadge>
                    <i v-else class="pi pi-bell" />
                </button>

                <OverlayPanel ref="on" appendTo="body" :pt="{ content: { class: 'p-0' } }">
                    <div class="flex flex-col" style="width: 25rem">
                        <div class="flex justify-between items-center py-3 px-4">
                            <span class="font-bold text-lg">Notificações</span>
                            <Button
                                v-if="unreadCount > 0"
                                label="Marcar todas como lidas"
                                class="p-button-text p-button-sm"
                                @click="marcarTodasComoLidas"
                            />
                        </div>
                        <Divider class="m-0" />

                        <ScrollPanel style="height: 250px" class="px-4">
                            <div class="flex flex-col gap-1">
                                <div
                                    v-for="notificacao in notificacoes"
                                    :key="notificacao.id"
                                    :class="[
                                        'flex align-items-center gap-3 p-3 border-round-md cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700',
                                        {
                                            'bg-gray-100 dark:bg-gray-800': !notificacao.lida,
                                            'opacity-60': notificacao.lida
                                        }
                                    ]"
                                    @click="handleNotificacaoClick(notificacao)"
                                >
                                    <Avatar
                                        :class="['flex-shrink-0', getNotificacaoClass(notificacao)]"
                                        :icon="getNotificacaoIcon(notificacao.tipo)"
                                        shape="circle"
                                    />
                                    <div class="flex flex-col">
                                        <p :class="['m-0 text-sm', { 'font-bold': !notificacao.lida, 'font-normal': notificacao.lida }]">
                                            {{ notificacao.mensagem }}
                                        </p>
                                    </div>
                                </div>
                                <div v-if="!notificacoes.length" class="text-center text-color-secondary p-4">Nenhuma notificação por aqui.</div>
                            </div>
                        </ScrollPanel>
                        <Divider class="m-0" />

                        <div class="px-4 py-3">
                            <Button
                                label="Ver todas as notificações"
                                icon="pi pi-arrow-right"
                                iconPos="right"
                                class="p-button-outlined w-full"
                                @click="
                                    router.push('/notificacoes');
                                    on.hide();
                                "
                            />
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
                    aria-haspopup="true"
                    aria-controls="overlay_panel"
                    @click="toggle"
                />
            </div>

            <OverlayPanel ref="op" id="overlay_panel">
                <div class="flex flex-col items-center gap-4 p-4" style="min-width: 250px">
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
                        <div v-if="perfil" class="text-xs text-muted-color mt-1">{{ perfil }}</div>
                    </div>

                    <div class="flex flex-col gap-2 w-full">
                        <Button
                            label="Meu Perfil"
                            icon="pi pi-user"
                            class="p-button-text"
                            @click="
                                router.push('/perfil');
                                toggle($event);
                            "
                        />
                        <Button label="Sair" icon="pi pi-sign-out" class="p-button-text p-button-danger" @click="userStore.logout()" />
                    </div>
                </div>
            </OverlayPanel>
        </div>
    </div>
</template>

<style>
.p-overlaybadge span {
    display: inline-flex !important;
    font-size: 0.75rem !important;
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
    background: var(--p-primary-500) !important;
    color: white !important;
}
.avatar-nao-lida {
    background: var(--p-primary-600) !important;
    color: white !important;
}
.avatar-lida {
    background: var(--p-gray-400) !important;
}
.dark .avatar-lida {
    background: var(--p-gray-600) !important;
    color: white !important;
}

.layout-topbar-quicklinks {
    align-items: center;
    gap: 0.125rem;
    margin-left: 0.5rem;
    margin-right: 0.5rem;
    flex: 1;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: thin;
}

.layout-topbar-quicklink {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.625rem;
    border-radius: var(--content-border-radius, 6px);
    color: var(--text-color-secondary);
    text-decoration: none;
    white-space: nowrap;
    transition: background-color 0.2s, color 0.2s;
    font-size: 0.8125rem;
}

.layout-topbar-quicklink:hover {
    background-color: var(--surface-hover);
    color: var(--text-color);
}

.layout-topbar-quicklink--active {
    background-color: var(--primary-color);
    color: var(--primary-contrast-color);
    font-weight: 600;
}

.layout-topbar-quicklink--active:hover {
    background-color: var(--primary-color);
    color: var(--primary-contrast-color);
}

.layout-topbar-quicklink i {
    font-size: 0.95rem;
}

.layout-topbar-quicklink-label {
    line-height: 1;
}

@media (max-width: 1199px) {
    .layout-topbar-quicklink-label {
        display: none;
    }

    .layout-topbar-quicklink {
        padding: 0.375rem;
        border-radius: 50%;
        width: 2.25rem;
        height: 2.25rem;
        justify-content: center;
    }
}
</style>
