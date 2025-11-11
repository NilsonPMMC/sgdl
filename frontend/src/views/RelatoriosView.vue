<template>
    <div class="fixed bottom-4 right-4 z-50 no-print hidden lg:block">
        <Button icon="pi pi-print" rounded severity="info" @click="imprimirPagina" v-tooltip.left="'Imprimir Relatório'" />
    </div>

    <div class="card no-print">
        <h5>Relatórios Gerenciais</h5>
        <div class="col-12">
            <Panel class="mb-3" header="Filtrar" toggleable>
                <div class="flex flex-wrap gap-4 mb-3">
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-datas">Período</label>
                        <DatePicker v-model="filtros.datas" selectionMode="range" :manualInput="false"
                            dateFormat="dd/mm/yy" placeholder="Início - Fim" fluid />
                    </div>

                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-status">Status</label>
                        <MultiSelect v-model="filtros.status" :options="opcoes.status" optionLabel="label"
                            optionValue="value" placeholder="Todos os Status" fluid />
                    </div>
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-vereadores">Autor (Vereador)</label>
                        <MultiSelect v-model="filtros.vereadores" :options="opcoes.vereadores" optionLabel="nome_formatado"
                        optionValue="id" placeholder="Todos os Autores" fluid />
                    </div>
                </div>
                <div class="flex flex-wrap gap-4 mb-3">
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-secretarias">Secretaria (Destino)</label>
                        <MultiSelect v-model="filtros.secretarias" :options="opcoes.secretarias" optionLabel="nome"
                            optionValue="id" placeholder="Todas as Secretarias" fluid />
                    </div>
                    
                    <div class="flex flex-col grow basis-0 gap-2">
                        <label for="filtro-servicos">Serviço</label>
                        <MultiSelect v-model="filtros.servicos" :options="opcoes.servicos" optionLabel="nome"
                            optionValue="id" placeholder="Todos os Serviços" fluid />
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
            <div class="col-span-12 md:col-span-6 lg:col-span-3">
                <div class="card h-full">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-gray-500 font-medium">TOTAL</div>
                            <div class="text-2xl font-bold mt-2">{{ statsCards.total }}</div>
                        </div>
                        <div class="flex items-center justify-center bg-blue-100 rounded-full w-12 h-12">
                            <i class="pi pi-inbox text-blue-500 text-xl"></i>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-span-12 md:col-span-6 lg:col-span-3">
                <div class="card h-full">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-gray-500 font-medium">ABERTAS</div>
                            <div class="text-2xl font-bold text-orange-500 mt-2">{{ statsCards.abertas }}</div>
                        </div>
                        <div class="flex items-center justify-center bg-orange-100 rounded-full w-12 h-12">
                            <i class="pi pi-folder-open text-orange-500 text-xl"></i>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-span-12 md:col-span-6 lg:col-span-3">
                <div class="card h-full">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-gray-500 font-medium">CONCLUÍDAS</div>
                            <div class="text-2xl font-bold text-green-500 mt-2">{{ statsCards.concluidas }}</div>
                        </div>
                        <div class="flex items-center justify-center bg-green-100 rounded-full w-12 h-12">
                            <i class="pi pi-check-circle text-green-500 text-xl"></i>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-span-12 md:col-span-6 lg:col-span-3">
                <div class="card h-full">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="text-gray-500 font-medium">ATRASADAS</div>
                            <div class="text-2xl font-bold text-red-500 mt-2">{{ statsCards.atrasadas }}</div>
                        </div>
                        <div class="flex items-center justify-center bg-red-100 rounded-full w-12 h-12">
                            <i class="pi pi-exclamation-triangle text-red-500 text-xl"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="grid grid-cols-12 gap-8 print-avoid-break print-chart-grid">
            <div class="col-span-12 lg:col-span-6 xl:col-span-6">
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Demandas por Secretaria</div>
                    <Chart type="bar" :data="barSecretariaData" :options="barOptions"></Chart>
                </div>
            </div>

            <div class="col-span-12 lg:col-span-6 xl:col-span-6">
                <div class="card flex flex-col items-center">
                    <div class="font-semibold text-xl mb-4">Visão Geral por Status</div>
                    <Chart type="doughnut" :data="doughnutData" :options="pieOptions"></Chart>
                </div>
            </div>
        </div>

        <div class="col-span-12 print-avoid-break">
            <div class="card">
                <div class="font-semibold text-xl mb-4">Dados das Demandas Filtradas</div>

                <DataTable :value="rawData" :rows="dataTableRows" paginator responsiveLayout="scroll"
                    :loading="isLoading" dataKey="id"
                    paginatorTemplate="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
                    currentPageReportTemplate="Mostrando {first} a {last} de {totalRecords}">

                    <Column field="protocolo_legislativo" header="Ofício" :sortable="true"></Column>
                    <Column field="protocolo_executivo" header="Protocolo" :sortable="true"></Column>

                    <Column field="criado_por_id" header="Autor" :sortable="true">
                        <template #body="slotProps">
                            {{ userMap[slotProps.data.criado_por_id] || 'Sem Autor' }}
                        </template>
                    </Column>

                    <Column field="secretaria_destino_nome" header="Secretaria" :sortable="true"></Column>

                    <Column field="status" header="Status" :sortable="true">
                        <template #body="slotProps">
                            <Tag :value="slotProps.data.status_display" :severity="getStatusSeverity(slotProps.data.status)" />
                        </template>
                    </Column>

                    <Column field="data_criacao" header="Criado em" :sortable="true">
                        <template #body="slotProps">
                            {{ new Date(slotProps.data.data_criacao).toLocaleDateString('pt-BR') }}
                        </template>
                    </Column>
                </DataTable>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, reactive, watch, nextTick, onUnmounted } from 'vue'; 
