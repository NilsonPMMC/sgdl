<script setup>
import { ref, onMounted, watch } from 'vue';
import ApiService from '@/service/ApiService.js';
import Chart from 'primevue/chart';
import { useLayout } from '@/layout/composables/layout';
import { useUserStore } from '@/stores/userStore';

const { isDarkTheme } = useLayout();
const userStore = useUserStore();
const stats = ref(null);
const loading = ref(true);

const barSecretariaData = ref(null);
const barVereadorData = ref(null);
const doughnutData = ref(null);
const lineData = ref(null);

const barOptions = ref(null);
const lineOptions = ref(null);
const doughnutOptions = ref(null);
const pieOptions = ref(null);

async function carregarDadosDoDashboard() {
    loading.value = true;
    try {
        let params = {};
        const currentUser = userStore.user;

        if (currentUser.perfil === 'VEREADOR') {
            params.autor = currentUser.id;
        } else if (currentUser.perfil === 'SECRETARIA') {
            params.secretaria_destino = currentUser.secretariaId;
        }
        
        const response = await ApiService.getDashboardStats(params);
        stats.value = response.data;
        formatChartData(response.data);

    } catch (error) {
        console.error("Erro ao buscar dados do dashboard:", error);
    } finally {
        loading.value = false;
    }
}

onMounted(() => {
    setChartOptions();
    carregarDadosDoDashboard();
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
        plugins: { legend: { labels: { color: textColor } } },
        scales: {
            x: { ticks: { color: textColorSecondary }, grid: { color: surfaceBorder } },
            y: { ticks: { color: textColorSecondary }, grid: { color: surfaceBorder } }
        }
    };
    doughnutOptions.value = {
        plugins: { legend: { labels: { color: textColor, usePointStyle: true } } }
    };
    pieOptions.value = { plugins: { legend: { labels: { color: textColor, usePointStyle: true } } } };
}

function formatChartData(data) {
    const documentStyle = getComputedStyle(document.body);
    barSecretariaData.value = {
        labels: data.por_secretaria.map(item => item.secretaria_destino__nome),
        datasets: [
            { label: 'Abertas', backgroundColor: documentStyle.getPropertyValue('--p-purple-500'), data: data.por_secretaria.map(item => item.abertas) },
            { label: 'Concluídas', backgroundColor: documentStyle.getPropertyValue('--p-teal-500'), data: data.por_secretaria.map(item => item.total - item.abertas) }
        ]
    };
    barVereadorData.value = {
        labels: data.por_vereador.map(item => `${item.autor__first_name || ''} ${item.autor__last_name || ''}`.trim() || 'Não Identificado'),
        datasets: [
            { label: 'Abertas', backgroundColor: documentStyle.getPropertyValue('--p-purple-500'), data: data.por_vereador.map(item => item.abertas) },
            { label: 'Concluídas', backgroundColor: documentStyle.getPropertyValue('--p-teal-500'), data: data.por_vereador.map(item => item.total - item.abertas) }
        ]
    };
    doughnutData.value = {
        labels: data.por_status_agrupado.map(item => item.status),
        datasets: [{
            data: data.por_status_agrupado.map(item => item.total),
            backgroundColor: [documentStyle.getPropertyValue('--p-cyan-500'), documentStyle.getPropertyValue('--p-purple-500'), documentStyle.getPropertyValue('--p-teal-500')]
        }]
    };
    lineData.value = {
        labels: data.mensal.map(item => item.mes),
        datasets: [
            { label: 'Total', data: data.mensal.map(item => item.total), fill: false, borderColor: documentStyle.getPropertyValue('--p-teal-500'), tension: 0.4 },
            { label: 'Abertas', data: data.mensal.map(item => item.abertas), fill: false, borderColor: documentStyle.getPropertyValue('--p-purple-500'), tension: 0.4 }
        ]
    };
}
</script>

<template>
    <div v-if="loading">
        <p>Carregando dados do dashboard...</p>
    </div>
    <Fluid v-if="stats && !loading" class="grid grid-cols-12 gap-8">
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
        <div class="col-span-12 lg:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="flex justify-between mb-4">
                    <div>
                        <span class="block text-muted-color font-medium mb-4">Atrasadas</span>
                        <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ stats.kpis.demandas_atrasadas }}</div>
                    </div>
                    <div class="flex items-center justify-center bg-red-100 dark:bg-red-400/10 rounded-border" style="width:2.5rem; height:2.5rem">
                        <i class="pi pi-clock text-red-500 !text-xl"></i>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="userStore.user.perfil !== 'VEREADOR'" class="col-span-12 lg:col-span-6 xl:col-span-6">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Demandas por Secretaria</div>
                <Chart type="bar" :data="barSecretariaData" :options="barOptions"></Chart>
            </div>
        </div>
        <div v-if="userStore.user.perfil !== 'VEREADOR'" class="col-span-12 lg:col-span-6 xl:col-span-6">
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
    </Fluid>
    <div v-else class="text-center">
        <p class="text-red-500">Não foi possível carregar os dados do dashboard.</p>
    </div>
</template>