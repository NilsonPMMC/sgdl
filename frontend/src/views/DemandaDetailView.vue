<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ApiService from '@/service/ApiService.js';
import { useUserStore } from '@/stores/userStore';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';

import Button from 'primevue/button';
import Tag from 'primevue/tag';
import ProgressSpinner from 'primevue/progressspinner';
import Editor from 'primevue/editor';
import Select from 'primevue/select';
import FileUpload from 'primevue/fileupload';
import Message from 'primevue/message';
import Textarea from 'primevue/textarea';
import Divider from 'primevue/divider';
import Avatar from 'primevue/avatar';
import Dialog from 'primevue/dialog';
import { descricaoParaHtml } from '@/utils/oficioTexto';
import {
    labelTramitacaoVereador,
    tramitacaoVisivelParaVereador
} from '@/constants/tramitacaoVisibilidade';

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
    anexos_arquivos: [],
    unidade_destino_id: null
});

const unidadesSetor = ref([]);

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
    { label: 'Execução', value: 'EXECUCAO' },
    { label: 'Conclusão', value: 'CONCLUSAO' }
]);

const isSecretaria = computed(() => {
    const perfilNome = userStore.currentUser?.perfil;
    if (!perfilNome || typeof perfilNome !== 'string') {
        return false;
    }
    return perfilNome.toUpperCase().trim() === 'SECRETARIA';
});

const isVereador = computed(() => userStore.currentUser?.perfil === 'VEREADOR');

const isGestor = computed(() => userStore.currentUser?.perfil === 'GESTOR');

const isProtocolo = computed(() => userStore.currentUser?.perfil === 'PROTOCOLO' || isGestor.value);

const isProtocoloPerfil = computed(() => userStore.currentUser?.perfil === 'PROTOCOLO');

const podeGerirSuperOs = computed(
    () => isSecretaria.value || isProtocolo.value
);

const mostrarCardSuperOs = computed(
    () => superOs.value?.ativo && podeGerirSuperOs.value
);

const podeDespacharDevolutiva = computed(() =>
    isProtocolo.value && demanda.value?.status === 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO'
);

const podeEncerrarDevolutiva = computed(
    () => isProtocolo.value && demanda.value?.status === 'DEVOLVIDO_VEREADOR'
);

const podeDespacharProtocolo = computed(
    () => isProtocoloPerfil.value && demanda.value?.status === 'AGUARDANDO_PROTOCOLO'
);

const usarDescricaoEstruturada = computed(
    () => isProtocolo.value || isSecretaria.value || isGestor.value
);

const descricaoExibicao = computed(() => {
    const raw = demanda.value?.descricao || '';
    return usarDescricaoEstruturada.value ? descricaoParaHtml(raw) : raw;
});

const todasSecretarias = ref([]);
const despachoDialog = ref(false);
const despachoData = ref({ secretaria_id: null });

const devolutivaResposta = ref('');
const pacoteDevolutiva = ref(null);
const textoRespostaCidadao = ref('');

const isVereadorAutor = computed(
    () =>
        userStore.currentUser?.perfil === 'VEREADOR' &&
        demanda.value?.autor?.id === userStore.currentUser?.id
);

const podeConfirmarCiencia = computed(
    () => demanda.value?.status === 'DEVOLVIDO_VEREADOR' && isVereadorAutor.value
);

