<script setup>
import { ref, onMounted, reactive, watch, nextTick, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import ApiService from '@/service/ApiService.js';
import { STATUS_CHOICES_REPORTS } from '@/constants.js';
import { useLayout } from '@/layout/composables/layout';
import { useUserStore } from '@/stores/userStore';

import Panel from 'primevue/panel';
import MultiSelect from 'primevue/multiselect';
import DatePicker from 'primevue/datepicker';
import Button from 'primevue/button';
import Chart from 'primevue/chart';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import ProgressSpinner from 'primevue/progressspinner';
import Message from 'primevue/message';
import Checkbox from 'primevue/checkbox';

const router = useRouter();
const isLoading = ref(false);
const isLoadingTable = ref(false);
const isLoaded = ref(false);
const isExporting = ref(false);
const apiService = ApiService;
const rawData = ref([]);
const processMiningSetor = ref([]);
const funilStatus = ref([]);
const comparativoVereador = ref(null);
const setorDrillDown = ref(null);
const { isDarkTheme } = useLayout();
const userStore = useUserStore();

const statsCards = ref({
    total: 0,
    abertas: 0,
    concluidas: 0,
    atrasadas: 0,
    pct_dentro_sla: null,
    pct_encerradas_no_sla: null
});

const tablePagination = ref({ first: 0, rows: 25 });
const tableTotalRecords = ref(0);

const filtros = reactive({
    datas: null,
    status: null,
    secretarias: null,
    servicos: null,
    vereadores: null,
    setores: null,
    clusters: null,
    superOs: false
});

const opcoes = reactive({
    status: STATUS_CHOICES_REPORTS.filter((s) => s.value !== 'RASCUNHO'),
    secretarias: [],
    servicos: [],
    vereadores: [],
    setores: [],
    clusters: []
});

const barSecretariaData = ref(null);
const doughnutData = ref(null);
const funilChartData = ref(null);
const barOptions = ref(null);
const pieOptions = ref(null);
const funilOptions = ref(null);

const statusLabelMap = Object.fromEntries(STATUS_CHOICES_REPORTS.map((s) => [s.value, s.label]));

const setoresComGargalo = computed(() =>
    (processMiningSetor.value || []).filter((s) => s.gargalo)
);

const getStatusSeverity = (status, isAtrasada = false) => {
    if (isAtrasada) return 'danger';
    switch (status) {
        case 'AGUARDANDO_PROTOCOLO':
            return 'info';
        case 'PROTOCOLADO':
            return 'warning';
        case 'EM_EXECUCAO':
            return 'primary';
        case 'FINALIZADO':
            return 'success';
        case 'CANCELADO':
            return 'danger';
        case 'AGUARDANDO_TRANSFERENCIA':
            return 'warning';
        default:
            return 'secondary';
    }
};

const formatarDuracaoSegundos = (segundos) => {
    if (segundos == null) return '—';
    const dias = Math.floor(segundos / 86400);
    const horas = Math.floor((segundos % 86400) / 3600);
    if (dias > 0) return `${dias}d ${horas}h`;
    if (horas > 0) return `${horas}h`;
    return `${Math.floor(segundos / 60)}min`;
};

const formatarDataCurta = (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('pt-BR');
};

const labelSetor = (row) => row?.unidade_administrativa?.sigla || row?.unidade_administrativa?.nome || '—';

const slaResumo = (row) => {
    const sla = row?.sla || {};
    if (sla.prazo_dias == null) return 'Sem SLA';
    const restante = sla.dias_restantes;
    if (restante == null) return `${sla.prazo_dias} dias`;
    if (restante < 0) return `${Math.abs(restante)}d em atraso`;
    return `${restante}d restantes`;
};

const formatarData = (data) => {
    if (!data) return null;
    const d = new Date(data);
    d.setMinutes(d.getMinutes() + d.getTimezoneOffset());
    return d.toISOString().split('T')[0];
};

const formatarParams = (extra = {}) => {
    const params = { ...extra };
    const currentUser = userStore.currentUser;

    if (filtros.datas && filtros.datas[0]) {
        params.data_inicio = formatarData(filtros.datas[0]);
    }
    if (filtros.datas && filtros.datas[1]) {
        const dataFim = new Date(filtros.datas[1]);
        dataFim.setDate(dataFim.getDate() + 1);
        params.data_fim = formatarData(dataFim);
    }
    if (filtros.status?.length) {
        params.status__in = filtros.status.join(',');
    }

    if (currentUser?.perfil === 'SECRETARIA') {
        if (currentUser.sinapse_orgao_id) {
            params.secretaria__in = String(currentUser.sinapse_orgao_id);
        }
    } else if (filtros.secretarias?.length) {
        params.secretaria__in = filtros.secretarias.join(',');
    }

    if (filtros.servicos?.length) {
        params.servico__in = filtros.servicos.join(',');
    }

    if (currentUser?.perfil === 'VEREADOR') {
        params.vereador__in = String(currentUser.id);
    } else if (filtros.vereadores?.length) {
        params.vereador__in = filtros.vereadores.join(',');
    }

    if (filtros.setores?.length) {
        params.unidade__in = filtros.setores.join(',');
    }
    if (filtros.clusters?.length) {
        params.cluster__in = filtros.clusters.join(',');
    }
    if (filtros.superOs) {
        params.super_os = 'true';
    }

    return params;
};

const formatarChartStatus = (data) => {
    const documentStyle = getComputedStyle(document.body);
    const labels = data.map((item) => statusLabelMap[item.status] || item.status);
    const totais = data.map((item) => item.total);

    return {
        labels,
        datasets: [
            {
                data: totais,
                backgroundColor: [
                    documentStyle.getPropertyValue('--p-cyan-500'),
                    documentStyle.getPropertyValue('--p-purple-500'),
                    documentStyle.getPropertyValue('--p-teal-500'),
                    documentStyle.getPropertyValue('--p-orange-500'),
                    documentStyle.getPropertyValue('--p-gray-500'),
                    documentStyle.getPropertyValue('--p-pink-500')
                ]
            }
        ]
    };
};

const formatarChartSecretaria = (data) => {
    const documentStyle = getComputedStyle(document.body);
    return {
        labels: data.map((item) => item.secretaria),
        datasets: [
            {
                label: 'Abertas',
                backgroundColor: documentStyle.getPropertyValue('--p-purple-500'),
                data: data.map((item) => item.abertas)
            },
            {
                label: 'Concluídas',
                backgroundColor: documentStyle.getPropertyValue('--p-teal-500'),
                data: data.map((item) => item.total - item.abertas)
            }
        ]
    };
};

const formatarChartFunil = (data) => {
    const documentStyle = getComputedStyle(document.body);
    const filtrado = (data || []).filter((item) => item.amostras > 0);
    return {
        labels: filtrado.map((item) => item.rotulo),
        datasets: [
            {
                label: 'Dias médios',
                backgroundColor: documentStyle.getPropertyValue('--p-indigo-500'),
                data: filtrado.map((item) => item.dias_medio ?? 0)
            }
        ]
    };
};

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
    pieOptions.value = {
        plugins: { legend: { labels: { color: textColor, usePointStyle: true } } }
    };
    funilOptions.value = {
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: textColorSecondary }, grid: { color: surfaceBorder }, title: { display: true, text: 'Dias', color: textColorSecondary } },
            y: { ticks: { color: textColorSecondary }, grid: { color: surfaceBorder } }
        }
    };
}

