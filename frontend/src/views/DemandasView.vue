<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from "primevue/useconfirm";
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService.js';

import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import Toolbar from 'primevue/toolbar';
import Tag from 'primevue/tag';
import Dialog from 'primevue/dialog';
import Select from 'primevue/select';
import InputText from 'primevue/inputtext';
import Panel from 'primevue/panel';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';

const demandas = ref([]);
const router = useRouter();
const toast = useToast();
const confirm = useConfirm();
const userStore = useUserStore();
const loading = ref(true);

const despachoDialog = ref(false);
const demandaParaDespacho = ref(null);
const todasSecretarias = ref([]);

const aprovacaoDialog = ref(false);
const demandaParaAprovacao = ref(null);
const novaSecretariaId = ref(null);
const secretariaDestinoId = ref(null);
const todosVereadores = ref([]);

const filtros = ref({
    q: null,
    status: null,
    secretaria_destino: null,
    autor: null
});

const statusAbertos = ['AGUARDANDO_PROTOCOLO', 'PROTOCOLADO', 'EM_EXECUCAO', 'AGUARDANDO_TRANSFERENCIA'];

// Helper function para verificar se uma *única* demanda está atrasada
const isAtrasada = (demanda) => {
    const hoje = new Date();
    // Clona a data de hoje e subtrai 30 dias para definir o limite
    const limite = new Date(new Date().setDate(hoje.getDate() - 30)); 
    const dataCriacao = new Date(demanda.data_criacao);
    
    // Está atrasada se a data de criação for anterior ao limite E o status ainda estiver aberto
    return dataCriacao < limite && statusAbertos.includes(demanda.status);
};

const totalAbertos = computed(() => {
    return demandas.value.filter(d => statusAbertos.includes(d.status)).length;
});

const totalFinalizados = computed(() => {
    return demandas.value.filter(d => d.status === 'FINALIZADO').length;
});

const totalAtrasados = computed(() => {
    // Reutiliza a função helper
    return demandas.value.filter(isAtrasada).length; 
});

const statusOptions = ref([
    { label: 'Todos os Status', value: null },
    { label: 'Aguardando Protocolo', value: 'AGUARDANDO_PROTOCOLO' },
    { label: 'Protocolado', value: 'PROTOCOLADO' },
    { label: 'Em Execução', value: 'EM_EXECUCAO' },
    { label: 'Aguardando Transferência', value: 'AGUARDANDO_TRANSFERENCIA'},
    { label: 'Finalizado', value: 'FINALIZADO' },
    { label: 'Cancelado', value: 'CANCELADO' }
]);

const isGestorOuProtocolo = computed(() => ['GESTOR', 'PROTOCOLO'].includes(userStore.currentUser?.perfil));
const showVereadorFilter = computed(() => ['GESTOR', 'PROTOCOLO', 'SECRETARIA'].includes(userStore.currentUser?.perfil));

const getStatusSeverity = (demanda) => {
    // 1. Verifica o atraso PRIMEIRO
    if (isAtrasada(demanda)) {
        return 'danger'; // Vermelho para atrasados
    }
    
    // 2. Se não estiver atrasado, usa a lógica de status normal
    const map = {
        'RASCUNHO': 'info',
        'AGUARDANDO_PROTOCOLO': 'warn',
        'PROTOCOLADO': 'primary',
        'EM_EXECUCAO': 'success',
        'FINALIZADO': 'success',
        'CANCELADO': 'danger',
        'AGUARDANDO_TRANSFERENCIA': 'warning'
    };
    return map[demanda.status] || 'contrast';
};

