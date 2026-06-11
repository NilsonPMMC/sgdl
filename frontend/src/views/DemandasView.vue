<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService.js';

import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import Toolbar from 'primevue/toolbar';
import Tag from 'primevue/tag';
import Dialog from 'primevue/dialog';
import Select from 'primevue/select';
import SelectButton from 'primevue/selectbutton';
import InputText from 'primevue/inputtext';
import Panel from 'primevue/panel';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import Message from 'primevue/message';
import Textarea from 'primevue/textarea';
import Checkbox from 'primevue/checkbox';

const DECLARACAO_ENVIO = 'ASSINO E ENVIO';

const demandas = ref([]);
const router = useRouter();
const route = useRoute();
const toast = useToast();
const confirm = useConfirm();
const userStore = useUserStore();
const loading = ref(true);
const erroCarregamento = ref(null);

const filtroMinhaUnidade = ref(true);
const filtroUnidadeId = ref(null);
const unidadesSetor = ref([]);

const despachoDialog = ref(false);
const superOsDialog = ref(false);
const demandaParaDespacho = ref(null);
const clusterParaDespacho = ref(null);
const todasSecretarias = ref([]);
const clustersFiltro = ref([]);

const aprovacaoDialog = ref(false);
const devolutivaDialog = ref(false);
const demandaParaDevolutiva = ref(null);
const devolutivaParecer = ref('');
const demandaParaAprovacao = ref(null);
const novaSecretariaId = ref(null);
const todosVereadores = ref([]);

const filtros = ref({
    q: null,
    status: null,
    secretaria_destino: null,
    autor: null,
    cluster: null,
    origem_vinculo: null,
    trilha: null
});

const painelFila = ref('protocolados');
const clockTick = ref(Date.now());
let clockInterval = null;

const opcoesPainel = [
    { label: 'Protocolados', value: 'protocolados', icon: 'pi pi-inbox' },
    { label: 'Operacionais', value: 'operacionais', icon: 'pi pi-cog' },
    { label: 'Devolutivas', value: 'devolutivas', icon: 'pi pi-reply' }
];

const isPainelProtocolo = computed(() =>
    ['PROTOCOLO', 'GESTOR'].includes(userStore.currentUser?.perfil)
);

const isSecretaria = computed(() => userStore.currentUser?.perfil === 'SECRETARIA');
const vinculoSecretaria = computed(() => userStore.currentUser?.vinculo_secretaria || null);
const vinculoSecretariaIncompleto = computed(
    () => vinculoSecretaria.value?.aplicavel && !vinculoSecretaria.value?.completo
);

const usaPainelFila = computed(() => isPainelProtocolo.value || isSecretaria.value);

const opcoesEscopoSecretaria = [
    { label: 'Meu setor', value: 'meu_setor' },
    { label: 'Toda secretaria', value: 'toda' }
];
const escopoSecretaria = ref('meu_setor');

const selectedDemandas = ref([]);
const envioLoteDialog = ref(false);
const previewLote = ref(null);
const carregandoPreviewLote = ref(false);
const enviandoLote = ref(false);
const declaracaoLoteAceita = ref(false);
const envioLotePendenteIds = ref([]);

const isVereadorOuGestor = computed(() =>
    ['VEREADOR', 'GESTOR'].includes(userStore.currentUser?.perfil)
);

const mostrarSelecaoLote = computed(() => {
    if (!isVereadorOuGestor.value) return false;
    if (filtros.value.status === 'RASCUNHO') return true;
    const qs = route.query?.status;
    return qs === 'RASCUNHO';
});

watch(mostrarSelecaoLote, (ativo) => {
    if (!ativo) selectedDemandas.value = [];
});

const showClusterFilter = computed(() =>
    ['GESTOR', 'PROTOCOLO'].includes(userStore.currentUser?.perfil)
);

const showSuperOsColumn = computed(() =>
    ['GESTOR', 'PROTOCOLO', 'SECRETARIA'].includes(userStore.currentUser?.perfil)
);

const podeAbrirGestorClusters = computed(() =>
    ['GESTOR', 'PROTOCOLO'].includes(userStore.currentUser?.perfil)
);

const podeDespacharSuperOs = (demanda) =>
    userStore.currentUser?.perfil === 'PROTOCOLO' &&
    demanda?.cluster?.id &&
    (demanda.cluster.demandas_count ?? 0) >= 2 &&
    !demanda.cluster.protocolo_super_os &&
    demanda.status === 'AGUARDANDO_PROTOCOLO';

const podeGerirTendencia = (demanda) =>
    userStore.currentUser?.perfil === 'PROTOCOLO' && Boolean(demanda?.tendencia_id);

const podeAcaoCluster = (demanda) =>
    userStore.currentUser?.perfil === 'PROTOCOLO' && Boolean(demanda?.cluster_acao_visivel);

const clusterComMinimo = (demanda) =>
    (demanda?.cluster?.demandas_count ?? 0) >= 2 || Boolean(demanda?.cluster?.protocolo_super_os);

const statusAbertos = [
    'AGUARDANDO_PROTOCOLO',
    'PROTOCOLADO',
    'EM_EXECUCAO',
    'AGUARDANDO_TRANSFERENCIA',
    'AGUARDANDO_DEVOLUTIVA_PROTOCOLO',
    'DEVOLVIDO_VEREADOR'
];

const formatTempoParado = (demanda) => {
    void clockTick.value;
    let segundos = demanda?.tempo_parado_segundos;
    if (segundos == null && demanda?.data_entrada_etapa) {
        const ref = new Date(demanda.data_entrada_etapa).getTime();
        segundos = Math.max(0, Math.floor((Date.now() - ref) / 1000));
    }
    if (segundos == null) return '—';
    const dias = Math.floor(segundos / 86400);
    const horas = Math.floor((segundos % 86400) / 3600);
    const minutos = Math.floor((segundos % 3600) / 60);
    if (dias > 0) return `${dias}d ${horas}h`;
    if (horas > 0) return `${horas}h ${minutos}min`;
    return `${minutos}min`;
};

