<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ApiService from '@/service/ApiService.js';
import { useUserStore } from '@/stores/userStore';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from "primevue/useconfirm";

import Button from 'primevue/button';
import Tag from 'primevue/tag';
import ProgressSpinner from 'primevue/progressspinner';
import Editor from 'primevue/editor';
import Select from 'primevue/select';
import FileUpload from 'primevue/fileupload';
import Message from 'primevue/message';
import Divider from 'primevue/divider';
import Avatar from 'primevue/avatar';

const route = useRoute();
const router = useRouter();
const demanda = ref(null);
const loading = ref(true);
const userStore = useUserStore();
const toast = useToast();
const confirm = useConfirm();

const novaTramitacao = ref({
    tipo: null,
    descricao: '',
    anexos_arquivos: []
});

const dataCriacaoFormatada = computed(() => {
  if (demanda.value?.data_criacao) {
    // Formato mais detalhado se preferir
    return new Date(demanda.value.data_criacao).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
  return '';
});

const tiposTramitacao = ref([
    { label: 'Comentário', value: 'COMENTARIO' },
    { label: 'Análise Técnica', value: 'ANALISE_TECNICA' },
    { label: 'Atraso por Falta de Material', value: 'ATRASO_MATERIAL' },
    { label: 'Atraso por Outros Motivos', value: 'ATRASO_OUTROS' },
    { label: 'Programação do Serviço', value: 'PROGRAMACAO' },
    { label: 'Conclusão do Serviço', value: 'CONCLUSAO' },
]);

const isSecretaria = computed(() => {
    const perfilNome = userStore.currentUser?.perfil;
    if (!perfilNome || typeof perfilNome !== 'string') {
        return false;
    }
    return perfilNome.toUpperCase().trim() === 'SECRETARIA';
});

const podeAgirNaDemanda = computed(() => {
    if (!demanda.value || !userStore.currentUser) return false;
    const isOwner = demanda.value.secretaria_destino?.id === userStore.currentUser.secretaria;
    const isActionableStatus = ![
        'FINALIZADO',
        'CANCELADO',
        'AGUARDANDO_TRANSFERENCIA',
        'AGUARDANDO_PROTOCOLO',
        'RASCUNHO'
    ].includes(demanda.value.status);
    return isSecretaria.value && isOwner && isActionableStatus;
});

const iniciarExecucao = () => {
    confirm.require({
        message: 'Deseja alterar o status da demanda para "Em Execução"? Um registro será adicionado ao histórico.',
        header: 'Iniciar Execução',
        icon: 'pi pi-play',
        accept: async () => {
            try {
                await ApiService.atualizarStatusDemanda(demanda.value.id, 'EM_EXECUCAO');
                toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Execução iniciada.', life: 3000 });
                // Recarrega a demanda para refletir a mudança de status e a nova tramitação
                const response = await ApiService.getDemandaById(demanda.value.id);
                demanda.value = response.data;
            } catch (error) {
                toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível iniciar a execução.', life: 3000 });
            }
        }
    });
};

const timelineOrdenada = computed(() => {
    if (demanda.value && demanda.value.tramitacoes) {
        // Cria uma cópia rasa e a inverte, para não modificar o dado original
        return [...demanda.value.tramitacoes].reverse();
    }
    return [];
});

onMounted(async () => {
    const demandaId = route.params.id;
    if (demandaId) {
        try {
            const response = await ApiService.getDemandaById(demandaId);
            demanda.value = response.data;
        } catch (error) {
            console.error("Erro ao buscar detalhes da demanda:", error);
            toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível carregar os detalhes da demanda.', life: 3000 });
        } finally {
            loading.value = false;
        }
    } else {
        loading.value = false;
    }
});

const solicitarTransferencia = () => {
    confirm.require({
        message: 'Você tem certeza que deseja solicitar a transferência desta demanda para outra secretaria? A demanda ficará bloqueada até que o Protocolo analise o pedido.',
        header: 'Confirmar Solicitação',
        icon: 'pi pi-exchange',
        acceptLabel: 'Sim, solicitar',
        rejectLabel: 'Cancelar',
        accept: async () => {
            try {
                await ApiService.solicitarTransferencia(demanda.value.id);
                toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Solicitação de transferência enviada.', life: 3000 });
                const response = await ApiService.getDemandaById(demanda.value.id);
                demanda.value = response.data;
            } catch (error) {
                console.error("Erro ao solicitar transferência:", error);
                toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível solicitar a transferência.', life: 3000 });
            }
        }
    });
};

const getStatusSeverity = (status) => {
    const map = {
        'RASCUNHO': 'info',
        'AGUARDANDO_PROTOCOLO': 'warn',
        'PROTOCOLADO': 'primary',
        'EM_EXECUCAO': 'success',
        'FINALIZADO': 'success',
        'CANCELADO': 'danger',
        'AGUARDANDO_TRANSFERENCIA': 'warning'
    };
    return map[status] || 'contrast';
};

const getTramitacaoTagSeverity = (tipoDisplay) => {
    const map = {
        'Comentário': 'secondary',
        'Análise Técnica': 'warning',
        'Atraso por Falta de Material': 'danger',
        'Atraso por Outros Motivos': 'danger',
        'Programação do Serviço': 'info',
        'Transferência de Setor/Secretaria': 'primary',
        'Conclusão do Serviço': 'success',
        'Envio Oficial': 'info',
        'Despacho para Secretaria': 'primary',
        'Atualização de Status': 'success'
    };
    return map[tipoDisplay] || 'contrast';
};

const formatarData = (timestamp) => {
    if (!timestamp) return '';
    const data = new Date(timestamp);
    return data.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const adicionarTramitacao = async () => {
    if (!novaTramitacao.value.tipo || !novaTramitacao.value.descricao) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Preencha o tipo e a descrição da tramitação.', life: 3000 });
        return;
    }

    // Se o tipo for 'CONCLUSAO', mostra o diálogo de confirmação
    if (novaTramitacao.value.tipo === 'CONCLUSAO') {
        confirm.require({
            message: 'Você está registrando a conclusão. Deseja também finalizar a demanda, alterando o status para "Finalizado"?',
            header: 'Finalizar Demanda?',
            icon: 'pi pi-check-square',
            acceptLabel: 'Sim, Finalizar Demanda',
            rejectLabel: 'Não, Apenas Registrar',
            accept: () => {
                // Se aceitar, chama a função de salvar com o parâmetro para finalizar
                salvarTramitacaoEFinalizar(true);
            },
            reject: () => {
                // Se rejeitar, chama a função de salvar sem finalizar
                salvarTramitacaoEFinalizar(false);
            }
        });
    } else {
        // Para qualquer outro tipo de tramitação, salva diretamente
        salvarTramitacaoEFinalizar(false);
    }
};

const salvarTramitacaoEFinalizar = async (finalizarDemanda = false) => {
    const formData = new FormData();
    formData.append('demanda', demanda.value.id);
    formData.append('tipo', novaTramitacao.value.tipo);
    formData.append('descricao', novaTramitacao.value.descricao);
    novaTramitacao.value.anexos_arquivos.forEach(file => {
        formData.append('arquivos_anexos', file);
    });

    try {
        // Passo 1: Sempre cria a tramitação
        await ApiService.createTramitacao(formData);
        
        // Passo 2 (Condicional): Se for para finalizar, atualiza o status
        if (finalizarDemanda) {
            await ApiService.atualizarStatusDemanda(demanda.value.id, 'FINALIZADO');
        }

        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Andamento registrado!', life: 3000 });

        // Recarrega os dados da demanda para mostrar a nova tramitação e o novo status (se aplicável)
        const response = await ApiService.getDemandaById(demanda.value.id);
        demanda.value = response.data;

        // Limpa o formulário
        novaTramitacao.value.tipo = null;
        novaTramitacao.value.descricao = '';
        novaTramitacao.value.anexos_arquivos = [];

    } catch (error) {
        console.error("Erro ao salvar andamento:", error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível salvar o andamento.', life: 3000 });
    }
};

const onTramitacaoFilesSelected = (event) => {
    novaTramitacao.value.anexos_arquivos = event.files;
};

const getTimelineIcon = (tipoDisplay) => {
    const map = {
        'Comentário': { icon: 'pi pi-comment', color: 'avatar-gray' },
        'Análise Técnica': { icon: 'pi pi-desktop', color: 'avatar-yellow' },
        'Atraso por Falta de Material': { icon: 'pi pi-exclamation-triangle', color: 'avatar-red' },
        'Atraso por Outros Motivos': { icon: 'pi pi-exclamation-triangle', color: 'avatar-red' },
        'Programação do Serviço': { icon: 'pi pi-calendar', color: 'avatar-cyan' },
        'Transferência de Setor/Secretaria': { icon: 'pi pi-share-alt', color: 'avatar-orange' },
        'Conclusão do Serviço': { icon: 'pi pi-check-square', color: 'avatar-purple' },
        'Envio Oficial': { icon: 'pi pi-send', color: 'avatar-blue' },
        'Despacho para Secretaria': { icon: 'pi pi-share-alt', color: 'avatar-orange' },
        'Atualização de Status': { icon: 'pi pi-sync', color: 'avatar-cyan' },
    };
    return map[tipoDisplay] || { icon: 'pi pi-info-circle', color: 'avatar-gray' };
};

const goBack = () => {
    router.back();
}
</script>

<template>
    <div v-if="loading" class="text-center">
        <ProgressSpinner />
    </div>
    <div v-else-if="!demanda" class="text-center">
        <Message severity="error">Demanda não encontrada ou erro ao carregar os dados.</Message>
        <Button label="Voltar" icon="pi pi-arrow-left" @click="goBack" class="p-button-text mt-4" />
    </div>
    <div v-else>
        <div class="flex items-center justify-between gap-2 mb-6">
            <div class="flex items-center gap-4">
                <Message severity="secondary" icon="pi pi-file-check">
                    {{ demanda.protocolo_executivo || demanda.protocolo_legislativo || 'Rascunho' }}
                    <Tag :value="demanda.status_display" :severity="getStatusSeverity(demanda.status)" class="ml-2" />
                </Message>
                <Button 
                    v-if="isSecretaria && demanda.status === 'PROTOCOLADO'"
                    label="Iniciar Execução" 
                    icon="pi pi-play" 
                    severity="success"
                    @click="iniciarExecucao"
                    size="small"
                />
                <Button 
                    v-if="podeAgirNaDemanda"
                    label="Solicitar Transferência" 
                    icon="pi pi-exchange" 
                    severity="warning"
                    @click="solicitarTransferencia" 
                    v-tooltip.top="'Solicitar a movimentação desta demanda para outra secretaria'"
                    size="small"
                    outlined
                />
            </div>
            <div class="flex gap-2">
                <Button icon="pi pi-arrow-left" @click="router.push('/demandas')" size="small" />
                <Button icon="pi pi-home" @click="router.push('/')" size="small" />
            </div>
        </div>
        
        <Message v-if="demanda.status === 'AGUARDANDO_TRANSFERENCIA'" severity="warn" class="mb-4">
            Esta demanda está aguardando a análise do Protocolo para ser transferida para outra secretaria. Nenhuma outra ação pode ser realizada no momento.
        </Message>

        <div class="card !m-0">
            <Tag class="mb-3">
                <small class="font-semibold">Criado em:</small>
                <small>{{ dataCriacaoFormatada }}</small>
            </Tag>
            <h4 class="mt-1">{{ demanda.titulo }}</h4>
            <div class="flex items-center gap-6 mb-4">
                <div class="flex items-center gap-2">
                    <i class="pi pi-check-square text-primary-500"></i>
                    <span>{{ demanda.servico?.nome }}</span>
                </div>
                <div class="flex items-center gap-2">
                    <i class="pi pi-sitemap text-primary-500"></i>
                    <span>{{ demanda.secretaria_destino?.nome || 'Aguardando despacho' }}</span>
                </div>
            </div>
            <div v-if="demanda.numero_externo" class="flex items-center gap-2 mb-4">
                <i class="pi pi-bookmark text-primary-500"></i>
                <span>Ref. Externa: {{ demanda.numero_externo }}</span>
                <a v-if="demanda.link_externo" :href="demanda.link_externo" target="_blank" rel="noopener noreferrer" 
                    v-tooltip.top="'Abrir link externo'"
                    class="text-primary-500 hover:text-primary-700">
                    <i class="pi pi-external-link"></i>
                </a>
            </div>
            <Divider />
            <div class="field col-12">
                <span class="font-semibold">Descrição:</span>
                <div class="mt-2 p-3 border-1 surface-border border-round" v-html="demanda.descricao"></div>
            </div>
            <Divider />
            <div class="mb-4">
                <span class="text-primary-500"><i class="pi pi-map-marker"></i> Endereço:</span>
                <p class="mt-2">{{ demanda.logradouro || 'Não informado' }}, Nº {{ demanda.numero || 'S/N' }} - {{ demanda.bairro || 'Não informado' }}</p>
            </div>
            <div v-if="demanda.anexos && demanda.anexos.length > 0" class="field col-12">
                <span class="text-primary-500"><i class="pi pi-paperclip"></i> Anexos:</span>
                <a v-for="anexo in demanda.anexos" :key="anexo.id" :href="anexo.arquivo" target="_blank" rel="noopener noreferrer" class="no-underline text-color hover:text-primary flex align-items-center border-1 surface-border border-round mt-2 p-2">
                    <i class="pi pi-file mr-2"></i>
                    <span>{{ anexo.arquivo.split('/').pop() }}</span>
                </a>
            </div>
        </div>

        <div v-if="timelineOrdenada.length > 0" class="pt-6 pb-6 timeline-container">
            <div class="flex flex-col gap-6">
                <div v-for="item in timelineOrdenada" :key="item.id" class="flex gap-3">
                    <div class="flex flex-col items-center timeline-icon-container">
                        <Avatar :icon="getTimelineIcon(item.tipo_display).icon" shape="circle" size="large" :class="getTimelineIcon(item.tipo_display).color" />
                    </div>
                    <div class="card flex-1">
                        <div class="flex justify-between items-center">
                            <span class="font-bold gap-3">
                                {{ item.responsavel?.first_name || item.responsavel?.username || 'Sistema' }}
                                <small class="text-color-secondary font-normal"> registrou um andamento em {{ formatarData(item.timestamp) }}</small>
                            </span>
                            <Tag :value="item.tipo_display" :severity="getTramitacaoTagSeverity(item.tipo_display)" class="mb-2" />
                        </div>
                        <Divider/>
                        <div v-html="item.descricao" class="mb-6"></div>
                        <div v-if="item.anexos_tramitacao && item.anexos_tramitacao.length > 0" class="flex gap-2 mt-3 text-sm">
                            <i class="pi pi-paperclip"></i>
                            <div class="flex flex-column gap-2">
                                <a v-for="anexo in item.anexos_tramitacao" :key="anexo.id" :href="anexo.arquivo" target="_blank" rel="noopener noreferrer" class="no-underline text-color hover:text-primary flex align-items-center">
                                    <i class="pi pi-file mr-2"></i>
                                    <span>{{ anexo.arquivo.split('/').pop() }}</span>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="isSecretaria && demanda.status === 'EM_EXECUCAO'">
            <div class="flex flex-col gap-8">
                <div class="flex gap-3">
                    <div class="flex flex-col items-center">
                        <Avatar label="+" size="large" :style="{ 'background-color': '#10b981', color: '#ffffff' }" shape="circle"></Avatar>
                    </div>
                    <div class="card flex-1">
                        <span class="font-semibold mb-3 block">Adicionar Andamento</span>
                        <Divider/>
                        <div class="grid grid-cols-12 gap-8">
                            <div class="col-span-full lg:col-span-3">
                                <div class="mb-3">
                                    <label for="tipoTramitacao" class="block mb-3">Tipo de Andamento</label>
                                    <Select id="tipoTramitacao" v-model="novaTramitacao.tipo" :options="tiposTramitacao" optionLabel="label" optionValue="value" placeholder="Selecione o tipo" fluid />
                                </div>
                                <div>
                                    <label class="block mb-3"><i class="pi pi-paperclip"></i> Anexos</label>
                                    <FileUpload name="anexos" :multiple="true" accept="image/*,application/pdf" :maxFileSize="2000000" chooseLabel="Selecionar Anexos" :auto="false" :showUploadButton="false" @select="onTramitacaoFilesSelected"/>
                                    <div v-if="novaTramitacao.anexos_arquivos.length > 0" class="mt-2 flex flex-wrap gap-2">
                                        <Tag v-for="file in novaTramitacao.anexos_arquivos" :key="file.name" :value="file.name" icon="pi pi-paperclip" removable @remove="novaTramitacao.anexos_arquivos = novaTramitacao.anexos_arquivos.filter(f => f.name !== file.name)" />
                                    </div>
                                </div>
                            </div>
                            <div class="col-span-full lg:col-span-9">
                                <div class="mb-3">
                                    <label for="descricaoTramitacao" class="block mb-3">Descrição do Andamento</label>
                                    <Editor id="descricaoTramitacao" v-model="novaTramitacao.descricao" editorStyle="height: 150px" />
                                </div>
                                <Button label="Adicionar Andamento" icon="pi pi-plus" @click="adicionarTramitacao" />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <Button 
            v-else-if="isSecretaria && demanda.status === 'PROTOCOLADO'"
            label="Iniciar Execução" 
            icon="pi pi-play" 
            severity="success"
            @click="iniciarExecucao"
        />

        <Button v-else icon="pi pi-arrow-left" @click="router.push('/demandas')" label="Voltar" />
    </div>
</template>

<style scoped>
.timeline-container {
    position: relative;
}
.timeline-container::before {
    content: '';
    position: absolute;
    top: 0;
    left: 20px;
    width: 1.5px;
    height: 100%;
    background-color: var(--surface-border);
    z-index: 1;
}
.timeline-icon-container {
    position: relative;
    z-index: 2;
    padding-top: 8px;
}
.timeline-container .card {
    border: 1px solid var(--surface-border);
    box-shadow: var(--card-shadow);
}
.avatar-blue {
    background: var(--p-blue-500) !important;
    color: white !important;
}
.avatar-gray {
    background: var(--p-gray-500) !important;
    color: white !important;
}
.avatar-yellow {
    background: var(--p-yellow-500) !important;
    color: white !important;
}
.avatar-red {
    background: var(--p-red-500) !important;
    color: white !important;
}
.avatar-cyan {
    background: var(--p-cyan-500) !important;
    color: white !important;
}
.avatar-orange {
    background: var(--p-orange-500) !important;
    color: white !important;
}
.avatar-purple {
    background: var(--p-purple-500) !important;
    color: white !important;
}
</style>