const carregarOpcoesFiltros = async () => {
    try {
        const promises = [
            apiService.getSecretarias(),
            apiService.getServicos(),
            apiService.listarUnidadesAdministrativas({ page_size: 500 }),
            apiService.listarClusters({ page_size: 200 })
        ];
        if (userStore.currentUser?.perfil !== 'VEREADOR') {
            promises.push(apiService.getUsuarios({ perfil: 'VEREADOR' }));
        }
        const results = await Promise.all(promises);
        const extrairDados = (response) => response.data.results || response.data;

        opcoes.secretarias = extrairDados(results[0]);
        opcoes.servicos = extrairDados(results[1]);
        opcoes.setores = extrairDados(results[2]).map((u) => ({
            ...u,
            nome_formatado: u.sigla ? `${u.sigla} — ${u.nome}` : u.nome
        }));
        opcoes.clusters = extrairDados(results[3]).map((c) => ({
            ...c,
            nome_formatado: c.protocolo_super_os ? `${c.protocolo_super_os} — ${c.titulo}` : c.titulo
        }));

        if (results[4]) {
            const vereadoresData = extrairDados(results[4]);
            opcoes.vereadores = vereadoresData.map((user) => ({
                ...user,
                nome_formatado: `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username
            }));
        }
    } catch (error) {
        console.error('Erro ao carregar opções dos filtros:', error);
    }
};

const loadDemandasTable = async () => {
    isLoadingTable.value = true;
    try {
        const page = Math.floor(tablePagination.value.first / tablePagination.value.rows) + 1;
        const params = formatarParams({
            page,
            page_size: tablePagination.value.rows
        });
        const resp = await apiService.getReportDemandasList(params);
        rawData.value = resp.data.results || resp.data || [];
        tableTotalRecords.value = resp.data.count ?? rawData.value.length;
    } catch (error) {
        console.error('Erro ao carregar tabela:', error);
        rawData.value = [];
        tableTotalRecords.value = 0;
    } finally {
        isLoadingTable.value = false;
    }
};

const onPageTable = (event) => {
    tablePagination.value = { first: event.first, rows: event.rows };
    loadDemandasTable();
};

const buscarRelatorios = async () => {
    isLoading.value = true;
    isLoaded.value = true;
    setorDrillDown.value = null;
    tablePagination.value.first = 0;

    const params = formatarParams();
    try {
        const [respKPIs, respStatus, respSecretaria, respMining, respFunil, respComparativo] = await Promise.all([
            apiService.getReportKPIs(params),
            apiService.getReportPorStatus(params),
            apiService.getReportPorSecretaria(params),
            apiService.getReportProcessMiningSetor(params),
            apiService.getReportFunilStatus(params),
            userStore.currentUser?.perfil !== 'VEREADOR'
                ? apiService.getReportComparativoVereador(params)
                : Promise.resolve({ data: null })
        ]);

        statsCards.value = {
            total: respKPIs.data.total_demandas || 0,
            abertas: respKPIs.data.demandas_abertas || 0,
            concluidas: respKPIs.data.demandas_concluidas || 0,
            atrasadas: respKPIs.data.demandas_atrasadas || 0,
            pct_dentro_sla: respKPIs.data.pct_dentro_sla,
            pct_encerradas_no_sla: respKPIs.data.pct_encerradas_no_sla
        };

        doughnutData.value = formatarChartStatus(respStatus.data);
        barSecretariaData.value = formatarChartSecretaria(respSecretaria.data);
        processMiningSetor.value = respMining.data || [];
        funilStatus.value = respFunil.data || [];
        funilChartData.value = formatarChartFunil(funilStatus.value);
        comparativoVereador.value = respComparativo.data;

        await loadDemandasTable();
    } catch (error) {
        console.error('Erro ao buscar relatórios:', error);
    } finally {
        isLoading.value = false;
    }
};

const limparFiltros = () => {
    filtros.datas = null;
    filtros.status = null;
    filtros.secretarias = null;
    filtros.servicos = null;
    filtros.vereadores = null;
    filtros.setores = null;
    filtros.clusters = null;
    filtros.superOs = false;
    setorDrillDown.value = null;
    buscarRelatorios();
};

const aplicarDrillDownSetor = (row) => {
    if (!row?.unidade_id) return;
    filtros.setores = [row.unidade_id];
    setorDrillDown.value = row.setor;
    buscarRelatorios();
};

const limparDrillDownSetor = () => {
    filtros.setores = null;
    setorDrillDown.value = null;
    buscarRelatorios();
};

const exportarCSV = async () => {
    isExporting.value = true;
    try {
        await apiService.exportReportCSV(formatarParams());
    } catch (error) {
        console.error('Erro ao exportar CSV:', error);
    } finally {
        isExporting.value = false;
    }
};

const verNoMapa = (row) => {
    if (!row?.tem_geolocalizacao) return;
    router.push({ name: 'mapa-calor', query: { demanda_id: row.id } });
};

const deltaClass = (valor) => {
    if (valor == null || valor === 0) return '';
    return valor > 0 ? 'text-red-500' : 'text-green-500';
};

const imprimirPagina = async () => {
    const saved = { ...tablePagination.value };
    tablePagination.value = { first: 0, rows: Math.max(tableTotalRecords.value, 100) };
    await loadDemandasTable();
    await nextTick();
    window.print();
    tablePagination.value = saved;
    await loadDemandasTable();
};

const afterPrint = () => {
    loadDemandasTable();
};

onMounted(() => {
    setChartOptions();
    carregarOpcoesFiltros();
    buscarRelatorios();
    window.addEventListener('afterprint', afterPrint);
});

onUnmounted(() => {
    window.removeEventListener('afterprint', afterPrint);
});

watch(isDarkTheme, setChartOptions);
</script>

<template>
    <div class="fixed bottom-4 right-4 z-50 no-print hidden lg:flex gap-2">
        <Button
            icon="pi pi-download"
            rounded
            severity="secondary"
            title="Exportar CSV"
            aria-label="Exportar CSV"
            :loading="isExporting"
            @click="exportarCSV"
        />
        <Button
            icon="pi pi-print"
            rounded
            severity="info"
            title="Imprimir Relatório"
            aria-label="Imprimir Relatório"
            @click="imprimirPagina"
        />
    </div>

    <div class="card no-print">
        <h5>Relatórios Gerenciais</h5>
        <div class="col-12">
            <Panel class="mb-3" header="Filtrar" toggleable>
                <div class="flex flex-wrap gap-4 mb-3">
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-datas">Período</label>
                        <DatePicker v-model="filtros.datas" selectionMode="range" :manualInput="false" dateFormat="dd/mm/yy" placeholder="Início - Fim" fluid />
                    </div>
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-status">Status</label>
                        <MultiSelect v-model="filtros.status" :options="opcoes.status" optionLabel="label" optionValue="value" placeholder="Todos os Status" fluid />
                    </div>
                    <div v-if="userStore.currentUser?.perfil !== 'VEREADOR'" class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-vereadores">Autor (Vereador)</label>
                        <MultiSelect v-model="filtros.vereadores" :options="opcoes.vereadores" optionLabel="nome_formatado" optionValue="id" placeholder="Todos os Autores" fluid />
                    </div>
                </div>
                <div class="flex flex-wrap gap-4 mb-3">
                    <div v-if="userStore.currentUser?.perfil !== 'SECRETARIA'" class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-secretarias">Secretaria (Destino)</label>
                        <MultiSelect v-model="filtros.secretarias" :options="opcoes.secretarias" optionLabel="nome" optionValue="id" placeholder="Todas as Secretarias" fluid />
                    </div>
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-servicos">Serviço</label>
                        <MultiSelect v-model="filtros.servicos" :options="opcoes.servicos" optionLabel="nome" optionValue="id" placeholder="Todos os Serviços" fluid />
                    </div>
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-setores">Setor</label>
                        <MultiSelect v-model="filtros.setores" :options="opcoes.setores" optionLabel="nome_formatado" optionValue="id" placeholder="Todos os Setores" fluid />
                    </div>
                </div>
                <div class="flex flex-wrap gap-4 mb-3 items-end">
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-clusters">Super OS (Cluster)</label>
                        <MultiSelect v-model="filtros.clusters" :options="opcoes.clusters" optionLabel="nome_formatado" optionValue="id" placeholder="Todos os clusters" fluid />
                    </div>
                    <div class="flex items-center gap-2 pb-2">
                        <Checkbox v-model="filtros.superOs" inputId="filtro-super-os" binary />
                        <label for="filtro-super-os" class="cursor-pointer">Somente Super OS</label>
                    </div>
                </div>
                <Button label="Buscar Relatórios" icon="pi pi-search" @click="buscarRelatorios" :loading="isLoading" class="mr-3" />
                <Button label="Limpar Filtros" icon="pi pi-filter-slash" @click="limparFiltros" severity="secondary" outlined />
            </Panel>
        </div>
    </div>

    <div v-if="isLoading" class="text-center p-5 no-print">
        <ProgressSpinner />
        <p>Buscando dados...</p>
    </div>

    <div v-if="!isLoading && isLoaded" class="relatorio-container">
        <div class="grid grid-cols-12 gap-4 mb-4 print-card-grid">
            <div class="col-span-12 md:col-span-6 lg:col-span-2">
                <div class="card h-full mb-0">
                    <div class="text-gray-500 font-medium text-sm">TOTAL</div>
                    <div class="text-2xl font-bold mt-1">{{ statsCards.total }}</div>
                </div>
            </div>
            <div class="col-span-12 md:col-span-6 lg:col-span-2">
                <div class="card h-full mb-0">
                    <div class="text-gray-500 font-medium text-sm">ABERTAS</div>
                    <div class="text-2xl font-bold text-orange-500 mt-1">{{ statsCards.abertas }}</div>
                </div>
            </div>
            <div class="col-span-12 md:col-span-6 lg:col-span-2">
                <div class="card h-full mb-0">
                    <div class="text-gray-500 font-medium text-sm">CONCLUÍDAS</div>
                    <div class="text-2xl font-bold text-green-500 mt-1">{{ statsCards.concluidas }}</div>
                </div>
            </div>
            <div class="col-span-12 md:col-span-6 lg:col-span-2">
                <div class="card h-full mb-0">
                    <div class="text-gray-500 font-medium text-sm">ATRASADAS</div>
                    <div class="text-2xl font-bold text-red-500 mt-1">{{ statsCards.atrasadas }}</div>
                </div>
            </div>
            <div class="col-span-12 md:col-span-6 lg:col-span-2">
                <div class="card h-full mb-0">
                    <div class="text-gray-500 font-medium text-sm">DENTRO DO SLA</div>
                    <div class="text-2xl font-bold text-teal-500 mt-1">
                        {{ statsCards.pct_dentro_sla != null ? `${statsCards.pct_dentro_sla}%` : '—' }}
                    </div>
                    <div class="text-xs text-muted-color mt-1">Abertas com prazo vigente</div>
                </div>
            </div>
            <div class="col-span-12 md:col-span-6 lg:col-span-2">
                <div class="card h-full mb-0">
                    <div class="text-gray-500 font-medium text-sm">ENCERRADAS NO SLA</div>
                    <div class="text-2xl font-bold text-blue-500 mt-1">
                        {{ statsCards.pct_encerradas_no_sla != null ? `${statsCards.pct_encerradas_no_sla}%` : '—' }}
                    </div>
                    <div class="text-xs text-muted-color mt-1">Finalizadas dentro do prazo</div>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-12 gap-8 print-avoid-break print-chart-grid">
            <div v-if="userStore.currentUser?.perfil !== 'SECRETARIA'" class="col-span-12 lg:col-span-4">
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Demandas por Secretaria</div>
                    <Chart type="bar" :data="barSecretariaData" :options="barOptions" />
                </div>
            </div>
            <div class="col-span-12 lg:col-span-4">
                <div class="card flex flex-col items-center">
                    <div class="font-semibold text-xl mb-4">Visão Geral por Status</div>
                    <Chart type="doughnut" :data="doughnutData" :options="pieOptions" />
                </div>
            </div>
            <div v-if="funilChartData" class="col-span-12 lg:col-span-4">
                <div class="card">
                    <div class="font-semibold text-xl mb-2">Funil — tempo entre etapas</div>
                    <p class="text-sm text-muted-color mb-3 m-0">Média em dias entre transições principais do fluxo.</p>
                    <Chart type="bar" :data="funilChartData" :options="funilOptions" />
                </div>
            </div>
        </div>

        <div v-if="setoresComGargalo.length" class="col-span-12 print-avoid-break no-print">
            <Message severity="warn" :closable="false">
                <span class="font-medium">Gargalos detectados:</span>
                {{ setoresComGargalo.map((s) => `${s.setor} (${s.tempo_medio_etapa_horas}h na etapa, limite ${s.gargalo_limite_horas}h)`).join(' · ') }}
            </Message>
        </div>

        <div v-if="processMiningSetor.length" class="col-span-12 print-avoid-break">
            <div class="card">
                <div class="font-semibold text-xl mb-2">Process mining — Setor</div>
                <p class="text-sm text-muted-color mb-4 m-0">
                    Clique em um setor para filtrar a tabela. Setores com tempo médio na etapa acima de 48h são marcados como gargalo.
                </p>
                <DataTable :value="processMiningSetor" size="small" stripedRows class="sgdl-table-scroll">
                    <Column field="setor" header="Setor" sortable>
                        <template #body="{ data }">
                            <button
                                type="button"
                                class="text-left p-link font-medium"
                                :class="{ 'text-primary': data.unidade_id }"
                                @click="aplicarDrillDownSetor(data)"
                            >
                                {{ data.setor }}
                                <Tag v-if="data.gargalo" value="Gargalo" severity="danger" class="ml-2" />
                            </button>
                        </template>
                    </Column>
                    <Column field="total" header="Total" sortable style="width: 5rem" />
                    <Column field="em_aberto" header="Em aberto" sortable style="width: 6rem" />
                    <Column field="atrasadas" header="Atrasadas" sortable style="width: 6rem">
                        <template #body="{ data }">
                            <Tag :value="String(data.atrasadas)" :severity="data.atrasadas ? 'danger' : 'success'" />
                        </template>
                    </Column>
                    <Column header="Tempo médio na etapa" style="width: 9rem">
                        <template #body="{ data }">
                            <span :class="{ 'text-red-500 font-medium': data.gargalo }">
                                {{ data.tempo_medio_etapa_horas != null ? `${data.tempo_medio_etapa_horas}h` : '—' }}
                            </span>
                        </template>
                    </Column>
                    <Column header="Média pós-protocolo" style="width: 9rem">
                        <template #body="{ data }">
                            {{ data.dias_medio_pos_protocolo != null ? `${data.dias_medio_pos_protocolo} dias` : '—' }}
                        </template>
                    </Column>
                </DataTable>
            </div>
        </div>

        <div
            v-if="comparativoVereador?.vereadores?.length && userStore.currentUser?.perfil !== 'VEREADOR'"
            class="col-span-12 print-avoid-break"
        >
            <div class="card">
                <div class="font-semibold text-xl mb-2">Comparativo — Vereador × média</div>
                <p class="text-sm text-muted-color mb-3 m-0">
                    Média geral: {{ comparativoVereador.media_geral?.pct_atraso ?? '—' }}% atraso ·
                    {{ comparativoVereador.media_geral?.dias_medio_pos_protocolo ?? '—' }} dias pós-protocolo
                </p>
                <DataTable :value="comparativoVereador.vereadores" size="small" stripedRows class="sgdl-table-scroll">
                    <Column field="vereador" header="Vereador" sortable />
                    <Column field="total" header="Total" sortable style="width: 5rem" />
                    <Column field="atrasadas" header="Atrasadas" sortable style="width: 6rem" />
                    <Column header="% atraso" sortable sortField="pct_atraso" style="width: 7rem">
                        <template #body="{ data }">
                            {{ data.pct_atraso != null ? `${data.pct_atraso}%` : '—' }}
                        </template>
                    </Column>
                    <Column header="Δ vs média" style="width: 7rem">
                        <template #body="{ data }">
                            <span :class="deltaClass(data.delta_pct_atraso_vs_media)">
                                {{ data.delta_pct_atraso_vs_media != null ? `${data.delta_pct_atraso_vs_media > 0 ? '+' : ''}${data.delta_pct_atraso_vs_media} pp` : '—' }}
                            </span>
                        </template>
                    </Column>
                    <Column header="Dias pós-protocolo" style="width: 8rem">
                        <template #body="{ data }">
                            {{ data.dias_medio_pos_protocolo != null ? `${data.dias_medio_pos_protocolo}d` : '—' }}
                        </template>
                    </Column>
                    <Column header="Δ dias" style="width: 6rem">
                        <template #body="{ data }">
                            <span :class="deltaClass(data.delta_dias_pos_protocolo_vs_media)">
                                {{ data.delta_dias_pos_protocolo_vs_media != null ? `${data.delta_dias_pos_protocolo_vs_media > 0 ? '+' : ''}${data.delta_dias_pos_protocolo_vs_media}d` : '—' }}
                            </span>
                        </template>
                    </Column>
                </DataTable>
            </div>
        </div>

        <div class="col-span-12 print-avoid-break">
            <div class="card">
                <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
                    <div>
                        <div class="font-semibold text-xl">Dados das Demandas Filtradas</div>
                        <p class="text-sm text-muted-color m-0 mt-1">
                            Rascunhos excluídos. Paginação no servidor.
                            <span v-if="setorDrillDown" class="ml-2">
                                Filtro setor: <strong>{{ setorDrillDown }}</strong>
                                <Button label="Limpar" link size="small" class="ml-1 p-0" @click="limparDrillDownSetor" />
                            </span>
                        </p>
                    </div>
                    <Button label="Exportar CSV" icon="pi pi-download" size="small" outlined class="no-print" :loading="isExporting" @click="exportarCSV" />
                </div>

                <DataTable
                    :value="rawData"
                    lazy
                    paginator
                    :rows="tablePagination.rows"
                    :first="tablePagination.first"
                    :totalRecords="tableTotalRecords"
                    responsiveLayout="scroll"
                    class="sgdl-table-scroll"
                    :loading="isLoadingTable"
                    dataKey="id"
                    paginatorTemplate="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
                    currentPageReportTemplate="Mostrando {first} a {last} de {totalRecords}"
                    :rowsPerPageOptions="[10, 25, 50, 100]"
                    @page="onPageTable"
                >
                    <Column field="protocolo_legislativo" header="Ofício" sortable />
                    <Column field="protocolo_executivo" header="Protocolo" sortable />
                    <Column field="autor_nome" header="Autor" sortable />
                    <Column field="secretaria_destino_nome" header="Órgão" sortable />
                    <Column header="Setor">
                        <template #body="{ data }">{{ labelSetor(data) }}</template>
                    </Column>
                    <Column header="Super OS" style="width: 7rem">
                        <template #body="{ data }">
                            {{ data.cluster?.protocolo_super_os || '—' }}
                        </template>
                    </Column>
                    <Column field="servico_nome" header="Serviço" style="min-width: 10rem" />
                    <Column header="SLA" style="width: 8rem">
                        <template #body="{ data }">
                            <span :class="{ 'text-red-500 font-medium': data.sla?.is_atrasada }">{{ slaResumo(data) }}</span>
                        </template>
                    </Column>
                    <Column header="Vencimento" style="width: 7rem">
                        <template #body="{ data }">{{ formatarDataCurta(data.sla?.data_vencimento) }}</template>
                    </Column>
                    <Column header="Pós-protocolo" style="width: 7rem">
                        <template #body="{ data }">
                            {{ data.sla?.dias_pos_protocolo != null ? `${data.sla.dias_pos_protocolo}d` : '—' }}
                        </template>
                    </Column>
                    <Column header="Na etapa" style="width: 7rem">
                        <template #body="{ data }">{{ formatarDuracaoSegundos(data.sla?.tempo_etapa_segundos) }}</template>
                    </Column>
                    <Column field="status" header="Status">
                        <template #body="{ data }">
                            <Tag
                                :value="data.sla?.is_atrasada ? 'ATRASADO' : data.status_display"
                                :severity="getStatusSeverity(data.status, data.sla?.is_atrasada)"
                            />
                        </template>
                    </Column>
                    <Column header="Mapa" style="width: 5rem" class="no-print">
                        <template #body="{ data }">
                            <Button
                                v-if="data.tem_geolocalizacao"
                                icon="pi pi-map-marker"
                                text
                                rounded
                                severity="info"
                                title="Ver no mapa"
                                aria-label="Ver no mapa"
                                @click="verNoMapa(data)"
                            />
                            <span v-else class="text-muted-color text-sm">—</span>
                        </template>
                    </Column>
                    <Column field="data_criacao" header="Criado em">
                        <template #body="{ data }">
                            {{ new Date(data.data_criacao).toLocaleDateString('pt-BR') }}
                        </template>
                    </Column>
                </DataTable>
            </div>
        </div>
    </div>
</template>

<style>
@media print {
    body .layout-sidebar,
    body .layout-topbar,
    body .layout-footer,
    body .no-print,
    .p-paginator {
        display: none !important;
    }

    body .layout-main-container {
        padding-top: 0 !important;
        margin-left: 0 !important;
        width: 100% !important;
        min-width: 100% !important;
    }

    .print-avoid-break {
        page-break-inside: avoid;
    }

    :root {
        --text-color: #495057 !important;
        --text-color-secondary: #6c757d !important;
        --surface-border: #dee2e6 !important;
    }

    body {
        margin: 0;
        padding: 0;
        background-color: #fff !important;
        color: #000 !important;
    }

    .card {
        background-color: #fff !important;
        box-shadow: none !important;
        border: 1px solid #dee2e6;
    }

    h5,
    .font-semibold,
    .text-gray-500,
    .text-2xl,
    .text-lg,
    .text-xl {
        color: #000 !important;
    }

    * {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }

    @page {
        size: A4 landscape;
        margin: 1.5cm;
    }

    .print-chart-grid {
        display: grid !important;
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 1.5rem !important;
    }
    .print-chart-grid > * {
        grid-column: span 1 / span 1 !important;
    }
    .print-card-grid {
        display: grid !important;
        grid-template-columns: repeat(6, 1fr) !important;
        gap: 0.75rem !important;
    }
    .print-card-grid > * {
        grid-column: span 1 / span 1 !important;
    }
}
</style>

<style scoped>
.card {
    margin-bottom: 1rem;
}
</style>
