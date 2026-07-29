<script setup>
import { computed, ref, onMounted, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import ApiService from '@/service/ApiService.js';
import Chart from 'primevue/chart';
import Button from 'primevue/button';
import Tag from 'primevue/tag';
import TabView from 'primevue/tabview';
import TabPanel from 'primevue/tabpanel';
import { useLayout } from '@/layout/composables/layout';
import { useUserStore } from '@/stores/userStore';

const { isDarkTheme } = useLayout();
const userStore = useUserStore();
const router = useRouter();
const stats = ref(null);
const loading = ref(true);

const perfilUsuario = computed(() => userStore.currentUser?.perfil);

const podeVerClusters = computed(() =>
    ['GESTOR', 'PROTOCOLO'].includes(perfilUsuario.value)
);

const podeVerSuperOsSecretaria = computed(() => perfilUsuario.value === 'SECRETARIA');

const isSecretaria = computed(() => perfilUsuario.value === 'SECRETARIA');

const mostrarGraficoPorSecretaria = computed(
    () => !['VEREADOR', 'SECRETARIA'].includes(perfilUsuario.value)
);

const podeVerResumoSuperOs = computed(
    () => podeVerClusters.value || podeVerSuperOsSecretaria.value
);

const mostrarKpisTrilha = computed(() =>
    ['GESTOR', 'PROTOCOLO'].includes(perfilUsuario.value)
);

const mostrarKpiAtrasadas = computed(() => perfilUsuario.value !== 'VEREADOR');

const clustersResumo = ref([]);
const loadingClusters = ref(false);

const barSecretariaData = ref(null);
const barVereadorData = ref(null);
const doughnutData = ref(null);
const trilhaDoughnutData = ref(null);
const trilhaLineData = ref(null);
const lineData = ref(null);

const barOptions = ref(null);
const lineOptions = ref(null);
const doughnutOptions = ref(null);
const pieOptions = ref(null);
const chartRefreshKey = ref(0);

function irRecusasCopiloto(motivo) {
    const query = motivo ? { motivo: String(motivo).slice(0, 120) } : {};
    router.push({ name: 'gestao-recusas-copiloto', query });
}

function onTabChange() {
    nextTick(() => {
        chartRefreshKey.value += 1;
    });
}

async function carregarDadosDoDashboard() {
    loading.value = true;
    try {
        let params = {};
        // **CORREÇÃO 1: Acessando a propriedade correta 'currentUser'**
        const currentUser = userStore.currentUser;

        // Adicionando uma verificação para garantir que currentUser e perfil existam
        if (currentUser && currentUser.perfil) {
            if (currentUser.perfil === 'VEREADOR') {
                params.autor = currentUser.id;
            } else if (currentUser.perfil === 'SECRETARIA') {
                // Supondo que o ID da secretaria esteja em currentUser.secretaria
                // Se o nome da propriedade for diferente, ajuste aqui.
                params.secretaria_destino = currentUser.secretaria;
            }
        }

        const response = await ApiService.getDashboardStats(params);
        stats.value = response.data;
        formatChartData(response.data);
        await nextTick();
        chartRefreshKey.value += 1;
    } catch (error) {
        console.error('Erro ao buscar dados do dashboard:', error);
    } finally {
        loading.value = false;
    }
}

async function carregarResumoClusters() {
    if (!podeVerResumoSuperOs.value) return;
    loadingClusters.value = true;
    try {
        const { data } = await ApiService.getClustersResumo({ limit: 5 });
        clustersResumo.value = data?.clusters || [];
    } catch {
        clustersResumo.value = [];
    } finally {
        loadingClusters.value = false;
    }
}

function abrirLiderSuperOs(cluster) {
    const liderId = cluster?.lider_demanda_id;
    if (liderId) {
        router.push({ name: 'demandas-detalhes', params: { id: String(liderId) } });
    }
}

function irDemandasPorTrilha(trilha) {
    router.push({ name: 'demandas', query: { trilha } });
}

function irGestaoTendencias() {
    router.push({ name: 'gestao-tendencias' });
}

const abasKpiDisponiveis = computed(() => {
    const abas = [];
    if (podeVerResumoSuperOs.value) abas.push('super-os');
    if (mostrarKpisTrilha.value) abas.push('trilhas');
    abas.push('dashboard');
    return abas;
});

onMounted(() => {
    setChartOptions();
    carregarDadosDoDashboard();
    carregarResumoClusters();
});

watch(isDarkTheme, setChartOptions);

function setChartOptions() {
    const documentStyle = getComputedStyle(document.documentElement);
    const textColor = documentStyle.getPropertyValue('--text-color');
    const textColorSecondary = documentStyle.getPropertyValue('--text-color-secondary');
    const surfaceBorder = documentStyle.getPropertyValue('--surface-border');
    barOptions.value = {
        plugins: { legend: { labels: { color: textColor } } },
        scales: {
            x: { stacked: true, ticks: { color: textColorSecondary }, grid: { color: surfaceBorder } },
            y: { stacked: true, ticks: { color: textColorSecondary }, grid: { color: surfaceBorder } }
        }
    };
    lineOptions.value = {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: textColor } } },
        scales: {
            x: { ticks: { color: textColorSecondary }, grid: { color: surfaceBorder } },
            y: { ticks: { color: textColorSecondary }, grid: { color: surfaceBorder } }
        }
    };
    doughnutOptions.value = {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: textColor, usePointStyle: true } } }
    };
    pieOptions.value = {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: textColor, usePointStyle: true } } }
    };
}