const carregarPacoteDevolutiva = async () => {
    if (!demanda.value?.id) return;
    if (!['DEVOLVIDO_VEREADOR', 'FINALIZADO', 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO'].includes(demanda.value.status)) {
        pacoteDevolutiva.value = null;
        return;
    }
    try {
        const { data } = await ApiService.getPacoteDevolutiva(demanda.value.id);
        pacoteDevolutiva.value = data;
        if (data?.texto_resposta_cidadao) {
            textoRespostaCidadao.value = data.texto_resposta_cidadao;
        }
    } catch {
        pacoteDevolutiva.value = demanda.value.pacote_devolutiva || null;
    }
};

const superOs = computed(() => demanda.value?.super_os || null);

const ehLiderSuperOs = computed(() => {
    if (!superOs.value?.ativo) return true;
    return superOs.value.eh_lider === true;
});

const podeAgirNaDemanda = computed(() => {
    if (!demanda.value || !userStore.currentUser) return false;
    const isOwner = demanda.value.secretaria_destino?.id === userStore.currentUser.secretaria;
    const isActionableStatus = ![
        'FINALIZADO',
        'CANCELADO',
        'AGUARDANDO_TRANSFERENCIA',
        'AGUARDANDO_PROTOCOLO',
        'AGUARDANDO_DEVOLUTIVA_PROTOCOLO',
        'DEVOLVIDO_VEREADOR',
        'RASCUNHO'
    ].includes(demanda.value.status);
    return isSecretaria.value && isOwner && isActionableStatus && ehLiderSuperOs.value;
});

const podeIniciarExecucao = computed(
    () => isSecretaria.value && demanda.value?.status === 'PROTOCOLADO' && ehLiderSuperOs.value
);

const abrirProcessoVinculado = (vincId) => {
    if (!vincId || String(vincId) === String(route.params.id)) return;
    router.push({ name: 'demandas-detalhes', params: { id: String(vincId) } });
};

const processoVinculadoClicavel = (vinc) => {
    if (!vinc?.id || String(vinc.id) === String(demanda.value?.id)) return false;
    if (isProtocoloPerfil.value) return true;
    if (isSecretaria.value && vinc.id === superOs.value?.lider_id) return true;
    return false;
};

const labelProcessoVinculado = (vinc) => {
    const proto = vinc.protocolo_executivo || vinc.protocolo_legislativo;
    const titulo = (vinc.titulo || '').trim();
    const curto = titulo.length > 28 ? `${titulo.slice(0, 28)}…` : titulo;
    return proto ? `${proto}${curto ? ` · ${curto}` : ''}` : `#${vinc.id}`;
};

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
    if (!demanda.value?.tramitacoes?.length) {
        return [];
    }
    let items = [...demanda.value.tramitacoes];
    if (isVereador.value) {
        items = items.filter((t) => tramitacaoVisivelParaVereador(t.tipo));
    }
    return items.reverse();
});

const orgaoIdDemanda = computed(() => {
    const d = demanda.value;
    if (!d) return null;
    return (
        d.sinapse_orgao_id ||
        d.secretaria_destino?.id ||
        d.unidade_administrativa?.sinapse_orgao_id ||
        userStore.currentUser?.sinapse_orgao_id ||
        null
    );
});

const carregarUnidadesSetor = async () => {
    const orgaoId = orgaoIdDemanda.value;
    if (!orgaoId) {
        unidadesSetor.value = [];
        return;
    }
    try {
        const { data } = await ApiService.listarUnidadesAdministrativas({
            sinapse_orgao_id: orgaoId,
            ativo: true
        });
        const lista = Array.isArray(data) ? data : data?.results || [];
        unidadesSetor.value = lista.map((u) => ({
            label: u.sigla ? `${u.sigla} — ${u.nome}` : u.nome,
            value: u.id
        }));
    } catch {
        unidadesSetor.value = [];
    }
};

const carregarDemanda = async (demandaId) => {
    if (!demandaId) {
        loading.value = false;
        return;
    }
    loading.value = true;
    try {
        const response = await ApiService.getDemandaById(demandaId);
        demanda.value = response.data;
        await Promise.all([carregarPacoteDevolutiva(), carregarUnidadesSetor()]);
    } catch (error) {
        console.error('Erro ao buscar detalhes da demanda:', error);
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: 'Não foi possível carregar os detalhes da demanda.',
            life: 3000
        });
    } finally {
        loading.value = false;
    }
};

watch(
    () => route.params.id,
    (id) => {
        if (id) carregarDemanda(id);
    }
);

const carregarSecretarias = async () => {
    if (!isProtocoloPerfil.value) return;
    try {
        const { data } = await ApiService.getSecretarias();
        todasSecretarias.value = data;
    } catch {
        todasSecretarias.value = [];
    }
};

