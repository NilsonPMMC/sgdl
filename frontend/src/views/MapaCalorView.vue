<script setup>
import { onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService.js';
import { useUserStore } from '@/stores/userStore';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import 'leaflet.markercluster';

// Componentes para os filtros
import Select from 'primevue/select';
import DatePicker from 'primevue/datepicker';
import Button from 'primevue/button';
import AutoComplete from 'primevue/autocomplete';
import Panel from 'primevue/panel';
import Divider from 'primevue/divider';

const userStore = useUserStore();
const loading = ref(true);
const map = ref(null);
const markerClusterGroup = ref(null);

const filtros = ref({
    tipo_servico: null,
    servico: null,
    status: null,
    data_inicio: null,
    data_fim: null
});

const tiposServico = ref([
    { label: 'Todos os Tipos', value: null },
    { label: 'Serviço', value: 'SERVIÇO' },
    { label: 'Implantação', value: 'IMPLANTAÇÃO' },
    { label: 'Vistoria', value: 'VISTORIA' },
    { label: 'Evento', value: 'EVENTO' },
    { label: 'Atendimento', value: 'ATENDIMENTO' },
]);

const statusOptions = ref([
    { label: 'Todos os Status', value: null },
    { label: 'Aguardando Protocolo', value: 'AGUARDANDO_PROTOCOLO' },
    { label: 'Protocolado', value: 'PROTOCOLADO' },
    { label: 'Em Execução', value: 'EM_EXECUCAO' },
    { label: 'Aguardando Transferência', value: 'AGUARDANDO_TRANSFERENCIA' },
    { label: 'Finalizado', value: 'FINALIZADO' },
    { label: 'Cancelado', value: 'CANCELADO' }
]);


const todosServicos = ref([]);
const filteredServicos = ref([]);

const createColoredIcon = (color) => {
    return L.divIcon({
        className: `custom-div-icon`,
        html: `
            <div class="icon-wrapper bg-${color}">
                <i class="pi pi-map-marker text-white" style="font-size: 1.5rem;"></i>
            </div>
        `, 
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });
};

const icons = {
    verde: createColoredIcon('green'),
    azul: createColoredIcon('blue'),
    vermelho: createColoredIcon('red')
};

const formatarDataParaAPI = (data) => {
    if (!data) return null;
    // O DatePicker pode retornar uma string ou um objeto Date
    const d = new Date(data);
    // Converte para o fuso horário local para evitar problemas de "um dia a menos"
    d.setMinutes(d.getMinutes() + d.getTimezoneOffset());
    return d.toISOString().split('T')[0]; // Formato 'YYYY-MM-DD'
};

const carregarLocalizacoes = async () => {
    loading.value = true;
    try {
        const params = {
            tipo_servico: filtros.value.tipo_servico,
            servico_id: filtros.value.servico ? filtros.value.servico.id : null,
            status: filtros.value.status,
            data_inicio: formatarDataParaAPI(filtros.value.data_inicio),
            data_fim: formatarDataParaAPI(filtros.value.data_fim)
        };

        const currentUser = userStore.currentUser;
        if (currentUser && currentUser.perfil) {
            if (currentUser.perfil === 'VEREADOR') {
                params.autor = currentUser.id;
            } else if (currentUser.perfil === 'SECRETARIA') {
                params.secretaria_destino = currentUser.secretaria;
            }
        }
        
        Object.keys(params).forEach(key => (params[key] == null || params[key] === '') && delete params[key]);

        const response = await ApiService.getDemandaLocations(params);
        const locationsData = response.data;

        markerClusterGroup.value.clearLayers();

        if (locationsData.length > 0) {
            const markers = locationsData.map(loc => {
                let icon;
                if (loc.is_atrasada) {
                    icon = icons.vermelho;
                } else if (loc.status === 'FINALIZADO') {
                    icon = icons.verde;
                } else {
                    icon = icons.azul;
                }
                
                const marker = L.marker([parseFloat(loc.lat), parseFloat(loc.lng)], { icon });
                marker.options.customData = { status: loc.status, is_atrasada: loc.is_atrasada };

                marker.bindPopup(`<b>${loc.protocolo || 'Rascunho'}</b><br>${loc.titulo}<br><a href="/demandas/detalhes/${loc.id}" target="_blank">Ver detalhes</a>`);
                return marker;
            });
            markerClusterGroup.value.addLayers(markers);
        }
    } catch (error) {
        console.error("Erro ao carregar localizações:", error);
    } finally {
        loading.value = false;
    }
};

onMounted(() => {
    map.value = L.map('map-container').setView([-23.523, -46.18], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(map.value);

    markerClusterGroup.value = L.markerClusterGroup({
        iconCreateFunction: function (cluster) {
            const markers = cluster.getAllChildMarkers();
            let atrasadas = 0;
            let concluidas = 0;
            
            markers.forEach(marker => {
                if (marker.options.customData.is_atrasada) {
                    atrasadas++;
                } else if (marker.options.customData.status === 'FINALIZADO') {
                    concluidas++;
                }
            });

            // Lógica de cores do cluster
            let cssClass = 'marker-cluster-';
            if (atrasadas > 0) {
                cssClass += 'red'; // Se tem qualquer uma atrasada, o cluster fica vermelho
            } else if (concluidas === markers.length) {
                cssClass += 'green'; // Se todas estão concluídas, fica verde
            } else {
                cssClass += 'blue'; // Caso contrário, azul (em andamento, no prazo)
            }
            
            return L.divIcon({
                html: '<div><span>' + cluster.getChildCount() + '</span></div>',
                className: 'marker-cluster ' + cssClass,
                iconSize: new L.Point(40, 40)
            });
        }
    });
    map.value.addLayer(markerClusterGroup.value);

    carregarLocalizacoes();

    ApiService.getServicos().then(response => {
        todosServicos.value = response.data;
    }).catch(error => {
        console.error("Erro ao buscar lista de serviços:", error);
    });
});

// Função de busca para o AutoComplete de serviço
const searchServico = (event) => {
    let baseList = todosServicos.value;
    if (filtros.value.tipo_servico) {
        baseList = baseList.filter(s => s.tipo === filtros.value.tipo_servico);
    }
    const query = event.query.trim().toLowerCase();
    if (!query.length) {
        filteredServicos.value = [...baseList];
    } else {
        filteredServicos.value = baseList.filter((servico) => {
            return servico.nome.toLowerCase().includes(query);
        });
    }
};
</script>

<template>
    <div class="card">
        <h5>Mapa de Calor das Demandas</h5>
        <Panel class="mb-3" header="Filtrar" toggleable>
            <div class="flex flex-wrap gap-4 mb-3">
                <div class="flex flex-col grow basis-0 gap-2">
                    <label for="tipo">Tipo de Serviço</label>
                    <Select 
                        id="tipo" 
                        v-model="filtros.tipo_servico" 
                        :options="tiposServico" 
                        optionLabel="label" 
                        optionValue="value" 
                        @change="filtros.servico = null" 
                    />
                </div>

                <div class="flex flex-col grow basis-0 gap-2">
                    <label for="servico">Serviço Específico</label>
                    <AutoComplete 
                        id="servico"
                        v-model="filtros.servico" 
                        :suggestions="filteredServicos" 
                        @complete="searchServico" 
                        optionLabel="nome"
                        forceSelection
                        placeholder="Digite para filtrar"
                        dropdown
                    />
                </div>
            </div>

            <div class="flex flex-wrap gap-4 mb-3">
                <div class="flex flex-col grow basis-0 gap-2">
                    <label for="status">Status</label>
                    <Select id="status" v-model="filtros.status" :options="statusOptions" optionLabel="label" optionValue="value" />
                </div>

                <div class="flex flex-col grow basis-0 gap-2">
                    <label for="data_inicio">De</label>
                    <DatePicker id="data_inicio" v-model="filtros.data_inicio" dateFormat="yy-mm-dd" />
                </div>

                <div class="flex flex-col grow basis-0 gap-2">
                    <label for="data_fim">Até</label>
                    <DatePicker id="data_fim" v-model="filtros.data_fim" dateFormat="yy-mm-dd" />
                </div>
            </div>
            
            <Button label="Filtrar" icon="pi pi-filter" @click="carregarLocalizacoes" />
        </Panel>
        
        <div v-if="loading" class="text-center">
             </div>
        <div id="map-container" style="height: 60vh"></div>
    </div>
</template>

<style lang="scss">
/* Estilos para os ícones de marcadores individuais */

/* 1. O Contêiner Externo (Controlado pelo Leaflet) */
/* (A rotação foi REMOVIDA daqui) */
.custom-div-icon {  
    display: flex;
    align-items: center;
    justify-content: center;
}

/* 2. O Wrapper Interno (Novo) */
/* (A rotação de -45deg foi MOVIDA para cá) */
.icon-wrapper {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.4);
    border-radius: 50% 50% 50% 0;

    /* Rotação do ícone inteiro (forma de gota) */
    transform: rotate(-45deg); 
}

/* 3. O ícone <i> (como você já tinha) */
/* (Esta regra "des-rotaciona" o ícone para ele ficar reto) */
.custom-div-icon .icon-wrapper i {
    transform: rotate(45deg);
}


/* Cores para os clusters - herdadas do MarkerCluster.Default.css mas com cores diferentes */
.marker-cluster-red { background-color: rgba(239, 68, 68, 0.6); }
.marker-cluster-red div { background-color: rgba(239, 68, 68, 0.8); }

.marker-cluster-green { background-color: rgba(34, 197, 94, 0.6); }
.marker-cluster-green div { background-color: rgba(34, 197, 94, 0.8); }

.marker-cluster-blue { background-color: rgba(59, 130, 246, 0.6); }
.marker-cluster-blue div { background-color: rgba(59, 130, 246, 0.8); }

/* Cores de fundo (já estavam corretas) */
.bg-red {
    background-color: rgb(239, 68, 68) !important; 
}
.bg-green {
    background-color: rgb(34, 197, 94) !important;
}
.bg-blue { 
    background-color: rgb(59, 130, 246) !important;
}
</style>