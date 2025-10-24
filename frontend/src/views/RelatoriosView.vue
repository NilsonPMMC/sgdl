<template>
    <div class="card">
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

    <div v-if="isLoading" class="text-center p-5">
        <ProgressSpinner />
        <p>Buscando dados...</p>
    </div>

    <div v-if="!isLoading && isLoaded" class="grid grid-cols-12 gap-8">
        
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

        <div class="col-span-12">
            <div class="font-semibold text-xl mb-4">Dados das Demandas Filtradas</div>
            <DataTable :value="rawData" :rows="10" paginator responsiveLayout="scroll"
                :loading="isLoading" dataKey="id">

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
</template>

<script setup>
import { ref, onMounted, reactive, watch } from 'vue'; 
import ApiService from '@/service/ApiService.js';
import { STATUS_CHOICES_REPORTS, CHART_COLORS } from '@/constants.js'; 
import { useLayout } from '@/layout/composables/layout'; 

import Panel from 'primevue/panel';
import MultiSelect from 'primevue/multiselect';
import DatePicker from 'primevue/datepicker';
import Button from 'primevue/button';
import Chart from 'primevue/chart';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';

// --- Estado ---
const isLoading = ref(false);
const isLoaded = ref(false);
const apiService = ApiService;
const rawData = ref(null);
const userMap = ref({});
const { isDarkTheme } = useLayout(); 

// --- Filtros ---
const filtros = reactive({
    datas: null,
    status: null,
    secretarias: null,
    servicos: null,
    vereadores: null 
});

// --- Opções dos Filtros (para os MultiSelect) ---
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
        case 'ABERTA': return 'info';
        case 'PROTOCOLADA': return 'warning';
        case 'EM_EXECUCAO': return 'primary';
        case 'CONCLUIDA': return 'success';
        case 'REJEITADA': return 'danger';
        default: return 'secondary';
    }
};

// --- Métodos de Formatação ---
const formatarData = (data) => {
    if (!data) return null;
    return data.toISOString().split('T')[0];
};

const formatarParams = () => {
    const params = {};
    if (filtros.datas && filtros.datas[0]) {
        params.data_inicio = formatarData(filtros.datas[0]);
    }
    if (filtros.datas && filtros.datas[1]) {
        params.data_fim = formatarData(filtros.datas[1]);
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

// --- Métodos de Formatação de Gráficos (API -> Chart.js) ---

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

// ATUALIZADO: Funcao para formatar o grafico de secretaria (agora com empilhamento correto)
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

// ATUALIZADO: Funcao 'setChartOptions' com stacked: true para os eixos x e y
function setChartOptions() {
    const documentStyle = getComputedStyle(document.documentElement);
    const textColor = documentStyle.getPropertyValue('--text-color');
    const textColorSecondary = documentStyle.getPropertyValue('--text-color-secondary');
    const surfaceBorder = documentStyle.getPropertyValue('--surface-border');
    
    barOptions.value = {
        plugins: { 
            legend: { 
                labels: { color: textColor } 
            } 
        },
        scales: {
            // ATUALIZADO: stacked: true para ambos os eixos para o empilhamento total
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


// --- Métodos de Busca ---
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
        const [respStatus, respSecretaria, respHeatmap, respDemandas] = await Promise.all([
            apiService.getReportPorStatus(params),
            apiService.getReportPorSecretaria(params),
            apiService.getReportHeatmap(params),
            apiService.getReportDemandasList(params) 
        ]);

        console.log("2. Resposta Demandas:", respDemandas.data);

        doughnutData.value = formatarChartStatus(respStatus.data);
        // ATUALIZADO: Chamando a função para o gráfico de secretaria empilhado
        barSecretariaData.value = formatarChartSecretaria(respSecretaria.data);

        const demandasData = respDemandas.data.results || respDemandas.data;

        if (demandasData && demandasData.length > 0) {
            const autorIds = [...new Set(demandasData.map(d => d.criado_por_id).filter(id => id != null))];
            console.log("3. IDs de Autores encontrados:", autorIds); 
            if (autorIds.length > 0) {
                try {
                    console.log("4. Buscando detalhes para IDs:", autorIds.join(',')); 
                    const respUsuarios = await apiService.getUsuarios({ id__in: autorIds.join(',') });
                    console.log("5. Resposta Usuarios:", respUsuarios.data); 
                    const usuariosData = respUsuarios.data.results || respUsuarios.data;
                    if (usuariosData && usuariosData.length > 0) { 
                        usuariosData.forEach(user => {
                            const nome = `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username;
                            userMap.value[user.id] = nome;
                        });
                        console.log("6. Mapa de Usuários criado:", userMap.value); 
                    } else {
                        console.log("6. Nenhum dado de usuário retornado pela API."); 
                    }
                } catch (userError) {
                    console.error("Erro ao buscar detalhes dos autores:", userError);
                    console.log("6. Falha ao buscar usuários."); 
                }
            } else {
                console.log("3b. Nenhum ID de autor válido para buscar."); 
            }
            rawData.value = demandasData;
        } else {
            console.log("2b. Nenhuma demanda encontrada."); 
        }
    } catch (error) {
        console.error("Erro ao buscar relatórios:", error);
    } finally {
        isLoading.value = false;
        console.log("7. Busca finalizada. rawData:", rawData.value); 
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


// --- Lifecycle Hooks ---
onMounted(() => {
    setChartOptions(); 
    carregarOpcoesFiltros(); 
    buscarRelatorios();      
});

watch(isDarkTheme, setChartOptions); 
</script>

<style scoped>
/* Adiciona um pouco de espaço entre os cards de filtro e gráficos */
.card {
    margin-bottom: 1rem;
}
</style>