const abrirDialogoDespacho = () => {
    const d = demanda.value;
    despachoData.value = {
        secretaria_id:
            d?.servico?.secretaria_responsavel?.id ||
            d?.secretaria_destino?.id ||
            d?.sinapse_orgao_id ||
            null
    };
    despachoDialog.value = true;
};

const confirmarDespacho = async () => {
    if (!despachoData.value.secretaria_id) {
        toast.add({ severity: 'warn', summary: 'Atenção', detail: 'Selecione a secretaria de destino.', life: 3000 });
        return;
    }
    try {
        await ApiService.despacharDemanda(demanda.value.id, despachoData.value);
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Demanda despachada.', life: 3000 });
        despachoDialog.value = false;
        await carregarDemanda(demanda.value.id);
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível despachar.',
            life: 4000
        });
    }
};

onMounted(() => {
    carregarDemanda(route.params.id);
    carregarSecretarias();
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
                console.error('Erro ao solicitar transferência:', error);
                toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível solicitar a transferência.', life: 3000 });
            }
        }
    });
};

const getStatusSeverity = (status) => {
    const map = {
        RASCUNHO: 'info',
        AGUARDANDO_PROTOCOLO: 'warn',
        PROTOCOLADO: 'primary',
        EM_EXECUCAO: 'success',
        FINALIZADO: 'success',
        CANCELADO: 'danger',
        AGUARDANDO_TRANSFERENCIA: 'warning',
        AGUARDANDO_DEVOLUTIVA_PROTOCOLO: 'warn',
        DEVOLVIDO_VEREADOR: 'info'
    };
    return map[status] || 'contrast';
};

const getTramitacaoTagSeverity = (tipoDisplay) => {
    const map = {
        Comentário: 'secondary',
        'Análise Técnica': 'warning',
        Execução: 'info',
        'Atraso por Falta de Material': 'danger',
        'Atraso por Outros Motivos': 'danger',
        'Programação do Serviço': 'info',
        'Transferência de Setor/Secretaria': 'primary',
        'Conclusão do Serviço': 'success',
        'Envio Oficial': 'info',
        'Despacho para Secretaria': 'primary',
        'Atualização de Status': 'success',
        'Solicitação de devolutiva': 'purple',
        'Devolutiva ao vereador': 'info',
        'Encerramento legislativo': 'success'
    };
    return map[tipoDisplay] || 'contrast';
};

const formatarData = (timestamp) => {
    if (!timestamp) return '';
    const data = new Date(timestamp);
    return data.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const limparFormularioTramitacao = () => {
    novaTramitacao.value.tipo = null;
    novaTramitacao.value.descricao = '';
    novaTramitacao.value.anexos_arquivos = [];
    novaTramitacao.value.unidade_destino_id = null;
};

const adicionarTramitacao = () => {
    if (!novaTramitacao.value.tipo || !novaTramitacao.value.descricao) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Preencha o tipo e a descrição da tramitação.', life: 3000 });
        return;
    }

    const tipoLabel = tiposTramitacao.value.find((t) => t.value === novaTramitacao.value.tipo)?.label || 'Andamento';
    const mensagemConclusao =
        'A conclusão operacional encaminha automaticamente a demanda ao Protocolo para devolutiva ao(s) vereador(es). O processo seguirá até o encerramento legislativo. Confirma o envio?';
    const mensagemPadrao =
        'Após registrar, este andamento não poderá ser editado. Confirma o envio para a timeline da demanda?';

    confirm.require({
        message: novaTramitacao.value.tipo === 'CONCLUSAO' ? mensagemConclusao : mensagemPadrao,
        header: novaTramitacao.value.tipo === 'CONCLUSAO' ? 'Confirmar conclusão operacional' : 'Confirmar andamento',
        icon: 'pi pi-send',
        acceptLabel: 'Sim, enviar',
        rejectLabel: 'Cancelar',
        accept: () => {
            if (novaTramitacao.value.tipo === 'CONCLUSAO') {
                salvarTramitacaoESolicitarDevolutiva();
            } else {
                salvarTramitacaoEFinalizar(false);
            }
        }
    });
};