function formatChartData(data) {
    const documentStyle = getComputedStyle(document.documentElement);
    barSecretariaData.value = {
        labels: data.por_secretaria.map((item) => item.secretaria_destino__nome),
        datasets: [
            { label: 'Abertas', backgroundColor: documentStyle.getPropertyValue('--p-purple-500'), data: data.por_secretaria.map((item) => item.abertas) },
            { label: 'Concluídas', backgroundColor: documentStyle.getPropertyValue('--p-teal-500'), data: data.por_secretaria.map((item) => item.total - item.abertas) }
        ]
    };
    barVereadorData.value = {
        labels: data.por_vereador.map((item) => `${item.autor__first_name || ''} ${item.autor__last_name || ''}`.trim() || 'Não Identificado'),
        datasets: [
            { label: 'Abertas', backgroundColor: documentStyle.getPropertyValue('--p-purple-500'), data: data.por_vereador.map((item) => item.abertas) },
            { label: 'Concluídas', backgroundColor: documentStyle.getPropertyValue('--p-teal-500'), data: data.por_vereador.map((item) => item.total - item.abertas) }
        ]
    };
    doughnutData.value = {
        labels: data.por_status_agrupado.map((item) => item.status),
        datasets: [
            {
                data: data.por_status_agrupado.map((item) => item.total),
                backgroundColor: [documentStyle.getPropertyValue('--p-cyan-500'), documentStyle.getPropertyValue('--p-purple-500'), documentStyle.getPropertyValue('--p-teal-500')]
            }
        ]
    };
    lineData.value = {
        labels: data.mensal.map((item) => item.mes),
        datasets: [
            { label: 'Total', data: data.mensal.map((item) => item.total), fill: false, borderColor: documentStyle.getPropertyValue('--p-teal-500'), tension: 0.4 },
            { label: 'Abertas', data: data.mensal.map((item) => item.abertas), fill: false, borderColor: documentStyle.getPropertyValue('--p-purple-500'), tension: 0.4 }
        ]
    };

    if (data.trilhas?.grafico_trilhas) {
        trilhaDoughnutData.value = {
            labels: data.trilhas.grafico_trilhas.map((item) => item.trilha),
            datasets: [
                {
                    data: data.trilhas.grafico_trilhas.map((item) => item.total),
                    backgroundColor: [
                        documentStyle.getPropertyValue('--p-cyan-500'),
                        documentStyle.getPropertyValue('--p-purple-500'),
                        documentStyle.getPropertyValue('--p-orange-500')
                    ]
                }
            ]
        };
    } else {
        trilhaDoughnutData.value = null;
    }

    if (data.trilhas_mensal?.length) {
        trilhaLineData.value = {
            labels: data.trilhas_mensal.map((item) => item.mes),
            datasets: [
                {
                    label: 'Carta',
                    data: data.trilhas_mensal.map((item) => item.carta),
                    fill: false,
                    borderColor: documentStyle.getPropertyValue('--p-cyan-500'),
                    tension: 0.4
                },
                {
                    label: 'Tendência',
                    data: data.trilhas_mensal.map((item) => item.tendencia),
                    fill: false,
                    borderColor: documentStyle.getPropertyValue('--p-purple-500'),
                    tension: 0.4
                }
            ]
        };
    } else {
        trilhaLineData.value = null;
    }
}
</script>