import ApiService from '@/service/ApiService.js';
import { STATUS_CHOICES_REPORTS, CHART_COLORS } from '@/constants.js'; 
import { useLayout } from '@/layout/composables/layout'; 

// --- Componentes PrimeVue ---
import Panel from 'primevue/panel';
import MultiSelect from 'primevue/multiselect';
import DatePicker from 'primevue/datepicker';
import Button from 'primevue/button';
import Chart from 'primevue/chart';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import ProgressSpinner from 'primevue/progressspinner';
import Tooltip from 'primevue/tooltip';
import Card from 'primevue/card';

// --- Diretivas ---
const vTooltip = Tooltip; 

// --- Estado ---
const isLoading = ref(false);
const isLoaded = ref(false);
const apiService = ApiService;
const rawData = ref(null);
const userMap = ref({});
const { isDarkTheme } = useLayout(); 

// --- Stats dos Cards ---
const statsCards = ref({
    total: 0,
    abertas: 0,
    concluidas: 0,
    atrasadas: 0
});

// =============================================
// MUDANÇA NO SCRIPT:
// Ref reativo para as linhas da tabela
// =============================================
const dataTableRows = ref(10); // Valor padrão da paginação

// --- Filtros ---
const filtros = reactive({
    datas: null,
    status: null,
    secretarias: null,
    servicos: null,
    vereadores: null 
});

// --- Opções dos Filtros ---
const opcoes = reactive({
    status: STATUS_CHOICES_REPORTS,
    secretarias: [],
    servicos: [],
    vereadores: [] 
});

// --- Dados dos Gráficos ---
const barSecretariaData = ref(null);
const doughnutData = ref(null);

// --- Opções dos Gráficos ---
const barOptions = ref(null);
const pieOptions = ref(null); 

const getStatusSeverity = (status) => {
    switch (status) {
        case 'AGUARDANDO_PROTOCOLO': return 'info';
        case 'PROTOCOLADO': return 'warning';
        case 'EM_EXECUCAO': return 'primary';
        case 'FINALIZADO': return 'success';
        case 'CANCELADO': return 'danger';
        case 'AGUARDANDO_TRANSFERENCIA': return 'warning';
        default: return 'secondary';
    }
};

// --- Métodos de Formatação ---
const formatarData = (data) => {
    if (!data) return null;
    const d = new Date(data);
    d.setMinutes(d.getMinutes() + d.getTimezoneOffset());
    return d.toISOString().split('T')[0];
};

