<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ApiService from '@/service/ApiService.js';
import { useUserStore } from '@/stores/userStore';

// Componentes do PrimeVue
import Button from 'primevue/button';
import Panel from 'primevue/panel';
import Tag from 'primevue/tag';
import ProgressSpinner from 'primevue/progressspinner';
import Timeline from 'primevue/timeline';
import Editor from 'primevue/editor';
import Select from 'primevue/select';
import FileUpload from 'primevue/fileupload';
import Message from 'primevue/message';
import Divider from 'primevue/divider';
import Avatar from 'primevue/avatar';
import { useToast } from 'primevue/usetoast';

const route = useRoute();
const router = useRouter();
const demanda = ref(null);
const loading = ref(true);
const userStore = useUserStore();
const toast = useToast();

const novaTramitacao = ref({
    tipo: null,
    descricao: '',
    anexos_arquivos: [] // Para guardar os arquivos do FileUpload
});
const tiposTramitacao = ref([
    { label: 'Comentário', value: 'COMENTARIO' },
    { label: 'Análise Técnica', value: 'ANALISE_TECNICA' },
    { label: 'Atraso por Falta de Material', value: 'ATRASO_MATERIAL' },
    { label: 'Atraso por Outros Motivos', value: 'ATRASO_OUTROS' },
    { label: 'Programação do Serviço', value: 'PROGRAMACAO' },
    { label: 'Transferência de Setor/Secretaria', value: 'TRANSFERENCIA' },
    { label: 'Conclusão do Serviço', value: 'CONCLUSAO' },
]);

// Propriedade computada para verificar reativamente o perfil do usuário
const isSecretaria = computed(() => {
    const perfilNome = userStore.currentUser?.perfil; 
    if (!perfilNome || typeof perfilNome !== 'string') {
        return false;
    }
    return perfilNome.toUpperCase().trim() === 'SECRETARIA';
});