<template>
    <div v-if="loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
        <p>Carregando dados do dashboard...</p>
    </div>
    <div v-if="stats && !loading" class="grid grid-cols-12 gap-8">
        <div class="col-span-12 lg:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="flex justify-between mb-4">
                    <div>
                        <span class="block text-muted-color font-medium mb-4">Total de Demandas</span>
                        <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ stats.kpis.total_demandas }}</div>
                    </div>
                    <div class="flex items-center justify-center bg-cyan-100 dark:bg-cyan-400/10 rounded-border" style="width: 2.5rem; height: 2.5rem">
                        <i class="pi pi-inbox text-cyan-500 !text-xl"></i>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-span-12 lg:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="flex justify-between mb-4">
                    <div>
                        <span class="block text-muted-color font-medium mb-4">Demandas em Aberto</span>
                        <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ stats.kpis.demandas_abertas }}</div>
                    </div>
                    <div class="flex items-center justify-center bg-purple-100 dark:bg-purple-400/10 rounded-border" style="width: 2.5rem; height: 2.5rem">
                        <i class="pi pi-sync text-purple-500 !text-xl"></i>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-span-12 lg:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="flex justify-between mb-4">
                    <div>
                        <span class="block text-muted-color font-medium mb-4">Demandas Concluídas</span>
                        <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ stats.kpis.demandas_concluidas }}</div>
                    </div>
                    <div class="flex items-center justify-center bg-teal-100 dark:bg-teal-400/10 rounded-border" style="width: 2.5rem; height: 2.5rem">
                        <i class="pi pi-check text-teal-500 !text-xl"></i>
                    </div>
                </div>
            </div>
        </div>
        <div v-if="mostrarKpiAtrasadas" class="col-span-12 lg:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="flex justify-between mb-4">
                    <div>
                        <span class="block text-muted-color font-medium mb-4">Atrasadas</span>
                        <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ stats.kpis.demandas_atrasadas }}</div>
                    </div>
                    <div class="flex items-center justify-center bg-red-100 dark:bg-red-400/10 rounded-border" style="width: 2.5rem; height: 2.5rem">
                        <i class="pi pi-clock text-red-500 !text-xl"></i>
                    </div>
                </div>
            </div>
        </div>

        <TabView v-if="abasKpiDisponiveis.length > 1" class="col-span-12 sgdl-dashboard-tabs" @tab-change="onTabChange">
            <TabPanel v-if="podeVerResumoSuperOs" header="Super OS">
                <div class="card mt-0">
                    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
                        <div>
                            <div class="font-semibold text-xl">
                                {{ podeVerSuperOsSecretaria ? 'Super Ordens de Serviço' : 'Super Ordens de Serviço (IA)' }}
                            </div>
                            <p class="text-sm text-muted-color m-0 mt-1">
                                <template v-if="podeVerSuperOsSecretaria">
                                    Agrupamentos com processos da sua secretaria — tramite pela demanda líder.
                                </template>
                                <template v-else>
                                    Demandas agrupadas por tema e local — evita despachos duplicados no mesmo buraco.
                                </template>
                            </p>
                        </div>
                        <div class="flex flex-wrap gap-2">
                            <Button
                                v-if="podeVerSuperOsSecretaria"
                                label="Fila do meu setor"
                                icon="pi pi-inbox"
                                outlined
                                size="small"
                                @click="router.push({ name: 'demandas', query: { fila: 'operacionais', minha_unidade: '1' } })"
                            />
                            <Button
                                v-if="podeVerClusters"
                                label="Ver todos os clusters"
                                icon="pi pi-objects-column"
                                outlined
                                size="small"
                                @click="router.push({ name: 'clusters' })"
                            />
                        </div>
                    </div>
                    <div v-if="loadingClusters" class="text-sm text-muted-color">Carregando Super OS…</div>
                    <div v-else-if="!clustersResumo.length" class="text-sm text-muted-color">
                        Nenhuma Super OS ativa no momento para o seu perfil.
                    </div>
                    <ul v-else class="list-none p-0 m-0 flex flex-col gap-2">
                        <li
                            v-for="c in clustersResumo"
                            :key="c.id"
                            class="flex flex-wrap items-center justify-between gap-2 py-2 border-b border-surface-200 dark:border-surface-700 last:border-0"
                        >
                            <div class="min-w-0 flex-1">
                                <Button
                                    v-if="podeVerSuperOsSecretaria && c.lider_demanda_id"
                                    :label="c.protocolo_super_os || c.titulo"
                                    link
                                    class="p-0 font-medium"
                                    @click="abrirLiderSuperOs(c)"
                                />
                                <span v-else class="font-medium">
                                    {{ c.protocolo_super_os || c.titulo }}
                                </span>
                                <span v-if="c.servico_nome" class="text-xs text-muted-color ml-2">
                                    · {{ c.servico_nome }}
                                </span>
                                <span v-if="c.bairro_referencia" class="text-xs text-muted-color ml-2">
                                    · {{ c.bairro_referencia }}
                                </span>
                            </div>
                            <div class="flex items-center gap-2 shrink-0">
                                <Tag :value="`${c.demandas_count} vinculados`" severity="info" />
                                <Tag
                                    v-if="(c.autores_distintos || 0) > 1"
                                    :value="`${c.autores_distintos} vereadores`"
                                    severity="warn"
                                />
                                <Button
                                    v-if="podeVerSuperOsSecretaria && c.lider_demanda_id"
                                    label="Abrir líder"
                                    icon="pi pi-external-link"
                                    size="small"
                                    text
                                    @click="abrirLiderSuperOs(c)"
                                />
                            </div>
                        </li>
                    </ul>
                </div>
            </TabPanel>

            <TabPanel v-if="mostrarKpisTrilha && stats.trilhas" header="Trilhas">
                <div class="grid grid-cols-12 gap-6">
                    <div class="col-span-12 lg:col-span-4">
                        <div class="card mb-0 h-full">
                            <div class="flex justify-between mb-4">
                                <div>
                                    <span class="block text-muted-color font-medium mb-4">Trilha Carta</span>
                                    <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">
                                        {{ stats.trilhas.carta.total }}
                                    </div>
                                    <span class="text-sm text-muted-color">
                                        {{ stats.trilhas.carta.percentual_demandas }}% das formalizadas
                                    </span>
                                </div>
                                <div class="flex items-center justify-center bg-cyan-100 dark:bg-cyan-400/10 rounded-border" style="width: 2.5rem; height: 2.5rem">
                                    <i class="pi pi-book text-cyan-500 !text-xl"></i>
                                </div>
                            </div>
                            <Button
                                label="Ver demandas (Carta)"
                                icon="pi pi-arrow-right"
                                text
                                size="small"
                                class="p-0"
                                @click="irDemandasPorTrilha('carta')"
                            />
                        </div>
                    </div>
                    <div class="col-span-12 lg:col-span-4">
                        <div class="card mb-0 h-full">
                            <div class="flex justify-between mb-4">
                                <div>
                                    <span class="block text-muted-color font-medium mb-4">Trilha Tendência</span>
                                    <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">
                                        {{ stats.trilhas.tendencia.total }}
                                    </div>
                                    <span class="text-sm text-muted-color">
                                        {{ stats.trilhas.tendencia.percentual_demandas }}% das formalizadas
                                    </span>
                                </div>
                                <div class="flex items-center justify-center bg-purple-100 dark:bg-purple-400/10 rounded-border" style="width: 2.5rem; height: 2.5rem">
                                    <i class="pi pi-chart-line text-purple-500 !text-xl"></i>
                                </div>
                            </div>
                            <Button
                                label="Ver demandas (Tendência)"
                                icon="pi pi-arrow-right"
                                text
                                size="small"
                                class="p-0"
                                @click="irDemandasPorTrilha('tendencia')"
                            />
                            <Button
                                label="Gestão de tendências"
                                icon="pi pi-chart-line"
                                text
                                size="small"
                                class="p-0 mt-1"
                                @click="irGestaoTendencias()"
                            />
                        </div>
                    </div>
                    <div class="col-span-12 lg:col-span-4">
                        <div class="card mb-0 h-full">
                            <div class="flex justify-between mb-4">
                                <div>
                                    <span class="block text-muted-color font-medium mb-4">Recusas (Copiloto)</span>
                                    <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">
                                        {{ stats.trilhas.recusa.total }}
                                    </div>
                                    <span class="text-sm text-muted-color">
                                        {{ stats.trilhas.recusa.percentual_motor }}% do motor de ingresso
                                    </span>
                                </div>
                                <div class="flex items-center justify-center bg-orange-100 dark:bg-orange-400/10 rounded-border" style="width: 2.5rem; height: 2.5rem">
                                    <i class="pi pi-ban text-orange-500 !text-xl"></i>
                                </div>
                            </div>
                            <Button
                                label="Ver recusas no Copiloto"
                                icon="pi pi-list"
                                text
                                size="small"
                                class="p-0"
                                @click="irRecusasCopiloto()"
                            />
                        </div>
                    </div>
                    <div class="col-span-12 lg:col-span-6">
                        <div class="card">
                            <div class="font-semibold text-xl mb-4">Motor de trilhas</div>
                            <div v-if="trilhaDoughnutData" class="relative w-full" style="height: 300px">
                                <Chart
                                    :key="'trilha-' + chartRefreshKey"
                                    type="doughnut"
                                    :data="trilhaDoughnutData"
                                    :options="doughnutOptions"
                                    class="w-full h-full"
                                />
                            </div>
                            <p v-else class="text-sm text-muted-color m-0">Sem dados de trilhas no período.</p>
                        </div>
                    </div>
                    <div class="col-span-12 lg:col-span-6">
                        <div class="card">
                            <div class="font-semibold text-xl mb-4">Carta × Tendência (mensal)</div>
                            <div v-if="trilhaLineData" class="relative w-full" style="height: 300px">
                                <Chart
                                    :key="'trilha-line-' + chartRefreshKey"
                                    type="line"
                                    :data="trilhaLineData"
                                    :options="lineOptions"
                                    class="w-full h-full"
                                />
                            </div>
                            <p v-else class="text-sm text-muted-color m-0">Sem série mensal no período.</p>
                        </div>
                    </div>
                </div>
            </TabPanel>

            <TabPanel header="Dashboard">
                <div class="grid grid-cols-12 gap-6">
                    <div v-if="mostrarGraficoPorSecretaria" class="col-span-12 lg:col-span-6">
                        <div class="card">
                            <div class="font-semibold text-xl mb-4">Demandas por Secretaria</div>
                            <Chart type="bar" :data="barSecretariaData" :options="barOptions"></Chart>
                        </div>
                    </div>
                    <div
                        v-if="userStore.currentUser?.perfil !== 'VEREADOR'"
                        :class="isSecretaria ? 'col-span-12' : 'col-span-12 lg:col-span-6'"
                    >
                        <div class="card">
                            <div class="font-semibold text-xl mb-4">Demandas por Vereador</div>
                            <Chart type="bar" :data="barVereadorData" :options="barOptions"></Chart>
                        </div>
                    </div>
                    <div class="col-span-12 lg:col-span-6">
                        <div class="card">
                            <div class="font-semibold text-xl mb-4">Visão Geral por Status</div>
                            <div v-if="doughnutData" class="relative w-full max-w-md mx-auto" style="height: 300px">
                                <Chart
                                    :key="'status-' + chartRefreshKey"
                                    type="doughnut"
                                    :data="doughnutData"
                                    :options="pieOptions"
                                    class="w-full h-full"
                                />
                            </div>
                        </div>
                    </div>
                    <div class="col-span-12 lg:col-span-6">
                        <div class="card">
                            <div class="font-semibold text-xl mb-4">Evolução Mensal</div>
                            <div v-if="lineData" class="relative w-full" style="height: 300px">
                                <Chart
                                    :key="'mensal-' + chartRefreshKey"
                                    type="line"
                                    :data="lineData"
                                    :options="lineOptions"
                                    class="w-full h-full"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </TabPanel>
        </TabView>

        <!-- Perfil com uma única aba (ex.: Vereador): gráficos direto -->
        <template v-else>
            <div v-if="mostrarGraficoPorSecretaria" class="col-span-12 lg:col-span-6 xl:col-span-6">
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Demandas por Secretaria</div>
                    <Chart type="bar" :data="barSecretariaData" :options="barOptions"></Chart>
                </div>
            </div>
            <div
                v-if="userStore.currentUser?.perfil !== 'VEREADOR'"
                :class="isSecretaria ? 'col-span-12' : 'col-span-12 lg:col-span-6 xl:col-span-6'"
            >
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Demandas por Vereador</div>
                    <Chart type="bar" :data="barVereadorData" :options="barOptions"></Chart>
                </div>
            </div>
            <div class="col-span-12 lg:col-span-6 xl:col-span-6">
                <div class="card flex flex-col items-center">
                    <div class="font-semibold text-xl mb-4">Visão Geral por Status</div>
                    <Chart type="doughnut" :data="doughnutData" :options="pieOptions"></Chart>
                </div>
            </div>
            <div class="col-span-12 lg:col-span-6 xl:col-span-6">
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Evolução Mensal</div>
                    <Chart type="line" :data="lineData" :options="lineOptions"></Chart>
                </div>
            </div>
        </template>
    </div>
    <div v-else class="text-center">
        <p class="text-red-500">Não foi possível carregar os dados do dashboard.</p>
    </div>
</template>
