<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService.js';
import {
    DECLARACAO_DESPACHO,
    DECLARACAO_GESTOR_PROTOCOLO,
    DECLARACAO_DEVOLUTIVA,
    DECLARACAO_CONCLUSAO_FINAL,
    CONTEXTO_ASSINATURA,
    badgeAssinaturaProtocolo,
    despachoInicialPendenteGestor,
    gestorPorId,
    modoPainelAssinaturaProtocolo,
    MODO_PAINEL_ASSINATURA,
    usuarioPodePainelProtocoloCentral,
    validarAssinaturaFormulario,
    payloadAssinaturaProtocolo,
    mensagemErroAssinatura
} from '@/constants/assinaturaEletronica';
import { payloadDespachoDestinos, buildDevolutivaPayload, estadoFormularioDevolutiva } from '@/utils/protocoloFormData';
import { filtrarArquivosDuplicados, mensagemAnexosRejeitados } from '@/utils/anexoValidacao';
import { formatarProtocoloLegislativo } from '@/utils/protocoloLegislativo';
import { buildContextoPlaceholders } from '@/constants/textoPadraoDespacho';
import FormularioTramitacao from '@/components/tramitacao/FormularioTramitacao.vue';
import FormularioDevolutivaProtocolo from '@/components/devolutiva/FormularioDevolutivaProtocolo.vue';
import DialogAssinaturaEletronica from '@/components/tramitacao/DialogAssinaturaEletronica.vue';
import DialogClusterAderencia from '@/components/demanda/DialogClusterAderencia.vue';
import {
    estadoFormularioTramitacao,
    inicializarDestinosDespacho,
    contarPernasDestinos,
    despachoEhTransversal,
    MAX_PERNAS_DESPACHO,
    MODO_DESPACHO,
    resumoDestinosTexto
} from '@/constants/tramitacaoFormulario';
import {
    rotuloFluxo
} from '@/constants/operacionalEstado';
import { ocultarMetricasSla, isDemandaAtrasadaParaExibicao } from '@/utils/metricasSlaVereador';

import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import Toolbar from 'primevue/toolbar';
import Tag from 'primevue/tag';
import Dialog from 'primevue/dialog';
import Select from 'primevue/select';
import MultiSelect from 'primevue/multiselect';
import SelectButton from 'primevue/selectbutton';
import InputText from 'primevue/inputtext';
import Panel from 'primevue/panel';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import Message from 'primevue/message';
import Checkbox from 'primevue/checkbox';
import ProgressSpinner from 'primevue/progressspinner';

const DECLARACAO_ENVIO = 'ASSINO E ENVIO';

const demandas = ref([]);
const router = useRouter();
const route = useRoute();
const toast = useToast();
const confirm = useConfirm();
const userStore = useUserStore();

const ocultarSlaVereador = computed(() => ocultarMetricasSla(userStore.currentUser?.perfil));
const loading = ref(false);
const erroCarregamento = ref(null);
const sincronizandoDemandasRota = ref(true);

const filtroMinhaUnidade = ref(true);
const filtroUnidadeId = ref(null);
const filtroUnidadesIds = ref([]);
const unidadesSetor = ref([]);

const despachoDialog = ref(false);
const assinaturaDespachoDialogVisible = ref(false);
const assinaturaDevolutivaDialogVisible = ref(false);
const executandoAssinatura = ref(false);
const superOsDialog = ref(false);
const clusterAderenciaDialog = ref(false);
const clusterAderenciaSituacao = ref(null);
const clusterAderenciaLoading = ref(false);
const demandaParaDespacho = ref(null);
const clusterParaDespacho = ref(null);
const despachoPreview = ref(null);
const despachoAssinatura = ref({ declaracaoOperador: false, declaracaoGestor: false, gestor_protocolo_id: null });
const gestoresProtocolo = ref([]);
const carregandoDespachoPreview = ref(false);
const todasSecretarias = ref([]);
const clustersFiltro = ref([]);

const aprovacaoDialog = ref(false);
const devolutivaDialog = ref(false);
const demandaParaDevolutiva = ref(null);
const devolutivaDemandaContext = computed(() => {
    const d = demandaParaDevolutiva.value;
    return d ? buildContextoPlaceholders(d) : {};
});
const despachoDemandaContext = computed(() => {
    const d = demandaParaDespacho.value;
    return d ? buildContextoPlaceholders(d) : {};
});
const formDevolutiva = ref(estadoFormularioDevolutiva());
const formDevolutivaRef = ref(null);
const devolutivaPreview = ref(null);
const devolutivaAssinatura = ref({
    declaracaoOperador: false,
    declaracaoGestor: false,
    gestor_protocolo_id: null
});
const carregandoDevolutivaPreview = ref(false);
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
    { label: 'Devolutivas', value: 'devolutivas', icon: 'pi pi-reply' },
    { label: 'Stand-by (estudo)', value: 'stand_by', icon: 'pi pi-pause-circle' },
    { label: 'Finalizados', value: 'finalizados', icon: 'pi pi-check-circle' }
];

const FILAS_GESTOR_SETORIAL = ['operacionais', 'stand_by', 'finalizados'];

const podePainelProtocoloCentral = computed(() =>
    usuarioPodePainelProtocoloCentral(userStore.currentUser, userStore)
);

const isPainelProtocolo = computed(
    () =>
        userStore.currentUser?.perfil === 'PROTOCOLO' || podePainelProtocoloCentral.value
);

const isPainelGestorSetorial = computed(
    () => userStore.currentUser?.perfil === 'GESTOR' && !podePainelProtocoloCentral.value
);

const exibirPainelFilas = computed(
    () => isPainelProtocolo.value || isPainelGestorSetorial.value
);

const opcoesPainelVisiveis = computed(() => {
    if (isPainelGestorSetorial.value) {
        return opcoesPainel.filter((o) => FILAS_GESTOR_SETORIAL.includes(o.value));
    }
    if (isPainelProtocolo.value) {
        return opcoesPainel;
    }
    return [];
});

const isCamara = computed(() => userStore.currentUser?.perfil === 'CAMARA');
const isSecretaria = computed(() => userStore.currentUser?.perfil === 'SECRETARIA');
const tituloPaginaDemandas = computed(() =>
    isCamara.value ? 'Indicações legislativas' : 'Gestão de Demandas'
);
const vinculoSecretaria = computed(() => userStore.currentUser?.vinculo_secretaria || null);
const vinculoSecretariaIncompleto = computed(
    () => vinculoSecretaria.value?.aplicavel && !vinculoSecretaria.value?.completo
);

const usaPainelFila = computed(
    () => isPainelProtocolo.value || isSecretaria.value || isPainelGestorSetorial.value
);

const opcoesEscopoOperacional = computed(() => {
    const opcoes = [
        { label: 'Em operação', value: 'em_operacao' },
        { label: 'Acompanhando', value: 'acompanhando' }
    ];
    if (isSecretaria.value) {
        opcoes.push({ label: 'Encerrado', value: 'encerrado' });
    }
    return opcoes;
});
const escopoSecretaria = ref('em_operacao');
const filtroStandByEstudo = ref(false);

const exibirEscopoOperacional = computed(() => {
    if (isSecretaria.value) return true;
    if (isPainelGestorSetorial.value) return painelFila.value === 'operacionais';
    return isPainelProtocolo.value && painelFila.value === 'operacionais';
});

const exibirFiltroSetores = computed(
    () => isSecretaria.value || isPainelGestorSetorial.value || isPainelProtocolo.value
);

const statusFinalizadoLista = ['FINALIZADO'];

const podeGerenciarAcompanhamentoLista = computed(
    () => ['SECRETARIA', 'GESTOR'].includes(userStore.currentUser?.perfil)
);

function podeAcaoAcompanhamentoRapida(demanda) {
    if (!podeGerenciarAcompanhamentoLista.value) return false;
    if (statusFinalizadoLista.includes(demanda?.status)) return false;
    return Boolean(demanda?.acompanhando || demanda?.pode_acompanhar);
}

async function alternarAcompanhamentoLista(demanda) {
    if (!demanda?.id || !podeAcaoAcompanhamentoRapida(demanda)) return;
    try {
        if (demanda.acompanhando) {
            await ApiService.desacompanharDemanda(demanda.id);
            toast.add({
                severity: 'info',
                summary: 'Acompanhamento',
                detail: 'Processo desfixado.',
                life: 3500
            });
        } else {
            await ApiService.acompanharDemanda(demanda.id, { origem: 'MANUAL' });
            toast.add({
                severity: 'success',
                summary: 'Acompanhamento',
                detail: 'Processo fixado. Veja em «Acompanhando».',
                life: 3500
            });
            if (escopoSecretaria.value === 'encerrado') {
                escopoSecretaria.value = 'acompanhando';
                return;
            }
        }
        await carregarDemandas();
    } catch (err) {
        toast.add({
            severity: 'warn',
            summary: 'Acompanhamento',
            detail: err?.response?.data?.detail || 'Não foi possível atualizar o acompanhamento.',
            life: 4000
        });
    }
}

const selectedDemandas = ref([]);
const envioLoteDialog = ref(false);
const previewLote = ref(null);
const carregandoPreviewLote = ref(false);
const enviandoLote = ref(false);
const declaracaoLoteAceita = ref(false);
const envioLotePendenteIds = ref([]);