const salvarTramitacaoESolicitarDevolutiva = async () => {
    const formData = new FormData();
    formData.append('demanda', demanda.value.id);
    formData.append('tipo', 'CONCLUSAO');
    formData.append('descricao', novaTramitacao.value.descricao);
    novaTramitacao.value.anexos_arquivos.forEach((file) => {
        formData.append('arquivos_anexos', file);
    });
    if (novaTramitacao.value.unidade_destino_id) {
        formData.append('unidade_destino_id', novaTramitacao.value.unidade_destino_id);
    }
    try {
        await ApiService.createTramitacao(formData);
        await ApiService.solicitarDevolutiva(demanda.value.id, {
            parecer_operacional: novaTramitacao.value.descricao
        });
        toast.add({
            severity: 'success',
            summary: 'Devolutiva solicitada',
            detail: 'O Protocolo receberá a demanda para despacho ao vereador.',
            life: 4000
        });
        const response = await ApiService.getDemandaById(demanda.value.id);
        demanda.value = response.data;
        limparFormularioTramitacao();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível solicitar a devolutiva.',
            life: 4000
        });
    }
};

const salvarTramitacaoEFinalizar = async (finalizarDemanda = false) => {
    const formData = new FormData();
    formData.append('demanda', demanda.value.id);
    formData.append('tipo', novaTramitacao.value.tipo);
    formData.append('descricao', novaTramitacao.value.descricao);
    novaTramitacao.value.anexos_arquivos.forEach((file) => {
        formData.append('arquivos_anexos', file);
    });
    if (novaTramitacao.value.unidade_destino_id) {
        formData.append('unidade_destino_id', novaTramitacao.value.unidade_destino_id);
    }

    try {
        await ApiService.createTramitacao(formData);

        if (finalizarDemanda) {
            await ApiService.solicitarDevolutiva(demanda.value.id, {
                parecer_operacional: novaTramitacao.value.descricao
            });
        }

        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Andamento registrado!', life: 3000 });

        // Recarrega os dados da demanda para mostrar a nova tramitação e o novo status (se aplicável)
        const response = await ApiService.getDemandaById(demanda.value.id);
        demanda.value = response.data;

        limparFormularioTramitacao();
        await carregarUnidadesSetor();
    } catch (error) {
        console.error('Erro ao salvar andamento:', error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível salvar o andamento.', life: 3000 });
    }
};

const onTramitacaoFilesSelected = (event) => {
    novaTramitacao.value.anexos_arquivos = event.files;
};

const getTimelineIcon = (tipoDisplay) => {
    const map = {
        Comentário: { icon: 'pi pi-comment', color: 'avatar-gray' },
        'Análise Técnica': { icon: 'pi pi-desktop', color: 'avatar-yellow' },
        Execução: { icon: 'pi pi-cog', color: 'avatar-blue' },
        'Atraso por Falta de Material': { icon: 'pi pi-exclamation-triangle', color: 'avatar-red' },
        'Atraso por Outros Motivos': { icon: 'pi pi-exclamation-triangle', color: 'avatar-red' },
        'Programação do Serviço': { icon: 'pi pi-calendar', color: 'avatar-cyan' },
        'Transferência de Setor/Secretaria': { icon: 'pi pi-share-alt', color: 'avatar-orange' },
        'Conclusão do Serviço': { icon: 'pi pi-check-square', color: 'avatar-purple' },
        'Envio Oficial': { icon: 'pi pi-send', color: 'avatar-blue' },
        'Despacho para Secretaria': { icon: 'pi pi-share-alt', color: 'avatar-orange' },
        'Atualização de Status': { icon: 'pi pi-sync', color: 'avatar-cyan' },
        'Solicitação de devolutiva': { icon: 'pi pi-send', color: 'avatar-purple' },
        'Devolutiva ao vereador': { icon: 'pi pi-reply', color: 'avatar-blue' },
        'Encerramento legislativo': { icon: 'pi pi-check-circle', color: 'avatar-green' }
    };
    return map[tipoDisplay] || { icon: 'pi pi-info-circle', color: 'avatar-gray' };
};

const despacharDevolutiva = async () => {
    if ((devolutivaResposta.value || '').trim().length < 10) {
        toast.add({ severity: 'warn', summary: 'Resposta obrigatória', detail: 'Informe a devolutiva ao vereador (mín. 10 caracteres).', life: 3000 });
        return;
    }
    try {
        await ApiService.despacharDevolutiva(demanda.value.id, {
            parecer_resposta: devolutivaResposta.value
        });
        toast.add({ severity: 'success', summary: 'Devolutiva enviada', detail: 'Vereador notificado.', life: 3000 });
        devolutivaResposta.value = '';
        const response = await ApiService.getDemandaById(demanda.value.id);
        demanda.value = response.data;
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível despachar a devolutiva.',
            life: 4000
        });
    }
};