const severidadeTempoParado = (demanda) => {
    void clockTick.value;
    let segundos = demanda?.tempo_parado_segundos;
    if (segundos == null && demanda?.data_entrada_etapa) {
        const ref = new Date(demanda.data_entrada_etapa).getTime();
        segundos = Math.max(0, Math.floor((Date.now() - ref) / 1000));
    }
    if (segundos == null) return 'secondary';
    if (segundos >= 72 * 3600) return 'danger';
    if (segundos >= 24 * 3600) return 'warn';
    return 'info';
};

const contagemPainelAtivo = computed(() => demandas.value.length);

const mensagemListaVazia = computed(() => {
    if (filtros.value.q) {
        return `Nenhum processo encontrado para «${filtros.value.q}». Revise a busca ou limpe os filtros.`;
    }
    if (isPainelProtocolo.value) {
        if (painelFila.value === 'protocolados') {
            return 'Nenhum processo aguardando despacho do Protocolo. Novos ofícios aparecem aqui após o envio oficial.';
        }
        if (painelFila.value === 'operacionais') {
            return 'Nenhum processo em tramitação operacional no momento.';
        }
        if (painelFila.value === 'devolutivas') {
            return 'Nenhuma devolutiva pendente. Processos concluídos pela secretaria aguardando resposta do Protocolo aparecem aqui.';
        }
    }
    if (isSecretaria.value) {
        if (escopoSecretaria.value === 'meu_setor') {
            return 'Nenhuma demanda no seu setor. Alterne para «Toda secretaria» ou confira se o setor está vinculado ao seu usuário em Gestão de Setores.';
        }
        if (filtroUnidadeId.value) {
            return 'Nenhuma demanda operacional neste setor com os filtros atuais.';
        }
        return 'Nenhuma demanda operacional na secretaria. Super OS aparecem apenas na demanda líder.';
    }
    if (userStore.currentUser?.perfil === 'VEREADOR') {
        return 'Você ainda não possui demandas. Use o Copiloto para criar um novo ofício.';
    }
    return 'Nenhuma demanda encontrada com os filtros atuais.';
});

const tituloPainelContexto = computed(() => {
    if (isSecretaria.value) {
        return escopoSecretaria.value === 'meu_setor' ? 'Fila do meu setor' : 'Fila operacional da secretaria';
    }
    if (painelFila.value === 'protocolados') return 'Fila de protocolados';
    if (painelFila.value === 'operacionais') return 'Fila operacional';
    if (painelFila.value === 'devolutivas') return 'Fila de devolutivas';
    return 'Demandas';
});

// Helper function para verificar se uma *única* demanda está atrasada
const isAtrasada = (demanda) => {
    // 1. O status deve estar "aberto"
    if (!statusAbertos.includes(demanda.status)) {
        // Ignora silenciosamente, pois não é um status "aberto"
        return false;
    }

    // 2. A demanda deve ter sido protocolada (ter data de início do prazo)
    if (!demanda.data_inicio_prazo) {
        return false;
    }

    // 3. O serviço associado deve ter um prazo definido
    if (!demanda.servico || typeof demanda.servico.prazo !== 'number') {
        return false;
    }

    const dataInicioPrazo = new Date(demanda.data_inicio_prazo);
    const prazoEmDias = demanda.servico.prazo;

    // 4. Calcula a data de vencimento
    const dataVencimento = new Date(dataInicioPrazo.getTime());
    dataVencimento.setDate(dataInicioPrazo.getDate() + prazoEmDias);
    return new Date() > dataVencimento;
};

const totalAbertos = computed(() => {
    return demandas.value.filter((d) => statusAbertos.includes(d.status)).length;
});

const totalFinalizados = computed(() => {
    return demandas.value.filter((d) => d.status === 'FINALIZADO').length;
});

const totalAtrasados = computed(() => {
    // Reutiliza a função helper
    return demandas.value.filter(isAtrasada).length;
});

const filtroHubAtrasadas = computed(() => route.query?.consulta === 'atrasadas');

const demandasExibidas = computed(() =>
    filtroHubAtrasadas.value ? demandas.value.filter(isAtrasada) : demandas.value
);

const limparFiltroHubAtrasadas = () => {
    const query = { ...route.query };
    delete query.consulta;
    router.replace({ name: 'demandas', query });
};

const statusOptions = ref([
    { label: 'Todos os Status', value: null },
    { label: 'Rascunho', value: 'RASCUNHO' },
    { label: 'Aguardando Protocolo', value: 'AGUARDANDO_PROTOCOLO' },
    { label: 'Protocolado', value: 'PROTOCOLADO' },
    { label: 'Em Execução', value: 'EM_EXECUCAO' },
    { label: 'Aguardando Transferência', value: 'AGUARDANDO_TRANSFERENCIA' },
    { label: 'Finalizado', value: 'FINALIZADO' },
    { label: 'Cancelado', value: 'CANCELADO' }
]);

const showVereadorFilter = computed(() => ['GESTOR', 'PROTOCOLO', 'SECRETARIA'].includes(userStore.currentUser?.perfil));

const getStatusSeverity = (demanda) => {
    // 1. Verifica o atraso PRIMEIRO
    if (isAtrasada(demanda)) {
        return 'danger'; // Vermelho para atrasados
    }

    // 2. Se não estiver atrasado, usa a lógica de status normal
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
    return map[demanda.status] || 'contrast';
};

const extrairMensagemErro = (error) => {
    const data = error?.response?.data;
    if (!data) return 'Não foi possível carregar as demandas. Verifique sua conexão e tente novamente.';
    if (typeof data.detail === 'string') return data.detail;
    if (typeof data.error === 'string') return data.error;
    if (Array.isArray(data) && data[0]) return String(data[0]);
    return 'Falha ao carregar demandas. Tente novamente.';
};

