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
import MultiSelect from 'primevue/multiselect';
import FileUpload from 'primevue/fileupload';
import Chip from 'primevue/chip';
import Message from 'primevue/message';
import Textarea from 'primevue/textarea';
import Divider from 'primevue/divider';
import Avatar from 'primevue/avatar';
import Dialog from 'primevue/dialog';
import Checkbox from 'primevue/checkbox';
import { descricaoParaHtml } from '@/utils/oficioTexto';
import { exibirProtocoloDemanda, formatarProtocoloLegislativo } from '@/utils/protocoloLegislativo';
import {
    DECLARACAO_CONCLUSAO,
    DECLARACAO_CONCLUSAO_FINAL,
    DECLARACAO_DESPACHO,
    DECLARACAO_DEVOLUTIVA,
    DECLARACAO_GESTOR_PROTOCOLO,
    CONTEXTO_ASSINATURA,
    despachoInicialPendenteGestor,
    conclusaoFinalPendenteGestor,
    usuarioDeveBloquearOperacaoAguardandoGestor,
    formatSignatarioLinha,
    gestorPorId,
    modoPainelAssinaturaProtocolo,
    MODO_PAINEL_ASSINATURA,
    usuarioEhGestorProtocoloSgac,
    usuarioPodePainelProtocoloCentral,
    validarAssinaturaFormulario,
    payloadAssinaturaProtocolo,
    mensagemErroAssinatura
} from '@/constants/assinaturaEletronica';
import {
    FLUXO_TRANSVERSAL,
    aplicarAtualizacaoTramitacaoLocal,
    mesclarTramitacoesProtocoloEditaveis,
    sincronizarTramitacoesNaTimeline,
    tramitacoesParaTimelineOperacional
} from '@/constants/operacionalEstado';
import OperacionalTimeline from '@/components/demanda/OperacionalTimeline.vue';
import FormularioScatterGather from '@/components/demanda/FormularioScatterGather.vue';
import FormularioResultadoOperacional from '@/components/demanda/FormularioResultadoOperacional.vue';
import {
    estadoInicialResultadoOperacional,
    validarResultadoOperacional,
    payloadResultadoOperacional
} from '@/constants/estudoViabilidade';
import FormularioTramitacao from '@/components/tramitacao/FormularioTramitacao.vue';
import TramitacaoJanelaCorrecao from '@/components/tramitacao/TramitacaoJanelaCorrecao.vue';
import DialogAssinaturaEletronica from '@/components/tramitacao/DialogAssinaturaEletronica.vue';
import DialogConfirmacaoTramitacao from '@/components/tramitacao/DialogConfirmacaoTramitacao.vue';
import ValidacaoGestorDemandaBanner from '@/components/tramitacao/ValidacaoGestorDemandaBanner.vue';
import FormularioDevolutivaProtocolo from '@/components/devolutiva/FormularioDevolutivaProtocolo.vue';
import ConclusaoDigitalVereador from '@/components/devolutiva/ConclusaoDigitalVereador.vue';
import DialogClusterAderencia from '@/components/demanda/DialogClusterAderencia.vue';
import DialogVincularSuperOsDemanda from '@/components/cluster/DialogVincularSuperOsDemanda.vue';
import {
    estadoFormularioTramitacao,
    inicializarDestinosAndamento,
    inicializarDestinosDespacho,
    destinoAndamentoPayload,
    destinosParaPayload,
    temIntegradosDestinos,
    resumoDestinosTexto,
    contarPernasDestinos,
    despachoEhTransversal,
    MAX_PERNAS_DESPACHO,
    MODO_ANDAMENTO,
    MODO_DESPACHO
} from '@/constants/tramitacaoFormulario';
import {
    descricaoTramitacaoVereador,
    montarTimelineVereador,
    filtrarTramitacoesVereador,
    labelTramitacaoVereador,
    perfilEhVereador,
    rotuloInstitucionalTramitacao
} from '@/constants/tramitacaoVisibilidade';
import { descricaoTramitacaoParaExibicao, pareceHtmlRico } from '@/utils/tramitacaoTexto';
import { buildContextoPlaceholders } from '@/constants/textoPadraoDespacho';
import { payloadDespachoDestinos, buildDevolutivaPayload, buildMultipartPayload, estadoFormularioDevolutiva } from '@/utils/protocoloFormData';

const route = useRoute();
const router = useRouter();
const demanda = ref(null);
const loading = ref(true);
const userStore = useUserStore();
const toast = useToast();
const confirm = useConfirm();

const formAndamento = ref(estadoFormularioTramitacao());
const formDespacho = ref(estadoFormularioTramitacao());
const formDespachoRef = ref(null);
const formAndamentoRef = ref(null);
const formDevolutivaRef = ref(null);
const confirmTramitacaoVisible = ref(false);
const pendingAssinarTramitacao = ref(false);

const orgaosCatalogo = ref([]);

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

const isVereador = computed(() => perfilEhVereador(userStore.currentUser?.perfil));

const isIndicacao = computed(() => demanda.value?.tipo_legislativo === 'INDICACAO');

/** Timeline institucional (sem parecer técnico) para vereador ou Câmara em indicações. */
const timelineModoInstitucional = computed(
    () => isVereador.value || (userStore.currentUser?.perfil === 'CAMARA' && isIndicacao.value)
);

const isGestor = computed(() => userStore.currentUser?.perfil === 'GESTOR');

const podeOperarProtocoloCentral = computed(
    () =>
        userStore.currentUser?.perfil === 'PROTOCOLO' ||
        usuarioPodePainelProtocoloCentral(userStore.currentUser, userStore)
);

const isProtocolo = computed(() => podeOperarProtocoloCentral.value);

const isProtocoloPerfil = computed(() => userStore.currentUser?.perfil === 'PROTOCOLO');

const ehGestorProtocoloSgac = computed(() =>
    usuarioEhGestorProtocoloSgac(userStore.currentUser, userStore)
);

const assinaturasResumo = computed(() => demanda.value?.assinaturas_resumo || {});

const despachoAguardandoGestor = computed(
    () =>
        demanda.value?.status === 'AGUARDANDO_PROTOCOLO' &&
        despachoInicialPendenteGestor(assinaturasResumo.value)
);

const conclusaoFinalAguardandoGestor = computed(() =>
    conclusaoFinalPendenteGestor(assinaturasResumo.value)
);

const bloqueioOperacaoAguardandoGestor = computed(() =>
    usuarioDeveBloquearOperacaoAguardandoGestor(
        assinaturasResumo.value,
        userStore.currentUser,
        userStore
    )
);

const validacaoGestorBannerRef = ref(null);

const podeGerirSuperOs = computed(
    () => isSecretaria.value || isProtocolo.value
);

const mostrarCardSuperOs = computed(
    () =>
        (superOs.value?.total_vinculados ?? 0) >= 2 &&
        (superOs.value?.demandas_vinculadas?.length ?? 0) >= 2 &&
        podeGerirSuperOs.value
);

const tituloCardCluster = computed(
    () => superOs.value?.tipo_display || 'Super Ordem de Serviço'
);

const ehClusterMultiDestino = computed(() => superOs.value?.tipo === 'MULTI_DESTINO');

const podeDespacharProtocolo = computed(
    () =>
        isProtocoloPerfil.value &&
        demanda.value?.status === 'AGUARDANDO_PROTOCOLO' &&
        !despachoAguardandoGestor.value
);