const formatarParams = () => {
    const params = {};
    if (filtros.datas && filtros.datas[0]) {
        params.data_inicio = formatarData(filtros.datas[0]);
    }
    if (filtros.datas && filtros.datas[1]) {
        let dataFim = new Date(filtros.datas[1]);
        dataFim.setDate(dataFim.getDate() + 1); 
        params.data_fim = formatarData(dataFim);
    }
    if (filtros.status && filtros.status.length > 0) {
        params.status__in = filtros.status.join(',');
    }
    if (filtros.secretarias && filtros.secretarias.length > 0) {
        params.secretaria__in = filtros.secretarias.join(',');
    }
    if (filtros.servicos && filtros.servicos.length > 0) {
        params.servico__in = filtros.servicos.join(',');
    }
    if (filtros.vereadores && filtros.vereadores.length > 0) {
        params.vereador__in = filtros.vereadores.join(',');
    }
    return params;
};

// --- Formatação de Gráficos (sem mudanças) ---

const formatarChartStatus = (data) => {
    const documentStyle = getComputedStyle(document.body);
    const labels = data.map(item => item.status);
    const totais = data.map(item => item.total);

    return {
        labels: labels,
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
    const labels = data.map(item => item.secretaria); 

    return {
        labels: labels,
        datasets: [
            { 
                label: 'Abertas', 
                backgroundColor: documentStyle.getPropertyValue('--p-purple-500'), 
                data: data.map(item => item.abertas) 
            },
            { 
                label: 'Concluídas', 
                backgroundColor: documentStyle.getPropertyValue('--p-teal-500'), 
                data: data.map(item => item.total - item.abertas) 
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
        plugins: { 
            legend: { 
                labels: { color: textColor, usePointStyle: true } 
            } 
        } 
    };
}


// --- Métodos de Busca (sem mudanças, usando getReportKPIs) ---
const carregarOpcoesFiltros = async () => {
    try {
        const [respSecretarias, respServicos, respVereadores] = await Promise.all([
            apiService.getSecretarias(),
            apiService.getServicos(),
            apiService.getUsuarios({ perfil: 'VEREADOR' }) 
        ]);
        const extrairDados = (response) => response.data.results || response.data;
        opcoes.secretarias = extrairDados(respSecretarias);
        opcoes.servicos = extrairDados(respServicos);
        const vereadoresData = extrairDados(respVereadores);
        opcoes.vereadores = vereadoresData.map(user => ({
            ...user,
            nome_formatado: (`${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username)
        }));
    } catch (error) {
        console.error("Erro ao carregar opções dos filtros:", error);
    }
};

const buscarRelatorios = async () => {
    isLoading.value = true;
    isLoaded.value = true;
    rawData.value = [];
    userMap.value = {};

    const params = formatarParams();
    console.log("1. Buscando relatórios com params:", params); 

    try {
        const [respKPIs, respStatus, respSecretaria, respHeatmap, respDemandas] = await Promise.all([
            apiService.getReportKPIs(params),
            apiService.getReportPorStatus(params),
            apiService.getReportPorSecretaria(params),
            apiService.getReportHeatmap(params),
            apiService.getReportDemandasList(params) 
        ]);

        statsCards.value = {
            total: respKPIs.data.total_demandas || 0,
            abertas: respKPIs.data.demandas_abertas || 0,
            concluidas: respKPIs.data.demandas_concluidas || 0,
            atrasadas: respKPIs.data.demandas_atrasadas || 0
        };

        console.log("2. Resposta Demandas:", respDemandas.data);

        doughnutData.value = formatarChartStatus(respStatus.data);
        barSecretariaData.value = formatarChartSecretaria(respSecretaria.data);

        const demandasData = respDemandas.data.results || respDemandas.data;

        if (demandasData && demandasData.length > 0) {
            rawData.value = demandasData; // Define os dados antes de buscar autores
            const autorIds = [...new Set(demandasData.map(d => d.criado_por_id).filter(id => id != null))];
            if (autorIds.length > 0) {
                try {
                    const respUsuarios = await apiService.getUsuarios({ id__in: autorIds.join(',') });
                    const usuariosData = respUsuarios.data.results || respUsuarios.data;
                    if (usuariosData && usuariosData.length > 0) { 
                        usuariosData.forEach(user => {
                            const nome = `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username;
                            userMap.value[user.id] = nome;
                        });
                    }
                } catch (userError) {
                    console.error("Erro ao buscar detalhes dos autores:", userError);
                }
            }
        } else {
            console.log("2.b Nenhuma demanda encontrada.");
        }
    } catch (error) {
        console.error("Erro ao buscar relatórios:", error);
    } finally {
        isLoading.value = false;
        console.log("7. Busca finalizada."); 
    }
};

const limparFiltros = () => {
    filtros.datas = null;
    filtros.status = null;
    filtros.secretarias = null;
    filtros.servicos = null;
    filtros.vereadores = null; 
    buscarRelatorios();
};


// =============================================
// MUDANÇAS NO SCRIPT:
// Lógica de impressão movida para cá
// =============================================

const imprimirPagina = async () => {
    // 1. Define para mostrar todas as linhas
    if (rawData.value && rawData.value.length > 0) {
        dataTableRows.value = rawData.value.length; 
    }

    // 2. Espera o Vue atualizar o DOM
    await nextTick();

    // 3. Chama a impressão
    window.print();
};

const afterPrint = () => {
    // 4. Restaura a paginação após a impressão
    dataTableRows.value = 10;
};

// --- Lifecycle Hooks ---
onMounted(() => {
    setChartOptions(); 
    carregarOpcoesFiltros(); 
    buscarRelatorios();      

    // Só precisamos escutar o 'afterprint'
    window.addEventListener('afterprint', afterPrint);
});

onUnmounted(() => {
    // 3. Remove os listeners ao sair da página
    window.removeEventListener('beforeprint', beforePrint);
    window.removeEventListener('afterprint', afterPrint);
});

watch(isDarkTheme, setChartOptions); 
</script>

<style>
@media print {
    /* Esconde tudo que não deve ser impresso */
    body .layout-sidebar,
    body .layout-topbar,
    body .layout-footer,
    body .no-print,
    .p-paginator {
        display: none !important;
    }

    /* Força o conteúdo principal a ocupar 100% */
    body .layout-main-container {
        padding-top: 0 !important;
        margin-left: 0 !important;
        width: 100% !important;
        min-width: 100% !important;
    }

    /* Evita quebras de página ruins */
    .print-avoid-break {
        page-break-inside: avoid;
    }

    /* ============================================= */
    /* CORREÇÃO 2: Força o tema claro (não-dark)     */
    /* ============================================= */
    :root {
        /* Força variáveis de tema claro para os gráficos */
        --text-color: #495057 !important;
        --text-color-secondary: #6C757D !important;
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
        border: 1px solid #dee2e6; /* Borda leve para delimitar */
    }

    /* Força textos a serem escuros */
    h5, .font-semibold, .text-gray-500, .text-2xl, .text-lg, .text-xl {
        color: #000 !important;
    }
    /* ============================================= */
    
    /* Garante que as cores dos gráficos sejam impressas */
    * {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }

    /* ============================================= */
    /* CORREÇÃO 1: Imprimir na horizontal (paisagem) */
    /* ============================================= */
    @page {
        size: A4 landscape; /* Define para paisagem */
        margin: 1.5cm;
    }
    
    /* ============================================= */
    /* CORREÇÃO 4: Contadores na mesma linha         */
    /* ============================================= */
    .print-chart-grid {
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important; /* Força 2 colunas */
        gap: 1.5rem !important;
    }
    .print-chart-grid > * {
        grid-column: span 1 / span 1 !important; /* Cada filho ocupa 1 coluna */
    }
    .print-card-grid {
        display: grid !important;
        grid-template-columns: repeat(4, 1fr) !important; /* Força 4 colunas */
        gap: 1rem !important;
    }
    .print-card-grid > * {
        grid-column: span 1 / span 1 !important; /* Cada card ocupa 1 coluna */
    }
}
</style>

<style scoped>
.card {
    margin-bottom: 1rem;
}
</style>