async function carregarDemandas() {
    loading.value = true;
    erroCarregamento.value = null;
    try {
        let params = { ...filtros.value };

        const currentUser = userStore.currentUser;
        if (!currentUser?.id) {
            loading.value = false;
            return;
        }

        switch (currentUser.perfil) {
            case 'VEREADOR':
                params.autor = currentUser.id;
                break;
            case 'SECRETARIA':
                if (currentUser.secretaria) {
                    params.secretaria_destino = currentUser.secretaria;
                    params.fila = 'operacionais';
                    delete params.status;
                    delete params.status__in;
                    if (escopoSecretaria.value === 'meu_setor') {
                        params.minha_unidade = '1';
                        delete params.unidade_administrativa;
                    } else {
                        delete params.minha_unidade;
                        if (filtroUnidadeId.value) {
                            params.unidade_administrativa = filtroUnidadeId.value;
                        }
                    }
                }
                break;
            case 'GESTOR':
            case 'PROTOCOLO':
                if (isPainelProtocolo.value && painelFila.value && !params.trilha) {
                    params.fila = painelFila.value;
                    delete params.status;
                    delete params.status__exclude;
                    if (painelFila.value === 'operacionais' && filtroUnidadeId.value) {
                        params.unidade_administrativa = filtroUnidadeId.value;
                    }
                } else if (params.status !== 'RASCUNHO') {
                    params.status__exclude = 'RASCUNHO';
                }
                break;
        }

        Object.keys(params).forEach((key) => (params[key] == null || params[key] === '') && delete params[key]);

        const response = await ApiService.getDemandas(params);
        demandas.value = response.data.results || response.data;
    } catch (error) {
        console.error('Erro ao buscar demandas:', error);
        demandas.value = [];
        erroCarregamento.value = extrairMensagemErro(error);
        toast.add({ severity: 'error', summary: 'Erro ao carregar', detail: erroCarregamento.value, life: 5000 });
    } finally {
        loading.value = false;
    }
}