const podeDespacharDevolutiva = computed(
    () =>
        !conclusaoFinalAguardandoGestor.value &&
        (podeConclusaoFinalOperacional.value ||
            (isProtocolo.value && demanda.value?.status === 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO'))
);

const usaEndpointConclusaoFinal = computed(() => podeConclusaoFinalOperacional.value);

const podeEncerrarDevolutiva = computed(
    () => isProtocolo.value && demanda.value?.status === 'DEVOLVIDO_VEREADOR'
);

const usarDescricaoEstruturada = computed(
    () => isProtocolo.value || isSecretaria.value || isGestor.value
);

const podeVerStandByExecutivo = computed(
    () => isProtocolo.value || isSecretaria.value || isGestor.value
);

const enderecoSugeridoDemanda = computed(() => {
    const d = demanda.value;
    if (!d) return '';
    const partes = [d.logradouro, d.numero ? `nº ${d.numero}` : null, d.bairro].filter(Boolean);
    return partes.join(', ');
});

const demandaContextoTextoPadrao = computed(() =>
    buildContextoPlaceholders(demanda.value, {
        orgao_destino: orgaoAndamentoNome.value || ''
    })
);

const todasSecretarias = ref([]);
const despachoDialog = ref(false);
const assinaturaDespachoDialogVisible = ref(false);
const assinaturaDevolutivaDialogVisible = ref(false);
const assinaturaConclusaoDialogVisible = ref(false);
const executandoAssinatura = ref(false);
const clusterAderenciaDialog = ref(false);
const clusterAderenciaSituacao = ref(null);
const clusterAderenciaLoading = ref(false);
const vincularSuperOsDialog = ref(false);
const vincularSuperOsLoading = ref(false);

const podeGerirClusterOperacional = computed(() =>
    ['PROTOCOLO', 'GESTOR', 'SECRETARIA'].includes(userStore.currentUser?.perfil)
);

const podeVincularSuperOs = computed(
    () =>
        podeGerirClusterOperacional.value &&
        demanda.value &&
        !demanda.value.cluster?.id &&
        demanda.value.status === 'AGUARDANDO_PROTOCOLO' &&
        Boolean(demanda.value.sinapse_servico_id)
);
const despachoPreview = ref(null);
const despachoAssinatura = ref({
    declaracaoOperador: false,
    declaracaoGestor: false,
    gestor_protocolo_id: null
});
const carregandoDespachoPreview = ref(false);
const gestoresProtocolo = ref([]);
const despachoData = formDespacho;
const despachoAnexos = computed({
    get: () => formDespacho.value.anexos || [],
    set: (v) => {
        formDespacho.value.anexos = v;
    }
});
const formDevolutiva = ref(estadoFormularioDevolutiva());
const devolutivaPreview = ref(null);
const devolutivaAssinatura = ref({
    declaracaoOperador: false,
    declaracaoGestor: false,
    gestor_protocolo_id: null
});
const carregandoDevolutivaPreview = ref(false);

const isDevolutivaAlertaLeitura = computed(() => Boolean(demanda.value?.devolutiva_alerta_leitura));

const podeGerenciarAcompanhamento = computed(() => isSecretaria.value || isGestor.value);
const acompanhandoDemanda = computed(() => Boolean(demanda.value?.acompanhando));
const podeAcompanharDemanda = computed(() => Boolean(demanda.value?.pode_acompanhar));
const somenteAcompanhamento = computed(() => Boolean(demanda.value?.somente_acompanhamento));

const TIPO_DEVOLUCAO_PROTOCOLO = 'DEVOLUCAO_PROTOCOLO';
const TIPO_CONCLUSAO_PARCIAL = 'CONCLUSAO_PARCIAL';

const estadoOperacional = ref(null);
const carregandoEstadoOperacional = ref(false);
const recusaDialog = ref(false);
const recusaParecer = ref('');
const vincularServicoDialog = ref(false);
const servicoVinculoId = ref(null);
const servicosCarta = ref([]);
const carregandoServicosCarta = ref(false);

const acoesOperacionais = computed(() => estadoOperacional.value?.acoes_disponiveis || []);

const podeAbrirPernasTransversal = computed(() =>
    acoesOperacionais.value.includes('abrir_pernas_transversal')
);

const orgaoLiderTransversal = computed(() => {
    const d = demanda.value;
    if (!d) return null;
    return (
        d.sinapse_orgao_lider_id ||
        estadoOperacional.value?.sinapse_orgao_lider_id ||
        orgaoIdDemanda.value
    );
});

const orgaoLiderTransversalNome = computed(() => {
    if (estadoOperacional.value?.orgao_lider_nome) {
        return estadoOperacional.value.orgao_lider_nome;
    }
    const id = orgaoLiderTransversal.value;
    if (!id) return '';
    const o = orgaosCatalogo.value.find((item) => Number(item.id) === Number(id));
    return o?.nome || '';
});

const secretariasIntegraveisTransversal = computed(() => {
    const sessao = orgaoIdDemanda.value;
    if (!sessao) return orgaosCatalogo.value;
    return orgaosCatalogo.value.filter((s) => Number(s.id) !== Number(sessao));
});

const podeVincularServico = computed(() => acoesOperacionais.value.includes('vincular_servico'));
const podeRecusaProtocolo = computed(() => acoesOperacionais.value.includes('recusa_protocolo'));
const podeConclusaoParcial = computed(() => acoesOperacionais.value.includes('conclusao_parcial'));
const podeDevolverProtocolo = computed(() => acoesOperacionais.value.includes('devolver_protocolo'));
const podeConclusaoFinalOperacional = computed(() => acoesOperacionais.value.includes('conclusao_final'));

const podeScatterGather = computed(
    () =>
        !bloqueioOperacaoAguardandoGestor.value &&
        acoesOperacionais.value.some((a) => String(a).startsWith('scatter_'))
);

const processoScatterGatherAtivo = computed(
    () =>
        Boolean(estadoOperacional.value?.processo_scatter_gather) ||
        podeScatterGather.value ||
        (estadoOperacional.value?.nos_ativos ?? 0) > 0 ||
        (estadoOperacional.value?.nos_usuario?.length ?? 0) > 0
);

const demandaScatterReferenciaId = computed(() => {
    const ref = estadoOperacional.value?.demanda_scatter_id;
    if (!ref || Number(ref) === Number(demanda.value?.id)) return null;
    return Number(ref);
});

const exibirAvisoDemandaScatterParalela = computed(
    () =>
        demanda.value?.status === 'EM_EXECUCAO' &&
        !podeScatterGather.value &&
        demandaScatterReferenciaId.value != null
);
const nosUsuarioScatter = computed(() => estadoOperacional.value?.nos_usuario || []);
const destinosOcupadosScatter = computed(
    () => estadoOperacional.value?.destinos_nos_ativos || []
);
const gruposNosScatter = computed(
    () => estadoOperacional.value?.grupos_nos_usuario || []
);
const gruposNosPainelScatter = computed(
    () => estadoOperacional.value?.grupos_nos_painel || []
);

const orgaoLiderImediatoNome = computed(() => {
    const ctx = estadoOperacional.value?.contexto_secretaria;
    if (ctx?.orgao_lider_imediato_nome) return ctx.orgao_lider_imediato_nome;
    return orgaoLiderTransversalNome.value;
});

const tipoOperacionalEspecial = computed(() =>
    [TIPO_DEVOLUCAO_PROTOCOLO, TIPO_CONCLUSAO_PARCIAL].includes(formAndamento.value.tipo)
);

const exibirDestinosForm = computed(
    () => demanda.value?.status === 'EM_EXECUCAO' && !tipoOperacionalEspecial.value
);

const podeOperarTramitacao = computed(
    () =>
        !bloqueioOperacaoAguardandoGestor.value &&
        !somenteAcompanhamento.value &&
        !isDevolutivaAlertaLeitura.value &&
        !processoScatterGatherAtivo.value &&
        !(usaFluxoOperacional.value && demanda.value?.status === 'EM_EXECUCAO') &&
        (podeRegistrarAndamento.value ||
            podeAbrirPernasTransversal.value ||
            podeDevolverProtocolo.value ||
            podeConclusaoParcial.value)
);

const formTemIntegrados = computed(() =>
    temIntegradosDestinos(formAndamento.value.destinos, orgaoIdDemanda.value)
);

const labelBotaoTramitacao = computed(() => {
    if (formAndamento.value.tipo === TIPO_DEVOLUCAO_PROTOCOLO) return 'Devolver ao Protocolo';
    if (formAndamento.value.tipo === TIPO_CONCLUSAO_PARCIAL) return 'Registrar conclusão parcial';
    if (formAndamento.value.tipo === 'CONCLUSAO') return 'Concluir operação (assinatura)';
    if (formTemIntegrados.value && formAndamento.value.tipo) {
        return 'Registrar andamento e abrir tramitação transversal';
    }
    if (formTemIntegrados.value) return 'Abrir tramitação transversal';
    return 'Adicionar andamento';
});

const usaFluxoOperacional = computed(() =>
    Boolean(demanda.value?.fluxo_roteamento || estadoOperacional.value?.fluxo_roteamento)
);

const superOsSeguidoraSemFluxoLocal = computed(
    () =>
        Boolean(superOs.value?.ativo && !superOs.value?.eh_lider && !demanda.value?.fluxo_roteamento)
);

const ehEntradaTendencia = computed(
    () => estadoOperacional.value?.tipo_entrada === 'TENDENCIA' || demanda.value?.origem_vinculo === 'TENDENCIA'
);

const rotuloServicoOuTendencia = computed(() => {
    if (ehEntradaTendencia.value) {
        return demanda.value?.tendencia?.titulo || 'Demanda por tendência (fora da carta)';
    }
    return demanda.value?.servico?.nome || 'Serviço não vinculado';
});

const tiposTramitacaoFiltrados = computed(() => {
    const tipos = [];
    if (podeDevolverProtocolo.value) {
        tipos.push({ label: 'Devolver ao Protocolo', value: TIPO_DEVOLUCAO_PROTOCOLO });
    }
    if (demanda.value?.status === 'EM_EXECUCAO') {
        const base = tiposTramitacao.value.filter((t) => {
            if (demanda.value?.fluxo_roteamento === FLUXO_TRANSVERSAL && t.value === 'CONCLUSAO') {
                return false;
            }
            return true;
        });
        tipos.push(...base);
        if (podeConclusaoParcial.value) {
            tipos.push({ label: 'Conclusão parcial', value: TIPO_CONCLUSAO_PARCIAL });
        }
    }
    return tipos;
});

const historicoTecnicoOperacional = computed(
    () => estadoOperacional.value?.historico_tecnico || null
);
const conclusaoDialog = ref(false);
const conclusaoPreview = ref(null);
const conclusaoAssinatura = ref({ declaracaoAceita: false });
const conclusaoResultado = ref(estadoInicialResultadoOperacional());
const carregandoConclusaoPreview = ref(false);
const pacoteDevolutiva = ref(null);

const isVereadorAutor = computed(
    () =>
        userStore.currentUser?.perfil === 'VEREADOR' &&
        demanda.value?.autor?.id === userStore.currentUser?.id
);

const mostrarConclusaoDigitalVereador = computed(
    () =>
        isVereadorAutor.value &&
        pacoteDevolutiva.value &&
        ['DEVOLVIDO_VEREADOR', 'FINALIZADO'].includes(demanda.value?.status)
);

const usaTimelineOperacional = computed(() => {
    if (mostrarConclusaoDigitalVereador.value) return false;
    const temTimeline = (estadoOperacional.value?.timeline?.length ?? 0) > 0;
    if (isVereador.value) return temTimeline || usaFluxoOperacional.value;
    return usaFluxoOperacional.value || temTimeline;
});

/** Timeline operacional — estado API (cluster unificado) ou tramitações locais / fallback vereador. */
const timelineOperacionalExibicao = computed(() => {
    const estado = estadoOperacional.value?.timeline;
    let base = [];
    if (!isVereador.value && Array.isArray(estado) && estado.length) {
        base = estado;
    } else if (!isVereador.value && demanda.value?.tramitacoes?.length) {
        base = tramitacoesParaTimelineOperacional(
            demanda.value.tramitacoes,
            demanda.value.id
        );
    } else if (Array.isArray(estado) && estado.length) {
        base = estado;
    } else if (!demanda.value?.tramitacoes?.length) {
        return [];
    } else {
        return filtrarTramitacoesVereador(demanda.value.tramitacoes, demanda.value.status).map((t) => ({
            id: t.id,
            demanda_id: demanda.value.id,
            tipo: t.tipo,
            descricao: t.descricao,
            metadata: {},
            orgao_nome: t.orgao_nome,
            orgao_id: null,
            responsavel: null,
            timestamp: t.timestamp,
            ramificacao: null
        }));
    }

    if (isProtocoloPerfil.value && demanda.value?.tramitacoes?.length) {
        base = mesclarTramitacoesProtocoloEditaveis(
            base,
            demanda.value.id,
            demanda.value.tramitacoes
        );
    }
    if (!isVereador.value && demanda.value?.tramitacoes?.length && base.length) {
        base = sincronizarTramitacoesNaTimeline(base, demanda.value.tramitacoes);
    }
    return base;
});

/** Despachos do Protocolo editáveis que ainda não entraram na timeline exibida. */
const tramitacoesCorrecaoProtocoloForaTimeline = computed(() => {
    if (!isProtocoloPerfil.value || !demanda.value?.tramitacoes?.length) return [];
    const idsTimeline = new Set(timelineOperacionalExibicao.value.map((i) => String(i.id)));
    const tipos = new Set(['DESPACHO', 'CONCLUSAO_FINAL', 'DEVOLUTIVA_PROTOCOLO', 'TRIAGEM_PROTOCOLO']);
    return demanda.value.tramitacoes.filter(
        (t) =>
            (t.pode_editar || t.aguardando_validacao_gestor) &&
            tipos.has(String(t.tipo || '').toUpperCase()) &&
            !idsTimeline.has(String(t.id))
    );
});

const timelineVereadorVisivel = computed(() =>
    montarTimelineVereador(
        timelineOperacionalExibicao.value,
        historicoTecnicoOperacional.value || pacoteDevolutiva.value?.historico_tecnico,
        demanda.value?.status,
        demanda.value?.id,
        estadoOperacional.value?.demanda_lider_id ||
            demanda.value?.super_os?.lider_id ||
            demanda.value?.id,
        (items) => items,
        true
    )
);

const mostrarOperacionalTimeline = computed(() => {
    if (isVereador.value) {
        return timelineVereadorVisivel.value.length > 0;
    }
    if (mostrarConclusaoDigitalVereador.value) return false;
    if (timelineOperacionalExibicao.value.length > 0) return true;
    return (
        usaFluxoOperacional.value &&
        (estadoOperacional.value?.timeline?.length ?? 0) > 0
    );
});

const descricaoExibicao = computed(() => {
    const raw = demanda.value?.descricao || '';
    if (!raw) return '';
    if (usarDescricaoEstruturada.value || mostrarConclusaoDigitalVereador.value || isVereador.value) {
        if (pareceHtmlRico(raw)) return raw;
        return descricaoParaHtml(raw);
    }
    return raw;
});

const carregarPacoteDevolutiva = async () => {
    if (!demanda.value?.id) return;
    const status = demanda.value.status;
    const statusesPermitidos = isVereador.value
        ? ['DEVOLVIDO_VEREADOR', 'FINALIZADO']
        : ['DEVOLVIDO_VEREADOR', 'FINALIZADO', 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO'];
    if (!statusesPermitidos.includes(status)) {
        pacoteDevolutiva.value = null;
        return;
    }
    try {
        const { data } = await ApiService.getPacoteDevolutiva(demanda.value.id);
        pacoteDevolutiva.value = data;
    } catch {
        pacoteDevolutiva.value = demanda.value.pacote_devolutiva || null;
    }
};

const superOs = computed(() => demanda.value?.super_os || null);
const orgaosIntegrados = computed(() => demanda.value?.orgaos_integrados || []);
const temGeolocalizacaoDemanda = computed(
    () => demanda.value?.latitude != null && demanda.value?.longitude != null
);

const verDemandaNoMapa = () => {
    if (!demanda.value?.id || !temGeolocalizacaoDemanda.value) return;
    router.push({ name: 'mapa-calor', query: { demanda_id: String(demanda.value.id) } });
};

const assinaturasParaTimelineOperacional = computed(() => {
    if (isVereador.value && !mostrarConclusaoDigitalVereador.value) {
        return pacoteDevolutiva.value?.assinaturas || demanda.value?.assinaturas || [];
    }
    return demanda.value?.assinaturas || [];
});

const gestorDespachoSelecionado = computed(() =>
    gestorPorId(gestoresProtocolo.value, despachoAssinatura.value.gestor_protocolo_id)
);
const gestorDevolutivaSelecionado = computed(() =>
    gestorPorId(gestoresProtocolo.value, formDevolutiva.value.gestor_protocolo_id)
);

const modoAssinaturaDespachoInicial = computed(() =>
    modoPainelAssinaturaProtocolo(CONTEXTO_ASSINATURA.DESPACHO_INICIAL, userStore.currentUser, userStore)
);

const modoAssinaturaDevolutiva = computed(() => {
    const ctx = usaEndpointConclusaoFinal.value
        ? CONTEXTO_ASSINATURA.CONCLUSAO_FINAL
        : CONTEXTO_ASSINATURA.DEVOLUTIVA;
    const previewModo = devolutivaPreview.value?.modo_assinatura;
    if (previewModo) return previewModo;
    return modoPainelAssinaturaProtocolo(ctx, userStore.currentUser, userStore);
});

const exibirDescricaoTramitacao = (item) => descricaoTramitacaoParaExibicao(item?.descricao);

const ehLiderSuperOs = computed(() => {
    if (!superOs.value?.ativo) return true;
    return superOs.value.eh_lider === true;
});

/** Super OS: secretaria deve operar na demanda líder (protocolada), não na seguidora. */
const idDemandaOperacionalSuperOs = (d) => {
    const so = d?.super_os;
    if (!so?.ativo || !so.tramitacao_apenas_lider) return null;
    if (so.eh_lider) return null;
    const lid = so.lider_id;
    if (!lid || Number(lid) === Number(d.id)) return null;
    return Number(lid);
};

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
    () =>
        isSecretaria.value &&
        demanda.value?.status === 'PROTOCOLADO' &&
        ehLiderSuperOs.value &&
        !usaFluxoOperacional.value
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
    const proto = exibirProtocoloDemanda(vinc, '');
    const titulo = (vinc.titulo || '').trim();
    const curto = titulo.length > 28 ? `${titulo.slice(0, 28)}…` : titulo;
    return proto ? `${proto}${curto ? ` · ${curto}` : ''}` : `#${vinc.id}`;
};

const iniciarExecucao = () => {
    confirm.require({
        message: 'A secretaria responsável iniciará a execução operacional deste processo.',
        header: 'Iniciar execução',
        icon: 'pi pi-play',
        accept: async () => {
            try {
                if (usaFluxoOperacional.value) {
                    await ApiService.iniciarExecucaoOperacional(demanda.value.id);
                } else {
                    await ApiService.atualizarStatusDemanda(demanda.value.id, 'EM_EXECUCAO');
                }
                toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Execução iniciada.', life: 3000 });
                await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
            } catch (error) {
                toast.add({
                    severity: 'error',
                    summary: 'Erro',
                    detail: error?.response?.data?.detail || 'Não foi possível iniciar a execução.',
                    life: 4000
                });
            }
        }
    });
};

const timelineOrdenada = computed(() => {
    if (!demanda.value?.tramitacoes?.length) {
        return [];
    }
    let items = isVereador.value
        ? filtrarTramitacoesVereador(demanda.value.tramitacoes, demanda.value.status)
        : [...demanda.value.tramitacoes];
    return items.reverse();
});

const orgaoIdDemanda = computed(() => {
    const d = demanda.value;
    if (!d) return null;
    if (isSecretaria.value && userStore.currentUser?.sinapse_orgao_id) {
        return Number(userStore.currentUser.sinapse_orgao_id);
    }
    return (
        d.sinapse_orgao_id ||
        d.secretaria_destino?.id ||
        d.unidade_administrativa?.sinapse_orgao_id ||
        userStore.currentUser?.sinapse_orgao_id ||
        null
    );
});

const orgaoAndamentoNome = computed(() => {
    const id = orgaoIdDemanda.value;
    if (!id) return '';
    const perna = (estadoOperacional.value?.pernas_operacionais || []).find(
        (p) => Number(p.sinapse_orgao_id) === Number(id)
    );
    if (perna?.orgao_nome) return perna.orgao_nome;
    const o = orgaosCatalogo.value.find((item) => Number(item.id) === Number(id));
    return o?.nome || '';
});

const podeRegistrarAndamento = computed(() => {
    if (processoScatterGatherAtivo.value || podeScatterGather.value) return false;
    if (!isSecretaria.value || demanda.value?.status !== 'EM_EXECUCAO') return false;
    if (ehLiderSuperOs.value) return true;
    const orgUser = userStore.currentUser?.sinapse_orgao_id;
    if (!orgUser || !estadoOperacional.value?.usa_pernas_operacionais) return false;
    const pernas =
        estadoOperacional.value?.pernas_operacionais ||
        estadoOperacional.value?.participantes_transversal ||
        [];
    return pernas.some(
        (p) => Number(p.sinapse_orgao_id) === Number(orgUser) && !p.concluida && !p.conclusao_parcial
    );
});

const carregarUnidadesSetor = async () => {
    const orgaoId = orgaoIdDemanda.value;
    if (orgaoId && !formAndamento.value.destinos?.length) {
        formAndamento.value.destinos = inicializarDestinosAndamento(orgaoId);
    }
};

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

const carregarEstadoOperacional = async () => {
    if (!demanda.value?.id) {
        estadoOperacional.value = null;
        return;
    }
    carregandoEstadoOperacional.value = true;
    try {
        const { data } = await ApiService.getEstadoOperacional(demanda.value.id);
        estadoOperacional.value = data;
        if (data?.status && demanda.value && demanda.value.status !== data.status) {
            demanda.value = { ...demanda.value, status: data.status };
        }
        if (
            data?.fluxo_roteamento &&
            demanda.value &&
            !demanda.value.fluxo_roteamento
        ) {
            const refreshed = await ApiService.getDemandaById(demanda.value.id);
            demanda.value = refreshed.data;
        }
    } catch {
        estadoOperacional.value = null;
    } finally {
        carregandoEstadoOperacional.value = false;
    }
};

const recarregarDemandaCompleta = async () => {
    const id = demanda.value?.id || route.params.id;
    if (!id) return;
    const response = await ApiService.getDemandaById(id);
    demanda.value = response.data;
    await Promise.all([
        carregarPacoteDevolutiva(),
        carregarUnidadesSetor(),
        carregarEstadoOperacional(),
        isSecretaria.value || isGestor.value || podeOperarProtocoloCentral.value
            ? carregarOrgaos()
            : Promise.resolve()
    ]);
};

/** Refresh imediato da timeline após correção + recarga completa em background. */
const onTramitacaoCorrigida = async (payload) => {
    if (payload?.id) {
        const atualizado = aplicarAtualizacaoTramitacaoLocal({
            demanda: demanda.value,
            estadoOperacional: estadoOperacional.value,
            payload
        });
        demanda.value = atualizado.demanda;
        estadoOperacional.value = atualizado.estadoOperacional;
    }
    await recarregarDemandaCompleta();
};

const carregarDemanda = async (demandaId) => {
    if (!demandaId) {
        loading.value = false;
        return;
    }
    loading.value = true;
    try {
        const response = await ApiService.getDemandaById(demandaId);
        const alvoOperacional = isSecretaria.value
            ? idDemandaOperacionalSuperOs(response.data)
            : null;
        if (alvoOperacional) {
            router.replace({ name: 'demandas-detalhes', params: { id: String(alvoOperacional) } });
            return;
        }
        demanda.value = response.data;
        await Promise.all([
            carregarPacoteDevolutiva(),
            carregarUnidadesSetor(),
            carregarEstadoOperacional(),
            isSecretaria.value || isGestor.value || podeOperarProtocoloCentral.value
            ? carregarOrgaos()
            : Promise.resolve()
        ]);
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
    await carregarOrgaos();
    todasSecretarias.value = orgaosCatalogo.value;
};

const despachoMultiOrgao = computed(() => despachoEhTransversal(formDespacho.value.destinos));

const montarPayloadDespacho = () =>
    payloadDespachoDestinos(formDespacho.value, orgaoCompetenteDespacho.value);

const onAnexosRejeitadosForm = (msg) => {
    toast.add({ severity: 'warn', summary: 'Anexos', detail: msg, life: 4000 });
};

const resumoDestinosAndamento = computed(() =>
    resumoDestinosTexto(formAndamento.value.destinos, orgaosCatalogo.value)
);

const resumoDestinosDespacho = computed(() =>
    resumoDestinosTexto(formDespacho.value.destinos, orgaosCatalogo.value)
);



const orgaoCompetenteDespacho = computed(() => {
    const d = demanda.value;
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
    const d = demanda.value;
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

const podeMontarDespacho = () => {
    const payload = montarPayloadDespacho();
    if (!payload.destinos?.length && !payload.secretaria_id) return false;
    const validacao = formDespachoRef.value?.validarDestinos?.();
    if (validacao && !validacao.ok) return false;
    const totalPernas =
        formDespachoRef.value?.contarPernasValidas?.() ??
        contarPernasDestinos(formDespacho.value.destinos);
    return totalPernas > 0 && totalPernas <= MAX_PERNAS_DESPACHO;
};

const detalheErroDespachoSetores = () =>
    formDespachoRef.value?.validarDestinos?.()?.mensagem ||
    'Informe o órgão competente e selecione os setores de destino.';

const abrirDialogoDespachoInterno = async () => {
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

const abrirDialogoDespacho = async () => {
    if (isProtocoloPerfil.value && demanda.value?.cluster?.id) {
        try {
            const { data } = await ApiService.getClusterSituacaoAderencia(demanda.value.id);
            if (data?.exibir_decisao) {
                clusterAderenciaSituacao.value = data;
                clusterAderenciaDialog.value = true;
                return;
            }
        } catch {
            /* segue fluxo unitário */
        }
    }
    await abrirDialogoDespachoInterno();
};

const confirmarAderenciaCluster = async () => {
    if (!demanda.value?.id) return;
    clusterAderenciaLoading.value = true;
    try {
        const { data } = await ApiService.aderirClusterLider(demanda.value.id);
        demanda.value = data;
        toast.add({
            severity: 'success',
            summary: 'Integrada ao líder',
            detail: `Demanda integrada ao processo líder. Protocolo executivo: ${data?.protocolo_executivo || '—'}.`,
            life: 5000
        });
        clusterAderenciaDialog.value = false;
        clusterAderenciaSituacao.value = null;
        await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
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
    if (!demanda.value?.id) return;
    clusterAderenciaLoading.value = true;
    try {
        const { data } = await ApiService.desvincularDemandaClusterIndividual(demanda.value.id);
        demanda.value = data;
        clusterAderenciaDialog.value = false;
        clusterAderenciaSituacao.value = null;
        await abrirDialogoDespachoInterno();
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

const abrirDialogoVincularSuperOs = () => {
    vincularSuperOsDialog.value = true;
};

const confirmarVincularSuperOs = async (clusterId) => {
    if (!demanda.value?.id || !clusterId) return;
    vincularSuperOsLoading.value = true;
    try {
        await ApiService.vincularDemandaCluster(clusterId, demanda.value.id);
        toast.add({
            severity: 'success',
            summary: 'Vinculado',
            detail: 'Ofício integrado ao grupo Super OS.',
            life: 4000
        });
        vincularSuperOsDialog.value = false;
        await recarregarDemandaCompleta();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível vincular ao grupo.',
            life: 4000
        });
    } finally {
        vincularSuperOsLoading.value = false;
    }
};

const gerarPreviewDespacho = async () => {
    if (!podeMontarDespacho()) {
        toast.add({
            severity: 'warn',
            summary: 'Atenção',
            detail: detalheErroDespachoSetores(),
            life: 4000
        });
        return;
    }
    carregandoDespachoPreview.value = true;
    try {
        const { data } = await ApiService.previewDespachoDemanda(demanda.value.id, montarPayloadDespacho());
        despachoPreview.value = data;
        if (data.gestores_protocolo?.length) {
            gestoresProtocolo.value = data.gestores_protocolo;
        }
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível gerar a prévia de assinatura.',
            life: 4000
        });
    } finally {
        carregandoDespachoPreview.value = false;
    }
};

const confirmarDespacho = async () => {
    if (!podeMontarDespacho()) {
        toast.add({
            severity: 'warn',
            summary: 'Atenção',
            detail: detalheErroDespachoSetores(),
            life: 4000
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
        await gerarPreviewDespacho();
        if (!despachoPreview.value?.hash_documento) return;
    }
    assinaturaDespachoDialogVisible.value = true;
};

const executarDespachoComAssinatura = async (payloadAssinatura) => {
    executandoAssinatura.value = true;
    try {
        const { data } = await ApiService.despacharDemanda(
            demanda.value.id,
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
                : 'Demanda despachada com assinatura eletrônica. Você tem cerca de 60 segundos para corrigir ou desfazer na timeline.');
        if (data.demandas_desdobradas?.length) {
            const extras = data.demandas_desdobradas.map((d) => d.protocolo_executivo).join(', ');
            detail += ` Desdobramentos: ${extras}.`;
        }
        toast.add({ severity: 'success', summary: 'Sucesso', detail, life: 5000 });
        assinaturaDespachoDialogVisible.value = false;
        despachoDialog.value = false;
        await carregarDemanda(demanda.value.id);
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

function contextoCorrecaoTramitacaoItem(item) {
    const tipo = String(item?.tipo || '').toUpperCase();
    if (tipo === 'DESPACHO' || tipo === 'TRIAGEM_PROTOCOLO') return 'despacho';
    if (tipo === 'CONCLUSAO_FINAL' || tipo === 'DEVOLUTIVA_PROTOCOLO') return 'conclusao';
    if (tipo === 'OPERACAO_NO') return 'scatter';
    return 'andamento';
}

const limparFormularioTramitacao = () => {
    formAndamento.value = estadoFormularioTramitacao({
        destinos: inicializarDestinosAndamento(orgaoIdDemanda.value)
    });
};

const parecerOperacionalTexto = () => {
    const raw = formAndamento.value.descricao || '';
    if (typeof document !== 'undefined') {
        const el = document.createElement('div');
        el.innerHTML = raw;
        return (el.textContent || el.innerText || '').replace(/\s+/g, ' ').trim();
    }
    return raw.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
};

const abrirDialogoConclusao = () => {
    if (parecerOperacionalTexto().length < 10) {
        toast.add({
            severity: 'warn',
            summary: 'Parecer obrigatório',
            detail: 'Informe o parecer operacional na descrição (mín. 10 caracteres).',
            life: 4000
        });
        return;
    }
    conclusaoPreview.value = null;
    conclusaoAssinatura.value = { declaracaoAceita: false };
    conclusaoResultado.value = estadoInicialResultadoOperacional();
    conclusaoDialog.value = true;
};

const gerarPreviewConclusao = async () => {
    const parecer = parecerOperacionalTexto();
    if (parecer.length < 10) {
        toast.add({
            severity: 'warn',
            summary: 'Parecer obrigatório',
            detail: 'Informe o parecer operacional (mín. 10 caracteres).',
            life: 4000
        });
        return false;
    }
    carregandoConclusaoPreview.value = true;
    try {
        const { data } = await ApiService.previewConclusaoSecretaria(demanda.value.id, {
            parecer_operacional: parecer
        });
        conclusaoPreview.value = data;
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
        carregandoConclusaoPreview.value = false;
    }
};

const confirmarConclusaoComAssinatura = async () => {
    const parecer = parecerOperacionalTexto();
    if (parecer.length < 10) {
        toast.add({
            severity: 'warn',
            summary: 'Parecer obrigatório',
            detail: 'Informe o parecer operacional (mín. 10 caracteres).',
            life: 4000
        });
        return;
    }
    const erroResultado = validarResultadoOperacional(conclusaoResultado.value);
    if (erroResultado) {
        toast.add({
            severity: 'warn',
            summary: 'Resultado operacional',
            detail: erroResultado,
            life: 4000
        });
        return;
    }
    if (!conclusaoPreview.value?.hash_documento) {
        const ok = await gerarPreviewConclusao();
        if (!ok) return;
    }
    assinaturaConclusaoDialogVisible.value = true;
};

const executarConclusaoComAssinatura = async (payloadAssinatura) => {
    const parecer = parecerOperacionalTexto();
    const payloadResultado = payloadResultadoOperacional(conclusaoResultado.value);
    executandoAssinatura.value = true;
    try {
        if (demanda.value?.fluxo_roteamento === 'FLUXO_DIRETO') {
            if (formAndamento.value.anexos?.length) {
                const formData = new FormData();
                formData.append('demanda', demanda.value.id);
                formData.append('tipo', 'COMENTARIO');
                formData.append('descricao', formAndamento.value.descricao || 'Anexos da conclusão operacional.');
                formAndamento.value.anexos.forEach((file) => {
                    formData.append('arquivos_anexos', file);
                });
                await ApiService.createTramitacao(formData);
            }
            await ApiService.conclusaoTecnicaOperacional(demanda.value.id, {
                parecer_operacional: parecer,
                hash_documento: payloadAssinatura.hash_documento,
                declaracao: payloadAssinatura.declaracao || DECLARACAO_CONCLUSAO,
                ...payloadResultado
            });
        } else {
            const formData = new FormData();
            formData.append('demanda', demanda.value.id);
            formData.append('tipo', 'CONCLUSAO');
            formData.append('descricao', formAndamento.value.descricao);
            formAndamento.value.anexos?.forEach((file) => {
                formData.append('arquivos_anexos', file);
            });
            if (formAndamento.value.unidade_destino_id) {
                formData.append('unidade_destino_id', formAndamento.value.unidade_destino_id);
            }
            await ApiService.createTramitacao(formData);
            await ApiService.solicitarDevolutiva(demanda.value.id, {
                parecer_operacional: parecer,
                hash_documento: payloadAssinatura.hash_documento,
                declaracao: payloadAssinatura.declaracao || DECLARACAO_CONCLUSAO,
                ...payloadResultado
            });
        }
        toast.add({
            severity: 'success',
            summary: 'Conclusão assinada',
            detail:
                'Assinatura registrada. A conclusão só será encaminhada após validação do gestor do setor em Assinaturas pendentes.',
            life: 5000
        });
        assinaturaConclusaoDialogVisible.value = false;
        conclusaoDialog.value = false;
        await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
        limparFormularioTramitacao();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível concluir.',
            life: 4000
        });
    } finally {
        executandoAssinatura.value = false;
    }
};

const adicionarTramitacao = () => {
    const descricao = (formAndamento.value.descricao || '').trim();
    const temIntegrados = formTemIntegrados.value;
    const tipo = formAndamento.value.tipo;

    if (tipo === TIPO_DEVOLUCAO_PROTOCOLO) {
        if (descricao.length < 10) {
            toast.add({
                severity: 'warn',
                summary: 'Justificativa',
                detail: 'Informe a justificativa (mín. 10 caracteres).',
                life: 3000
            });
            return;
        }
        confirm.require({
            message:
                'Devolver ao Protocolo para novo roteamento? A secretaria deixará de operar este processo até novo despacho.',
            header: 'Devolução ao Protocolo',
            icon: 'pi pi-replay',
            accept: () => executarTramitacaoConfirmada({ assinar_eletronicamente: false })
        });
        return;
    }

    if (tipo === TIPO_CONCLUSAO_PARCIAL) {
        if (descricao.length < 10) {
            toast.add({
                severity: 'warn',
                summary: 'Parecer',
                detail: 'Informe o parecer parcial (mín. 10 caracteres).',
                life: 3000
            });
            return;
        }
        confirm.require({
            message: `Registrar conclusão parcial encaminhada a ${orgaoLiderImediatoNome.value || 'secretaria líder'}?`,
            header: 'Conclusão parcial',
            icon: 'pi pi-check',
            accept: () => executarTramitacaoConfirmada({ assinar_eletronicamente: false })
        });
        return;
    }

    if (temIntegrados && !descricao) {
        toast.add({
            severity: 'error',
            summary: 'Descrição obrigatória',
            detail: 'Descreva o encaminhamento transversal ou o andamento.',
            life: 3000
        });
        return;
    }
    if (!temIntegrados && (!formAndamento.value.tipo || !descricao)) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Preencha o tipo e a descrição da tramitação.', life: 3000 });
        return;
    }
    if (temIntegrados && contarPernasDestinos(formAndamento.value.destinos) > MAX_PERNAS_DESPACHO) {
        toast.add({
            severity: 'error',
            summary: 'Limite excedido',
            detail: `Máximo de ${MAX_PERNAS_DESPACHO} pernas por tramitação.`,
            life: 4000
        });
        return;
    }
    if (temIntegrados) {
        const validacao = formAndamentoRef.value?.validarDestinos?.();
        if (validacao && !validacao.ok) {
            toast.add({
                severity: 'warn',
                summary: 'Setor obrigatório',
                detail: validacao.mensagem || 'Selecione o setor de cada órgão integrado.',
                life: 4000
            });
            return;
        }
        const totalPernas = formAndamentoRef.value?.contarPernasValidas?.() ?? 0;
        if (totalPernas <= 0) {
            toast.add({
                severity: 'warn',
                summary: 'Setor obrigatório',
                detail: 'Selecione ao menos um setor para cada órgão integrado.',
                life: 4000
            });
            return;
        }
    }

    if (formAndamento.value.tipo === 'CONCLUSAO') {
        if (temIntegrados) {
            toast.add({
                severity: 'warn',
                summary: 'Ação inválida',
                detail: 'Remova os órgãos integrados antes de registrar conclusão.',
                life: 4000
            });
            return;
        }
        abrirDialogoConclusao();
        return;
    }

    confirmTramitacaoVisible.value = true;
};

const executarTramitacaoConfirmada = async ({ assinar_eletronicamente }) => {
    pendingAssinarTramitacao.value = assinar_eletronicamente;
    formAndamento.value.assinar_eletronicamente = assinar_eletronicamente;
    await salvarTramitacaoEFinalizar();
};

const salvarTramitacaoEFinalizar = async () => {
    const temIntegrados = formTemIntegrados.value;
    const descricao = formAndamento.value.descricao;
    const tipo = formAndamento.value.tipo;

    try {
        if (tipo === TIPO_DEVOLUCAO_PROTOCOLO) {
            await ApiService.devolverProtocoloOperacional(demanda.value.id, {
                justificativa: descricao
            });
            toast.add({
                severity: 'success',
                summary: 'Devolvido',
                detail: 'Processo retornou à fila do Protocolo.',
                life: 4000
            });
            await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
            limparFormularioTramitacao();
            return;
        }

        if (tipo === TIPO_CONCLUSAO_PARCIAL) {
            const anexos = formAndamento.value.anexos || [];
            if (anexos.length) {
                const formData = new FormData();
                formData.append('demanda', demanda.value.id);
                formData.append('tipo', 'COMENTARIO');
                formData.append('descricao', 'Anexos da conclusão parcial operacional.');
                anexos.forEach((file) => formData.append('arquivos_anexos', file));
                await ApiService.createTramitacao(formData);
            }
            const { data } = await ApiService.conclusaoParcialOperacional(demanda.value.id, {
                parecer_operacional: descricao
            });
            toast.add({
                severity: 'success',
                summary: 'Conclusão parcial',
                detail: data?.operacional?.processo_avancou
                    ? 'Todas as secretarias concluíram — processo encaminhado ao Protocolo para conclusão final.'
                    : 'Conclusão parcial registrada para sua secretaria. O processo aguarda as demais secretarias integradas.',
                life: 5000
            });
            await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
            limparFormularioTramitacao();
            return;
        }

        if (temIntegrados) {
            const payload = destinosParaPayload(formAndamento.value, orgaoIdDemanda.value);
            await ApiService.abrirPernasTransversal(demanda.value.id, {
                ...payload,
                observacao: descricao
            });
        }

        if (formAndamento.value.tipo) {
            const formData = new FormData();
            formData.append('demanda', demanda.value.id);
            formData.append('tipo', formAndamento.value.tipo);
            formData.append('descricao', descricao);
            formAndamento.value.anexos?.forEach((file) => {
                formData.append('arquivos_anexos', file);
            });
            const destino = destinoAndamentoPayload(formAndamento.value);
            if (destino.unidade_destino_id) {
                formData.append('unidade_destino_id', destino.unidade_destino_id);
            }
            await ApiService.createTramitacao(formData);
        }

        const msg =
            temIntegrados && formAndamento.value.tipo
                ? 'Tramitação transversal e andamento registrados!'
                : temIntegrados
                  ? 'Tramitação transversal aberta — secretarias integradas notificadas na timeline.'
                  : 'Andamento registrado!';
        toast.add({ severity: 'success', summary: 'Sucesso', detail: msg, life: 4000 });

        await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
        limparFormularioTramitacao();
    } catch (error) {
        console.error('Erro ao salvar tramitação:', error);
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível registrar a tramitação.',
            life: 4000
        });
    }
};

const onScatterGatherSuccess = async (data) => {
    const avancou = data?.processo_avancou;
    const aguardandoGestor = data?.aguardando_validacao_gestor;
    const parcial = data?.encerramento_parcial;
    const bloqueados = data?.nos_bloqueados || [];
    const encerrados = data?.nos_encerrados || [];
    const houveEncerramento = Array.isArray(encerrados) && encerrados.length > 0;

    if (parcial && bloqueados.length) {
        const idsEnc = encerrados.map((n) => n.id).join(', #');
        const idsBloc = bloqueados.map((b) => b.no_id).join(', #');
        toast.add({
            severity: 'warn',
            summary: 'Encerramento parcial',
            detail: idsEnc
                ? `Encerrado(s): #${idsEnc}. Permanece(m) aberto(s): #${idsBloc} — há encaminhamentos filhos em outras secretarias.`
                : `Alguns nós não puderam ser encerrados (#${idsBloc}).`,
            life: 8000
        });
    } else {
        toast.add({
            severity: 'success',
            summary: 'Operação registrada',
            detail: aguardandoGestor
                ? 'Assinatura registrada. O encerramento só será concluído após validação do gestor em Assinaturas pendentes.'
                : avancou
                  ? 'Todos os nós encerrados — processo aguardando conclusão final do Protocolo.'
                  : 'Ação scatter-gather registrada na timeline.',
            life: 5000
        });
    }
    if (data?.operacional) {
        estadoOperacional.value = data.operacional;
    }
    await recarregarDemandaCompleta();

    if (houveEncerramento && podeGerenciarAcompanhamento.value && !acompanhandoDemanda.value) {
        confirm.require({
            header: 'Acompanhar processo',
            message:
                'Deseja fixar este processo para acompanhamento gerencial? Você receberá alertas de prazo e marcos até a finalização.',
            icon: 'pi pi-bookmark',
            acceptLabel: 'Sim, acompanhar',
            rejectLabel: 'Agora não',
            accept: async () => {
                try {
                    const noId = encerrados[0]?.id;
                    await ApiService.acompanharDemanda(demanda.value.id, {
                        origem: 'ENCERRAMENTO',
                        no_operacional_id: noId || undefined
                    });
                    await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
                    toast.add({
                        severity: 'success',
                        summary: 'Acompanhamento',
                        detail: 'Processo fixado. Veja em «Acompanhando» na lista de protocolos.',
                        life: 5000
                    });
                } catch (err) {
                    toast.add({
                        severity: 'warn',
                        summary: 'Acompanhamento',
                        detail: err?.response?.data?.detail || 'Não foi possível fixar o processo.',
                        life: 4000
                    });
                }
            }
        });
    }
};

const onScatterGatherError = (msg) => {
    toast.add({
        severity: 'error',
        summary: 'Scatter-gather',
        detail: msg || 'Não foi possível registrar a operação.',
        life: 4000
    });
};

const fixarAcompanhamento = async () => {
    if (!demanda.value?.id) return;
    try {
        await ApiService.acompanharDemanda(demanda.value.id, { origem: 'MANUAL' });
        await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
        toast.add({
            severity: 'success',
            summary: 'Acompanhamento',
            detail: 'Processo fixado para acompanhamento.',
            life: 4000
        });
    } catch (err) {
        toast.add({
            severity: 'warn',
            summary: 'Acompanhamento',
            detail: err?.response?.data?.detail || 'Não foi possível fixar o processo.',
            life: 4000
        });
    }
};

const desfixarAcompanhamento = () => {
    if (!demanda.value?.id) return;
    confirm.require({
        header: 'Desfixar processo',
        message: 'Deseja parar de acompanhar este processo? Você deixará de receber alertas de prazo e marcos.',
        icon: 'pi pi-bookmark',
        acceptLabel: 'Desfixar',
        rejectLabel: 'Cancelar',
        acceptClass: 'p-button-danger',
        accept: async () => {
            try {
                await ApiService.desacompanharDemanda(demanda.value.id);
                await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
                toast.add({
                    severity: 'info',
                    summary: 'Acompanhamento',
                    detail: 'Processo desfixado.',
                    life: 4000
                });
            } catch (err) {
                toast.add({
                    severity: 'warn',
                    summary: 'Acompanhamento',
                    detail: err?.response?.data?.detail || 'Não foi possível desfixar.',
                    life: 4000
                });
            }
        }
    });
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

const textoDevolutivaLimpo = (html) => (html || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

const invalidarPreviewDevolutiva = () => {
    devolutivaPreview.value = null;
    devolutivaAssinatura.value = {
        declaracaoOperador: false,
        declaracaoGestor: false,
        gestor_protocolo_id: null
    };
};

const despacharDevolutiva = async () => {
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
            const previewFn = usaEndpointConclusaoFinal.value
                ? () =>
                      ApiService.previewConclusaoFinalOperacional(demanda.value.id, {
                          parecer_resposta: parecer
                      })
                : () =>
                      ApiService.previewDespachoDevolutiva(demanda.value.id, {
                          parecer_resposta: parecer
                      });
            const { data } = await previewFn();
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
        const formComGestor = {
            ...formDevolutiva.value,
            gestor_protocolo_id: payloadAssinatura.gestor_protocolo_id
        };
        const declaracaoOp = usaEndpointConclusaoFinal.value ? DECLARACAO_CONCLUSAO_FINAL : DECLARACAO_DEVOLUTIVA;
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
        const arquivos = formDevolutiva.value.anexos_novos || [];
        if (usaEndpointConclusaoFinal.value) {
            await ApiService.conclusaoFinalOperacional(demanda.value.id, payload, arquivos);
        } else {
            await ApiService.despacharDevolutiva(demanda.value.id, payload, arquivos);
        }
        toast.add({
            severity: 'success',
            summary: usaEndpointConclusaoFinal.value ? 'Conclusão final registrada' : 'Devolutiva enviada',
            detail: usaEndpointConclusaoFinal.value
                ? 'Assinatura registrada. Após validação do gestor, você terá cerca de 60 segundos para corrigir ou desfazer na timeline.'
                : 'Demanda finalizada e vereador notificado. Você tem cerca de 60 segundos para corrigir ou desfazer na timeline.',
            life: 5000
        });
        assinaturaDevolutivaDialogVisible.value = false;
        formDevolutiva.value = estadoFormularioDevolutiva();
        devolutivaPreview.value = null;
        devolutivaAssinatura.value = {
            declaracaoOperador: false,
            declaracaoGestor: false,
            gestor_protocolo_id: null
        };
        await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível despachar a devolutiva.',
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
        const previewFn = usaEndpointConclusaoFinal.value
            ? () =>
                  ApiService.previewConclusaoFinalOperacional(demanda.value.id, {
                      parecer_resposta: parecer
                  })
            : () =>
                  ApiService.previewDespachoDevolutiva(demanda.value.id, {
                      parecer_resposta: parecer
                  });
        const { data } = await previewFn();
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

const goBack = () => {
    router.back();
};

const abrirVincularServico = async () => {
    servicoVinculoId.value = demanda.value?.sinapse_servico_id || null;
    vincularServicoDialog.value = true;
    carregandoServicosCarta.value = true;
    try {
        const { data } = await ApiService.getServicos();
        const lista = Array.isArray(data) ? data : data?.results || [];
        servicosCarta.value = lista.map((s) => ({
            ...s,
            label: s.nome || s.titulo || s.service_name || `Serviço #${s.id}`
        }));
    } catch {
        servicosCarta.value = [];
    } finally {
        carregandoServicosCarta.value = false;
    }
};

const confirmarVincularServico = async () => {
    if (!servicoVinculoId.value) {
        toast.add({ severity: 'warn', summary: 'Serviço', detail: 'Selecione um serviço da carta.', life: 3000 });
        return;
    }
    try {
        await ApiService.vincularServicoOperacional(demanda.value.id, servicoVinculoId.value);
        toast.add({ severity: 'success', summary: 'Vinculado', detail: 'Serviço associado — prossiga com o despacho.', life: 4000 });
        vincularServicoDialog.value = false;
        await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível vincular o serviço.',
            life: 4000
        });
    }
};

const confirmarRecusaProtocolo = async () => {
    if ((recusaParecer.value || '').trim().length < 10) {
        toast.add({ severity: 'warn', summary: 'Parecer', detail: 'Informe a justificativa (mín. 10 caracteres).', life: 3000 });
        return;
    }
    try {
        await ApiService.recusaProtocoloOperacional(demanda.value.id, { parecer: recusaParecer.value });
        toast.add({ severity: 'success', summary: 'Recusa registrada', detail: 'Demanda devolvida ao vereador.', life: 4000 });
        recusaDialog.value = false;
        recusaParecer.value = '';
        await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível registrar a recusa.',
            life: 4000
        });
    }
};

const emitirConclusaoParcial = async () => {
    if ((parecerParcial.value || '').trim().length < 10) {
        toast.add({ severity: 'warn', summary: 'Parecer', detail: 'Informe o parecer parcial (mín. 10 caracteres).', life: 3000 });
        return;
    }
    try {
        const { data } = await ApiService.conclusaoParcialOperacional(demanda.value.id, {
            parecer_operacional: parecerParcial.value
        });
        toast.add({
            severity: 'success',
            summary: 'Conclusão parcial',
            detail: data?.operacional?.processo_avancou
                ? 'Todas as secretarias concluíram — aguardando Protocolo.'
                : 'Parecer registrado nesta secretaria.',
            life: 4000
        });
        parecerParcial.value = '';
        await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Não foi possível registrar a conclusão parcial.',
            life: 4000
        });
    }
};

const devolverAoProtocolo = async () => {
    if ((justificativaDevolucao.value || '').trim().length < 10) {
        toast.add({ severity: 'warn', summary: 'Justificativa', detail: 'Informe a justificativa (mín. 10 caracteres).', life: 3000 });
        return;
    }
    confirm.require({
        message: 'Devolver ao Protocolo para novo roteamento? A secretaria deixará de operar este processo até novo despacho.',
        header: 'Devolução ao Protocolo',
        icon: 'pi pi-replay',
        accept: async () => {
            try {
                await ApiService.devolverProtocoloOperacional(demanda.value.id, {
                    justificativa: justificativaDevolucao.value
                });
                toast.add({ severity: 'success', summary: 'Devolvido', detail: 'Processo retornou à fila do Protocolo.', life: 4000 });
                justificativaDevolucao.value = '';
                await recarregarDemandaCompleta();
        validacaoGestorBannerRef.value?.recarregar?.();
            } catch (error) {
                toast.add({
                    severity: 'error',
                    summary: 'Erro',
                    detail: error?.response?.data?.detail || 'Não foi possível devolver ao Protocolo.',
                    life: 4000
                });
            }
        }
    });
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
                    {{ exibirProtocoloDemanda(demanda, 'Rascunho') }}
                    <Tag :value="demanda.status_display" :severity="getStatusSeverity(demanda.status)" class="ml-2" />
                    <Tag
                        v-if="podeVerStandByExecutivo && demanda.stand_by_estudo_viabilidade"
                        value="Stand-by (estudo)"
                        severity="warn"
                        icon="pi pi-pause-circle"
                        class="ml-1"
                    />
                </Message>
                <Button
                    v-if="podeDespacharProtocolo"
                    label="Enviar / Despachar"
                    icon="pi pi-send"
                    severity="success"
                    @click="abrirDialogoDespacho"
                    size="small"
                />
                <Button
                    v-if="podeVincularSuperOs"
                    label="Vincular a Super OS"
                    icon="pi pi-link"
                    severity="help"
                    outlined
                    size="small"
                    @click="abrirDialogoVincularSuperOs"
                />
                <Button v-if="podeIniciarExecucao" label="Iniciar Execução" icon="pi pi-play" severity="success" @click="iniciarExecucao" size="small" />
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

        <div v-if="mostrarCardSuperOs" class="card mb-4 super-os-card">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-2">
                <div class="flex flex-wrap items-center gap-2">
                    <Tag
                        v-if="superOs.tipo_display"
                        :value="superOs.tipo_display"
                        :severity="ehClusterMultiDestino ? 'help' : 'info'"
                    />
                    <Tag
                        v-if="superOs.protocolo_super_os"
                        :value="superOs.protocolo_super_os"
                        severity="secondary"
                    />
                    <span class="super-os-total">{{ superOs.total_vinculados }}</span>
                    <span class="text-sm text-muted-color">processos vinculados</span>
                </div>
                <Button
                    v-if="podeGerirClusterOperacional && superOs.cluster_id"
                    label="Abrir Super OS"
                    icon="pi pi-objects-column"
                    size="small"
                    text
                    @click="router.push({ name: 'clusters', query: { id: String(superOs.cluster_id) } })"
                />
            </div>
            <p v-if="superOs.orgao_competente_nome || superOs.orgaos_envolvidos?.length" class="text-xs text-muted-color m-0 mb-2">
                <template v-if="superOs.orgao_competente_nome">
                    Órgão competente (carta): <strong>{{ superOs.orgao_competente_nome }}</strong>.
                </template>
                <template v-if="superOs.orgaos_envolvidos?.length > 1">
                    Órgãos no grupo:
                    {{ superOs.orgaos_envolvidos.map((o) => o.orgao_nome).join(', ') }}.
                </template>
            </p>
            <p class="text-xs text-muted-color m-0 mb-3">
                <template v-if="ehClusterMultiDestino && isSecretaria">
                    Despacho integrado multi-órgão — cada secretaria opera seu processo vinculado.
                </template>
                <template v-else-if="superOs.eh_lider && isSecretaria && superOs.ativo">
                    Andamentos registrados aqui são replicados nos processos abaixo.
                </template>
                <template v-else-if="!superOs.eh_lider && isSecretaria && superOs.ativo && !podeScatterGather">
                    Processo vinculado — a tramitação operacional é feita na demanda líder
                    (#{{ superOs.lider_id }}).
                    <Button
                        v-if="demandaScatterReferenciaId && demandaScatterReferenciaId !== demanda.id"
                        label="Abrir demanda operacional"
                        icon="pi pi-external-link"
                        link
                        class="p-0 ml-1"
                        @click="router.push({ name: 'demandas-detalhes', params: { id: String(demandaScatterReferenciaId) } })"
                    />
                </template>
                <template v-else-if="isProtocoloPerfil">
                    Clique em um processo para abrir os detalhes. A demanda atual está destacada.
                </template>
                <template v-else>
                    Processos agrupados neste {{ tituloCardCluster.toLowerCase() }}.
                </template>
            </p>
            <div class="flex flex-wrap gap-2">
                <template v-for="vinc in superOs.demandas_vinculadas" :key="vinc.id">
                    <Button
                        v-if="processoVinculadoClicavel(vinc)"
                        :label="`${vinc.id === superOs.lider_id ? 'Líder · ' : ''}${labelProcessoVinculado(vinc)}${vinc.orgao_nome && ehClusterMultiDestino ? ` · ${vinc.orgao_nome}` : ''}`"
                        size="small"
                        outlined
                        severity="secondary"
                        class="super-os-tag-btn"
                        v-tooltip.top="`${vinc.status_display || vinc.status}${vinc.id === superOs.lider_id ? ' · demanda líder' : ''}`"
                        @click="abrirProcessoVinculado(vinc.id)"
                    />
                    <Tag
                        v-else
                        :value="`${vinc.id === demanda.id ? 'Atual · ' : ''}${vinc.id === superOs.lider_id ? 'Líder · ' : ''}${labelProcessoVinculado(vinc)}${vinc.orgao_nome && ehClusterMultiDestino ? ` · ${vinc.orgao_nome}` : ''}`"
                        :severity="vinc.id === demanda.id ? 'success' : vinc.id === superOs.lider_id ? 'info' : 'secondary'"
                        v-tooltip.top="vinc.status_display || vinc.status"
                    />
                </template>
            </div>
        </div>

        <Message v-if="demanda.status === 'AGUARDANDO_TRANSFERENCIA'" severity="warn" class="mb-4">
            Esta demanda está aguardando a análise do Protocolo para ser transferida para outra secretaria. Nenhuma outra ação pode ser realizada no momento.
        </Message>

        <ValidacaoGestorDemandaBanner
            v-if="demanda"
            ref="validacaoGestorBannerRef"
            :demanda-id="demanda.id"
            :assinaturas-resumo="assinaturasResumo"
            :auto-abrir-validacao-id="route.query.validacao_assinatura"
            @validated="recarregarDemandaCompleta"
        />

        <Message v-if="demanda.status === 'AGUARDANDO_PROTOCOLO' && isProtocoloPerfil && ehEntradaTendencia && !despachoAguardandoGestor" severity="warn" class="mb-4">
            <div class="flex flex-col gap-3">
                <span>
                    Tendência aguardando triagem — vincule a um serviço da carta, despache manualmente ou recuse ao vereador.
                </span>
                <div class="flex flex-wrap gap-2">
                    <Button v-if="podeVincularServico" label="Vincular serviço" icon="pi pi-link" size="small" @click="abrirVincularServico" />
                    <Button v-if="podeRecusaProtocolo" label="Recusar ao vereador" icon="pi pi-times" severity="danger" size="small" outlined @click="recusaDialog = true" />
                    <Button v-if="podeDespacharProtocolo" label="Despachar manualmente" icon="pi pi-send" severity="success" size="small" @click="abrirDialogoDespacho" />
                </div>
            </div>
        </Message>

        <Message v-else-if="demanda.status === 'AGUARDANDO_PROTOCOLO' && isProtocoloPerfil && !despachoAguardandoGestor" severity="warn" class="mb-4">
            Ofício aguardando despacho — use <strong>Enviar / Despachar</strong> para encaminhar à secretaria.
        </Message>

        <Message v-if="demanda.status === 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO' && isProtocolo" severity="info" class="mb-4">
            <template v-if="usaFluxoOperacional">
                Conclusão técnica consolidada.
            </template>
            <template v-else>
                Devolutiva operacional recebida.
            </template>
        </Message>

        <Message v-if="mostrarConclusaoDigitalVereador" severity="success" class="mb-4">
            O Protocolo concluiu este processo. Revise o laudo digital abaixo e, se desejar, responda à
            pesquisa de satisfação.
        </Message>

        <ConclusaoDigitalVereador
            v-if="mostrarConclusaoDigitalVereador"
            class="mb-4"
            :pacote="pacoteDevolutiva"
            :mostrar-historico-tecnico="!mostrarOperacionalTimeline"
        />

        <div v-if="isDevolutivaAlertaLeitura" class="card mb-4">
            <Message severity="info" :closable="false" class="m-0 mb-3">
                Sua secretaria foi informada sobre a devolutiva final deste processo.
                <strong>Somente leitura</strong> — não é possível registrar tramitações.
            </Message>
            <div v-if="pacoteDevolutiva?.resposta_protocolo" class="mt-3">
                <span class="font-semibold block mb-2">Resposta do Protocolo ao vereador</span>
                <div
                    class="demanda-descricao-html p-3 surface-ground border-round"
                    v-html="pacoteDevolutiva.resposta_protocolo"
                />
            </div>
            <div v-if="pacoteDevolutiva?.anexos_devolutiva?.length" class="mt-3">
                <span class="font-semibold block mb-2">Anexos da devolutiva</span>
                <div class="flex flex-col gap-2">
                    <a
                        v-for="anexo in pacoteDevolutiva.anexos_devolutiva"
                        :key="anexo.id"
                        :href="anexo.arquivo"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-primary text-sm"
                    >
                        {{ anexo.nome || anexo.arquivo?.split('/').pop() }}
                    </a>
                </div>
            </div>
        </div>

        <div v-if="podeDespacharDevolutiva" class="card mb-4">
            <h5 class="mt-0">
                {{ usaEndpointConclusaoFinal ? 'Conclusão final' : 'Despachar devolutiva' }}
            </h5>
            <FormularioDevolutivaProtocolo
                ref="formDevolutivaRef"
                v-model="formDevolutiva"
                :demanda-id="demanda.id"
                :demanda-context="demandaContextoTextoPadrao"
                :orgaos="orgaosCatalogo"
                :usa-fluxo-operacional="usaFluxoOperacional"
                :historico-tecnico="historicoTecnicoOperacional"
                :preview-ativa="Boolean(devolutivaPreview?.hash_documento)"
                @invalidar-preview="invalidarPreviewDevolutiva"
                @anexos-rejeitados="(msg) => toast.add({ severity: 'warn', summary: 'Anexos', detail: msg, life: 4000 })"
            />
            <Button
                :label="
                    usaEndpointConclusaoFinal
                        ? 'Assinar e concluir processo'
                        : 'Assinar e enviar devolutiva'
                "
                icon="pi pi-verified"
                class="mt-4"
                :loading="carregandoDevolutivaPreview"
                @click="despacharDevolutiva"
            />
        </div>

        <Message v-if="somenteAcompanhamento" severity="info" class="mb-4" :closable="false">
            Você acompanha este processo em modo <strong>somente leitura</strong> — sem ações operacionais.
        </Message>

        <div class="card mb-1">
            <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
                <Tag class="m-0">
                    <small class="font-semibold">Criado em:</small>
                    <small>{{ dataCriacaoFormatada }}</small>
                </Tag>
                <div v-if="podeGerenciarAcompanhamento" class="flex gap-2">
                    <Button
                        v-if="acompanhandoDemanda"
                        label="Desfixar"
                        icon="pi pi-bookmark-fill"
                        severity="secondary"
                        outlined
                        size="small"
                        @click="desfixarAcompanhamento"
                    />
                    <Button
                        v-else-if="podeAcompanharDemanda"
                        label="Fixar acompanhamento"
                        icon="pi pi-bookmark"
                        severity="help"
                        outlined
                        size="small"
                        @click="fixarAcompanhamento"
                    />
                </div>
            </div>
            <Message
                v-if="podeVerStandByExecutivo && demanda.referencias_stand_by?.length"
                severity="warn"
                :closable="false"
                class="mb-4"
            >
                <p class="m-0 mb-2 font-medium">Referências na base stand-by (estudo/viabilidade)</p>
                <ul class="m-0 pl-4 text-sm">
                    <li v-for="ref in demanda.referencias_stand_by" :key="ref.id">
                        <router-link
                            :to="{ name: 'demandas-detalhes', params: { id: String(ref.demanda_id) } }"
                            class="text-primary"
                        >
                            Demanda #{{ ref.demanda_id }}
                        </router-link>
                        — {{ ref.resultado_operacional_label }}
                        <span v-if="ref.escopo_geografico"> · escopo: {{ ref.escopo_geografico }}</span>
                    </li>
                </ul>
            </Message>
            <Message
                v-if="podeVerStandByExecutivo && demanda.registro_estudo_viabilidade"
                severity="info"
                :closable="false"
                class="mb-4"
            >
                <p class="m-0 font-medium">Registro stand-by (estudo/viabilidade)</p>
                <p class="m-0 mt-1 text-sm">
                    {{ demanda.registro_estudo_viabilidade.resultado_operacional_label }}
                    <span v-if="demanda.registro_estudo_viabilidade.motivo_nao_execucao_label">
                        — {{ demanda.registro_estudo_viabilidade.motivo_nao_execucao_label }}
                    </span>
                    <span v-if="demanda.registro_estudo_viabilidade.escopo_geografico">
                        · Escopo: {{ demanda.registro_estudo_viabilidade.escopo_geografico }}
                    </span>
                </p>
            </Message>
            <h4 class="mt-1">{{ demanda.titulo }}</h4>
            <div class="flex items-center gap-6 mb-4">
                <div class="flex items-center gap-2 flex-wrap">
                    <i
                        :class="ehEntradaTendencia ? 'pi pi-chart-line text-primary-400' : 'pi pi-check-square text-primary-400'"
                    ></i>
                    <Tag v-if="ehEntradaTendencia" value="Tendência" severity="info" class="text-xs" />
                    <span>{{ rotuloServicoOuTendencia }}</span>
                    <span
                        v-if="ehEntradaTendencia && demanda.tendencia?.volume_total != null"
                        class="text-sm text-muted-color"
                    >
                        · volume {{ demanda.tendencia.volume_total }}
                    </span>
                </div>
                <div class="flex items-center gap-2">
                    <i class="pi pi-sitemap text-primary-400"></i>
                    <span>{{ demanda.secretaria_destino?.nome || 'Aguardando despacho' }}</span>
                </div>
                <div v-if="orgaosIntegrados.length && !mostrarCardSuperOs" class="flex items-center gap-2">
                    <i class="pi pi-share-alt text-primary-400"></i>
                    <span>
                        Órgãos integrados:
                        {{ orgaosIntegrados.map((o) => o.orgao_nome).join(', ') }}
                    </span>
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
                <span class="text-primary-400"><i class="pi pi-map-marker"></i> Endereço:</span>
                <p class="mt-2 flex flex-wrap items-center gap-2 m-0">
                    <span>
                        {{ demanda.logradouro || 'Não informado' }}, Nº {{ demanda.numero || 'S/N' }} - {{ demanda.bairro || 'Não informado' }}
                    </span>
                    <Button
                        v-if="temGeolocalizacaoDemanda"
                        label="Ver no mapa de calor"
                        icon="pi pi-map"
                        link
                        size="small"
                        class="p-0"
                        @click="verDemandaNoMapa"
                    />
                </p>
            </div>
            <div v-if="demanda.anexos && demanda.anexos.length > 0" class="field col-12">
                <span class="text-primary-400"><i class="pi pi-paperclip"></i> Anexos:</span>
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
            v-if="isVereador && demanda.status === 'EM_EXECUCAO' && !mostrarOperacionalTimeline && !mostrarConclusaoDigitalVereador"
            severity="info"
            class="mb-4"
            :closable="false"
        >
            A secretaria está executando o serviço. Você será notificado quando houver conclusão ou devolutiva.
        </Message>

        <div
            v-if="tramitacoesCorrecaoProtocoloForaTimeline.length"
            class="flex flex-col gap-3 mb-4"
        >
            <Message severity="info" :closable="false" class="m-0">
                Despacho do Protocolo registrado — use a janela abaixo para corrigir ou desfazer antes do prazo.
            </Message>
            <div
                v-for="t in tramitacoesCorrecaoProtocoloForaTimeline"
                :key="`corr-prot-${t.id}`"
                class="card"
            >
                <div class="flex justify-between items-center mb-2 flex-wrap gap-2">
                    <span class="font-semibold">{{ t.tipo_display || t.tipo }}</span>
                    <small class="text-muted-color">{{ formatarData(t.timestamp) }}</small>
                </div>
                <TramitacaoJanelaCorrecao
                    :tramitacao-id="t.id"
                    :descricao-atual="t.descricao || ''"
                    :pode-editar="t.pode_editar"
                    :segundos-restantes="t.segundos_restantes_edicao"
                    :aguardando-validacao-gestor="
                        Boolean(t.aguardando_validacao_gestor || t.metadata?.aguardando_validacao_gestor)
                    "
                    :contexto="contextoCorrecaoTramitacaoItem(t)"
                    @atualizado="onTramitacaoCorrigida"
                />
            </div>
        </div>

        <OperacionalTimeline
            v-if="mostrarOperacionalTimeline"
            :timeline="timelineOperacionalExibicao"
            :fluxo-roteamento="demanda.fluxo_roteamento || estadoOperacional?.fluxo_roteamento || ''"
            :participantes="estadoOperacional?.participantes_transversal || []"
            :pendencias="estadoOperacional?.pendencias_parciais || []"
            :demanda-lider-id="estadoOperacional?.demanda_lider_id || demanda.super_os?.lider_id"
            :modo-vereador="timelineModoInstitucional"
            :status-demanda="demanda.status"
            :assinaturas="assinaturasParaTimelineOperacional"
            :arvore-nos="estadoOperacional?.arvore_nos || []"
            :nos-ativos="estadoOperacional?.nos_ativos ?? 0"
            :historico-tecnico="historicoTecnicoOperacional || pacoteDevolutiva?.historico_tecnico || null"
            :demanda-atual-id="demanda.id"
            class="mb-4"
            @atualizado="onTramitacaoCorrigida"
        />

        <div v-else-if="timelineOrdenada.length > 0 && !isVereador" class="pt-6 pb-6 timeline-container">
            <div class="flex flex-col gap-6">
                <div v-for="item in timelineOrdenada" :key="item.id" class="flex gap-3">
                    <div class="flex flex-col items-center timeline-icon-container">
                        <Avatar :icon="getTimelineIcon(item.tipo_display).icon" shape="circle" size="large" :class="getTimelineIcon(item.tipo_display).color" />
                    </div>
                    <div class="card flex-1">
                        <div class="flex justify-between items-center">
                            <span class="font-bold gap-3">
                                <template v-if="isVereador">{{ rotuloInstitucionalTramitacao(item) }}</template>
                                <template v-else>{{ item.responsavel?.first_name || item.responsavel?.username || 'Sistema' }}</template>
                                <small class="text-color-secondary font-normal"> registrou um andamento em {{ formatarData(item.timestamp) }}</small>
                            </span>
                            <Tag
                                :value="isVereador ? labelTramitacaoVereador(item) : item.tipo_display"
                                :severity="getTramitacaoTagSeverity(item.tipo_display)"
                                class="mb-2"
                            />
                        </div>
                        <Divider />
                        <p
                            v-if="isVereador && item.tipo === 'DEVOLUTIVA_PROTOCOLO' && (item.orgao_nome || item.unidade_nome)"
                            class="text-sm text-muted-color m-0 mb-3"
                        >
                            <i class="pi pi-building mr-1"></i>
                            Executado por: {{ item.orgao_nome }}
                            <template v-if="item.unidade_nome"> — {{ item.unidade_nome }}</template>
                        </p>
                        <div class="mb-6 tramitacao-descricao">
                            <template v-if="isVereador">
                                <p class="m-0 whitespace-pre-wrap">{{ descricaoTramitacaoVereador(item) }}</p>
                            </template>
                            <template v-else>
                                <div
                                    v-if="exibirDescricaoTramitacao(item).modo === 'html'"
                                    class="tramitacao-descricao-html"
                                    v-html="exibirDescricaoTramitacao(item).html"
                                />
                                <p
                                    v-else-if="exibirDescricaoTramitacao(item).modo === 'texto'"
                                    class="m-0 tramitacao-descricao-texto"
                                >
                                    {{ exibirDescricaoTramitacao(item).texto }}
                                </p>
                            </template>
                        </div>
                        <p v-if="!isVereador && item.unidade_destino" class="text-sm text-muted-color m-0 mb-3">
                            <i class="pi pi-sitemap mr-1"></i>
                            Setor destino: {{ item.unidade_destino.sigla || item.unidade_destino.nome }}
                        </p>
                        <div v-if="!isVereador && item.anexos && item.anexos.length > 0" class="flex gap-2 mt-3 text-sm">
                            <i class="pi pi-paperclip"></i>
                            <div class="flex flex-column gap-2">
                                <a v-for="anexo in item.anexos" :key="anexo.id" :href="anexo.arquivo" target="_blank" rel="noopener noreferrer" class="no-underline text-color hover:text-primary flex align-items-center">
                                    <i class="pi pi-file mr-2"></i>
                                    <span>{{ anexo.arquivo.split('/').pop() }}</span>
                                </a>
                            </div>
                        </div>
                        <TramitacaoJanelaCorrecao
                            v-if="item.pode_editar"
                            :tramitacao-id="item.id"
                            :descricao-atual="item.descricao || ''"
                            :pode-editar="item.pode_editar"
                            :segundos-restantes="item.segundos_restantes_edicao"
                            :aguardando-validacao-gestor="Boolean(item.aguardando_validacao_gestor)"
                            :contexto="contextoCorrecaoTramitacaoItem(item)"
                            @atualizado="onTramitacaoCorrigida"
                        />
                    </div>
                </div>
            </div>
        </div>

        <div v-if="podeScatterGather && !somenteAcompanhamento" class="flex flex-col gap-8 mb-8">
            <div class="flex gap-3">
                <div class="flex flex-col items-center">
                    <Avatar icon="pi pi-sitemap" size="large" class="avatar-primary" shape="circle" />
                </div>
                <div class="card flex-1">
                    <span class="font-semibold mb-2 block">Tramitação operacional</span>
                    <Divider />
                    <FormularioScatterGather
                        :demanda-id="demanda.id"
                        :demanda-context="demandaContextoTextoPadrao"
                        :nos-usuario="nosUsuarioScatter"
                        :acoes-disponiveis="acoesOperacionais"
                        :orgaos="orgaosCatalogo"
                        :destinos-ocupados="destinosOcupadosScatter"
                        :grupos-nos-usuario="gruposNosScatter"
                        :grupos-nos-painel="gruposNosPainelScatter"
                        :endereco-sugerido="enderecoSugeridoDemanda"
                        @success="onScatterGatherSuccess"
                        @error="onScatterGatherError"
                    />
                </div>
            </div>
        </div>

        <Message
            v-else-if="exibirAvisoDemandaScatterParalela"
            severity="warn"
            :closable="false"
            class="mb-8"
        >
            A tramitação scatter-gather deste processo está na demanda
            <strong>#{{ demandaScatterReferenciaId }}</strong>
            (protocolo vinculado ao cluster). O formulário aqui usa regras legadas e não permite
            encaminhar a outros órgãos.
            <Button
                label="Abrir demanda operacional"
                icon="pi pi-external-link"
                link
                class="p-0 ml-1"
                @click="router.push({ name: 'demandas-detalhes', params: { id: String(demandaScatterReferenciaId) } })"
            />
        </Message>

        <div v-if="podeOperarTramitacao">
            <div class="flex flex-col gap-8">
                <div class="flex gap-3">
                    <div class="flex flex-col items-center">
                        <Avatar label="+" size="large" class="avatar-primary" shape="circle"></Avatar>
                    </div>
                    <div class="card flex-1">
                        <span class="font-semibold mb-2 block">Tramitação operacional</span>
                        <Message
                            v-if="podeDevolverProtocolo && demanda.status === 'PROTOCOLADO'"
                            severity="warn"
                            :closable="false"
                            class="text-sm m-0 mb-3"
                        >
                            Antes de iniciar a execução, você pode
                            <strong>devolver ao Protocolo</strong> escolhendo esse tipo de andamento.
                        </Message>
                        <Message
                            v-if="formAndamento.tipo === TIPO_CONCLUSAO_PARCIAL"
                            severity="info"
                            :closable="false"
                            class="text-sm m-0 mb-3"
                        >
                            A conclusão parcial será registrada para
                            <strong>{{ orgaoLiderImediatoNome || 'secretaria líder' }}</strong>
                            (líder imediato no fluxo transversal).
                        </Message>
                        <Message
                            v-else-if="podeAbrirPernasTransversal"
                            severity="info"
                            :closable="false"
                            class="text-sm m-0 mb-3"
                        >
                            Registre andamentos internos (setor) e, quando necessário, abra
                            <strong>órgãos integrados</strong> (subpastas) — conclusões sobem ao líder imediato.
                        </Message>
                        <Divider />
                        <FormularioTramitacao
                            ref="formAndamentoRef"
                            v-model="formAndamento"
                            :modo="MODO_ANDAMENTO"
                            layout="card"
                            :demanda-id="demanda?.id"
                            :demanda-context="demandaContextoTextoPadrao"
                            :orgaos="orgaosCatalogo"
                            :orgao-fixo-id="orgaoIdDemanda"
                            :orgao-competente-nome="orgaoAndamentoNome"
                            :orgaos-integraveis="secretariasIntegraveisTransversal"
                            :permitir-integrados="podeAbrirPernasTransversal && !tipoOperacionalEspecial"
                            :exibir-destinos="exibirDestinosForm"
                            :tipos-andamento="tiposTramitacaoFiltrados"
                            @anexos-rejeitados="onAnexosRejeitadosForm"
                            @anexo-invalido="onAnexosRejeitadosForm"
                        />
                        <div class="mt-4">
                            <Button
                                :label="labelBotaoTramitacao"
                                :icon="
                                    formAndamento.tipo === TIPO_DEVOLUCAO_PROTOCOLO
                                        ? 'pi pi-replay'
                                        : formAndamento.tipo === TIPO_CONCLUSAO_PARCIAL
                                          ? 'pi pi-check'
                                          : formTemIntegrados
                                            ? 'pi pi-share-alt'
                                            : formAndamento.tipo === 'CONCLUSAO'
                                              ? 'pi pi-check-square'
                                              : 'pi pi-plus'
                                "
                                :severity="formAndamento.tipo === TIPO_DEVOLUCAO_PROTOCOLO ? 'warn' : undefined"
                                :outlined="formAndamento.tipo === TIPO_DEVOLUCAO_PROTOCOLO"
                                @click="adicionarTramitacao"
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <Button v-else-if="podeIniciarExecucao" label="Iniciar Execução" icon="pi pi-play" severity="success" @click="iniciarExecucao" />

        <Button
            v-else-if="!podeScatterGather && !podeOperarTramitacao"
            icon="pi pi-arrow-left"
            @click="router.push('/demandas')"
            label="Voltar"
        />

        <Dialog v-model:visible="conclusaoDialog" header="Conclusão operacional (assinatura eletrônica)" :modal="true" style="width: 520px">
            <div class="flex flex-col gap-4">
                <Message severity="info" :closable="false" class="text-sm m-0">
                    A conclusão assinada encaminha a demanda ao Protocolo para devolutiva ao vereador.
                    Podem assinar a <strong>secretaria responsável</strong> ou o <strong>gestor setorial</strong> do setor.
                </Message>
                <p v-if="demanda" class="m-0 text-sm text-muted-color">
                    {{ exibirProtocoloDemanda(demanda, `#${demanda.id}`) }} — {{ demanda.titulo }}
                </p>
                <p class="m-0 text-sm tramitacao-descricao-texto">
                    <span class="font-medium">Parecer operacional:</span>
                    {{ parecerOperacionalTexto() }}
                </p>
                <FormularioResultadoOperacional
                    v-model="conclusaoResultado"
                    :endereco-sugerido="enderecoSugeridoDemanda"
                />
            </div>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="conclusaoDialog = false" />
                <Button
                    label="Assinar e concluir"
                    icon="pi pi-verified"
                    severity="success"
                    :loading="carregandoConclusaoPreview"
                    @click="confirmarConclusaoComAssinatura"
                />
            </template>
        </Dialog>

        <DialogVincularSuperOsDemanda
            v-model:visible="vincularSuperOsDialog"
            :demanda="demanda"
            :vinculando="vincularSuperOsLoading"
            @vinculado="confirmarVincularSuperOs"
        />

        <DialogClusterAderencia
            v-model:visible="clusterAderenciaDialog"
            :demanda="demanda"
            :situacao="clusterAderenciaSituacao"
            :carregando="clusterAderenciaLoading"
            @aderir="confirmarAderenciaCluster"
            @desvincular="confirmarDesvincularClusterDespacho"
        />

        <Dialog v-model:visible="despachoDialog" header="Despachar demanda (assinatura eletrônica)" :modal="true" style="width: 640px">
            <div class="flex flex-col gap-4">
                <p v-if="demanda" class="m-0 text-sm text-muted-color">
                    {{ formatarProtocoloLegislativo(demanda.protocolo_legislativo) || `#${demanda.id}` }} — {{ demanda.titulo }}
                </p>
                <FormularioTramitacao
                    v-if="despachoDialog"
                    ref="formDespachoRef"
                    v-model="formDespacho"
                    :modo="MODO_DESPACHO"
                    layout="dialog"
                    :demanda-id="demanda?.id"
                    :demanda-context="demandaContextoTextoPadrao"
                    :exibir-assinatura-formulario="false"
                    :orgaos="orgaosCatalogo"
                    :orgao-competente-id="orgaoCompetenteDespacho"
                    :orgao-competente-nome="orgaoCompetenteNome"
                    :orgaos-integraveis="secretariasIntegraveis"
                    @invalidar-preview="despachoPreview = null"
                    @anexos-rejeitados="onAnexosRejeitadosForm"
                    @anexo-invalido="onAnexosRejeitadosForm"
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

        <Dialog v-model:visible="recusaDialog" header="Recusa ao vereador" :modal="true" style="width: 520px">
            <div class="flex flex-col gap-3">
                <Message severity="warn" :closable="false" class="m-0 text-sm">
                    A demanda será devolvida ao vereador com parecer justificado. Use apenas para tendências fora da competência municipal.
                </Message>
                <Textarea v-model="recusaParecer" rows="5" class="w-full" placeholder="Parecer de recusa (mín. 10 caracteres)..." />
            </div>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="recusaDialog = false" />
                <Button label="Confirmar recusa" icon="pi pi-times-circle" severity="danger" @click="confirmarRecusaProtocolo" />
            </template>
        </Dialog>

        <Dialog v-model:visible="vincularServicoDialog" header="Vincular serviço da carta" :modal="true" style="width: 520px">
            <div class="flex flex-col gap-3">
                <Message severity="info" :closable="false" class="m-0 text-sm">
                    Associe esta tendência a um serviço Sinapse antes do despacho.
                </Message>
                <Select
                    v-model="servicoVinculoId"
                    :options="servicosCarta"
                    optionLabel="label"
                    optionValue="id"
                    placeholder="Selecione o serviço"
                    filter
                    :loading="carregandoServicosCarta"
                    class="w-full"
                />
            </div>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="vincularServicoDialog = false" />
                <Button label="Vincular" icon="pi pi-link" @click="confirmarVincularServico" />
            </template>
        </Dialog>

        <DialogConfirmacaoTramitacao
            v-model:visible="confirmTramitacaoVisible"
            titulo="Confirmar andamento"
            mensagem="Após registrar, você terá cerca de 60 segundos para corrigir o texto ou desfazer o andamento. Deseja enviar para a timeline da demanda?"
            :resumo-destinos="resumoDestinosAndamento"
            :modo="MODO_ANDAMENTO"
            :assinar-no-formulario="formAndamento.assinar_eletronicamente"
            @confirmar="executarTramitacaoConfirmada"
        />

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
            mensagem-intro="Assine como operador do protocolo. O gestor validará a assinatura em seguida. Após a execução do despacho, você terá cerca de 60 segundos para corrigir o texto ou desfazer na timeline."
            @confirmar="executarDespachoComAssinatura"
            @gerar-preview="gerarPreviewDespacho"
        />

        <DialogAssinaturaEletronica
            v-model:visible="assinaturaConclusaoDialogVisible"
            titulo="Assinatura eletrônica — conclusão operacional"
            :preview="conclusaoPreview"
            :modo="MODO_PAINEL_ASSINATURA.OPERADOR_APENAS"
            :declaracao-operador-texto="DECLARACAO_CONCLUSAO"
            label-confirmar="Assinar e concluir"
            :loading="executandoAssinatura"
            :loading-preview="carregandoConclusaoPreview"
            mensagem-intro="Assine a conclusão operacional. O gestor do setor validará em seguida."
            @confirmar="executarConclusaoComAssinatura"
            @gerar-preview="gerarPreviewConclusao"
        />

        <DialogAssinaturaEletronica
            v-model:visible="assinaturaDevolutivaDialogVisible"
            :titulo="
                usaEndpointConclusaoFinal
                    ? 'Assinatura eletrônica — conclusão final'
                    : 'Assinatura eletrônica — devolutiva'
            "
            :preview="devolutivaPreview"
            :gestores="gestoresProtocolo"
            :modo="modoAssinaturaDevolutiva"
            :declaracao-operador-texto="
                usaEndpointConclusaoFinal ? DECLARACAO_CONCLUSAO_FINAL : DECLARACAO_DEVOLUTIVA
            "
            :declaracao-gestor-texto="DECLARACAO_GESTOR_PROTOCOLO"
            :label-confirmar="
                usaEndpointConclusaoFinal ? 'Assinar e concluir processo' : 'Assinar e enviar devolutiva'
            "
            :loading="executandoAssinatura"
            :loading-preview="carregandoDevolutivaPreview"
            :mensagem-intro="
                usaEndpointConclusaoFinal
                    ? 'Assine como operador. O gestor do protocolo validará em seguida. Após a execução, você terá cerca de 60 segundos para corrigir ou desfazer na timeline.'
                    : 'Revise a devolutiva e confirme a assinatura eletrônica. Após o envio, você terá cerca de 60 segundos para corrigir ou desfazer na timeline.'
            "
            @confirmar="executarDevolutivaComAssinatura"
            @gerar-preview="gerarPreviewDevolutivaDialog"
        />
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

.tramitacao-descricao-texto {
    white-space: pre-line;
    line-height: 1.6;
}

.tramitacao-descricao-html :deep(p) {
    margin: 0 0 0.75rem;
    line-height: 1.6;
}

.tramitacao-descricao-html :deep(p:last-child) {
    margin-bottom: 0;
}

.tramitacao-descricao-html :deep(br) {
    display: block;
    content: '';
    margin-top: 0.35rem;
}

.avatar-primary,
.avatar-blue {
    background: var(--p-primary-500) !important;
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