const encerrarDevolutiva = () => {
    confirm.require({
        message: 'Encerrar sem registro de ciência do vereador? (uso administrativo do Protocolo)',
        header: 'Encerrar demanda',
        icon: 'pi pi-check',
        accept: async () => {
            try {
                await ApiService.encerrarDevolutiva(demanda.value.id);
                toast.add({ severity: 'success', summary: 'Encerrada', detail: 'Demanda finalizada.', life: 3000 });
                const response = await ApiService.getDemandaById(demanda.value.id);
                demanda.value = response.data;
            } catch (error) {
                toast.add({
                    severity: 'error',
                    summary: 'Erro',
                    detail: error?.response?.data?.detail || 'Não foi possível encerrar.',
                    life: 4000
                });
            }
        }
    });
};

const previewRespostaCidadao = async () => {
    try {
        const { data } = await ApiService.previewRespostaCidadao(
            demanda.value.id,
            textoRespostaCidadao.value
        );
        const blob = new Blob([data], { type: 'application/pdf' });
        window.open(URL.createObjectURL(blob), '_blank');
    } catch {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível gerar a pré-visualização.', life: 3000 });
    }
};

const confirmarCienciaEncerramento = () => {
    confirm.require({
        message:
            'Confirma ciência da devolutiva, gera o ofício de resposta ao cidadão e encerra a demanda?',
        header: 'Ciência e encerramento',
        icon: 'pi pi-check-circle',
        accept: async () => {
            try {
                await ApiService.confirmarCiencia(demanda.value.id, {
                    texto_resposta_cidadao: textoRespostaCidadao.value,
                    gerar_oficio: true,
                    encerrar: true
                });
                toast.add({
                    severity: 'success',
                    summary: 'Ciclo concluído',
                    detail: 'Ciência registrada e ofício ao cidadão gerado.',
                    life: 4000
                });
                const response = await ApiService.getDemandaById(demanda.value.id);
                demanda.value = response.data;
                await carregarPacoteDevolutiva();
            } catch (error) {
                toast.add({
                    severity: 'error',
                    summary: 'Erro',
                    detail: error?.response?.data?.detail || 'Não foi possível concluir.',
                    life: 4000
                });
            }
        }
    });
};

