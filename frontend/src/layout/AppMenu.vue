<script setup>
import { computed } from 'vue';
import { useUserStore } from '@/stores/userStore';
import { PERFIS_COPILOTO } from '@/constants';
import AppMenuItem from './AppMenuItem.vue';

const userStore = useUserStore();
const perfil = computed(() => userStore.currentUser?.perfil);

const temPerfil = (...perfis) => {
    if (!perfis.length) return true;
    return perfis.includes(perfil.value);
};

const link = (label, icon, to, ...perfisVisiveis) => ({
    label,
    icon: `pi pi-fw ${icon}`,
    to,
    visible: temPerfil(...perfisVisiveis)
});

const linkOperacaoAvancada = (label, icon, to) => ({
    label,
    icon: `pi pi-fw ${icon}`,
    to,
    visible: temPerfil('PROTOCOLO') || userStore.isGestorGeral
});

/** Rotas de CRUD administrativo — apenas Gestor Geral (U7). */
const linkGestorAdmin = (label, icon, to) => ({
    label,
    icon: `pi pi-fw ${icon}`,
    to,
    visible: userStore.isGestorGeral
});

const secao = (label, items) => {
    const visiveis = items.filter((item) => item.visible !== false);
    if (!visiveis.length) return null;
    return { label, items: visiveis };
};

const model = computed(() =>
    [
        secao('Principal', [
            link('Copiloto', 'pi-comments', '/copiloto', ...PERFIS_COPILOTO),
            link('Consulta rápida', 'pi-search', '/consulta', 'VEREADOR', 'PROTOCOLO', 'SECRETARIA', 'GESTOR'),
            link('Dashboard', 'pi-home', '/'),
            link('Demandas', 'pi-book', '/demandas'),
            link('Mapa operacional', 'pi-map', '/mapa-calor'),
            link('Notificações', 'pi-bell', '/notificacoes'),
            link('Assinaturas pendentes', 'pi-verified', '/assinaturas-pendentes', 'GESTOR', 'PROTOCOLO')
        ]),
        secao('Análise', [link('Relatórios', 'pi-chart-bar', '/relatorios', 'GESTOR')]),
        secao('Carta e triagem', [
            link('Carta de Serviços', 'pi-bookmark', '/carta-servicos', 'VEREADOR', 'GESTOR', 'PROTOCOLO', 'SECRETARIA'),
            link('Gestão de Tendências', 'pi-chart-line', '/gestao-tendencias', 'GESTOR', 'PROTOCOLO'),
            link('Recusas Copiloto', 'pi-ban', '/gestao-recusas-copiloto', 'GESTOR', 'PROTOCOLO')
        ]),
        secao('Operação', [
            link('Super Ordens', 'pi-objects-column', '/clusters', 'GESTOR', 'PROTOCOLO'),
            linkOperacaoAvancada('Fluxo por serviço', 'pi-directions', '/gestao-fluxo-servicos'),
            link('Setores (UA)', 'pi-sitemap', '/gestao-setores', 'GESTOR', 'PROTOCOLO', 'SECRETARIA')
        ]),
        secao('Administração', [
            linkGestorAdmin('Gestão de usuários', 'pi-users', '/gestao-usuarios'),
            linkGestorAdmin('Reconciliação Sinapse', 'pi-link', '/integracoes/sinapse/reconciliacao'),
            linkGestorAdmin('FAQ Copiloto', 'pi-sparkles', '/faq-copiloto'),
            linkGestorAdmin('Modelo de ofício', 'pi-file-edit', '/configuracao-oficio'),
            linkGestorAdmin('SLA da carta', 'pi-clock', '/configuracao-carta'),
            linkGestorAdmin('Assuntos da carta', 'pi-tags', '/assuntos-carta')
        ])
    ].filter(Boolean)
);
</script>

<template>
    <ul class="layout-menu">
        <template v-for="(item, i) in model" :key="item.label">
            <app-menu-item v-if="!item.separator" :item="item" :index="i" />
            <li v-if="item.separator" class="menu-separator" />
        </template>
    </ul>
</template>