async function carregarDemandas() {
    loading.value = true;
    try {
        // Começa com os filtros da UI
        let params = { ...filtros.value };

        const currentUser = userStore.currentUser;
        if (!currentUser?.id) { loading.value = false; return; }

        // Adiciona os filtros de permissão do perfil
        switch (currentUser.perfil) {
            case 'VEREADOR': 
                params.autor = currentUser.id; // Sobrescreve qualquer filtro de autor
                break;
            case 'SECRETARIA':
                if (currentUser.secretaria) {
                    params.secretaria_destino = currentUser.secretaria; // Sobrescreve
                    params.status__in = ['PROTOCOLADO', 'EM_EXECUCAO', 'FINALIZADO', 'AGUARDANDO_TRANSFERENCIA'].join(',');
                }
                break;
            case 'GESTOR':
            case 'PROTOCOLO':
                params.status__exclude = 'RASCUNHO';
                break;
        }
        
        // Limpa parâmetros nulos antes de enviar
        Object.keys(params).forEach(key => (params[key] == null || params[key] === '') && delete params[key]);

        const response = await ApiService.getDemandas(params);
        demandas.value = response.data.results || response.data;
    } catch (error) {
        console.error('Erro ao buscar demandas:', error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao carregar demandas.', life: 3000 });
    } finally {
        loading.value = false;
    }
}

const limparFiltros = () => {
    filtros.value = { q: null, status: null, secretaria_destino: null, autor: null };
    carregarDemandas();
};

onMounted(() => {
    carregarDemandas();
    ApiService.getSecretarias().then(response => {
        todasSecretarias.value = response.data;
    });
    if (showVereadorFilter.value) {
        ApiService.getUsuarios({ perfil: 'VEREADOR' }).then(response => {
            todosVereadores.value = response.data;
        });
    }
});

const editarDemanda = (id) => router.push(`/demandas/editar/${id}`);
const visualizarDemanda = (id) => router.push(`/demandas/detalhes/${id}`);

const excluirDemanda = (id) => {
    confirm.require({
        message: 'Você tem certeza que quer excluir este rascunho?',
        header: 'Confirmação de Exclusão',
        icon: 'pi pi-exclamation-triangle',
        accept: async () => {
            try {
                await ApiService.deleteDemanda(id);
                toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Rascunho excluído.', life: 3000 });
                carregarDemandas();
            } catch (error) {
                toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível excluir o rascunho.', life: 3000 });
            }
        }
    });
};

const despachoData = ref({
    secretaria_id: null,
    numero_externo: '',
    link_externo: ''
});

const abrirDialogoDespacho = (demanda) => {
    demandaParaDespacho.value = demanda;
    
    despachoData.value = {
        secretaria_id: demanda.servico?.secretaria_responsavel?.id || null,
        numero_externo: '', 
        link_externo: ''
    };
    
    despachoDialog.value = true;
};

const confirmarDespacho = async () => {
    if (!despachoData.value.secretaria_id) {
        toast.add({ severity: 'warn', summary: 'Atenção', detail: 'Por favor, selecione uma secretaria.', life: 3000 });
        return;
    }
    
    try {
        await ApiService.despacharDemanda(demandaParaDespacho.value.id, despachoData.value);
        
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Demanda despachada.', life: 3000 });
        despachoDialog.value = false;
        carregarDemandas();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível despachar.', life: 3000 });
    }
};

const abrirDialogoAprovarTransferencia = (demanda) => {
    demandaParaAprovacao.value = demanda;
    novaSecretariaId.value = null;
    aprovacaoDialog.value = true;
};

const confirmarAprovacaoTransferencia = async () => {
    if (!novaSecretariaId.value) return;
    try {
        await ApiService.aprovarTransferencia(demandaParaAprovacao.value.id, novaSecretariaId.value);
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Transferência aprovada!', life: 3000 });
        aprovacaoDialog.value = false;
        carregarDemandas();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível aprovar a transferência.', life: 3000 });
    }
};
</script>

<template>
  <div class="grid">
    <div class="col-12">
      <div class="card">
        <Toolbar class="mb-4">
          <template #start>
            <h5 class="m-0">Gestão de Demandas</h5>
          </template>
          <template #end>
            <Button v-if="userStore.currentUser?.perfil === 'VEREADOR'" label="Novo Ofício" icon="pi pi-plus" class="p-button-success mr-2" @click="router.push('/demandas/novo')" />
          </template>
        </Toolbar>

        <div class="grid grid-cols-12 gap-8 mb-4">
            <Panel class="col-span-12 lg:col-span-6 xl:col-span-4">
                <div class="flex justify-between mb-4">
                    <div>
                        <span class="block text-muted-color font-medium mb-4">Em Aberto</span>
                        <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ totalAbertos }}</div>
                    </div>
                    <div class="flex items-center justify-center bg-blue-100 rounded-border" style="width:2.5rem;height:2.5rem">
                        <i class="pi pi-sync text-blue-500 text-xl"></i>
                    </div>
                </div>
            </Panel>
            <Panel class="col-span-12 lg:col-span-6 xl:col-span-4">
                <div class="flex justify-between mb-4">
                    <div>
                        <span class="block text-muted-color font-medium mb-4">Finalizadas</span>
                        <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ totalFinalizados }}</div>
                    </div>
                    <div class="flex items-center justify-center bg-green-100 rounded-border" style="width:2.5rem;height:2.5rem">
                        <i class="pi pi-check-square text-green-500 text-xl"></i>
                    </div>
                </div>
            </Panel>
            <Panel class="col-span-12 lg:col-span-6 xl:col-span-4">
                <div class="flex justify-between mb-4">
                    <div>
                        <span class="block text-muted-color font-medium mb-4">Atrasadas</span>
                        <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ totalAtrasados }}</div>
                    </div>
                    <div class="flex items-center justify-center bg-red-100 rounded-border" style="width:2.5rem;height:2.5rem">
                        <i class="pi pi-clock text-red-500 text-xl"></i>
                    </div>
                </div>
            </Panel>
        </div>

        <Panel class="mb-4" header="Filtros de Busca" toggleable>
                <IconField class="mb-3">
                    <InputIcon class="pi pi-search" />
                    <InputText id="buscaGeral" v-model="filtros.q" placeholder="Ofício, Protocolo ou Título" fluid />
                </IconField>

                <div class="flex flex-col md:flex-row gap-4 mb-3">
                    <div class="flex flex-col gap-2 w-full">
                        <label for="status">Status</label>
                        <Select id="status" v-model="filtros.status" :options="statusOptions" optionLabel="label" optionValue="value" placeholder="Selecione" />
                    </div>
                    <div v-if="userStore.currentUser?.perfil !== 'SECRETARIA'" class="flex flex-col gap-2 w-full">
                        <label for="secretaria">Secretaria</label>
                        <Select id="secretaria" v-model="filtros.secretaria_destino" :options="todasSecretarias" optionLabel="nome" optionValue="id" placeholder="Selecione" />
                    </div>
                    <div v-if="showVereadorFilter" class="flex flex-col gap-2 w-full">
                        <label for="vereador">Vereador</label>
                        <Select id="vereador" v-model="filtros.autor" :options="todosVereadores" optionLabel="first_name" optionValue="id" placeholder="Selecione" />
                    </div>
                </div>

                <Button label="Filtrar" class="mr-3" icon="pi pi-filter" @click="carregarDemandas" />
                <Button label="Limpar" icon="pi pi-times" @click="limparFiltros" class="p-button-outlined" />
        </Panel>

        <DataTable :value="demandas" 
                   :loading="loading" 
                   responsiveLayout="scroll"
                   paginator :rows="10" :rowsPerPageOptions="[5, 10, 20, 50]"
        >
          <Column field="protocolo_legislativo" header="Ofício" :sortable="true"></Column>
          <Column field="protocolo_executivo" header="Protocolo" :sortable="true"></Column>
          <Column field="data_criacao" header="Criado em" :sortable="true">
            <template #body="{ data }">
                {{ new Date(data.data_criacao).toLocaleDateString('pt-BR') }}
            </template>
          </Column>
          <Column field="titulo" header="Título" :sortable="true"></Column>
          <Column field="status" header="Status" :sortable="true">
            <template #body="{ data }">
                <Tag :value="isAtrasada(data) ? 'ATRASADO' : data.status_display" :severity="getStatusSeverity(data)" />
            </template>
          </Column>
          <Column field="secretaria_destino.nome" header="Secretaria Destino"></Column>
          <Column field="autor.first_name" header="Autor"></Column>
          
          <Column header="Ações" style="min-width: 10rem">
            <template #body="slotProps">
              <Button v-if="userStore.currentUser?.perfil === 'VEREADOR' && slotProps.data.status === 'RASCUNHO'" icon="pi pi-pencil" text rounded @click="editarDemanda(slotProps.data.id)" v-tooltip.top="'Editar'"/>
              <Button v-if="userStore.currentUser?.perfil === 'VEREADOR' && slotProps.data.status === 'RASCUNHO'" icon="pi pi-trash" severity="danger" text rounded @click="excluirDemanda(slotProps.data.id)" v-tooltip.top="'Excluir'"/>
              
              <Button v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && slotProps.data.status === 'AGUARDANDO_PROTOCOLO'" icon="pi pi-send" severity="success" text rounded @click="abrirDialogoDespacho(slotProps.data)" v-tooltip.top="'Despachar'"/>
              <Button v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && slotProps.data.status === 'AGUARDANDO_TRANSFERENCIA'" icon="pi pi-check-circle" severity="warning" text rounded @click="abrirDialogoAprovarTransferencia(slotProps.data)" v-tooltip.top="'Revisar Transferência'"/>

              <Button v-if="slotProps.data.status !== 'RASCUNHO'" icon="pi pi-eye" severity="secondary" text rounded @click="visualizarDemanda(slotProps.data.id)" v-tooltip.top="'Visualizar'"/>
            </template>
          </Column>
        </DataTable>

        <Dialog v-model:visible="despachoDialog" header="Despachar Demanda" :modal="true" style="width: 450px;">
            <div class="flex flex-col gap-4">
                <div>
                    <label for="secretaria" class="block mb-3">Enviar para a Secretaria</label>
                    <Select id="secretaria" 
                            v-model="despachoData.secretaria_id" 
                            :options="todasSecretarias" 
                            optionLabel="nome" 
                            optionValue="id" 
                            placeholder="Selecione uma secretaria" 
                            fluid />
                </div>

                <div>
                    <label for="num_externo" class="block mb-3">Referência Externa (Opcional)</label>
                    <InputText id="num_externo" 
                            v-model="despachoData.numero_externo" 
                            placeholder="Ex: 1Doc 1234/2025 ou SEI..." fluid />
                </div>

                <div>
                    <label for="link_externo" class="block mb-3">Link Externo (Opcional)</label>
                    <InputText id="link_externo" 
                            v-model="despachoData.link_externo" 
                            placeholder="http://..." fluid />
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="despachoDialog = false" />
                <Button label="Confirmar Despacho" icon="pi pi-check" @click="confirmarDespacho" />
            </template>
        </Dialog>

        <Dialog v-model:visible="aprovacaoDialog" header="Aprovar Transferência" :modal="true" style="width: 450px;">
            <div v-if="demandaParaAprovacao">
                <p class="mb-4">A secretaria <strong>{{ demandaParaAprovacao.secretaria_destino?.nome }}</strong> solicitou a transferência. Selecione a nova secretaria.</p>
                <div class="field">
                    <label for="novaSecretaria" class="block mb-3">Nova Secretaria de Destino</label>
                    <Select id="novaSecretaria" v-model="novaSecretariaId" :options="todasSecretarias" optionLabel="nome" optionValue="id" placeholder="Selecione a nova secretaria" fluid />
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="aprovacaoDialog = false" />
                <Button label="Confirmar Transferência" icon="pi pi-check" severity="warning" @click="confirmarAprovacaoTransferencia" />
            </template>
        </Dialog>

      </div>
    </div>
  </div>
</template>