onMounted(async () => {
    // Garante que os dados do usuário sejam carregados se ainda não estiverem na store.
    // Isso é crucial para que as permissões (como `isSecretaria`) funcionem corretamente.
    if (!userStore.currentUser) {
        try {
            // Assumindo que sua store tem uma action `fetchCurrentUser` para buscar os dados do usuário logado.
            // Se o método tiver outro nome, ajuste aqui.
            if (typeof userStore.fetchCurrentUser === 'function') {
                await userStore.fetchCurrentUser();
            }
        } catch (error) {
            console.error("Erro ao buscar dados do usuário logado:", error);
            toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível verificar as permissões do usuário.', life: 3000 });
        }
    }

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

const getStatusSeverity = (status) => {
    const map = {
        'RASCUNHO': 'info',
        'AGUARDANDO_PROTOCOLO': 'warn',
        'PROTOCOLADO': 'primary',
        'EM_EXECUCAO': 'success',
        'FINALIZADO': 'success',
        'CANCELADO': 'danger'
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
    return data.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

const adicionarTramitacao = async () => {
    if (!novaTramitacao.value.tipo || !novaTramitacao.value.descricao) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Preencha o tipo e a descrição da tramitação.', life: 3000 });
        return;
    }

    const formData = new FormData();
    formData.append('demanda', demanda.value.id);
    formData.append('tipo', novaTramitacao.value.tipo);
    formData.append('descricao', novaTramitacao.value.descricao);

    novaTramitacao.value.anexos_arquivos.forEach(file => {
        formData.append('arquivos_anexos', file);
    });

    try {
        await ApiService.createTramitacao(formData);
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Tramitação registrada com sucesso!', life: 3000 });

        const response = await ApiService.getDemandaById(demanda.value.id);
        demanda.value = response.data;

        novaTramitacao.value.tipo = null;
        novaTramitacao.value.descricao = '';
        novaTramitacao.value.anexos_arquivos = [];

    } catch (error) {
        console.error("Erro ao adicionar tramitação:", error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível registrar a tramitação.', life: 3000 });
    }
};

const onTramitacaoFilesSelected = (event) => {
    novaTramitacao.value.anexos_arquivos = event.files;
};

const getTimelineIcon = (tipoDisplay) => {
    const map = {
        'Comentário': { icon: 'pi pi-comment', color: 'bg-gray-500' },
        'Análise Técnica': { icon: 'pi pi-desktop', color: 'bg-yellow-500' },
        'Atraso por Falta de Material': { icon: 'pi pi-exclamation-triangle', color: 'bg-red-500' },
        'Atraso por Outros Motivos': { icon: 'pi pi-exclamation-triangle', color: 'bg-red-500' },
        'Programação do Serviço': { icon: 'pi pi-calendar', color: 'bg-cyan-500' },
        'Transferência de Setor/Secretaria': { icon: 'pi pi-share-alt', color: 'bg-orange-500' },
        'Conclusão do Serviço': { icon: 'pi pi-check-square', color: 'bg-purple-500' },
        'Envio Oficial': { icon: 'pi pi-send', color: 'bg-blue-500' },
        'Despacho para Secretaria': { icon: 'pi pi-share-alt', color: 'bg-orange-500' },
        'Atualização de Status': { icon: 'pi pi-sync', color: 'bg-cyan-500' },
    };
    return map[tipoDisplay] || { icon: 'pi pi-info-circle', color: 'bg-gray-500' };
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
        <div class="card bg-yellow-100 border-yellow-400 mb-4">
            <h5 class="font-bold text-yellow-800">Informações de Depuração (Usuário Logado)</h5>
            <div v-if="userStore.currentUser">
                <p class="text-sm">Objeto currentUser encontrado. Verificando perfil...</p>
                <pre class="whitespace-pre-wrap break-all text-sm text-yellow-900">{{ JSON.stringify(userStore.currentUser, null, 2) }}</pre>
                <p class="text-sm mt-2">
                    Resultado da verificação 'isSecretaria': 
                    <strong :class="isSecretaria ? 'text-green-600' : 'text-red-600'">{{ isSecretaria }}</strong>
                </p>
            </div>
            <div v-else>
                <p class="text-sm text-red-600"><strong>userStore.currentUser está nulo ou indefinido.</strong></p>
            </div>
        </div>

        <div class="flex items-center justify-between gap-2 mb-6">
            <div class="flex items-center justify-between">
                <Message severity="secondary" icon="pi pi-file-check">
                    {{ demanda.protocolo_executivo || demanda.protocolo_legislativo || 'Rascunho' }}
                    <Tag :value="demanda.status" :severity="getStatusSeverity(demanda.status)" class="ml-2" />
                </Message>
            </div>
            <div class="flex gap-2">
                <Button icon="pi pi-arrow-left" @click="router.push('/demandas')" size="small" />
                <Button icon="pi pi-home" @click="router.push('/')" size="small" />
            </div>
        </div>

        <div class="card !m-0">
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

            <Divider />

            <div class="field col-12">
                <span class="font-semibold">Descrição:</span>
                <div class="mt-2 p-3 border-1 surface-border border-round" v-html="demanda.descricao"></div>
            </div>

            <Divider />

            <div class="mb-4">
                <span class="text-primary-500">
                    <i class="pi pi-map-marker"></i>
                    Endereço:
                </span>
                <p class="mt-2">{{ demanda.logradouro || 'Não informado' }}, Nº {{ demanda.numero || 'S/N' }} - {{ demanda.bairro || 'Não informado' }}</p>
            </div>

            <div v-if="demanda.anexos && demanda.anexos.length > 0" class="field col-12">
                <span class="text-primary-500">
                    <i class="pi pi-paperclip"></i>
                    Anexos:
                </span>
                <a v-for="anexo in demanda.anexos" :key="anexo.id" :href="anexo.arquivo" target="_blank" rel="noopener noreferrer" class="no-underline text-color hover:text-primary flex align-items-center border-1 surface-border border-round mt-2 p-2">
                    <i class="pi pi-file mr-2"></i>
                    <span>{{ anexo.arquivo.split('/').pop() }}</span>
                </a>
            </div>
        </div>

        <div v-if="demanda.tramitacoes && demanda.tramitacoes.length > 0" class="pt-6 pb-6 timeline-container">
            <div class="flex flex-col gap-6">
                <div v-for="item in demanda.tramitacoes" :key="item.id" class="flex gap-3">

                    <div class="flex flex-col items-center timeline-icon-container">
                        <Avatar :icon="getTimelineIcon(item.tipo_display).icon" shape="circle" size="large" :class="getTimelineIcon(item.tipo_display).color" />
                    </div>

                    <div class="card flex-1">
                        <div class="flex justify-between items-center">
                            <span class="font-bold gap-3">
                                {{ item.responsavel?.perfil?.nome || 'Sistema' }}
                                <small class="text-color-secondary font-normal"> registrou um andamento em {{ formatarData(item.timestamp) }}</small>
                            </span>
                            <Tag :value="item.tipo_display" :severity="getTramitacaoTagSeverity(item.tipo_display)" class="mb-2" />
                        </div>

                        <Divider/>
                        
                        <div v-html="item.descricao" class="mb-6"></div>

                        <div v-if="item.anexos && item.anexos.length > 0" class="flex gap-2 mt-3 text-sm">
                            <i class="pi pi-paperclip"></i>
                            <div class="flex flex-column gap-2">
                                <a v-for="anexo in item.anexos" :key="anexo.id" :href="anexo.arquivo" target="_blank" rel="noopener noreferrer" class="no-underline text-color hover:text-primary flex align-items-center">
                                    <i class="pi pi-file mr-2"></i>
                                    <span>{{ anexo.arquivo.split('/').pop() }}</span>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="isSecretaria && demanda.status !== 'FINALIZADO'">
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
                                    <label class="block mb-3">
                                        <i class="pi pi-paperclip"></i>
                                        Anexos
                                    </label>
                                    <FileUpload 
                                        name="anexos" 
                                        :multiple="true" 
                                        accept="image/*,application/pdf" 
                                        :maxFileSize="2000000"
                                        chooseLabel="Selecionar Anexos"
                                        uploadLabel="Enviar"
                                        cancelLabel="Cancelar"
                                        :auto="false"
                                        :showUploadButton="false"
                                        @select="onTramitacaoFilesSelected"
                                    />
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
        <Button v-else icon="pi pi-arrow-left" @click="router.push('/demandas')" label="Voltar" />
    </div>
</template>

<style scoped>
.timeline-container {
    position: relative;
}

/* A linha vertical contínua */
.timeline-container::before {
    content: '';
    position: absolute;
    top: 0;
    left: 20px; /* Ajustado para alinhar com o centro do Avatar 'large' */
    width: 1.5px; /* Aumentei a espessura para melhor visualização */
    height: 100%;
    background-color: var(--surface-border);
    z-index: 1; /* Fica no fundo */
}

/* O container do ícone */
.timeline-icon-container {
    position: relative;
    z-index: 2; /* Garante que o ícone fique SEMPRE na frente da linha */
    padding-top: 8px; /* Ajuste para centralizar o ícone com o card */
}

/* Ajuste fino para remover a borda padrão dos cards dentro da timeline */
.timeline-container .card {
    border: 1px solid var(--surface-border);
    box-shadow: var(--card-shadow);
}
</style>