const carregarUnidadesSetor = async () => {
    const orgaoId =
        userStore.currentUser?.secretaria ||
        userStore.currentUser?.sinapse_orgao_id;
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

const limparFiltros = () => {
    filtros.value = {
        q: null,
        status: null,
        secretaria_destino: null,
        autor: null,
        cluster: null,
        origem_vinculo: null,
        trilha: null
    };
    router.replace({ name: 'demandas', query: {} });
    carregarDemandas();
};

const TRILHA_META = {
    carta: {
        label: 'Trilha Carta',
        descricao: 'Demandas formalizadas com serviço da Carta Sinapse confirmado.',
        severity: 'info'
    },
    tendencia: {
        label: 'Trilha Tendência',
        descricao: 'Demandas formalizadas fora da carta — exigem triagem manual do Protocolo.',
        severity: 'warn'
    }
};

const trilhaAtiva = computed(() => {
    const t = (filtros.value.trilha || route.query?.trilha || '').toString().toLowerCase();
    return TRILHA_META[t] ? t : null;
});

const limparTrilha = () => {
    filtros.value.trilha = null;
    filtros.value.origem_vinculo = null;
    const query = { ...route.query };
    delete query.trilha;
    delete query.origem_vinculo;
    router.replace({ name: 'demandas', query });
    carregarDemandas();
};

function aplicarQueryRota() {
    const trilhaQs = route.query?.trilha;
    if (trilhaQs === 'carta' || trilhaQs === 'tendencia') {
        filtros.value.trilha = trilhaQs;
        filtros.value.origem_vinculo = null;
    } else {
        const ov = route.query?.origem_vinculo;
        if (ov === 'CARTA' || ov === 'TENDENCIA') {
            filtros.value.origem_vinculo = ov;
            filtros.value.trilha = ov === 'CARTA' ? 'carta' : 'tendencia';
        }
    }
}

const irCluster = (clusterId) => {
    if (clusterId) {
        router.push({ name: 'clusters', query: { id: String(clusterId) } });
    }
};

const acaoCluster = (demanda) => {
    if (podeDespacharSuperOs(demanda)) {
        abrirDialogoSuperOs(demanda);
        return;
    }
    if (demanda?.cluster?.id) {
        irCluster(demanda.cluster.id);
        return;
    }
    router.push({ name: 'clusters' });
};

const irGerirTendencia = (demanda) => {
    if (!demanda?.tendencia_id) return;
    router.push({ name: 'gestao-tendencias', query: { id: String(demanda.tendencia_id) } });
};

onMounted(() => {
    const qs = route.query?.status;
    if (typeof qs === 'string' && qs) {
        filtros.value.status = qs;
    }
    const filaQs = route.query?.fila;
    if (typeof filaQs === 'string' && ['protocolados', 'operacionais', 'devolutivas'].includes(filaQs)) {
        painelFila.value = filaQs;
    }
    if (route.query?.minha_unidade === '0') {
        escopoSecretaria.value = 'toda';
    }
    aplicarQueryRota();
    if (['SECRETARIA', 'PROTOCOLO', 'GESTOR'].includes(userStore.currentUser?.perfil)) {
        carregarUnidadesSetor();
    }
    carregarDemandas().then(() => tentarEnvioLoteDaQuery());
    clockInterval = setInterval(() => {
        clockTick.value = Date.now();
    }, 60_000);
    ApiService.getSecretarias().then((response) => {
        todasSecretarias.value = response.data;
    });
    if (showVereadorFilter.value) {
        ApiService.getUsuarios({ perfil: 'VEREADOR' }).then((response) => {
            todosVereadores.value = response.data;
        });
    }
    if (showClusterFilter.value) {
        ApiService.listarClusters()
            .then((response) => {
                const data = response.data;
                const lista = Array.isArray(data) ? data : data?.results || [];
                clustersFiltro.value = lista.map((c) => ({
                    label: c.protocolo_super_os
                        ? `${c.protocolo_super_os} — ${c.titulo}`
                        : `${c.titulo} (#${c.id})`,
                    value: c.id
                }));
            })
            .catch(() => {
                clustersFiltro.value = [];
            });
    }
});

onUnmounted(() => {
    if (clockInterval) clearInterval(clockInterval);
});

watch(
    () => [route.query.trilha, route.query.origem_vinculo],
    () => {
        aplicarQueryRota();
        carregarDemandas();
    }
);

watch(painelFila, (fila) => {
    if (!isPainelProtocolo.value) return;
    filtros.value.status = null;
    filtroUnidadeId.value = null;
    router.replace({ query: { ...route.query, fila } });
    carregarDemandas();
});

watch(escopoSecretaria, () => {
    if (!isSecretaria.value) return;
    filtroUnidadeId.value = null;
    router.replace({
        query: {
            ...route.query,
            fila: 'operacionais',
            minha_unidade: escopoSecretaria.value === 'meu_setor' ? '1' : '0'
        }
    });
    carregarDemandas();
});

watch(filtroUnidadeId, () => {
    if (isSecretaria.value && escopoSecretaria.value === 'toda') {
        carregarDemandas();
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
    secretaria_id: null
});

const abrirDialogoDespacho = (demanda) => {
    demandaParaDespacho.value = demanda;

    despachoData.value = {
        secretaria_id: demanda.servico?.secretaria_responsavel?.id || null
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

const abrirDialogoSuperOs = (demanda) => {
    clusterParaDespacho.value = demanda.cluster;
    despachoData.value = {
        secretaria_id: demanda.servico?.secretaria_responsavel?.id || null
    };
    superOsDialog.value = true;
};

const confirmarDespachoSuperOs = async () => {
    if (!despachoData.value.secretaria_id) {
        toast.add({ severity: 'warn', summary: 'Atenção', detail: 'Selecione a secretaria de destino.', life: 3000 });
        return;
    }
    try {
        const { data } = await ApiService.despacharClusterSuperOs(
            clusterParaDespacho.value.id,
            despachoData.value
        );
        const n = data?.total ?? data?.demandas_protocoladas?.length ?? 0;
        toast.add({
            severity: 'success',
            summary: 'Super OS despachada',
            detail: `${data?.protocolo_super_os || 'Lote'} — ${n} demanda(s) protocolada(s).`,
            life: 5000
        });
        superOsDialog.value = false;
        carregarDemandas();
    } catch (error) {
        const detail = error?.response?.data?.detail || 'Não foi possível despachar a Super OS.';
        toast.add({ severity: 'error', summary: 'Erro', detail, life: 4000 });
    }
};

const abrirDialogoDevolutiva = (demanda) => {
    demandaParaDevolutiva.value = demanda;
    devolutivaParecer.value = '';
    devolutivaDialog.value = true;
};

const confirmarDevolutiva = async () => {
    if ((devolutivaParecer.value || '').trim().length < 10) {
        toast.add({ severity: 'warn', summary: 'Parecer obrigatório', detail: 'Informe a resposta ao vereador.', life: 3000 });
        return;
    }
    try {
        await ApiService.despacharDevolutiva(demandaParaDevolutiva.value.id, {
            parecer_resposta: devolutivaParecer.value
        });
        toast.add({ severity: 'success', summary: 'Devolutiva enviada', life: 3000 });
        devolutivaDialog.value = false;
        carregarDemandas();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Falha ao despachar devolutiva.',
            life: 4000
        });
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

function idsDemandasSelecionadas(lista) {
    return (lista || []).map((d) => d.id).filter(Boolean);
}

async function abrirEnvioLote(listaOpcional) {
    const lista = listaOpcional?.length ? listaOpcional : selectedDemandas.value;
    const ids = idsDemandasSelecionadas(lista);
    if (ids.length < 2) {
        toast.add({
            severity: 'warn',
            summary: 'Seleção',
            detail: 'Selecione ao menos 2 rascunhos para envio em lote.',
            life: 4000
        });
        return;
    }
    envioLotePendenteIds.value = ids;
    previewLote.value = null;
    declaracaoLoteAceita.value = false;
    envioLoteDialog.value = true;
    carregandoPreviewLote.value = true;
    try {
        const { data } = await ApiService.previewEnvioLote(ids);
        previewLote.value = data;
    } catch (error) {
        envioLoteDialog.value = false;
        toast.add({
            severity: 'error',
            summary: 'Pré-visualização',
            detail: error?.response?.data?.detail || error?.response?.data?.error || 'Falha ao preparar o lote.',
            life: 6000
        });
    } finally {
        carregandoPreviewLote.value = false;
    }
}

async function abrirPreviewPdfLote(demandaId) {
    try {
        const { data } = await ApiService.previewEnvioOficialPdf(demandaId);
        const blob = new Blob([data], { type: 'application/pdf' });
        window.open(URL.createObjectURL(blob), '_blank', 'noopener');
    } catch {
        toast.add({ severity: 'error', summary: 'PDF', detail: 'Não foi possível abrir a pré-visualização.', life: 4000 });
    }
}

async function confirmarEnvioLote() {
    if (!declaracaoLoteAceita.value) {
        toast.add({
            severity: 'warn',
            summary: 'Declaração',
            detail: 'Marque a declaração de assinatura eletrônica para continuar.',
            life: 4000
        });
        return;
    }
    const ids = envioLotePendenteIds.value;
    const hashes = (previewLote.value?.itens || []).map((item) => ({
        demanda_id: item.demanda_id,
        hash_documento: item.hash_documento
    }));
    enviandoLote.value = true;
    try {
        const { data } = await ApiService.enviarDemandasLote({
            demanda_ids: ids,
            declaracao: DECLARACAO_ENVIO,
            hashes
        });
        envioLoteDialog.value = false;
        selectedDemandas.value = [];
        envioLotePendenteIds.value = [];
        await carregarDemandas();
        toast.add({
            severity: 'success',
            summary: 'Lote enviado',
            detail: `${data?.total || ids.length} ofício(s) assinado(s) e encaminhado(s) ao Protocolo.`,
            life: 6000
        });
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Envio em lote',
            detail: error?.response?.data?.error || error?.response?.data?.detail || 'Falha ao enviar o lote.',
            life: 6000
        });
    } finally {
        enviandoLote.value = false;
    }
}

async function tentarEnvioLoteDaQuery() {
    const raw = route.query?.enviar_lote;
    if (typeof raw !== 'string' || !raw.trim()) return;
    const ids = raw
        .split(',')
        .map((x) => parseInt(x.trim(), 10))
        .filter((n) => Number.isFinite(n));
    if (ids.length < 2) return;
    const selecionadas = demandas.value.filter((d) => ids.includes(d.id));
    if (selecionadas.length < 2) return;
    selectedDemandas.value = selecionadas;
    const query = { ...route.query };
    delete query.enviar_lote;
    router.replace({ name: 'demandas', query });
    await abrirEnvioLote(selecionadas);
}
</script>

<template>
    <div class="grid min-w-0">
        <div class="col-12 min-w-0">
            <div class="card min-w-0">
                <Toolbar class="mb-4">
                    <template #start>
                        <div>
                            <h5 class="m-0">Gestão de Demandas</h5>
                            <p v-if="isPainelProtocolo" class="text-sm text-muted-color m-0 mt-1">
                                Prioridade: processos com maior tempo de espera na etapa atual
                            </p>
                        </div>
                    </template>
                    <template #end>
                        <Button
                            v-if="mostrarSelecaoLote && selectedDemandas.length >= 2"
                            :label="`Assinar e enviar (${selectedDemandas.length})`"
                            icon="pi pi-send"
                            class="p-button-success mr-2"
                            @click="abrirEnvioLote()"
                        />
                        <Button
                            v-if="['VEREADOR', 'GESTOR'].includes(userStore.currentUser?.perfil)"
                            label="Novo ofício (Copiloto)"
                            icon="pi pi-comments"
                            class="p-button-success mr-2"
                            @click="router.push('/copiloto')"
                        />
                    </template>
                </Toolbar>

                <Message
                    v-if="trilhaAtiva"
                    :severity="TRILHA_META[trilhaAtiva].severity"
                    :closable="false"
                    class="mb-4 text-sm"
                >
                    <div class="flex flex-wrap items-center justify-between gap-2">
                        <span>
                            <strong>{{ TRILHA_META[trilhaAtiva].label }}</strong> —
                            {{ TRILHA_META[trilhaAtiva].descricao }}
                        </span>
                        <Button label="Limpar filtro de trilha" icon="pi pi-times" text size="small" @click="limparTrilha" />
                    </div>
                </Message>

                <div v-if="isPainelProtocolo" class="mb-4 flex flex-col gap-3">
                    <SelectButton
                        v-model="painelFila"
                        :options="opcoesPainel"
                        optionLabel="label"
                        optionValue="value"
                        :allowEmpty="false"
                    />
                    <Message severity="info" :closable="false" class="text-sm m-0">
                        <template v-if="painelFila === 'protocolados'">
                            <strong>{{ contagemPainelAtivo }}</strong> processo(s) aguardando triagem/despacho do
                            Protocolo — ordenados do mais antigo ao mais recente.
                        </template>
                        <template v-else-if="painelFila === 'operacionais'">
                            <strong>{{ contagemPainelAtivo }}</strong> processo(s) em tramitação operacional
                            (secretarias/setores) — priorize os com maior tempo parado.
                        </template>
                        <template v-else>
                            <strong>{{ contagemPainelAtivo }}</strong> devolutiva(s) pendente(s) — resposta da
                            secretaria aguardando despacho ao vereador.
                        </template>
                    </Message>
                    <div v-if="painelFila === 'operacionais' && unidadesSetor.length" class="flex flex-col gap-2 max-w-md">
                        <label class="text-sm font-medium">Filtrar por setor</label>
                        <Select
                            v-model="filtroUnidadeId"
                            :options="unidadesSetor"
                            optionLabel="label"
                            optionValue="value"
                            placeholder="Todos os setores"
                            showClear
                            fluid
                            @change="carregarDemandas"
                        />
                    </div>
                </div>

                <div v-if="isSecretaria" class="mb-4 flex flex-col gap-3">
                    <SelectButton
                        v-model="escopoSecretaria"
                        :options="opcoesEscopoSecretaria"
                        optionLabel="label"
                        optionValue="value"
                        :allowEmpty="false"
                    />
                    <Message severity="info" :closable="false" class="text-sm m-0">
                        <strong>{{ contagemPainelAtivo }}</strong> demanda(s) em
                        <strong>{{ tituloPainelContexto.toLowerCase() }}</strong>
                        — Super OS listam só a demanda líder; processos vinculados aparecem no detalhe.
                    </Message>
                    <div
                        v-if="escopoSecretaria === 'toda' && unidadesSetor.length"
                        class="flex flex-col gap-2 max-w-md"
                    >
                        <label class="text-sm font-medium">Setor específico</label>
                        <Select
                            v-model="filtroUnidadeId"
                            :options="unidadesSetor"
                            optionLabel="label"
                            optionValue="value"
                            placeholder="Todos os setores da secretaria"
                            showClear
                            fluid
                        />
                    </div>
                    <Message
                        v-if="escopoSecretaria === 'meu_setor' && vinculoSecretariaIncompleto && !loading"
                        severity="warn"
                        :closable="false"
                        class="text-sm m-0"
                    >
                        Vínculo incompleto:
                        {{ (vinculoSecretaria?.avisos || []).join(' ') }}
                        Solicite ao Gestor ou Protocolo a configuração em «Usuários secretaria».
                    </Message>
                    <Message
                        v-else-if="escopoSecretaria === 'meu_setor' && !unidadesSetor.length && !loading && !vinculoSecretariaIncompleto"
                        severity="warn"
                        :closable="false"
                        class="text-sm m-0"
                    >
                        Nenhum setor vinculado ao seu usuário.
                        <router-link to="/gestao-setores" class="text-primary ml-1">Cadastre em Gestão de Setores</router-link>
                        ou use «Toda secretaria».
                    </Message>
                </div>

                <Message
                    v-if="erroCarregamento && !loading"
                    severity="error"
                    :closable="false"
                    class="mb-4"
                >
                    <div class="flex flex-wrap items-center justify-between gap-3">
                        <span>{{ erroCarregamento }}</span>
                        <Button label="Tentar novamente" icon="pi pi-refresh" size="small" outlined @click="carregarDemandas" />
                    </div>
                </Message>

                <Message
                    v-else-if="!loading && demandas.length === 0"
                    severity="secondary"
                    :closable="false"
                    class="mb-4"
                >
                    {{ mensagemListaVazia }}
                </Message>

                <div class="grid grid-cols-12 gap-8 mb-4">
                    <Panel class="col-span-12 lg:col-span-6 xl:col-span-4">
                        <div class="flex justify-between mb-4">
                            <div>
                                <span class="block text-muted-color font-medium mb-4">Em Aberto</span>
                                <div class="text-surface-900 dark:text-surface-0 font-medium text-xl">{{ totalAbertos }}</div>
                            </div>
                            <div class="flex items-center justify-center bg-blue-100 rounded-border" style="width: 2.5rem; height: 2.5rem">
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
                            <div class="flex items-center justify-center bg-green-100 rounded-border" style="width: 2.5rem; height: 2.5rem">
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
                            <div class="flex items-center justify-center bg-red-100 rounded-border" style="width: 2.5rem; height: 2.5rem">
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
                        <div v-if="!isPainelProtocolo" class="flex flex-col gap-2 w-full">
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
                        <div v-if="showClusterFilter" class="flex flex-col gap-2 w-full">
                            <label for="cluster">Super OS (cluster)</label>
                            <Select
                                id="cluster"
                                v-model="filtros.cluster"
                                :options="clustersFiltro"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Todos"
                                showClear
                            />
                        </div>
                    </div>

                    <Button label="Filtrar" class="mr-3" icon="pi pi-filter" @click="carregarDemandas" />
                    <Button label="Limpar" icon="pi pi-times" @click="limparFiltros" class="p-button-outlined" />
                </Panel>

                <Message
                    v-if="filtroHubAtrasadas"
                    severity="warn"
                    :closable="true"
                    class="mb-3"
                    @close="limparFiltroHubAtrasadas"
                >
                    Exibindo apenas demandas com SLA vencido (atalho do hub de consulta).
                </Message>

                <div class="sgdl-datatable-host demandas-table-host">
                <DataTable
                    v-model:selection="selectedDemandas"
                    :value="demandasExibidas"
                    :loading="loading"
                    scrollable
                    class="sgdl-table-scroll"
                    :tableStyle="{ minWidth: '80rem', width: 'max-content' }"
                    paginator
                    :rows="10"
                    :rowsPerPageOptions="[5, 10, 20, 50]"
                    :dataKey="'id'"
                >
                    <Column
                        v-if="mostrarSelecaoLote"
                        selectionMode="multiple"
                        headerStyle="width: 3rem"
                    />
                    <Column field="protocolo_legislativo" header="Ofício" :sortable="true" style="min-width: 9rem"></Column>
                    <Column field="protocolo_executivo" header="Protocolo" :sortable="true" style="min-width: 7rem"></Column>
                    <Column field="data_criacao" header="Criado em" :sortable="true" style="min-width: 7rem">
                        <template #body="{ data }">
                            {{ new Date(data.data_criacao).toLocaleDateString('pt-BR') }}
                        </template>
                    </Column>
                    <Column field="titulo" header="Título" :sortable="true" style="min-width: 14rem">
                        <template #body="{ data }">
                            <div class="flex flex-col gap-1">
                                <span>{{ data.titulo }}</span>
                                <Tag
                                    v-if="isPainelProtocolo && data.fluxo_automatico"
                                    value="Fluxo auto"
                                    severity="success"
                                    class="w-fit text-xs"
                                    v-tooltip.top="'Será protocolado automaticamente ao receber o ofício'"
                                />
                            </div>
                        </template>
                    </Column>
                    <Column field="status" header="Status" :sortable="!isPainelProtocolo" style="min-width: 9rem">
                        <template #body="{ data }">
                            <div class="flex flex-col items-start gap-1">
                                <Tag
                                    :value="isAtrasada(data) ? 'ATRASADO' : data.status_display"
                                    :severity="getStatusSeverity(data)"
                                />
                            </div>
                        </template>
                    </Column>
                    <Column v-if="usaPainelFila" header="Setor" style="min-width: 8rem">
                        <template #body="{ data }">
                            <span v-if="data.unidade_administrativa">
                                {{ data.unidade_administrativa.sigla || data.unidade_administrativa.nome }}
                            </span>
                            <span v-else class="text-muted-color text-sm">—</span>
                        </template>
                    </Column>
                    <Column v-if="usaPainelFila" header="Parado há" style="min-width: 7rem">
                        <template #body="{ data }">
                            <Tag
                                :value="formatTempoParado(data)"
                                :severity="severidadeTempoParado(data)"
                                v-tooltip.top="
                                    data.data_entrada_etapa
                                        ? `Desde ${new Date(data.data_entrada_etapa).toLocaleString('pt-BR')}`
                                        : 'Tempo na etapa atual'
                                "
                            />
                        </template>
                    </Column>
                    <Column field="secretaria_destino.nome" header="Secretaria Destino" style="min-width: 11rem"></Column>
                    <Column v-if="showSuperOsColumn" header="Super OS" style="min-width: 10rem">
                        <template #body="{ data }">
                            <template v-if="(data.super_os?.ativo) || (data.cluster && clusterComMinimo(data))">
                                <div class="flex flex-col gap-1 items-start">
                                    <Button
                                        v-if="(data.super_os?.protocolo_super_os || data.cluster?.protocolo_super_os) && podeAbrirGestorClusters"
                                        :label="data.super_os?.protocolo_super_os || data.cluster.protocolo_super_os"
                                        link
                                        size="small"
                                        class="p-0"
                                        @click="irCluster(data.cluster.id)"
                                    />
                                    <Button
                                        v-else-if="data.super_os?.protocolo_super_os || data.cluster?.protocolo_super_os"
                                        :label="data.super_os?.protocolo_super_os || data.cluster.protocolo_super_os"
                                        link
                                        size="small"
                                        class="p-0"
                                        @click="visualizarDemanda(data.id)"
                                        v-tooltip.top="'Abrir demanda líder da Super OS'"
                                    />
                                    <Tag
                                        v-if="(data.super_os?.total_vinculados || data.cluster?.demandas_count) >= 2"
                                        :value="`${data.super_os?.total_vinculados || data.cluster.demandas_count} vinculados`"
                                        severity="info"
                                        class="text-xs"
                                    />
                                </div>
                            </template>
                            <span v-else class="text-muted-color text-sm">—</span>
                        </template>
                    </Column>
                    <Column field="autor.first_name" header="Autor" style="min-width: 8rem"></Column>

                    <Column header="Ações" :style="{ minWidth: isPainelProtocolo ? '14rem' : '12rem' }">
                        <template #body="slotProps">
                            <template v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && isPainelProtocolo">
                                <Button
                                    v-if="podeAcaoCluster(slotProps.data)"
                                    icon="pi pi-sitemap"
                                    severity="help"
                                    text
                                    rounded
                                    @click="acaoCluster(slotProps.data)"
                                    v-tooltip.top="
                                        podeDespacharSuperOs(slotProps.data)
                                            ? 'Cluster — Despachar Super OS'
                                            : 'Cluster — ver agrupamento'
                                    "
                                />
                                <Button
                                    v-if="slotProps.data.status === 'AGUARDANDO_PROTOCOLO'"
                                    icon="pi pi-send"
                                    severity="success"
                                    text
                                    rounded
                                    @click="abrirDialogoDespacho(slotProps.data)"
                                    v-tooltip.top="'Enviar — despachar ao setor'"
                                />
                                <Button
                                    v-if="podeGerirTendencia(slotProps.data)"
                                    icon="pi pi-compass"
                                    severity="info"
                                    text
                                    rounded
                                    @click="irGerirTendencia(slotProps.data)"
                                    v-tooltip.top="'Gerir tendência'"
                                />
                                <Button
                                    v-if="slotProps.data.status === 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO'"
                                    icon="pi pi-reply"
                                    severity="info"
                                    text
                                    rounded
                                    @click="abrirDialogoDevolutiva(slotProps.data)"
                                    v-tooltip.top="'Despachar devolutiva ao vereador'"
                                />
                                <Button
                                    v-if="slotProps.data.status === 'AGUARDANDO_TRANSFERENCIA'"
                                    icon="pi pi-check-circle"
                                    severity="warning"
                                    text
                                    rounded
                                    @click="abrirDialogoAprovarTransferencia(slotProps.data)"
                                    v-tooltip.top="'Revisar transferência'"
                                />
                                <Button
                                    icon="pi pi-eye"
                                    severity="secondary"
                                    text
                                    rounded
                                    @click="visualizarDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Ver — acompanhar'"
                                />
                            </template>
                            <template v-else>
                                <Button
                                    v-if="['VEREADOR', 'GESTOR'].includes(userStore.currentUser?.perfil) && slotProps.data.status === 'RASCUNHO'"
                                    icon="pi pi-pencil"
                                    text
                                    rounded
                                    @click="editarDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Editar rascunho'"
                                />
                                <Button
                                    v-if="userStore.currentUser?.perfil === 'VEREADOR' && slotProps.data.status === 'RASCUNHO'"
                                    icon="pi pi-trash"
                                    severity="danger"
                                    text
                                    rounded
                                    @click="excluirDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Excluir'"
                                />
                                <Button
                                    v-if="podeDespacharSuperOs(slotProps.data)"
                                    icon="pi pi-sitemap"
                                    severity="help"
                                    text
                                    rounded
                                    @click="abrirDialogoSuperOs(slotProps.data)"
                                    v-tooltip.top="'Despachar Super OS (lote)'"
                                />
                                <Button
                                    v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && slotProps.data.status === 'AGUARDANDO_PROTOCOLO'"
                                    icon="pi pi-send"
                                    severity="success"
                                    text
                                    rounded
                                    @click="abrirDialogoDespacho(slotProps.data)"
                                    v-tooltip.top="'Despachar (unitário)'"
                                />
                                <Button
                                    v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && slotProps.data.status === 'AGUARDANDO_TRANSFERENCIA'"
                                    icon="pi pi-check-circle"
                                    severity="warning"
                                    text
                                    rounded
                                    @click="abrirDialogoAprovarTransferencia(slotProps.data)"
                                    v-tooltip.top="'Revisar Transferência'"
                                />
                                <Button
                                    v-if="slotProps.data.status !== 'RASCUNHO'"
                                    icon="pi pi-eye"
                                    severity="secondary"
                                    text
                                    rounded
                                    @click="visualizarDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Visualizar'"
                                />
                            </template>
                        </template>
                    </Column>
                </DataTable>
                </div>

                <Dialog
                    v-model:visible="superOsDialog"
                    header="Despachar Super Ordem de Serviço"
                    :modal="true"
                    style="width: 480px"
                >
                    <div v-if="clusterParaDespacho" class="flex flex-col gap-4">
                        <p class="m-0 text-sm text-muted-color">
                            Protocola em lote todas as demandas
                            <strong>aguardando protocolo</strong> do cluster
                            <strong>{{ clusterParaDespacho.titulo }}</strong>
                            (#{{ clusterParaDespacho.id }}). Gera um protocolo Super OS único no SGDL.
                        </p>
                        <div>
                            <label for="secretaria_super" class="block mb-3">Secretaria de destino</label>
                            <Select
                                id="secretaria_super"
                                v-model="despachoData.secretaria_id"
                                :options="todasSecretarias"
                                optionLabel="nome"
                                optionValue="id"
                                placeholder="Selecione"
                                fluid
                            />
                        </div>
                    </div>
                    <template #footer>
                        <Button label="Cancelar" icon="pi pi-times" text @click="superOsDialog = false" />
                        <Button label="Confirmar Super OS" icon="pi pi-sitemap" @click="confirmarDespachoSuperOs" />
                    </template>
                </Dialog>

                <Dialog v-model:visible="despachoDialog" header="Despachar Demanda" :modal="true" style="width: 450px">
                    <div class="flex flex-col gap-4">
                        <div>
                            <label for="secretaria" class="block mb-3">Enviar para a Secretaria</label>
                            <Select id="secretaria" v-model="despachoData.secretaria_id" :options="todasSecretarias" optionLabel="nome" optionValue="id" placeholder="Selecione uma secretaria" fluid />
                        </div>
                    </div>
                    <template #footer>
                        <Button label="Cancelar" icon="pi pi-times" text @click="despachoDialog = false" />
                        <Button label="Confirmar Despacho" icon="pi pi-check" @click="confirmarDespacho" />
                    </template>
                </Dialog>

                <Dialog v-model:visible="devolutivaDialog" header="Despachar devolutiva ao vereador" :modal="true" style="width: 520px">
                    <div v-if="demandaParaDevolutiva" class="flex flex-col gap-3">
                        <p class="m-0 text-sm text-muted-color">
                            Demanda {{ demandaParaDevolutiva.protocolo_executivo }} — autor:
                            {{ demandaParaDevolutiva.autor?.first_name || demandaParaDevolutiva.autor?.username }}
                        </p>
                        <Textarea
                            v-model="devolutivaParecer"
                            rows="5"
                            class="w-full"
                            placeholder="Resposta do Protocolo ao vereador (parecer de devolutiva)..."
                        />
                    </div>
                    <template #footer>
                        <Button label="Cancelar" icon="pi pi-times" text @click="devolutivaDialog = false" />
                        <Button label="Enviar devolutiva" icon="pi pi-reply" @click="confirmarDevolutiva" />
                    </template>
                </Dialog>

                <Dialog v-model:visible="aprovacaoDialog" header="Aprovar Transferência" :modal="true" style="width: 450px">
                    <div v-if="demandaParaAprovacao">
                        <p class="mb-4">
                            A secretaria <strong>{{ demandaParaAprovacao.secretaria_destino?.nome }}</strong> solicitou a transferência. Selecione a nova secretaria.
                        </p>
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

                <Dialog
                    v-model:visible="envioLoteDialog"
                    header="Assinatura eletrônica em lote"
                    :modal="true"
                    style="width: 560px"
                >
                    <div class="flex flex-col gap-4">
                        <Message severity="info" :closable="false" class="text-sm m-0">
                            Revise cada ofício abaixo. Uma única declaração assina
                            <strong>{{ envioLotePendenteIds.length }}</strong> envio(s) oficial(is).
                        </Message>
                        <div v-if="carregandoPreviewLote" class="text-sm text-muted-color">
                            Gerando pré-visualizações…
                        </div>
                        <ul v-else-if="previewLote?.itens?.length" class="list-none p-0 m-0 flex flex-col gap-2 max-h-64 overflow-y-auto">
                            <li
                                v-for="item in previewLote.itens"
                                :key="item.demanda_id"
                                class="flex flex-wrap items-center justify-between gap-2 py-2 border-b border-surface-200 last:border-0"
                            >
                                <div class="min-w-0 flex-1">
                                    <span class="font-medium text-sm">{{ item.titulo }}</span>
                                    <p class="m-0 text-xs text-muted-color break-all">
                                        Hash: {{ item.hash_documento?.slice(0, 16) }}…
                                    </p>
                                </div>
                                <Button
                                    label="PDF"
                                    icon="pi pi-file-pdf"
                                    text
                                    size="small"
                                    @click="abrirPreviewPdfLote(item.demanda_id)"
                                />
                            </li>
                        </ul>
                        <div class="flex items-start gap-2">
                            <Checkbox v-model="declaracaoLoteAceita" inputId="declaracao_lote" binary />
                            <label for="declaracao_lote" class="text-sm cursor-pointer">
                                Declaro que li os ofícios, concordo com o conteúdo e
                                <strong>assino eletronicamente</strong> todos os envios ({{ DECLARACAO_ENVIO }}).
                            </label>
                        </div>
                    </div>
                    <template #footer>
                        <Button label="Cancelar" icon="pi pi-times" text @click="envioLoteDialog = false" />
                        <Button
                            label="Assino e envio todos"
                            icon="pi pi-check"
                            :loading="enviandoLote"
                            :disabled="carregandoPreviewLote || !declaracaoLoteAceita"
                            @click="confirmarEnvioLote"
                        />
                    </template>
                </Dialog>
            </div>
        </div>
    </div>
</template>

<style scoped>
.demandas-table-host :deep(.p-datatable-table-container) {
    overflow-x: auto !important;
}

.demandas-table-host :deep(.p-datatable-table) {
    width: max-content !important;
    min-width: 80rem;
}
</style>