const goBack = () => {
    router.back();
};
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
                    v-if="podeDespacharProtocolo"
                    label="Enviar / Despachar"
                    icon="pi pi-send"
                    severity="success"
                    @click="abrirDialogoDespacho"
                    size="small"
                />
                <Button v-if="podeIniciarExecucao" label="Iniciar Execução" icon="pi pi-play" severity="success" @click="iniciarExecucao" size="small" />
                <Button
                    v-if="podeConfirmarCiencia"
                    label="Confirmar ciência e encerrar"
                    icon="pi pi-check-circle"
                    severity="success"
                    @click="confirmarCienciaEncerramento"
                    size="small"
                />
                <Button
                    v-if="podeEncerrarDevolutiva && isProtocolo"
                    label="Encerrar (Protocolo)"
                    icon="pi pi-check"
                    severity="secondary"
                    outlined
                    @click="encerrarDevolutiva"
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

        <Message
            v-if="superOs?.ativo && isVereador"
            severity="info"
            class="mb-4"
            :closable="false"
        >
            Seu processo integra a Super OS
            <strong v-if="superOs.protocolo_super_os">{{ superOs.protocolo_super_os }}</strong>.
            Acompanhe os andamentos da secretaria na linha do tempo abaixo.
        </Message>

        <div v-if="mostrarCardSuperOs" class="card mb-4 super-os-card">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-2">
                <div class="flex flex-wrap items-center gap-2">
                    <Tag
                        v-if="superOs.protocolo_super_os"
                        :value="superOs.protocolo_super_os"
                        severity="info"
                    />
                    <span class="super-os-total">{{ superOs.total_vinculados }}</span>
                    <span class="text-sm text-muted-color">processos vinculados</span>
                </div>
                <Button
                    v-if="isProtocoloPerfil && superOs.cluster_id"
                    label="Gestor de clusters"
                    icon="pi pi-objects-column"
                    size="small"
                    text
                    @click="router.push({ name: 'clusters', query: { id: String(superOs.cluster_id) } })"
                />
            </div>
            <p class="text-xs text-muted-color m-0 mb-3">
                <template v-if="superOs.eh_lider && isSecretaria">
                    Andamentos registrados aqui são replicados nos processos abaixo.
                </template>
                <template v-else-if="!superOs.eh_lider && isSecretaria">
                    Processo vinculado — a tramitação operacional é feita na demanda líder
                    (#{{ superOs.lider_id }}).
                </template>
                <template v-else-if="isProtocoloPerfil">
                    Clique em um processo para abrir os detalhes. A demanda atual está destacada.
                </template>
                <template v-else>
                    Processos agrupados nesta Super OS.
                </template>
            </p>
            <div class="flex flex-wrap gap-2">
                <template v-for="vinc in superOs.demandas_vinculadas" :key="vinc.id">
                    <Button
                        v-if="processoVinculadoClicavel(vinc)"
                        :label="`${vinc.id === superOs.lider_id ? 'Líder · ' : ''}${labelProcessoVinculado(vinc)}`"
                        size="small"
                        outlined
                        severity="secondary"
                        class="super-os-tag-btn"
                        v-tooltip.top="`${vinc.status_display || vinc.status}${vinc.id === superOs.lider_id ? ' · demanda líder' : ''}`"
                        @click="abrirProcessoVinculado(vinc.id)"
                    />
                    <Tag
                        v-else
                        :value="`${vinc.id === demanda.id ? 'Atual · ' : ''}${vinc.id === superOs.lider_id ? 'Líder · ' : ''}${labelProcessoVinculado(vinc)}`"
                        :severity="vinc.id === demanda.id ? 'success' : vinc.id === superOs.lider_id ? 'info' : 'secondary'"
                        v-tooltip.top="vinc.status_display || vinc.status"
                    />
                </template>
            </div>
        </div>

        <Message v-if="demanda.status === 'AGUARDANDO_TRANSFERENCIA'" severity="warn" class="mb-4">
            Esta demanda está aguardando a análise do Protocolo para ser transferida para outra secretaria. Nenhuma outra ação pode ser realizada no momento.
        </Message>

        <Message v-if="demanda.status === 'AGUARDANDO_PROTOCOLO' && isProtocoloPerfil" severity="warn" class="mb-4">
            Ofício aguardando despacho — use <strong>Enviar / Despachar</strong> para encaminhar à secretaria.
        </Message>

        <Message v-if="demanda.status === 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO' && isProtocolo" severity="info" class="mb-4">
            Devolutiva operacional recebida — despache a resposta ao vereador abaixo.
        </Message>

        <Message v-if="demanda.status === 'DEVOLVIDO_VEREADOR' && isVereadorAutor" severity="success" class="mb-4">
            Devolutiva recebida do Protocolo. Revise o parecer abaixo, redija a resposta ao cidadão e confirme ciência para encerrar.
        </Message>

        <div v-if="pacoteDevolutiva && demanda.status === 'DEVOLVIDO_VEREADOR'" class="card mb-4">
            <h5 class="mt-0">Pacote de devolutiva</h5>
            <div v-if="pacoteDevolutiva.parecer_operacional" class="mb-3">
                <span class="font-semibold block mb-1">Parecer da secretaria</span>
                <p class="m-0 whitespace-pre-wrap text-sm">{{ pacoteDevolutiva.parecer_operacional }}</p>
            </div>
            <div v-if="pacoteDevolutiva.resposta_protocolo" class="mb-3">
                <span class="font-semibold block mb-1">Resposta do Protocolo</span>
                <p class="m-0 whitespace-pre-wrap text-sm">{{ pacoteDevolutiva.resposta_protocolo }}</p>
            </div>
            <div v-if="podeConfirmarCiencia" class="flex flex-col gap-2 mt-4">
                <label class="font-semibold">Resposta ao cidadão (ofício final)</label>
                <Textarea
                    v-model="textoRespostaCidadao"
                    rows="5"
                    class="w-full"
                    placeholder="Texto que constará no ofício de resposta ao cidadão..."
                />
                <div class="flex flex-wrap gap-2">
                    <Button label="Pré-visualizar PDF" icon="pi pi-file-pdf" outlined @click="previewRespostaCidadao" />
                </div>
            </div>
        </div>

        <div v-if="podeDespacharDevolutiva" class="card mb-4">
            <h5 class="mt-0">Despachar devolutiva ao vereador</h5>
            <Textarea v-model="devolutivaResposta" rows="4" class="w-full" placeholder="Resposta / parecer do Protocolo ao vereador..." />
            <Button label="Enviar devolutiva" icon="pi pi-reply" class="mt-3" @click="despacharDevolutiva" />
        </div>

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
            <Divider />
            <div class="field col-12">
                <span class="font-semibold">Descrição:</span>
                <div
                    class="demanda-descricao-html mt-2 p-3 border-1 surface-border border-round"
                    v-html="descricaoExibicao"
                ></div>
            </div>
            <Divider />
            <div class="mb-4">
                <span class="text-primary-500"><i class="pi pi-map-marker"></i> Endereço:</span>
                <p class="mt-2">{{ demanda.logradouro || 'Não informado' }}, Nº {{ demanda.numero || 'S/N' }} - {{ demanda.bairro || 'Não informado' }}</p>
            </div>
            <div v-if="demanda.anexos && demanda.anexos.length > 0" class="field col-12">
                <span class="text-primary-500"><i class="pi pi-paperclip"></i> Anexos:</span>
                <a
                    v-for="anexo in demanda.anexos"
                    :key="anexo.id"
                    :href="anexo.arquivo"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="no-underline text-color hover:text-primary flex align-items-center border-1 surface-border border-round mt-2 p-2"
                >
                    <i class="pi pi-file mr-2"></i>
                    <span>{{ anexo.arquivo.split('/').pop() }}</span>
                </a>
            </div>
        </div>

        <Message
            v-if="isVereador && demanda.status === 'EM_EXECUCAO' && timelineOrdenada.length === 0"
            severity="info"
            class="mb-4"
            :closable="false"
        >
            A secretaria está executando o serviço. Você será notificado quando houver conclusão ou devolutiva.
        </Message>

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
                            <Tag
                                :value="isVereador ? labelTramitacaoVereador(item) : item.tipo_display"
                                :severity="getTramitacaoTagSeverity(item.tipo_display)"
                                class="mb-2"
                            />
                        </div>
                        <Divider />
                        <div v-html="item.descricao" class="mb-6"></div>
                        <p v-if="!isVereador && item.unidade_destino" class="text-sm text-muted-color m-0 mb-3">
                            <i class="pi pi-sitemap mr-1"></i>
                            Setor destino: {{ item.unidade_destino.sigla || item.unidade_destino.nome }}
                        </p>
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

        <div v-if="isSecretaria && demanda.status === 'EM_EXECUCAO' && ehLiderSuperOs">
            <div class="flex flex-col gap-8">
                <div class="flex gap-3">
                    <div class="flex flex-col items-center">
                        <Avatar label="+" size="large" :style="{ 'background-color': '#10b981', color: '#ffffff' }" shape="circle"></Avatar>
                    </div>
                    <div class="card flex-1">
                        <span class="font-semibold mb-3 block">Adicionar Andamento</span>
                        <Divider />
                        <div class="grid grid-cols-12 gap-8">
                            <div class="col-span-full lg:col-span-3">
                                <div class="mb-3">
                                    <label for="tipoTramitacao" class="block mb-3">Tipo de Andamento</label>
                                    <Select id="tipoTramitacao" v-model="novaTramitacao.tipo" :options="tiposTramitacao" optionLabel="label" optionValue="value" placeholder="Selecione o tipo" fluid />
                                </div>
                                <div class="mb-3">
                                    <label for="setorDestino" class="block mb-3">Setor de tramitação</label>
                                    <Select
                                        v-if="unidadesSetor.length"
                                        id="setorDestino"
                                        v-model="novaTramitacao.unidade_destino_id"
                                        :options="unidadesSetor"
                                        optionLabel="label"
                                        optionValue="value"
                                        placeholder="Selecione o setor de destino"
                                        showClear
                                        fluid
                                    />
                                    <small v-else class="text-muted-color block">
                                        Nenhum setor cadastrado para este órgão.
                                        <router-link to="/gestao-setores" class="text-primary ml-1">
                                            Cadastrar em Gestão de Setores
                                        </router-link>
                                    </small>
                                </div>
                                <div>
                                    <label class="block mb-3"><i class="pi pi-paperclip"></i> Anexos</label>
                                    <FileUpload name="anexos" :multiple="true" accept="image/*,application/pdf" :maxFileSize="2000000" chooseLabel="Selecionar Anexos" :auto="false" :showUploadButton="false" @select="onTramitacaoFilesSelected" />
                                    <div v-if="novaTramitacao.anexos_arquivos.length > 0" class="mt-2 flex flex-wrap gap-2">
                                        <Tag
                                            v-for="file in novaTramitacao.anexos_arquivos"
                                            :key="file.name"
                                            :value="file.name"
                                            icon="pi pi-paperclip"
                                            removable
                                            @remove="novaTramitacao.anexos_arquivos = novaTramitacao.anexos_arquivos.filter((f) => f.name !== file.name)"
                                        />
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

        <Button v-else-if="podeIniciarExecucao" label="Iniciar Execução" icon="pi pi-play" severity="success" @click="iniciarExecucao" />

        <Button v-else icon="pi pi-arrow-left" @click="router.push('/demandas')" label="Voltar" />

        <Dialog v-model:visible="despachoDialog" header="Despachar demanda" :modal="true" style="width: 450px">
            <div class="flex flex-col gap-4">
                <p v-if="demanda" class="m-0 text-sm text-muted-color">
                    {{ demanda.protocolo_legislativo || `#${demanda.id}` }} — {{ demanda.titulo }}
                </p>
                <div>
                    <label for="secretariaDespacho" class="block mb-3">Enviar para a Secretaria</label>
                    <Select
                        id="secretariaDespacho"
                        v-model="despachoData.secretaria_id"
                        :options="todasSecretarias"
                        optionLabel="nome"
                        optionValue="id"
                        placeholder="Selecione uma secretaria"
                        fluid
                    />
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="despachoDialog = false" />
                <Button label="Confirmar despacho" icon="pi pi-check" @click="confirmarDespacho" />
            </template>
        </Dialog>
    </div>
</template>

<style scoped>
.demanda-descricao-html :deep(p) {
    margin: 0 0 0.75rem;
    line-height: 1.6;
}

.demanda-descricao-html :deep(p:last-child) {
    margin-bottom: 0;
}

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
.super-os-card {
    padding: 0.75rem 1rem;
}
.super-os-total {
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1;
    color: var(--p-primary-color);
}
.super-os-tag-btn {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
}
</style>