const alertasDuplicidadeLote = computed(() => {
    const itens = previewLote.value?.itens || [];
    const alertas = [];
    for (const item of itens) {
        for (const a of item.alertas_duplicidade || []) {
            alertas.push({ ...a, demanda_envio_id: item.demanda_id, demanda_envio_titulo: item.titulo });
        }
    }
    return alertas;
});

const duplicidadeLoteSugerirNaoEnviar = computed(() =>
    (previewLote.value?.itens || []).some((item) => item.duplicidade_resumo?.sugerir_nao_enviar)
);

const isVereadorOuGestor = computed(() =>
    ['VEREADOR', 'GESTOR'].includes(userStore.currentUser?.perfil)
);

const isCriadorLegislativoLote = computed(() =>
    ['VEREADOR', 'GESTOR', 'CAMARA'].includes(userStore.currentUser?.perfil)
);

const mostrarSelecaoLote = computed(() => {
    if (!isCriadorLegislativoLote.value) return false;
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
    ['GESTOR', 'PROTOCOLO', 'SECRETARIA'].includes(userStore.currentUser?.perfil)
);

const podeDespacharSuperOs = (demanda) =>
    userStore.currentUser?.perfil === 'PROTOCOLO' &&
    demanda?.cluster?.id &&
    (demanda.cluster.demandas_count ?? 0) >= 2 &&
    !demanda.cluster.protocolo_super_os &&
    demanda.status === 'AGUARDANDO_PROTOCOLO' &&
    demanda.super_os?.eh_lider !== false;

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

const exibirTempoExecucaoTotal = computed(
    () => exibirPainelFilas.value && painelFila.value === 'finalizados'
);

const formatDuracaoSegundos = (segundos) => {
    if (segundos == null) return '—';
    const dias = Math.floor(segundos / 86400);
    const horas = Math.floor((segundos % 86400) / 3600);
    const minutos = Math.floor((segundos % 3600) / 60);
    if (dias > 0) return `${dias}d ${horas}h`;
    if (horas > 0) return `${horas}h ${minutos}min`;
    return `${minutos}min`;
};

const formatTempoParado = (demanda) => {
    void clockTick.value;
    let segundos = demanda?.tempo_parado_segundos;
    if (segundos == null && demanda?.data_entrada_etapa) {
        const ref = new Date(demanda.data_entrada_etapa).getTime();
        segundos = Math.max(0, Math.floor((Date.now() - ref) / 1000));
    }
    return formatDuracaoSegundos(segundos);
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

const resolverTempoExecucaoSegundos = (demanda) => {
    let segundos = demanda?.tempo_execucao_segundos;
    if (segundos != null) return segundos;
    if (!demanda?.data_finalizacao) return null;
    const fim = new Date(demanda.data_finalizacao).getTime();
    const inicioRef = demanda.data_inicio_prazo || demanda.data_criacao;
    if (!inicioRef) return null;
    const inicio = new Date(inicioRef).getTime();
    return Math.max(0, Math.floor((fim - inicio) / 1000));
};

const formatTempoExecucaoTotal = (demanda) => {
    const segundos = resolverTempoExecucaoSegundos(demanda);
    if (segundos == null) return '—';
    return `Total ${formatDuracaoSegundos(segundos)}`;
};

const severidadeTempoExecucao = (demanda) => {
    const segundos = resolverTempoExecucaoSegundos(demanda);
    if (segundos == null) return 'secondary';
    const prazoDias = demanda?.prazo_efetivo_dias ?? demanda?.servico?.prazo;
    if (prazoDias && segundos > prazoDias * 86400) return 'warn';
    return 'success';
};

const tooltipTempoColuna = (demanda) => {
    if (exibirTempoExecucaoTotal.value) {
        const inicioRef = demanda?.data_inicio_prazo || demanda?.data_criacao;
        if (inicioRef && demanda?.data_finalizacao) {
            const inicio = new Date(inicioRef).toLocaleString('pt-BR');
            const fim = new Date(demanda.data_finalizacao).toLocaleString('pt-BR');
            return `Total: ${inicio} → ${fim}`;
        }
        return 'Tempo total de execução do processo';
    }
    if (demanda?.data_entrada_etapa) {
        return `Desde ${new Date(demanda.data_entrada_etapa).toLocaleString('pt-BR')}`;
    }
    return 'Tempo na etapa atual';
};

function rotuloLocalizacaoItem(item) {
    if (!item) return '—';
    const base = rotuloCompactoLocalizacao(item);
    if (item.quantidade > 1) return `${base}×${item.quantidade}`;
    return base;
}

function rotuloCompactoLocalizacao(item) {
    if (!item) return '—';
    let base = item.setor_sigla || item.setor_nome || item.orgao_nome || '—';
    if (base.startsWith('MCRUZ-')) base = base.slice(6);
    if (base.length > 14) base = `${base.slice(0, 12)}…`;
    return base;
}

function escapeHtml(texto) {
    return String(texto ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function rotuloStatusLocalizacao(item) {
    if (item.tipo === 'no') {
        return item.aberto === false ? 'Concluído' : 'Aberto';
    }
    if (item.tipo === 'perna') {
        return item.aberto === false ? 'Perna concluída' : 'Perna em execução';
    }
    if (item.tipo === 'direto') {
        return 'Fluxo direto';
    }
    return item.aberto === false ? 'Concluído' : 'Em operação';
}

function htmlTooltipLocalizacao(demanda) {
    const itens = localizacaoOperacionalLinha(demanda);
    if (!itens.length) return '';

    const linhas = itens
        .map((item) => {
            const sigla = item.setor_sigla || item.setor_nome || item.orgao_nome || '—';
            const orgao = item.orgao_nome || '';
            const status = rotuloStatusLocalizacao(item);
            const badgeClass =
                item.aberto === false
                    ? 'sgdl-loc-tip__badge--fechado'
                    : 'sgdl-loc-tip__badge--aberto';
            const qtd =
                item.quantidade > 1
                    ? `<span class="sgdl-loc-tip__qtd">${item.quantidade}×</span>`
                    : '';

            return `<div class="sgdl-loc-tip__item">
                <div class="sgdl-loc-tip__row">
                    <span class="sgdl-loc-tip__sigla">${escapeHtml(sigla)}</span>
                    ${qtd}
                    <span class="sgdl-loc-tip__badge ${badgeClass}">${escapeHtml(status)}</span>
                </div>
                ${orgao ? `<div class="sgdl-loc-tip__orgao">${escapeHtml(orgao)}</div>` : ''}
            </div>`;
        })
        .join('');

    return `<div class="sgdl-loc-tip">${linhas}</div>`;
}

function tooltipLocalizacaoConfig(demanda) {
    const html = htmlTooltipLocalizacao(demanda);
    if (!html) return null;
    return {
        value: html,
        escape: false,
        class: 'sgdl-tooltip-localizacao',
        fitContent: false,
        showDelay: 150
    };
}

function localizacaoOperacionalLinha(demanda) {
    const itens = demanda?.setores_operacionais_abertos;
    if (itens?.length) return itens;
    if (demanda?.unidade_administrativa) {
        const u = demanda.unidade_administrativa;
        return [{
            setor_sigla: u.sigla,
            setor_nome: u.nome,
            orgao_nome: '',
            aberto: true,
            tipo: 'direto',
            quantidade: 1
        }];
    }
    return [];
}

const LOCALIZACAO_MAX_CHIPS = 2;

function resumoLocalizacaoCelula(demanda) {
    const itens = localizacaoOperacionalLinha(demanda);
    if (!itens.length) {
        return { visiveis: [], extras: 0 };
    }
    return {
        visiveis: itens.slice(0, LOCALIZACAO_MAX_CHIPS),
        extras: Math.max(0, itens.length - LOCALIZACAO_MAX_CHIPS)
    };
}

const colunaLocalizacaoHeader = computed(() => {
    if (isSecretaria.value && escopoSecretaria.value === 'encerrado') {
        return 'Setor destino';
    }
    if (usaPainelFila.value && painelFila.value === 'operacionais') {
        return 'Onde está';
    }
    return 'Setor';
});

const contadoresResumo = ref({ abertos: 0, finalizados: 0, atrasados: 0 });
const tablePagination = ref({ first: 0, rows: 25 });
const totalDemandas = ref(0);
const demandasJaCarregadas = ref(false);
const posCargaInicialDemandas = ref(false);
let carregamentoDemandasSeq = 0;
let demandasFetchPromise = null;
let demandasFetchKey = '';
let ultimaCargaDemandasConcluida = { chave: '', em: 0 };

const mensagemListaVazia = computed(() => {
    if (filtros.value.q) {
        return `Nenhum processo encontrado para «${filtros.value.q}». Revise a busca ou limpe os filtros.`;
    }
    if (exibirPainelFilas.value) {
        if (isPainelProtocolo.value && painelFila.value === 'protocolados') {
            return 'Nenhum processo aguardando despacho do Protocolo. Novos ofícios aparecem aqui após o envio oficial.';
        }
        if (painelFila.value === 'operacionais') {
            if (isPainelGestorSetorial.value && escopoSecretaria.value === 'encerrado') {
                return 'Nenhuma demanda encerrada no escopo do seu setor.';
            }
            if (
                (isPainelGestorSetorial.value || isPainelProtocolo.value) &&
                escopoSecretaria.value === 'acompanhando'
            ) {
                return 'Nenhum processo fixado para acompanhamento.';
            }
            return 'Nenhum processo em tramitação operacional no momento.';
        }
        if (isPainelProtocolo.value && painelFila.value === 'devolutivas') {
            return 'Nenhuma devolutiva pendente. Processos concluídos pela secretaria aguardando resposta do Protocolo aparecem aqui.';
        }
        if (painelFila.value === 'stand_by') {
            return 'Nenhuma demanda na base stand-by de estudo e viabilidade.';
        }
        if (painelFila.value === 'finalizados') {
            return 'Nenhum processo finalizado no momento.';
        }
    }
    if (isSecretaria.value) {
        if (escopoSecretaria.value === 'encerrado') {
            return 'Nenhuma demanda encerrada no seu setor. Processos concluídos por você aparecem aqui após encerrar a participação.';
        }
        if (escopoSecretaria.value === 'acompanhando') {
            return 'Nenhum processo fixado para acompanhamento. Fixe após encerrar sua participação ou a qualquer momento enquanto o processo estiver em operação.';
        }
        return 'Nenhuma demanda em operação no seu setor. Confira se o setor está vinculado ao seu usuário em Gestão de Setores.';
    }
    if (isPainelProtocolo.value && painelFila.value === 'operacionais' && escopoSecretaria.value === 'acompanhando') {
        return 'Nenhum processo fixado para acompanhamento.';
    }
    if (isCamara.value) {
        return 'Nenhuma indicação registrada. Use o Copiloto para criar uma nova indicação legislativa.';
    }
    if (userStore.currentUser?.perfil === 'VEREADOR') {
        return 'Você ainda não possui demandas. Use o Copiloto para criar um novo ofício.';
    }
    return 'Nenhuma demanda encontrada com os filtros atuais.';
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

const totalAbertos = computed(() => contadoresResumo.value.abertos);

const totalFinalizados = computed(() => contadoresResumo.value.finalizados);

const totalAtrasados = computed(() => contadoresResumo.value.atrasados);

const filtroHubAtrasadas = computed(() => route.query?.consulta === 'atrasadas');

const limparFiltroHubAtrasadas = () => {
    const query = { ...route.query };
    delete query.consulta;
    resetPaginaDemandas();
    router.replace({ name: 'demandas', query });
    carregarDemandas();
};

const aplicarFiltrosDemandas = () => {
    resetPaginaDemandas();
    carregarDemandas();
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
    if (isDemandaAtrasadaParaExibicao(demanda, userStore.currentUser?.perfil, isAtrasada)) {
        return 'danger';
    }
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

const badgeAssinaturaLista = (demanda) => badgeAssinaturaProtocolo(demanda);

const podeDespacharDemandaLista = (demanda) =>
    demanda?.status === 'AGUARDANDO_PROTOCOLO' &&
    !despachoInicialPendenteGestor(demanda?.assinaturas_resumo);

const gestorDespachoSelecionadoLista = computed(() =>
    gestorPorId(gestoresProtocolo.value, despachoAssinatura.value.gestor_protocolo_id)
);

const modoAssinaturaDespachoInicial = computed(() =>
    modoPainelAssinaturaProtocolo(CONTEXTO_ASSINATURA.DESPACHO_INICIAL, userStore.currentUser, userStore)
);

const modoAssinaturaDevolutiva = computed(() => {
    const ctx = demandaParaDevolutiva.value?.fluxo_roteamento
        ? CONTEXTO_ASSINATURA.CONCLUSAO_FINAL
        : CONTEXTO_ASSINATURA.DEVOLUTIVA;
    const painel = modoPainelAssinaturaProtocolo(ctx, userStore.currentUser, userStore);
    const previewModo = devolutivaPreview.value?.modo_assinatura;
    if (previewModo === 'dual_protocolo' && painel === MODO_PAINEL_ASSINATURA.OPERADOR_APENAS) {
        return painel;
    }
    if (previewModo && previewModo !== 'dual_protocolo') return previewModo;
    return painel;
});

const extrairMensagemErro = (error) => {
    const data = error?.response?.data;
    if (!data) return 'Não foi possível carregar as demandas. Verifique sua conexão e tente novamente.';
    if (typeof data.detail === 'string') return data.detail;
    if (typeof data.error === 'string') return data.error;
    if (Array.isArray(data) && data[0]) return String(data[0]);
    return 'Falha ao carregar demandas. Tente novamente.';
};

function extrairListaDemandas(response) {
    const data = response?.data;
    return data?.results || data || [];
}

function extrairTotalDemandas(response, fallback = 0) {
    const data = response?.data;
    if (data && typeof data === 'object' && data.count != null) {
        return data.count;
    }
    return fallback;
}

function montarParamsDemandas() {
    let params = { ...filtros.value };
    const currentUser = userStore.currentUser;

    if (filtroHubAtrasadas.value && !ocultarMetricasSla(currentUser?.perfil)) {
        params.consulta = 'atrasadas';
    }

    switch (currentUser?.perfil) {
        case 'CAMARA':
            params.autor = currentUser.id;
            params.tipo_legislativo = 'INDICACAO';
            break;
        case 'VEREADOR':
            params.autor = currentUser.id;
            break;
        case 'SECRETARIA':
            if (currentUser.secretaria || currentUser.sinapse_orgao_id) {
                params.fila = 'operacionais';
                params.escopo_setor = escopoSecretaria.value;
                if (filtroStandByEstudo.value) {
                    params.stand_by_estudo = true;
                }
                delete params.status;
                delete params.status__in;
                delete params.secretaria_destino;
                delete params.minha_unidade;
                delete params.unidade_administrativa;
                if (filtroUnidadesIds.value?.length) {
                    params.unidades_administrativas = [...filtroUnidadesIds.value];
                }
            }
            break;
        case 'GESTOR':
        case 'PROTOCOLO':
            if (exibirPainelFilas.value && painelFila.value && !params.trilha) {
                params.fila = painelFila.value;
                delete params.status;
                delete params.status__exclude;
                if (painelFila.value === 'operacionais') {
                    params.escopo_setor = escopoSecretaria.value;
                }
                if (exibirFiltroSetores.value && filtroUnidadesIds.value?.length) {
                    params.unidades_administrativas = [...filtroUnidadesIds.value];
                } else if (painelFila.value === 'operacionais' && filtroUnidadeId.value) {
                    params.unidade_administrativa = filtroUnidadeId.value;
                }
            } else if (params.status !== 'RASCUNHO') {
                params.status__exclude = 'RASCUNHO';
            }
            break;
    }

    Object.keys(params).forEach((key) => (params[key] == null || params[key] === '') && delete params[key]);
    return params;
}

function montarChaveRequisicaoDemandas() {
    const page = Math.floor(tablePagination.value.first / tablePagination.value.rows) + 1;
    const params = {
        ...montarParamsDemandas(),
        page,
        page_size: tablePagination.value.rows
    };
    if (isPainelProtocolo.value) {
        params.include_resumo = '1';
    }
    return JSON.stringify(params);
}

function finalizarPosCargaInicialDemandas() {
    if (posCargaInicialDemandas.value) return;
    posCargaInicialDemandas.value = true;
    tentarEnvioLoteDaQuery();
    carregarAuxiliaresDemandas();
}

function aplicarResumoFilas(data) {
    if (!data) return;
    contadoresResumo.value = {
        abertos: data.abertos ?? 0,
        finalizados: data.finalizados ?? 0,
        atrasados: data.atrasados ?? 0
    };
}

async function carregarContadoresResumo() {
    if (!isPainelProtocolo.value) return;
    try {
        const { data } = await ApiService.getDemandasResumoFilas();
        aplicarResumoFilas(data);
    } catch {
        contadoresResumo.value = { abertos: 0, finalizados: 0, atrasados: 0 };
    }
}

const resetPaginaDemandas = () => {
    tablePagination.value = { ...tablePagination.value, first: 0 };
};

const onPageDemandas = (event) => {
    tablePagination.value = { first: event.first, rows: event.rows };
    demandasJaCarregadas.value = true;
    carregarDemandas().then(finalizarPosCargaInicialDemandas);
};

async function carregarDemandas({ forcar = false } = {}) {
    const chave = montarChaveRequisicaoDemandas();
    const agora = Date.now();

    if (!forcar) {
        if (demandasFetchPromise && demandasFetchKey === chave) {
            return demandasFetchPromise;
        }
        if (
            chave === ultimaCargaDemandasConcluida.chave &&
            agora - ultimaCargaDemandasConcluida.em < 1500
        ) {
            return;
        }
    }

    demandasFetchKey = chave;
    const seq = ++carregamentoDemandasSeq;

    demandasFetchPromise = (async () => {
        loading.value = true;
        erroCarregamento.value = null;
        try {
            if (!userStore.currentUser?.id) {
                return;
            }

            const params = JSON.parse(chave);
            const response = await ApiService.getDemandas(params);
            if (seq !== carregamentoDemandasSeq) return;

            const lista = extrairListaDemandas(response);
            demandas.value = lista;
            totalDemandas.value = extrairTotalDemandas(response, lista.length);
            if (response.data?.resumo_filas) {
                aplicarResumoFilas(response.data.resumo_filas);
            } else if (isPainelProtocolo.value) {
                await carregarContadoresResumo();
            }
            ultimaCargaDemandasConcluida = { chave, em: Date.now() };
        } catch (error) {
            if (seq !== carregamentoDemandasSeq) return;
            console.error('Erro ao buscar demandas:', error);
            demandas.value = [];
            totalDemandas.value = 0;
            erroCarregamento.value = extrairMensagemErro(error);
            toast.add({ severity: 'error', summary: 'Erro ao carregar', detail: erroCarregamento.value, life: 5000 });
        } finally {
            if (seq === carregamentoDemandasSeq) {
                loading.value = false;
            }
        }
    })();

    try {
        await demandasFetchPromise;
    } finally {
        if (demandasFetchKey === chave) {
            demandasFetchPromise = null;
        }
    }
}

const carregarUnidadesSetor = async () => {
    const user = userStore.currentUser;
    if (!user?.id) {
        unidadesSetor.value = [];
        return;
    }
    if (!exibirFiltroSetores.value) {
        unidadesSetor.value = [];
        return;
    }
    try {
        const params = { ativo: true };
        if (isSecretaria.value) {
            const orgaoId = user.secretaria?.id || user.sinapse_orgao_id;
            if (!orgaoId) {
                unidadesSetor.value = [];
                return;
            }
            params.sinapse_orgao_id = orgaoId;
        }
        const { data } = await ApiService.listarUnidadesAdministrativas(params);
        let lista = Array.isArray(data) ? data : data?.results || [];
        if (isSecretaria.value) {
            const idsVinculados = new Set(vinculoSecretaria.value?.unidade_ids || []);
            if (idsVinculados.size) {
                lista = lista.filter((u) => idsVinculados.has(u.id));
            }
        }
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
    filtroUnidadesIds.value = [];
    resetPaginaDemandas();
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
    resetPaginaDemandas();
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

const carregarAuxiliaresDemandas = () => {
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
};

onMounted(() => {
    if (ocultarMetricasSla(userStore.currentUser?.perfil) && route.query?.consulta === 'atrasadas') {
        const query = { ...route.query };
        delete query.consulta;
        router.replace({ name: 'demandas', query });
    }
    const qs = route.query?.status;
    if (typeof qs === 'string' && qs) {
        filtros.value.status = qs;
    }
    const filaQs = route.query?.fila;
    if (typeof filaQs === 'string' && ['protocolados', 'operacionais', 'devolutivas', 'stand_by', 'finalizados'].includes(filaQs)) {
        const filasSetorial = FILAS_GESTOR_SETORIAL;
        if (
            userStore.currentUser?.perfil === 'PROTOCOLO' ||
            podePainelProtocoloCentral.value ||
            (userStore.currentUser?.perfil === 'GESTOR' &&
                !podePainelProtocoloCentral.value &&
                filasSetorial.includes(filaQs))
        ) {
            painelFila.value = filaQs;
        } else if (userStore.currentUser?.perfil === 'GESTOR' && !podePainelProtocoloCentral.value) {
            painelFila.value = 'operacionais';
        } else if (filaQs === 'operacionais') {
            painelFila.value = filaQs;
        }
    } else if (userStore.currentUser?.perfil === 'GESTOR' && !podePainelProtocoloCentral.value) {
        painelFila.value = 'operacionais';
    }
    if (typeof route.query?.escopo_setor === 'string' && ['em_operacao', 'encerrado', 'acompanhando'].includes(route.query.escopo_setor)) {
        escopoSecretaria.value = route.query.escopo_setor;
    } else if (route.query?.minha_unidade === '0') {
        escopoSecretaria.value = 'encerrado';
    }
    aplicarQueryRota();
    sincronizandoDemandasRota.value = false;
    if (['SECRETARIA', 'PROTOCOLO', 'GESTOR'].includes(userStore.currentUser?.perfil)) {
        carregarUnidadesSetor();
    }
    nextTick(() => {
        // PrimeVue lazy emite @page após montar; fallback só se isso não ocorrer.
        setTimeout(() => {
            if (demandasJaCarregadas.value) return;
            demandasJaCarregadas.value = true;
            carregarDemandas().then(finalizarPosCargaInicialDemandas);
        }, 80);
    });
    clockInterval = setInterval(() => {
        clockTick.value = Date.now();
    }, 60_000);
});

onUnmounted(() => {
    if (clockInterval) clearInterval(clockInterval);
});

watch(
    () => [route.query.trilha, route.query.origem_vinculo, route.query.consulta],
    () => {
        if (sincronizandoDemandasRota.value) return;
        aplicarQueryRota();
        resetPaginaDemandas();
        carregarDemandas();
    }
);

watch(isPainelGestorSetorial, (setorial) => {
    if (setorial && !FILAS_GESTOR_SETORIAL.includes(painelFila.value)) {
        painelFila.value = 'operacionais';
    }
    if (setorial && escopoSecretaria.value === 'encerrado') {
        escopoSecretaria.value = 'em_operacao';
    }
}, { immediate: true });

watch(painelFila, (fila) => {
    if (sincronizandoDemandasRota.value || !exibirPainelFilas.value) return;
    filtros.value.status = null;
    filtroUnidadeId.value = null;
    filtroUnidadesIds.value = [];
    resetPaginaDemandas();
    router.replace({ query: { ...route.query, fila } });
    carregarDemandas();
});

watch(escopoSecretaria, () => {
    if (sincronizandoDemandasRota.value || !exibirEscopoOperacional.value) return;
    resetPaginaDemandas();
    router.replace({
        query: {
            ...route.query,
            fila: isSecretaria.value ? 'operacionais' : painelFila.value,
            escopo_setor: escopoSecretaria.value
        }
    });
    carregarDemandas();
});

const editarDemanda = (id) => router.push(`/demandas/editar/${id}`);
const editarIndicacao = (id) => router.push({ name: 'indicacao-editar', params: { id } });
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

const formDespacho = ref(estadoFormularioTramitacao());
const despachoData = formDespacho;
const despachoAnexos = computed({
    get: () => formDespacho.value.anexos || [],
    set: (v) => {
        formDespacho.value.anexos = v;
    }
});

const orgaosCatalogo = ref([]);

const orgaoCompetenteDespacho = computed(() => {
    const d = demandaParaDespacho.value;
    if (!d) return null;
    return (
        d.servico?.secretaria_responsavel?.id ||
        d.secretaria_destino?.id ||
        d.sinapse_orgao_id ||
        despachoPreview.value?.orgao_competente_id ||
        null
    );
});

const orgaoCompetenteNome = computed(() => {
    const d = demandaParaDespacho.value;
    const nome =
        d?.servico?.secretaria_responsavel?.nome ||
        d?.secretaria_destino?.nome ||
        despachoPreview.value?.orgao_competente_nome;
    if (nome) return nome;
    const id = orgaoCompetenteDespacho.value;
    const sec = todasSecretarias.value.find((s) => s.id === id);
    return sec?.nome || (id ? `Órgão #${id}` : '—');
});

const secretariasIntegraveis = computed(() => {
    const excluir = orgaoCompetenteDespacho.value;
    if (!excluir) return todasSecretarias.value;
    return todasSecretarias.value.filter((s) => s.id !== excluir);
});

const despachoMultiOrgao = computed(() => despachoEhTransversal(formDespacho.value.destinos));

const resumoDestinosDespacho = computed(() =>
    resumoDestinosTexto(formDespacho.value.destinos, orgaosCatalogo.value)
);

const montarPayloadDespacho = () =>
    payloadDespachoDestinos(formDespacho.value, orgaoCompetenteDespacho.value);

const carregarOrgaos = async () => {
    if (orgaosCatalogo.value.length) return orgaosCatalogo.value;
    try {
        const { data } = await ApiService.getSecretarias();
        orgaosCatalogo.value = Array.isArray(data) ? data : [];
    } catch {
        orgaosCatalogo.value = [];
    }
    return orgaosCatalogo.value;
};

const onAnexosRejeitadosForm = (msg) => {
    toast.add({ severity: 'warn', summary: 'Anexos', detail: msg, life: 4000 });
};

const podeMontarDespacho = () => {
    const payload = montarPayloadDespacho();
    if (!payload.destinos?.length && !payload.secretaria_id) return false;
    return contarPernasDestinos(formDespacho.value.destinos) <= MAX_PERNAS_DESPACHO;
};

const onDespachoAnexosSelected = (event) => {
    const { aceitos, rejeitados } = filtrarArquivosDuplicados(event.files, despachoAnexos.value.map((f) => f.name));
    despachoAnexos.value = [...despachoAnexos.value, ...aceitos];
    const msg = mensagemAnexosRejeitados(rejeitados);
    if (msg) {
        toast.add({ severity: 'warn', summary: 'Anexos', detail: msg, life: 4000 });
    }
};

const textoDevolutivaLimpo = (html) => (html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

const invalidarPreviewDevolutiva = () => {
    devolutivaPreview.value = null;
    devolutivaAssinatura.value = {
        declaracaoOperador: false,
        declaracaoGestor: false,
        gestor_protocolo_id: null
    };
};

const abrirDialogoDespachoInterno = async (demanda) => {
    let demandaCtx = demanda;
    if (demanda?.id && !demanda.autor) {
        try {
            const { data } = await ApiService.getDemandaById(demanda.id);
            demandaCtx = { ...demanda, ...data };
        } catch {
            /* mantém resumo da lista */
        }
    }
    demandaParaDespacho.value = demandaCtx;
    formDespacho.value = estadoFormularioTramitacao({
        destinos: inicializarDestinosDespacho(orgaoCompetenteDespacho.value)
    });
    despachoPreview.value = null;
    despachoAssinatura.value = { declaracaoOperador: false, declaracaoGestor: false, gestor_protocolo_id: null };
    await carregarOrgaos();
    todasSecretarias.value = orgaosCatalogo.value;
    try {
        const { data } = await ApiService.getGestoresProtocolo();
        gestoresProtocolo.value = Array.isArray(data) ? data : [];
    } catch {
        gestoresProtocolo.value = [];
    }
    despachoDialog.value = true;
};

const abrirDialogoDespacho = async (demanda) => {
    if (userStore.currentUser?.perfil === 'PROTOCOLO' && demanda?.cluster?.id) {
        try {
            const { data } = await ApiService.getClusterSituacaoAderencia(demanda.id);
            if (data?.exibir_decisao) {
                demandaParaDespacho.value = demanda;
                clusterAderenciaSituacao.value = data;
                clusterAderenciaDialog.value = true;
                return;
            }
        } catch {
            /* segue fluxo unitário */
        }
    }
    await abrirDialogoDespachoInterno(demanda);
};

const confirmarAderenciaCluster = async () => {
    if (!demandaParaDespacho.value?.id) return;
    clusterAderenciaLoading.value = true;
    try {
        const { data } = await ApiService.aderirClusterLider(demandaParaDespacho.value.id);
        toast.add({
            severity: 'success',
            summary: 'Integrada ao líder',
            detail: `Demanda integrada ao processo líder. Protocolo executivo: ${data?.protocolo_executivo || '—'}.`,
            life: 5000
        });
        clusterAderenciaDialog.value = false;
        clusterAderenciaSituacao.value = null;
        carregarDemandas();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível integrar ao processo líder.',
            life: 4000
        });
    } finally {
        clusterAderenciaLoading.value = false;
    }
};

const confirmarDesvincularClusterDespacho = async () => {
    if (!demandaParaDespacho.value?.id) return;
    clusterAderenciaLoading.value = true;
    try {
        const { data } = await ApiService.desvincularDemandaClusterIndividual(demandaParaDespacho.value.id);
        clusterAderenciaDialog.value = false;
        clusterAderenciaSituacao.value = null;
        await abrirDialogoDespachoInterno({ ...demandaParaDespacho.value, ...data, cluster: null });
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível desvincular a demanda do cluster.',
            life: 4000
        });
    } finally {
        clusterAderenciaLoading.value = false;
    }
};

const gerarPreviewDespacho = async () => {
    if (!podeMontarDespacho()) {
        toast.add({
            severity: 'warn',
            summary: 'Atenção',
            detail: 'Não foi possível identificar o órgão competente da carta.',
            life: 3000
        });
        return false;
    }
    carregandoDespachoPreview.value = true;
    try {
        const { data } = await ApiService.previewDespachoDemanda(demandaParaDespacho.value.id, montarPayloadDespacho());
        despachoPreview.value = data;
        if (data.gestores_protocolo?.length) {
            gestoresProtocolo.value = data.gestores_protocolo;
        }
        return true;
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível gerar a prévia de assinatura.',
            life: 4000
        });
        return false;
    } finally {
        carregandoDespachoPreview.value = false;
    }
};

const confirmarDespacho = async () => {
    if (!podeMontarDespacho()) {
        toast.add({
            severity: 'warn',
            summary: 'Atenção',
            detail: 'Não foi possível identificar o órgão competente da carta.',
            life: 3000
        });
        return;
    }
    const textoDespacho = (formDespacho.value.descricao || '').trim();
    if (textoDespacho.length < 10) {
        toast.add({
            severity: 'warn',
            summary: 'Despacho',
            detail: 'Informe o texto do despacho do protocolo (mínimo 10 caracteres).',
            life: 4000
        });
        return;
    }
    if (!despachoPreview.value?.hash_documento) {
        const ok = await gerarPreviewDespacho();
        if (!ok) return;
    }
    assinaturaDespachoDialogVisible.value = true;
};

const executarDespachoComAssinatura = async (payloadAssinatura) => {
    executandoAssinatura.value = true;
    try {
        const { data } = await ApiService.despacharDemanda(
            demandaParaDespacho.value.id,
            {
                ...montarPayloadDespacho(),
                ...payloadAssinatura
            },
            despachoAnexos.value
        );

        let detail =
            data.mensagem ||
            (data.aguardando_validacao_gestor
                ? 'Assinatura registrada. O despacho só será executado após validação do gestor em Assinaturas pendentes.'
                : 'Demanda despachada com assinatura eletrônica.');
        if (data.demandas_desdobradas?.length) {
            const extras = data.demandas_desdobradas.map((d) => d.protocolo_executivo).join(', ');
            detail += ` Desdobramentos criados: ${extras}.`;
        }
        toast.add({ severity: 'success', summary: 'Sucesso', detail, life: 5000 });
        assinaturaDespachoDialogVisible.value = false;
        despachoDialog.value = false;
        carregarDemandas();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível despachar.',
            life: 4000
        });
    } finally {
        executandoAssinatura.value = false;
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

const abrirDialogoDevolutiva = async (demanda) => {
    let demandaCtx = demanda;
    if (demanda?.id && !demanda.autor) {
        try {
            const { data } = await ApiService.getDemandaById(demanda.id);
            demandaCtx = { ...demanda, ...data };
        } catch {
            /* mantém resumo da lista */
        }
    }
    demandaParaDevolutiva.value = demandaCtx;
    formDevolutiva.value = estadoFormularioDevolutiva();
    invalidarPreviewDevolutiva();
    await carregarOrgaos();
    try {
        const { data } = await ApiService.getGestoresProtocolo();
        gestoresProtocolo.value = Array.isArray(data) ? data : [];
    } catch {
        gestoresProtocolo.value = [];
    }
    devolutivaDialog.value = true;
};

const confirmarDevolutiva = async () => {
    const parecer = formDevolutiva.value.parecer_resposta || '';
    const validacaoAlerta = formDevolutivaRef.value?.validarAlertaDestinos?.();
    if (validacaoAlerta && !validacaoAlerta.ok) {
        toast.add({
            severity: 'warn',
            summary: 'Alerta de devolutiva',
            detail: validacaoAlerta.mensagem || 'Selecione o setor de cada órgão no alerta.',
            life: 4000
        });
        return;
    }
    if (textoDevolutivaLimpo(parecer).length < 10) {
        toast.add({
            severity: 'warn',
            summary: 'Resposta obrigatória',
            detail: 'Informe a devolutiva ao vereador (mín. 10 caracteres).',
            life: 3000
        });
        return;
    }
    if (!devolutivaPreview.value?.hash_documento) {
        carregandoDevolutivaPreview.value = true;
        try {
            const { data } = await ApiService.previewDespachoDevolutiva(demandaParaDevolutiva.value.id, {
                parecer_resposta: parecer
            });
            devolutivaPreview.value = data;
            if (data.gestores_protocolo?.length) {
                gestoresProtocolo.value = data.gestores_protocolo;
            }
        } catch (error) {
            toast.add({
                severity: 'error',
                summary: 'Erro',
                detail: error?.response?.data?.detail || 'Não foi possível gerar a prévia.',
                life: 4000
            });
            return;
        } finally {
            carregandoDevolutivaPreview.value = false;
        }
    }
    assinaturaDevolutivaDialogVisible.value = true;
};

const executarDevolutivaComAssinatura = async (payloadAssinatura) => {
    executandoAssinatura.value = true;
    try {
        const arquivos = formDevolutiva.value.anexos_novos || [];
        const usaConclusaoFinal = Boolean(demandaParaDevolutiva.value?.fluxo_roteamento);
        const formComGestor = {
            ...formDevolutiva.value,
            gestor_protocolo_id: payloadAssinatura.gestor_protocolo_id
        };
        const declaracaoOp = usaConclusaoFinal ? DECLARACAO_CONCLUSAO_FINAL : DECLARACAO_DEVOLUTIVA;
        const payload = {
            ...buildDevolutivaPayload(
                formComGestor,
                payloadAssinatura.hash_documento || devolutivaPreview.value.hash_documento,
                {
                    declaracaoOperadorText: declaracaoOp,
                    declaracaoGestorText: DECLARACAO_GESTOR_PROTOCOLO
                },
                modoAssinaturaDevolutiva.value
            ),
            ...payloadAssinatura
        };
        if (usaConclusaoFinal) {
            await ApiService.conclusaoFinalOperacional(
                demandaParaDevolutiva.value.id,
                payload,
                arquivos
            );
        } else {
            await ApiService.despacharDevolutiva(
                demandaParaDevolutiva.value.id,
                payload,
                arquivos
            );
        }
        toast.add({
            severity: 'success',
            summary: usaConclusaoFinal ? 'Conclusão final registrada' : 'Devolutiva registrada',
            detail: usaConclusaoFinal
                ? 'Assinatura registrada. Após validação do gestor do protocolo, a demanda será finalizada.'
                : 'Assinatura registrada. A devolutiva só será enviada ao vereador após validação do gestor.',
            life: 4000
        });
        assinaturaDevolutivaDialogVisible.value = false;
        devolutivaDialog.value = false;
        carregarDemandas();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Falha ao despachar devolutiva.',
            life: 4000
        });
    } finally {
        executandoAssinatura.value = false;
    }
};

const gerarPreviewDevolutivaDialog = async () => {
    const parecer = formDevolutiva.value.parecer_resposta || '';
    if (textoDevolutivaLimpo(parecer).length < 10) return;
    carregandoDevolutivaPreview.value = true;
    try {
        const { data } = await ApiService.previewDespachoDevolutiva(demandaParaDevolutiva.value.id, {
            parecer_resposta: parecer
        });
        devolutivaPreview.value = data;
        if (data.gestores_protocolo?.length) {
            gestoresProtocolo.value = data.gestores_protocolo;
        }
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível gerar a prévia.',
            life: 4000
        });
    } finally {
        carregandoDevolutivaPreview.value = false;
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
                            <h5 class="m-0">{{ tituloPaginaDemandas }}</h5>
                            <p v-if="isCamara" class="m-0 mt-1 text-sm text-muted-color">
                                Protocolo da Câmara — encaminhamento ao Protocolo Executivo após assinatura.
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
                            v-if="isCamara"
                            label="Nova indicação (Copiloto)"
                            icon="pi pi-comments"
                            class="p-button-success mr-2"
                            @click="router.push('/copiloto')"
                        />
                        <Button
                            v-else-if="['VEREADOR', 'GESTOR'].includes(userStore.currentUser?.perfil)"
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

                <div v-if="exibirPainelFilas" class="mb-4 flex flex-col gap-3">
                    <SelectButton
                        v-model="painelFila"
                        :options="opcoesPainelVisiveis"
                        optionLabel="label"
                        optionValue="value"
                        :allowEmpty="false"
                    />
                </div>

                <div v-if="exibirEscopoOperacional" class="mb-4 flex flex-col gap-3">
                    <div
                        v-if="exibirFiltroSetores && unidadesSetor.length"
                        class="flex flex-col gap-2 max-w-md"
                    >
                        <label class="text-sm font-medium">Setor</label>
                        <MultiSelect
                            v-model="filtroUnidadesIds"
                            :options="unidadesSetor"
                            optionLabel="label"
                            optionValue="value"
                            placeholder="Todos os setores"
                            display="chip"
                            showClear
                            fluid
                            @change="aplicarFiltrosDemandas"
                        />
                    </div>
                    <SelectButton
                        v-model="escopoSecretaria"
                        :options="opcoesEscopoOperacional"
                        optionLabel="label"
                        optionValue="value"
                        :allowEmpty="false"
                    />
                    <Message
                        v-if="isSecretaria && vinculoSecretariaIncompleto && !loading"
                        severity="warn"
                        :closable="false"
                        class="text-sm m-0"
                    >
                        Vínculo incompleto:
                        {{ (vinculoSecretaria?.avisos || []).join(' ') }}
                        Solicite ao Gestor ou Protocolo a configuração em «Usuários secretaria».
                    </Message>
                    <Message
                        v-else-if="isSecretaria && !unidadesSetor.length && !loading && !vinculoSecretariaIncompleto"
                        severity="warn"
                        :closable="false"
                        class="text-sm m-0"
                    >
                        Nenhum setor vinculado ao seu usuário.
                        <router-link to="/gestao-setores" class="text-primary ml-1">Cadastre em Gestão de Setores</router-link>.
                    </Message>
                    <div
                        v-if="isSecretaria && escopoSecretaria === 'encerrado'"
                        class="flex items-center gap-2"
                    >
                        <Checkbox
                            v-model="filtroStandByEstudo"
                            binary
                            inputId="filtro_stand_by_estudo"
                            @change="aplicarFiltrosDemandas"
                        />
                        <label for="filtro_stand_by_estudo" class="text-sm cursor-pointer">
                            Somente stand-by (estudo/viabilidade)
                        </label>
                    </div>
                </div>

                <Message
                    v-if="erroCarregamento && !loading"
                    severity="error"
                    :closable="false"
                    class="mb-4"
                >
                    <div class="flex flex-wrap items-center justify-between gap-3">
                        <span>{{ erroCarregamento }}</span>
                        <Button label="Tentar novamente" icon="pi pi-refresh" size="small" outlined @click="carregarDemandas({ forcar: true })" />
                    </div>
                </Message>

                <Message
                    v-else-if="!loading && totalDemandas === 0"
                    severity="secondary"
                    :closable="false"
                    class="mb-4"
                >
                    {{ mensagemListaVazia }}
                </Message>

                <div v-if="isPainelProtocolo" class="grid grid-cols-12 gap-8 mb-4">
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
                        <div
                            v-if="!isCamara && userStore.currentUser?.perfil !== 'SECRETARIA' && !isPainelGestorSetorial"
                            class="flex flex-col gap-2 w-full"
                        >
                            <label for="secretaria">Secretaria</label>
                            <Select id="secretaria" v-model="filtros.secretaria_destino" :options="todasSecretarias" optionLabel="nome" optionValue="id" placeholder="Selecione" />
                        </div>
                        <div v-if="exibirFiltroSetores && unidadesSetor.length" class="flex flex-col gap-2 w-full">
                            <label for="setor_busca">Setor</label>
                            <MultiSelect
                                id="setor_busca"
                                v-model="filtroUnidadesIds"
                                :options="unidadesSetor"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Todos os setores"
                                display="chip"
                                showClear
                                fluid
                            />
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

                    <Button label="Filtrar" class="mr-3" icon="pi pi-filter" @click="aplicarFiltrosDemandas" />
                    <Button label="Limpar" icon="pi pi-times" @click="limparFiltros" class="p-button-outlined" />
                </Panel>

                <Message
                    v-if="filtroHubAtrasadas && !ocultarSlaVereador"
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
                    :value="demandas"
                    :loading="loading"
                    lazy
                    scrollable
                    class="sgdl-table-scroll"
                    :tableStyle="{ minWidth: '80rem', width: 'max-content' }"
                    paginator
                    :rows="tablePagination.rows"
                    :first="tablePagination.first"
                    :totalRecords="totalDemandas"
                    :rowsPerPageOptions="[10, 25, 50, 100]"
                    paginatorTemplate="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
                    currentPageReportTemplate="Mostrando {first} a {last} de {totalRecords}"
                    :dataKey="'id'"
                    @page="onPageDemandas"
                >
                    <Column
                        v-if="mostrarSelecaoLote"
                        selectionMode="multiple"
                        headerStyle="width: 3rem"
                    />
                    <Column
                        header="Ações"
                        frozen
                        alignFrozen="left"
                        :style="{ minWidth: isPainelProtocolo ? '9rem' : '7.5rem' }"
                    >
                        <template #body="slotProps">
                            <div class="flex flex-nowrap items-center gap-0.5">
                            <template v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && isPainelProtocolo">
                                <Button
                                    v-if="podeAcaoCluster(slotProps.data)"
                                    icon="pi pi-sitemap"
                                    severity="help"
                                    text
                                    rounded
                                    size="small"
                                    @click="acaoCluster(slotProps.data)"
                                    v-tooltip.top="
                                        podeDespacharSuperOs(slotProps.data)
                                            ? 'Cluster — Despachar Super OS'
                                            : 'Cluster — ver agrupamento'
                                    "
                                />
                                <Button
                                    v-if="podeDespacharDemandaLista(slotProps.data)"
                                    icon="pi pi-send"
                                    severity="success"
                                    text
                                    rounded
                                    size="small"
                                    @click="abrirDialogoDespacho(slotProps.data)"
                                    v-tooltip.top="'Enviar — despachar ao setor'"
                                />
                                <Button
                                    v-if="podeGerirTendencia(slotProps.data)"
                                    icon="pi pi-compass"
                                    severity="info"
                                    text
                                    rounded
                                    size="small"
                                    @click="irGerirTendencia(slotProps.data)"
                                    v-tooltip.top="'Gerir tendência'"
                                />
                                <Button
                                    v-if="slotProps.data.status === 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO'"
                                    icon="pi pi-reply"
                                    severity="info"
                                    text
                                    rounded
                                    size="small"
                                    @click="abrirDialogoDevolutiva(slotProps.data)"
                                    v-tooltip.top="'Despachar devolutiva ao vereador'"
                                />
                                <Button
                                    v-if="slotProps.data.status === 'AGUARDANDO_TRANSFERENCIA'"
                                    icon="pi pi-check-circle"
                                    severity="warning"
                                    text
                                    rounded
                                    size="small"
                                    @click="abrirDialogoAprovarTransferencia(slotProps.data)"
                                    v-tooltip.top="'Revisar transferência'"
                                />
                                <Button
                                    icon="pi pi-eye"
                                    severity="secondary"
                                    text
                                    rounded
                                    size="small"
                                    @click="visualizarDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Ver — acompanhar'"
                                />
                            </template>
                            <template v-else-if="isCamara">
                                <Button
                                    v-if="slotProps.data.status === 'RASCUNHO'"
                                    icon="pi pi-pencil"
                                    text
                                    rounded
                                    size="small"
                                    @click="editarIndicacao(slotProps.data.id)"
                                    v-tooltip.top="'Revisar rascunho'"
                                />
                                <Button
                                    v-if="slotProps.data.status === 'RASCUNHO'"
                                    icon="pi pi-trash"
                                    severity="danger"
                                    text
                                    rounded
                                    size="small"
                                    @click="excluirDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Excluir rascunho'"
                                />
                                <Button
                                    icon="pi pi-eye"
                                    severity="secondary"
                                    text
                                    rounded
                                    size="small"
                                    @click="visualizarDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Ver detalhes e acompanhar'"
                                />
                            </template>
                            <template v-else>
                                <Button
                                    v-if="podeAcaoAcompanhamentoRapida(slotProps.data)"
                                    :icon="slotProps.data.acompanhando ? 'pi pi-bookmark-fill' : 'pi pi-bookmark'"
                                    :severity="slotProps.data.acompanhando ? 'help' : 'secondary'"
                                    text
                                    rounded
                                    size="small"
                                    @click="alternarAcompanhamentoLista(slotProps.data)"
                                    v-tooltip.top="
                                        slotProps.data.acompanhando
                                            ? 'Desfixar acompanhamento'
                                            : 'Fixar acompanhamento'
                                    "
                                />
                                <Button
                                    v-if="['VEREADOR', 'GESTOR'].includes(userStore.currentUser?.perfil) && slotProps.data.status === 'RASCUNHO'"
                                    icon="pi pi-pencil"
                                    text
                                    rounded
                                    size="small"
                                    @click="editarDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Editar rascunho'"
                                />
                                <Button
                                    v-if="userStore.currentUser?.perfil === 'VEREADOR' && slotProps.data.status === 'RASCUNHO'"
                                    icon="pi pi-trash"
                                    severity="danger"
                                    text
                                    rounded
                                    size="small"
                                    @click="excluirDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Excluir'"
                                />
                                <Button
                                    v-if="podeDespacharSuperOs(slotProps.data)"
                                    icon="pi pi-sitemap"
                                    severity="help"
                                    text
                                    rounded
                                    size="small"
                                    @click="abrirDialogoSuperOs(slotProps.data)"
                                    v-tooltip.top="'Despachar Super OS (lote)'"
                                />
                                <Button
                                    v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && podeDespacharDemandaLista(slotProps.data)"
                                    icon="pi pi-send"
                                    severity="success"
                                    text
                                    rounded
                                    size="small"
                                    @click="abrirDialogoDespacho(slotProps.data)"
                                    v-tooltip.top="'Despachar (unitário)'"
                                />
                                <Button
                                    v-if="userStore.currentUser?.perfil === 'PROTOCOLO' && slotProps.data.status === 'AGUARDANDO_TRANSFERENCIA'"
                                    icon="pi pi-check-circle"
                                    severity="warning"
                                    text
                                    rounded
                                    size="small"
                                    @click="abrirDialogoAprovarTransferencia(slotProps.data)"
                                    v-tooltip.top="'Revisar Transferência'"
                                />
                                <Button
                                    v-if="slotProps.data.status !== 'RASCUNHO'"
                                    icon="pi pi-eye"
                                    severity="secondary"
                                    text
                                    rounded
                                    size="small"
                                    @click="visualizarDemanda(slotProps.data.id)"
                                    v-tooltip.top="'Visualizar'"
                                />
                            </template>
                            </div>
                        </template>
                    </Column>
                    <Column
                        v-if="usaPainelFila"
                        :header="colunaLocalizacaoHeader"
                        bodyClass="col-localizacao-operacional"
                        headerClass="col-localizacao-operacional"
                        style="width: 10.5rem; min-width: 10.5rem; max-width: 10.5rem"
                    >
                        <template #body="{ data }">
                            <template v-if="isSecretaria && escopoSecretaria === 'encerrado'">
                                <span
                                    v-if="data.unidade_administrativa"
                                    class="localizacao-texto truncate block"
                                    v-tooltip.top="data.unidade_administrativa.nome"
                                >
                                    {{ rotuloCompactoLocalizacao({
                                        setor_sigla: data.unidade_administrativa.sigla,
                                        setor_nome: data.unidade_administrativa.nome
                                    }) }}
                                </span>
                                <span v-else class="text-muted-color text-xs">—</span>
                            </template>
                            <template v-else-if="localizacaoOperacionalLinha(data).length">
                                <div
                                    class="localizacao-celula"
                                    v-tooltip.top="tooltipLocalizacaoConfig(data)"
                                >
                                    <span
                                        v-for="(loc, idx) in resumoLocalizacaoCelula(data).visiveis"
                                        :key="`${loc.setor_id || loc.orgao_id}-${loc.aberto}-${idx}`"
                                        class="localizacao-chip"
                                        :class="loc.aberto === false ? 'localizacao-chip--fechado' : 'localizacao-chip--aberto'"
                                    >
                                        {{ rotuloLocalizacaoItem(loc) }}
                                    </span>
                                    <span
                                        v-if="resumoLocalizacaoCelula(data).extras > 0"
                                        class="localizacao-chip localizacao-chip--mais"
                                    >
                                        +{{ resumoLocalizacaoCelula(data).extras }}
                                    </span>
                                </div>
                            </template>
                            <span v-else class="text-muted-color text-xs">—</span>
                        </template>
                    </Column>
                    <Column
                        field="protocolo_legislativo"
                        :header="isCamara ? 'Número' : 'Ofício'"
                        :sortable="true"
                        style="min-width: 9rem"
                    >
                        <template #body="{ data }">
                            <div class="flex flex-col gap-1">
                                <span>{{ formatarProtocoloLegislativo(data.protocolo_legislativo) || (isCamara ? 'Rascunho' : '—') }}</span>
                                <Tag
                                    v-if="data.tipo_legislativo === 'INDICACAO'"
                                    value="Indicação"
                                    severity="help"
                                    class="w-fit text-xs"
                                />
                                <Tag
                                    v-else-if="!isCamara && data.tipo_legislativo !== 'INDICACAO'"
                                    value="Ofício"
                                    severity="info"
                                    class="w-fit text-xs"
                                />
                            </div>
                        </template>
                    </Column>
                    <Column
                        v-if="isCamara"
                        header="Vereadores"
                        style="min-width: 10rem"
                    >
                        <template #body="{ data }">
                            <span class="text-sm">
                                {{
                                    (data.vereadores_vinculados || [])
                                        .map((v) => v.nome)
                                        .join(', ') || '—'
                                }}
                            </span>
                        </template>
                    </Column>
                    <Column
                        v-if="!isCamara"
                        field="protocolo_executivo"
                        header="Protocolo"
                        :sortable="true"
                        style="min-width: 7rem"
                    />
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
                                    :value="
                                        isDemandaAtrasadaParaExibicao(data, userStore.currentUser?.perfil, isAtrasada)
                                            ? 'ATRASADO'
                                            : data.status_display
                                    "
                                    :severity="getStatusSeverity(data)"
                                />
                                <Tag
                                    v-if="isPainelProtocolo && badgeAssinaturaLista(data)"
                                    :value="badgeAssinaturaLista(data).label"
                                    :severity="badgeAssinaturaLista(data).severity"
                                    icon="pi pi-verified"
                                    class="text-xs"
                                />
                                <Tag
                                    v-if="data.stand_by_estudo_viabilidade && ['PROTOCOLO', 'SECRETARIA', 'GESTOR'].includes(userStore.currentUser?.perfil)"
                                    value="Stand-by"
                                    severity="warn"
                                    icon="pi pi-pause-circle"
                                    class="text-xs"
                                />
                            </div>
                        </template>
                    </Column>
                    <Column
                        v-if="usaPainelFila"
                        :header="exibirTempoExecucaoTotal ? 'Tempo de execução' : 'Parado há'"
                        style="min-width: 7rem"
                    >
                        <template #body="{ data }">
                            <Tag
                                :value="
                                    exibirTempoExecucaoTotal
                                        ? formatTempoExecucaoTotal(data)
                                        : formatTempoParado(data)
                                "
                                :severity="
                                    exibirTempoExecucaoTotal
                                        ? severidadeTempoExecucao(data)
                                        : severidadeTempoParado(data)
                                "
                                v-tooltip.top="tooltipTempoColuna(data)"
                            />
                        </template>
                    </Column>
                    <Column
                        v-if="!isCamara"
                        :header="isSecretaria && escopoSecretaria === 'encerrado' ? 'Secretaria encaminhada' : 'Secretaria Destino'"
                        field="secretaria_destino.nome"
                        style="min-width: 11rem"
                    />
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

                <DialogClusterAderencia
                    v-model:visible="clusterAderenciaDialog"
                    :demanda="demandaParaDespacho"
                    :situacao="clusterAderenciaSituacao"
                    :carregando="clusterAderenciaLoading"
                    @aderir="confirmarAderenciaCluster"
                    @desvincular="confirmarDesvincularClusterDespacho"
                />

                <Dialog v-model:visible="despachoDialog" header="Despachar demanda (assinatura eletrônica)" :modal="true" style="width: 640px">
                    <div class="flex flex-col gap-4">
                        <p v-if="demandaParaDespacho" class="m-0 text-sm text-muted-color">
                            {{ formatarProtocoloLegislativo(demandaParaDespacho.protocolo_legislativo) || `#${demandaParaDespacho.id}` }} — {{ demandaParaDespacho.titulo }}
                        </p>
                        <FormularioTramitacao
                            v-if="despachoDialog"
                            v-model="formDespacho"
                            :modo="MODO_DESPACHO"
                            layout="dialog"
                            :demanda-id="demandaParaDespacho?.id"
                            :demanda-context="despachoDemandaContext"
                            :exibir-assinatura-formulario="false"
                            :orgaos="orgaosCatalogo"
                            :orgao-competente-id="orgaoCompetenteDespacho"
                            :orgao-competente-nome="orgaoCompetenteNome"
                            :orgaos-integraveis="secretariasIntegraveis"
                            @invalidar-preview="despachoPreview = null"
                            @anexos-rejeitados="onAnexosRejeitadosForm"
                        >
                            <template #extra>
                                <Message
                                    v-if="despachoMultiOrgao"
                                    severity="info"
                                    :closable="false"
                                    class="m-0 text-sm"
                                >
                                    Após o despacho, todas as secretarias envolvidas entram na etapa
                                    <strong>Operação</strong> com nós abertos — cada uma despacha ou encerra sua
                                    participação até o Protocolo concluir o processo.
                                </Message>
                                <Message
                                    v-if="despachoPreview?.multi_secretaria"
                                    severity="info"
                                    :closable="false"
                                    class="m-0"
                                >
                                    Despacho integrado — o processo principal permanece no órgão competente
                                    <strong v-if="despachoPreview.orgao_competente_nome">
                                        ({{ despachoPreview.orgao_competente_nome }})
                                    </strong>.
                                    <span v-if="despachoPreview.orgaos_integrados?.length">
                                        Integrados:
                                        {{ despachoPreview.orgaos_integrados.map((o) => o.orgao_nome).join(', ') }}.
                                    </span>
                                </Message>
                            </template>
                        </FormularioTramitacao>
                    </div>
                    <template #footer>
                        <Button label="Cancelar" icon="pi pi-times" text @click="despachoDialog = false" />
                        <Button
                            label="Assinar e despachar"
                            icon="pi pi-verified"
                            :loading="carregandoDespachoPreview"
                            @click="confirmarDespacho"
                        />
                    </template>
                </Dialog>

                <Dialog
                    v-model:visible="devolutivaDialog"
                    header="Despachar devolutiva ao vereador"
                    :modal="true"
                    style="width: min(720px, 96vw)"
                >
                    <div v-if="demandaParaDevolutiva" class="flex flex-col gap-3">
                        <p class="m-0 text-sm text-muted-color">
                            Demanda {{ demandaParaDevolutiva.protocolo_executivo }} — autor:
                            {{ demandaParaDevolutiva.autor?.first_name || demandaParaDevolutiva.autor?.username }}
                        </p>
                        <FormularioDevolutivaProtocolo
                            ref="formDevolutivaRef"
                            v-model="formDevolutiva"
                            :demanda-id="demandaParaDevolutiva.id"
                            :demanda-context="devolutivaDemandaContext"
                            :orgaos="orgaosCatalogo"
                            :usa-fluxo-operacional="Boolean(demandaParaDevolutiva.fluxo_roteamento)"
                            :preview-ativa="Boolean(devolutivaPreview?.hash_documento)"
                            @invalidar-preview="invalidarPreviewDevolutiva"
                            @anexos-rejeitados="(msg) => toast.add({ severity: 'warn', summary: 'Anexos', detail: msg, life: 4000 })"
                        />
                    </div>
                    <template #footer>
                        <Button label="Cancelar" icon="pi pi-times" text @click="devolutivaDialog = false" />
                        <Button
                            label="Assinar e enviar devolutiva"
                            icon="pi pi-verified"
                            :loading="carregandoDevolutivaPreview"
                            @click="confirmarDevolutiva"
                        />
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
                        <Message
                            v-if="alertasDuplicidadeLote.length"
                            :severity="duplicidadeLoteSugerirNaoEnviar ? 'error' : 'warn'"
                            :closable="false"
                            class="text-sm m-0"
                        >
                            <p class="m-0 font-medium">
                                {{
                                    duplicidadeLoteSugerirNaoEnviar
                                        ? 'Atenção — possível duplicidade em tramitação'
                                        : 'Possível duplicidade de rascunho'
                                }}
                            </p>
                            <ul class="m-0 mt-2 list-disc pl-5 max-h-40 overflow-y-auto">
                                <li v-for="(a, idx) in alertasDuplicidadeLote" :key="`${a.demanda_id}-${idx}`">
                                    <span v-if="a.demanda_envio_titulo" class="text-muted-color">
                                        Ao enviar «{{ a.demanda_envio_titulo }}»:
                                    </span>
                                    {{ a.mensagem }}
                                </li>
                            </ul>
                            <p v-if="duplicidadeLoteSugerirNaoEnviar" class="m-0 mt-2">
                                Recomendamos não assinar. Você ainda pode continuar se tiver certeza de que são pedidos
                                diferentes.
                            </p>
                        </Message>
                        <ul v-if="previewLote?.itens?.length" class="list-none p-0 m-0 flex flex-col gap-2 max-h-64 overflow-y-auto">
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

        <DialogAssinaturaEletronica
            v-model:visible="assinaturaDespachoDialogVisible"
            titulo="Assinatura eletrônica — despacho inicial"
            :preview="despachoPreview"
            :gestores="gestoresProtocolo"
            :modo="modoAssinaturaDespachoInicial"
            :declaracao-operador-texto="DECLARACAO_DESPACHO"
            label-confirmar="Assinar e despachar"
            :loading="executandoAssinatura"
            :loading-preview="carregandoDespachoPreview"
            mensagem-intro="Assine como operador do protocolo. O gestor validará a assinatura em seguida."
            @confirmar="executarDespachoComAssinatura"
            @gerar-preview="gerarPreviewDespacho"
        />

        <DialogAssinaturaEletronica
            v-model:visible="assinaturaDevolutivaDialogVisible"
            titulo="Assinatura eletrônica — devolutiva"
            :preview="devolutivaPreview"
            :gestores="gestoresProtocolo"
            :modo="modoAssinaturaDevolutiva"
            :declaracao-operador-texto="DECLARACAO_DEVOLUTIVA"
            :declaracao-gestor-texto="DECLARACAO_GESTOR_PROTOCOLO"
            label-confirmar="Assinar e enviar devolutiva"
            :loading="executandoAssinatura"
            :loading-preview="carregandoDevolutivaPreview"
            mensagem-intro="Revise a devolutiva e confirme a assinatura eletrônica."
            @confirmar="executarDevolutivaComAssinatura"
            @gerar-preview="gerarPreviewDevolutivaDialog"
        />
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

.demandas-table-host :deep(.col-localizacao-operacional) {
    white-space: nowrap !important;
    overflow: hidden;
    vertical-align: middle;
    box-sizing: border-box;
}

.localizacao-celula {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: 0.2rem;
    max-width: 100%;
    overflow: hidden;
}

.localizacao-texto {
    font-size: 0.7rem;
    line-height: 1.2;
    max-width: 100%;
}

.localizacao-chip {
    flex: 0 1 auto;
    min-width: 0;
    max-width: 4.5rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.65rem;
    line-height: 1.25;
    padding: 0.1rem 0.35rem;
    border-radius: 0.25rem;
    font-weight: 600;
}

.localizacao-chip--aberto {
    background: color-mix(in srgb, var(--p-primary-color) 16%, var(--p-content-background));
    color: var(--p-primary-color);
    border: 1px solid color-mix(in srgb, var(--p-primary-color) 35%, transparent);
}

.localizacao-chip--fechado {
    background: var(--p-content-hover-background);
    color: var(--p-text-muted-color);
    border: 1px solid var(--p-content-border-color);
}

.localizacao-chip--mais {
    flex: 0 0 auto;
    max-width: none;
    background: var(--p-content-hover-background);
    color: var(--p-text-muted-color);
    border: 1px solid var(--p-content-border-color);
}
</style>

<style>
/* Tooltip portaled no body — fora do escopo do componente */
.p-tooltip.sgdl-tooltip-localizacao {
    max-width: min(24rem, 92vw);
}

.p-tooltip.sgdl-tooltip-localizacao .p-tooltip-text {
    padding: 0.55rem 0.65rem;
    background: var(--p-content-background);
    color: var(--p-text-color);
    border: 1px solid var(--p-content-border-color);
    box-shadow: 0 4px 16px color-mix(in srgb, var(--p-text-color) 12%, transparent);
}

.p-tooltip.sgdl-tooltip-localizacao .p-tooltip-arrow {
    border-top-color: var(--p-content-border-color);
    border-bottom-color: var(--p-content-border-color);
}

.sgdl-loc-tip {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    text-align: left;
}

.sgdl-loc-tip__item + .sgdl-loc-tip__item {
    padding-top: 0.45rem;
    border-top: 1px solid var(--p-content-border-color);
}

.sgdl-loc-tip__row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
}

.sgdl-loc-tip__sigla {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    color: var(--p-text-color);
}

.sgdl-loc-tip__qtd {
    font-size: 0.65rem;
    font-weight: 600;
    color: var(--p-text-muted-color);
}

.sgdl-loc-tip__badge {
    font-size: 0.62rem;
    font-weight: 600;
    line-height: 1.2;
    padding: 0.08rem 0.35rem;
    border-radius: 0.25rem;
    white-space: nowrap;
}

.sgdl-loc-tip__badge--aberto {
    background: color-mix(in srgb, var(--p-primary-color) 18%, var(--p-content-background));
    color: var(--p-primary-color);
    border: 1px solid color-mix(in srgb, var(--p-primary-color) 32%, transparent);
}

.sgdl-loc-tip__badge--fechado {
    background: var(--p-content-hover-background);
    color: var(--p-text-muted-color);
    border: 1px solid var(--p-content-border-color);
}

.sgdl-loc-tip__orgao {
    margin-top: 0.15rem;
    font-size: 0.68rem;
    line-height: 1.35;
    color: var(--p-text-muted-color);
}
</style>
