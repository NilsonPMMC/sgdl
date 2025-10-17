<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from "primevue/useconfirm";
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService.js';

import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import Toolbar from 'primevue/toolbar';
import Dialog from 'primevue/dialog';
import Select from 'primevue/select';

const demandas = ref([]);
const router = useRouter();
const toast = useToast();
const confirm = useConfirm();
const userStore = useUserStore();
const loading = ref(true);

const despachoDialog = ref(false);
const demandaParaDespacho = ref(null);
const secretariaDestinoId = ref(null);
const todasSecretarias = ref([]);

async function carregarDemandas() {
    loading.value = true;
    try {
        let params = {};
        const currentUser = userStore.currentUser;
        if (!currentUser?.id) {
            loading.value = false;
            return;
        }
        switch (currentUser.perfil) {
            case 'VEREADOR': params.autor = currentUser.id; break;
            case 'PROTOCOLO': params.status__exclude = 'RASCUNHO'; break;
            case 'SECRETARIA':
                if (currentUser.secretaria) {
                    params.secretaria_destino = currentUser.secretaria;
                    params.status__in = ['PROTOCOLADO', 'EM_EXECUCAO', 'FINALIZADO'].join(',');
                }
                break;
            case 'GESTOR': params.status__exclude = 'RASCUNHO'; break;
            default: demandas.value = []; return;
        }
        const response = await ApiService.getDemandas(params);
        demandas.value = response.data;
    } catch (error) {
        console.error('Erro ao buscar demandas:', error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao carregar demandas.', life: 3000 });
    } finally {
        loading.value = false;
    }
}

onMounted(() => {
    carregarDemandas();

    if (userStore.currentUser?.perfil === 'PROTOCOLO') {
        ApiService.getSecretarias().then(response => {
            todasSecretarias.value = response.data;
        });
    }
});

const editarDemanda = (id) => {
    router.push(`/demandas/editar/${id}`);
};

const visualizarDemanda = (id) => {
    router.push(`/demandas/detalhes/${id}`);
};

const excluirDemanda = (id) => {
    confirm.require({
        message: 'Você tem certeza que quer excluir este rascunho? Esta ação não pode ser desfeita.',
        header: 'Confirmação de Exclusão',
        icon: 'pi pi-exclamation-triangle',
        acceptLabel: 'Sim, excluir',
        rejectLabel: 'Cancelar',
        accept: async () => {
            try {
                await ApiService.deleteDemanda(id);
                toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Rascunho excluído.', life: 3000 });
                carregarDemandas(); // Recarrega a lista para remover o item excluído
            } catch (error) {
                toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível excluir o rascunho.', life: 3000 });
            }
        }
    });
};

const abrirDialogoDespacho = (demanda) => {
    console.log('Dados da Demanda para despacho:', demanda);
    
    demandaParaDespacho.value = demanda;
    secretariaDestinoId.value = demanda.servico?.secretaria_responsavel?.id || null;
    despachoDialog.value = true;
};

const confirmarDespacho = async () => {
    if (!secretariaDestinoId.value) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Selecione uma secretaria.', life: 3000 });
        return;
    }
    try {
        await ApiService.despacharDemanda(demandaParaDespacho.value.id, secretariaDestinoId.value);
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Demanda despachada.', life: 3000 });
        despachoDialog.value = false;
        carregarDemandas(); // Recarrega a lista
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível despachar.', life: 3000 });
    }
};

const iniciarExecucao = async (id) => {
    try {
        await ApiService.updateDemanda(id, { status: 'EM_EXECUCAO' }); // Exemplo de como poderia ser
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Execução da demanda iniciada.', life: 3000 });
        carregarDemandas();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível iniciar a demanda.', life: 3000 });
    }
};

const finalizarDemanda = (id) => {
    confirm.require({
        message: 'Você tem certeza que deseja finalizar a execução desta demanda?',
        header: 'Confirmar Finalização',
        icon: 'pi pi-check-circle',
        acceptClass: 'p-button-success',
        acceptLabel: 'Sim, finalizar',
        rejectLabel: 'Cancelar',
        accept: async () => {
            try {
                await ApiService.updateDemanda(id, { status: 'FINALIZADO' }); // Exemplo de como poderia ser
                toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Demanda finalizada.', life: 3000 });
                carregarDemandas();
            } catch (error) {
                toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível finalizar a demanda.', life: 3000 });
            }
        }
    });
};
</script>

<template>
  <div class="grid">
    <div class="col-12">
      <div class="card">
        <Toolbar class="mb-4">
          <template #start>
            <div class="my-2">
              <h5 class="m-0">Gestão de Demandas</h5>
            </div>
          </template>
          <template #end>
            <Button v-if="userStore.currentUser?.perfil === 'VEREADOR'" label="Novo Ofício" icon="pi pi-plus" class="p-button-success mr-2" @click="router.push('/demandas/novo')" />
          </template>
        </Toolbar>

        <DataTable :value="demandas" :loading="loading" responsiveLayout="scroll">
          <Column v-if="userStore.currentUser?.perfil === 'VEREADOR' || userStore.currentUser?.perfil === 'PROTOCOLO'" field="protocolo_legislativo" header="Ofício" :sortable="true"></Column>
          <Column field="protocolo_executivo" header="Protocolo" :sortable="true"></Column>
          <Column field="titulo" header="Título" :sortable="true"></Column>
          <Column field="status" header="Status" :sortable="true"></Column>
          <Column field="autor.first_name" header="Autor"></Column>
          <Column field="data_criacao" header="Criado em" :sortable="true"></Column>
          <Column header="Ações" style="width: 10rem">
            <template #body="slotProps">
                <Button v-if="userStore.currentUser?.perfil === 'VEREADOR' && slotProps.data.status === 'RASCUNHO'" icon="pi pi-pencil" text rounded @click="editarDemanda(slotProps.data.id)" v-tooltip.top="'Editar'"/>
                <Button v-if="userStore.currentUser?.perfil === 'VEREADOR' && slotProps.data.status === 'RASCUNHO'" icon="pi pi-trash" severity="danger" text rounded @click="excluirDemanda(slotProps.data.id)" v-tooltip.top="'Excluir'"/>
                
                <Button v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && slotProps.data.status === 'AGUARDANDO_PROTOCOLO'" icon="pi pi-send" severity="success" text rounded @click="abrirDialogoDespacho(slotProps.data)" v-tooltip.top="'Despachar'"/>
                
                <Button v-if="userStore.currentUser?.perfil === 'SECRETARIA' && slotProps.data.status === 'PROTOCOLADO'" icon="pi pi-play" severity="success" text rounded @click="iniciarExecucao(slotProps.data.id)" v-tooltip.top="'Iniciar Execução'"/>
                <Button v-if="userStore.currentUser?.perfil === 'SECRETARIA' && slotProps.data.status === 'EM_EXECUCAO'" icon="pi pi-check-square" severity="success" text rounded @click="finalizarDemanda(slotProps.data.id)" v-tooltip.top="'Finalizar Demanda'"/>

                <Button v-if="slotProps.data.status !== 'RASCUNHO'" icon="pi pi-eye" severity="secondary" text rounded @click="visualizarDemanda(slotProps.data.id)" v-tooltip.top="'Visualizar'"/>
            </template>
        </Column>
        </DataTable>

        <Dialog v-model:visible="despachoDialog" header="Despachar Demanda" :modal="true" class="p-fluid" style="width: 450px;">
            <div class="field">
                <label class="block mb-3" for="secretaria">Enviar para a Secretaria</label>
                <Select id="secretaria" v-model="secretariaDestinoId" :options="todasSecretarias" optionLabel="nome" optionValue="id" placeholder="Selecione uma secretaria" fluid />
            </div>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="despachoDialog = false" />
                <Button label="Confirmar Despacho" icon="pi pi-check" @click="confirmarDespacho" />
            </template>
        </Dialog>
      </div>
    </div>
  </div>
</template>