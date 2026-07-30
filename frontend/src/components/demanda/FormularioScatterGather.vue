<script setup>
import { ref, computed, watch } from 'vue';
import Button from 'primevue/button';
import MultiSelect from 'primevue/multiselect';
import SelectButton from 'primevue/selectbutton';
import Tag from 'primevue/tag';
import Dialog from 'primevue/dialog';
import Message from 'primevue/message';
import DestinosTramitacaoEditor from '@/components/tramitacao/DestinosTramitacaoEditor.vue';
import FormularioTramitacao from '@/components/tramitacao/FormularioTramitacao.vue';
import DialogConfirmacaoTramitacao from '@/components/tramitacao/DialogConfirmacaoTramitacao.vue';
import {
    acaoScatterRequerDestino,
    ACAO_SCATTER_DESPACHAR,
    ACAO_SCATTER_DESPACHAR_ENCERRAR,
    ACAO_SCATTER_ENCERRAR,
    rotuloNoOperacional,
    rotuloDestinoOcupado,
    montarGruposNosEquivalentes,
    montarGruposNosOperador,
    nosPodemEncerrar,
    mensagemEncerramentoBloqueado
} from '@/constants/scatterGather';
import {
    MODO_DESPACHO,
    MODO_ANDAMENTO,
    novoDestino,
    estadoFormularioTramitacao,
    regrasAssinaturaScatter,
    resumoDestinosTexto
} from '@/constants/tramitacaoFormulario';
import { destinosParaPayload } from '@/constants/tramitacaoFormulario';
import { payloadAssinaturaScatter } from '@/constants/assinaturaEletronica';
import { buildMultipartPayload } from '@/utils/protocoloFormData';
import ApiService from '@/service/ApiService.js';
import FormularioResultadoOperacional from '@/components/demanda/FormularioResultadoOperacional.vue';
import {
    estadoInicialResultadoOperacional,
    validarResultadoOperacional,
    payloadResultadoOperacional
} from '@/constants/estudoViabilidade';

const props = defineProps({
    demandaId: { type: [Number, String], required: true },
    demandaContext: { type: Object, default: () => ({}) },
    nosUsuario: { type: Array, default: () => [] },
    acoesDisponiveis: { type: Array, default: () => [] },
    orgaos: { type: Array, default: () => [] },
    orgaoFixoId: { type: Number, default: null },
    destinosOcupados: { type: Array, default: () => [] },
    gruposNosUsuario: { type: Array, default: () => [] },
    gruposNosPainel: { type: Array, default: () => [] },
    enderecoSugerido: { type: String, default: '' }
});

const emit = defineEmits(['success', 'error']);

const form = ref({
    no_id: null,
    acao: null,
    destinos: [novoDestino()]
});

const formTramitacao = ref(estadoFormularioTramitacao());
const resultadoOperacional = ref(estadoInicialResultadoOperacional());

const enviando = ref(false);
const dialogConflito = ref(false);
const conflitosPendentes = ref([]);
const payloadPendente = ref(null);
const multipartPendente = ref(false);
const unificadoPendente = ref(false);
const usarDespachoUnificado = ref(false);
const dialogEncerrarLote = ref(false);
const dialogEncerrarParticipacao = ref(false);
const confirmOperacaoVisible = ref(false);
const acaoOperacaoPendente = ref(null);
const encerrarGrupoPendente = ref(null);
const grupoEncerrarLote = ref(null);
const formEncerrarLote = ref(estadoFormularioTramitacao());
const resultadoEncerrarLote = ref(estadoInicialResultadoOperacional());
const enviandoEncerrarLote = ref(false);
const editorDestinosRef = ref(null);

const MODO_DESPACHO_SCATTER = 'despacho';
const MODO_ENCERRAR_SCATTER = 'encerrar';

const modoOperacao = ref(MODO_DESPACHO_SCATTER);
const responderTodos = ref(false);
const nosSelecionadosIds = ref([]);

const podeDespachar = computed(() => props.acoesDisponiveis.includes('scatter_despachar'));
const podeEncerrar = computed(() => props.acoesDisponiveis.includes('scatter_encerrar'));
const podeEncerrarAposDespacho = computed(() =>
    props.acoesDisponiveis.includes('scatter_despachar_encerrar')
);

const idsOperacaoAtivos = computed(() => {
    if (nosSelecionadosIds.value.length) {
        return nosSelecionadosIds.value.map((id) => Number(id));
    }
    if (form.value.no_id != null) return [Number(form.value.no_id)];
    return [];
});

const podeEncerrarSelecionados = computed(() =>
    nosPodemEncerrar(idsOperacaoAtivos.value, gruposPainel.value, props.nosUsuario)
);

const opcoesModoOperacao = computed(() => {
    const opcoes = [];
    if (podeDespachar.value) {
        opcoes.push({ label: 'Despachar', value: MODO_DESPACHO_SCATTER, icon: 'pi pi-share-alt' });
    }
    if (podeEncerrar.value) {
        opcoes.push({
            label: 'Encerrar participação',
            value: MODO_ENCERRAR_SCATTER,
            icon: 'pi pi-times-circle'
        });
    }
    return opcoes;
});

const mensagemBloqueioEncerrar = computed(() =>
    mensagemEncerramentoBloqueado(idsOperacaoAtivos.value, gruposPainel.value, props.nosUsuario)
);

const encerrarBloqueado = computed(
    () => ehModoEncerrar.value && !podeEncerrarSelecionados.value
);

const ehModoEncerrar = computed(() => modoOperacao.value === MODO_ENCERRAR_SCATTER);
const exibirEditorDestinos = computed(() => !ehModoEncerrar.value && podeDespachar.value);
const labelDescricaoForm = computed(() =>
    ehModoEncerrar.value ? 'Descrição do encerramento' : 'Descrição do despacho'
);

const acaoScatterAtual = computed(() => {
    if (ehModoEncerrar.value) return ACAO_SCATTER_ENCERRAR;
    if (form.value.acao === ACAO_SCATTER_DESPACHAR_ENCERRAR) return ACAO_SCATTER_DESPACHAR_ENCERRAR;
    return ACAO_SCATTER_DESPACHAR;
});

const regrasAssinaturaScatterAtual = computed(() =>
    regrasAssinaturaScatter(acaoScatterAtual.value)
);

function validarAssinaturaScatter(acao) {
    const regras = regrasAssinaturaScatter(acao);
    if (!regras.obrigatoria) return true;
    if (formTramitacao.value.assinar_eletronicamente) return true;
    emit(
        'error',
        `Assinatura eletrônica obrigatória para ${regras.rotulo.toLowerCase()}. Marque a declaração antes de continuar.`
    );
    return false;
}

const resumoDestinosOperacao = computed(() =>
    resumoDestinosTexto(form.value.destinos, props.orgaos)
);

const tituloConfirmacaoOperacao = computed(() => {
    const acao = acaoOperacaoPendente.value;
    if (acao === ACAO_SCATTER_ENCERRAR) return 'Confirmar encerramento';
    if (acao === ACAO_SCATTER_DESPACHAR_ENCERRAR) return 'Confirmar despacho e encerramento';
    return 'Confirmar despacho operacional';
});

const mensagemConfirmacaoOperacao = computed(() => {
    const acao = acaoOperacaoPendente.value;
    if (acao === ACAO_SCATTER_ENCERRAR) {
        return 'Revise a descrição do encerramento antes de registrar. Esta ação encerra sua participação neste nó operacional.';
    }
    if (acao === ACAO_SCATTER_DESPACHAR_ENCERRAR) {
        return 'Revise os destinos abaixo antes de despachar e encerrar sua participação neste nó.';
    }
    return 'Revise os destinos abaixo antes de registrar o despacho operacional.';
});

const labelConfirmarOperacao = computed(() => {
    const acao = acaoOperacaoPendente.value;
    if (acao === ACAO_SCATTER_ENCERRAR) return 'Confirmar encerramento';
    if (acao === ACAO_SCATTER_DESPACHAR_ENCERRAR) return 'Confirmar despacho e encerrar';
    return 'Confirmar despacho';
});

function abrirConfirmacaoOperacao(acao, grupoEncerrar = null) {
    acaoOperacaoPendente.value = acao;
    encerrarGrupoPendente.value = grupoEncerrar;
    confirmOperacaoVisible.value = true;
}

async function executarOperacaoConfirmada({ assinar_eletronicamente }) {
    formTramitacao.value.assinar_eletronicamente = assinar_eletronicamente;
    const acao = acaoOperacaoPendente.value;
    if (!acao) return;
    if (!validarAssinaturaScatter(acao)) return;

    if (acao === ACAO_SCATTER_ENCERRAR) {
        const grupo = encerrarGrupoPendente.value;
        if (grupo) {
            await executarEncerrarSelecionados(grupo);
        } else {
            await executarEncerrarSelecionados({
                no_ids: nosSelecionadosIds.value.length
                    ? nosSelecionadosIds.value
                    : [form.value.no_id],
                no_canonico_id: form.value.no_id
            });
        }
        return;
    }

    await enviar(false, acao);
}

const gruposPainel = computed(() =>
    montarGruposNosOperador(props.nosUsuario, props.gruposNosPainel)
);

const gruposEquivalentes = computed(() =>
    montarGruposNosEquivalentes(props.nosUsuario, props.gruposNosUsuario)
);

const exibirPainelEquivalentes = computed(() => gruposPainel.value.length > 0);

const grupoDoNoSelecionado = computed(() => {
    const ids = idsOperacaoAtivos.value;
    if (!ids.length) return null;
    for (const g of gruposEquivalentes.value) {
        const set = new Set((g.no_ids || []).map((id) => Number(id)));
        if (ids.every((id) => set.has(Number(id)))) {
            return g;
        }
    }
    if (form.value.no_id) {
        return (
            gruposEquivalentes.value.find((g) => g.no_ids?.includes(form.value.no_id)) || null
        );
    }
    return null;
});

const podeDespachoUnificado = computed(
    () =>
        props.acoesDisponiveis.includes('scatter_despachar_unificado') &&
        idsOperacaoAtivos.value.length > 1 &&
        grupoDoNoSelecionado.value?.equivalentes &&
        grupoDoNoSelecionado.value.quantidade > 1 &&
        !ehModoEncerrar.value
);

const opcoesNo = computed(() =>
    (props.nosUsuario || []).map((no) => ({
        label: rotuloNoOperacional(no),
        value: no.id,
        no
    }))
);

/** Select oculto quando o painel cobre os nós da secretaria. */
const exibirSeletorNo = computed(() => {
    if (opcoesNo.value.length <= 1) return false;
    const painel = gruposPainel.value;
    if (painel.length === 1) {
        const idsGrupo = new Set((painel[0].no_ids || []).map((id) => Number(id)));
        if (opcoesNo.value.every((o) => idsGrupo.has(Number(o.value)))) return false;
    }
    return true;
});

const noAtivoResumo = computed(() => {
    const ids = idsOperacaoAtivos.value;
    if (ids.length > 1) {
        return { label: `${ids.length} nós selecionados` };
    }
    const id = ids[0] ?? form.value.no_id;
    if (!id) return null;
    return opcoesNo.value.find((o) => Number(o.value) === Number(id)) || null;
});

function sincronizarNoPrincipal(ids) {
    const lista = Array.isArray(ids) ? ids.map((id) => Number(id)).filter(Boolean) : [];
    nosSelecionadosIds.value = lista;
    form.value.no_id = lista[0] ?? null;
}

watch(
    () => nosSelecionadosIds.value,
    (ids) => {
        const principal = ids?.length ? Number(ids[0]) : null;
        if (form.value.no_id !== principal) {
            form.value.no_id = principal;
        }
    },
    { deep: true }
);

watch(
    () => [props.nosUsuario, gruposPainel.value],
    () => {
        const nos = props.nosUsuario || [];
        if (nos.length === 1) {
            sincronizarNoPrincipal([nos[0].id]);
            return;
        }
        const painel = gruposPainel.value || [];
        if (painel.length === 1 && painel[0].no_ids?.length === nos.length) {
            sincronizarNoPrincipal(painel[0].no_ids);
        }
    },
    { immediate: true, deep: true }
);

function limparFormulario() {
    form.value = {
        no_id: props.nosUsuario?.length === 1 ? props.nosUsuario[0].id : null,
        acao: null,
        destinos: [novoDestino()]
    };
    formTramitacao.value = estadoFormularioTramitacao();
    resultadoOperacional.value = estadoInicialResultadoOperacional();
    responderTodos.value = false;
    nosSelecionadosIds.value =
        props.nosUsuario?.length === 1 ? [props.nosUsuario[0].id] : [];
    usarDespachoUnificado.value = false;
}

function montarPayload(confirmarDuplicado = false, unificado = false, noIdOverride = null, acaoOverride = null) {
    const acao = acaoOverride || form.value.acao || acaoScatterAtual.value;
    const payload = {
        acao,
        observacao: formTramitacao.value.descricao?.trim() || '',
        descricao: formTramitacao.value.descricao?.trim() || ''
    };
    if (unificado && grupoDoNoSelecionado.value) {
        payload.no_ids = idsOperacaoAtivos.value.length
            ? idsOperacaoAtivos.value
            : grupoDoNoSelecionado.value.no_ids;
        payload.no_canonico_id = grupoDoNoSelecionado.value.no_canonico_id;
    } else {
        payload.no_id = noIdOverride ?? form.value.no_id ?? idsOperacaoAtivos.value[0];
    }
    if (confirmarDuplicado) {
        payload.confirmar_destino_duplicado = true;
    }
    if (!ehModoEncerrar.value && podeDespachar.value) {
        const { destinos } = destinosParaPayload({ destinos: form.value.destinos });
        if (destinos?.length) payload.destinos = destinos;
    }
    return anexarPayloadResultadoEncerramento(payload);
}

function anexarPayloadResultadoEncerramento(payload, formResultado = resultadoOperacional.value) {
    if (!ehModoEncerrar.value) {
        return payload;
    }
    return anexarResultadoOperacionalPayload(payload, formResultado);
}

function anexarResultadoOperacionalPayload(payload, formResultado) {
    return { ...payload, ...payloadResultadoOperacional(formResultado) };
}

function validarFormularioResultadoEncerramento(formResultado = resultadoOperacional.value) {
    if (!ehModoEncerrar.value) {
        return null;
    }
    return validarResultadoOperacional(formResultado);
}

function montarPayloadAssinado(
    confirmarDuplicado = false,
    unificado = false,
    noIdOverride = null,
    acaoOverride = null
) {
    const acao = acaoOverride || form.value.acao || acaoScatterAtual.value;
    const payload = anexarPayloadResultadoEncerramento(
        montarPayload(confirmarDuplicado, unificado, noIdOverride, acaoOverride)
    );
    return payloadAssinaturaScatter(payload, acao, formTramitacao.value.assinar_eletronicamente);
}

async function executarEnvio(payload, multipart, unificado = false) {
    const apiCall = unificado
        ? ApiService.nosUnificadosOperacional
        : ApiService.scatterGatherOperacional;
    const { data } = await apiCall(props.demandaId, payload, multipart);
    emit('success', data);
    limparFormulario();
    dialogConflito.value = false;
    conflitosPendentes.value = [];
    payloadPendente.value = null;
}

async function executarDespachoMultiplos(acao, confirmarDuplicado = false) {
    const ids = idsOperacaoAtivos.value;
    enviando.value = true;
    try {
        let ultimaResposta = null;
        for (let i = 0; i < ids.length; i += 1) {
            const noId = ids[i];
            const payload = montarPayloadAssinado(confirmarDuplicado, false, noId);
            payload.acao = acao;
            const anexos = i === 0 ? formTramitacao.value.anexos : [];
            const { body, multipart } = buildMultipartPayload(payload, anexos);
            const { data } = await ApiService.scatterGatherOperacional(
                props.demandaId,
                body,
                multipart
            );
            ultimaResposta = data;
        }
        emit('success', ultimaResposta);
        limparFormulario();
        dialogConflito.value = false;
        conflitosPendentes.value = [];
        payloadPendente.value = null;
    } catch (err) {
        const data = err?.response?.data;
        emit(
            'error',
            data?.detail ||
                'Não foi possível registrar a operação em todos os nós selecionados.'
        );
    } finally {
        enviando.value = false;
    }
}

async function enviar(confirmarDuplicado = false, acaoOverride = null) {
    const ids = idsOperacaoAtivos.value;
    if (!ids.length) {
        emit('error', 'Selecione ao menos um nó operacional.');
        return;
    }
    const acao = acaoOverride || form.value.acao;
    if (!acao) {
        emit('error', 'Ação operacional não definida.');
        return;
    }
    form.value.acao = acao;
    const texto = formTramitacao.value.descricao?.trim() || '';
    const rotuloTexto = ehModoEncerrar.value ? 'encerramento' : 'despacho';
    if (texto.length < 10) {
        emit('error', `Informe a descrição do ${rotuloTexto} (mínimo 10 caracteres).`);
        return;
    }
    if (ehModoEncerrar.value) {
        const erroResultado = validarFormularioResultadoEncerramento();
        if (erroResultado) {
            emit('error', erroResultado);
            return;
        }
    }
    if (!ehModoEncerrar.value && acaoScatterRequerDestino(acao)) {
        const linhas = (form.value.destinos || []).filter((d) => d.secretaria_id);
        if (!linhas.length && podeEncerrar.value && podeEncerrarSelecionados.value) {
            modoOperacao.value = MODO_ENCERRAR_SCATTER;
            form.value.acao = ACAO_SCATTER_ENCERRAR;
            await executarEncerrarSelecionados({
                no_ids: nosSelecionadosIds.value.length
                    ? nosSelecionadosIds.value
                    : [form.value.no_id],
                no_canonico_id: form.value.no_id
            });
            return;
        }
        if (!linhas.length) {
            emit('error', 'Informe ao menos um órgão/setor de destino.');
            return;
        }
        const validacao = editorDestinosRef.value?.validarSetores?.();
        if (validacao && !validacao.ok) {
            emit('error', validacao.mensagem || 'Selecione o setor de cada órgão de destino.');
            return;
        }
    }

    if (!validarAssinaturaScatter(acao)) {
        return;
    }

    enviando.value = true;
    const unificado = Boolean(
        ids.length > 1 && usarDespachoUnificado.value && podeDespachoUnificado.value
    );
    if (ids.length > 1 && !unificado && !ehModoEncerrar.value) {
        enviando.value = false;
        await executarDespachoMultiplos(acao, confirmarDuplicado);
        return;
    }
    try {
        const payload = montarPayloadAssinado(confirmarDuplicado, unificado);
        payload.acao = acao;
        const { body, multipart } = buildMultipartPayload(payload, formTramitacao.value.anexos);
        await executarEnvio(body, multipart, unificado);
    } catch (err) {
        const data = err?.response?.data;
        if (data?.codigo === 'NO_DESTINO_DUPLICADO' && data?.conflitos?.length) {
            conflitosPendentes.value = data.conflitos;
            unificadoPendente.value = unificado;
            const { body, multipart } = buildMultipartPayload(
                montarPayloadAssinado(false, unificado),
                formTramitacao.value.anexos
            );
            payloadPendente.value = body;
            multipartPendente.value = multipart;
            dialogConflito.value = true;
            return;
        }
        emit('error', data?.detail || 'Não foi possível registrar a operação.');
    } finally {
        enviando.value = false;
    }
}

async function confirmarConflito() {
    if (!payloadPendente.value) return;
    enviando.value = true;
    const unificado = Boolean(usarDespachoUnificado.value && podeDespachoUnificado.value);
    try {
        const payload = { ...payloadPendente.value, confirmar_destino_duplicado: true };
        await executarEnvio(payload, multipartPendente.value, unificadoPendente.value);
    } catch (err) {
        emit('error', err?.response?.data?.detail || 'Não foi possível registrar a operação.');
    } finally {
        enviando.value = false;
    }
}

function cancelarConflito() {
    dialogConflito.value = false;
    conflitosPendentes.value = [];
    payloadPendente.value = null;
}

function onSelecionarNo(payload) {
    const { noId, todos, ids, grupo } = payload || {};
    if (noId != null) {
        form.value.no_id = noId;
    }
    responderTodos.value = Boolean(todos);
    nosSelecionadosIds.value = Array.isArray(ids) ? ids : noId != null ? [noId] : [];
    usarDespachoUnificado.value = Boolean(todos && grupo?.equivalentes);
}

function onPainelSuccess(data) {
    emit('success', data);
    limparFormulario();
    responderTodos.value = false;
    nosSelecionadosIds.value = [];
    usarDespachoUnificado.value = false;
}

function onEncerrarSelecionados(grupo) {
    onEncerrarLote(grupo);
}

function validarEncerramentoPermitido(ids) {
    if (nosPodemEncerrar(ids, gruposPainel.value, props.nosUsuario)) return true;
    emit(
        'error',
        mensagemEncerramentoBloqueado(ids, gruposPainel.value, props.nosUsuario) ||
            'Encerramento bloqueado — há encaminhamentos filhos em outras secretarias.'
    );
    return false;
}

async function executarEncerrarSelecionados(grupo) {
    const ids = (grupo.no_ids || []).map((id) => Number(id)).filter(Boolean);
    if (!ids.length) {
        emit('error', 'Selecione ao menos um nó para encerrar.');
        return;
    }
    if (!validarEncerramentoPermitido(ids)) return;
    const texto = formTramitacao.value.descricao?.trim() || '';
    if (texto.length < 10) {
        emit('error', 'Informe a descrição do encerramento (mínimo 10 caracteres).');
        return;
    }

    if (!validarAssinaturaScatter(ACAO_SCATTER_ENCERRAR)) return;

    const erroResultado = validarFormularioResultadoEncerramento();
    if (erroResultado) {
        emit('error', erroResultado);
        return;
    }

    enviando.value = true;
    try {
        let resposta = null;
        if (ids.length === 1) {
            const payload = payloadAssinaturaScatter(
                anexarPayloadResultadoEncerramento({
                    acao: ACAO_SCATTER_ENCERRAR,
                    no_id: ids[0],
                    observacao: texto,
                    descricao: texto
                }),
                ACAO_SCATTER_ENCERRAR,
                formTramitacao.value.assinar_eletronicamente
            );
            const { body, multipart } = buildMultipartPayload(payload, formTramitacao.value.anexos);
            const { data } = await ApiService.scatterGatherOperacional(
                props.demandaId,
                body,
                multipart
            );
            resposta = data;
        } else {
            const payload = payloadAssinaturaScatter(
                anexarPayloadResultadoEncerramento({
                    acao: 'ENCERRAR_LOTE',
                    no_ids: ids,
                    no_canonico_id: grupo.no_canonico_id ?? ids[0],
                    observacao: texto,
                    descricao: texto
                }),
                'ENCERRAR_LOTE',
                formTramitacao.value.assinar_eletronicamente
            );
            const { body, multipart } = buildMultipartPayload(payload, formTramitacao.value.anexos);
            const { data } = await ApiService.nosUnificadosOperacional(
                props.demandaId,
                body,
                multipart
            );
            resposta = data;
        }
        emit('success', resposta || {});
        limparFormulario();
    } catch (err) {
        emit('error', err?.response?.data?.detail || 'Não foi possível encerrar a participação.');
    } finally {
        enviando.value = false;
    }
}

function onEncerrarLote(grupo) {
    grupoEncerrarLote.value = grupo;
    formEncerrarLote.value = estadoFormularioTramitacao({
        descricao:
            'Encerramento unificado dos nós operacionais equivalentes nesta secretaria.'
    });
    resultadoEncerrarLote.value = estadoInicialResultadoOperacional();
    dialogEncerrarLote.value = true;
}

function fecharEncerrarLote() {
    dialogEncerrarLote.value = false;
    grupoEncerrarLote.value = null;
    formEncerrarLote.value = estadoFormularioTramitacao();
    resultadoEncerrarLote.value = estadoInicialResultadoOperacional();
}

async function confirmarEncerrarLote() {
    const grupo = grupoEncerrarLote.value;
    if (!grupo) return;
    const texto = formEncerrarLote.value.descricao?.trim() || '';
    if (texto.length < 10) {
        emit('error', 'Informe a descrição do encerramento (mínimo 10 caracteres).');
        return;
    }
    const erroResultado = validarResultadoOperacional(resultadoEncerrarLote.value);
    if (erroResultado) {
        emit('error', erroResultado);
        return;
    }
    enviandoEncerrarLote.value = true;
    try {
        const payload = payloadAssinaturaScatter(
            anexarResultadoOperacionalPayload(
                {
                    acao: 'ENCERRAR_LOTE',
                    no_ids: grupo.no_ids,
                    no_canonico_id: grupo.no_canonico_id,
                    observacao: texto,
                    descricao: texto
                },
                resultadoEncerrarLote.value
            ),
            'ENCERRAR_LOTE',
            true
        );
        const { body, multipart } = buildMultipartPayload(
            payload,
            formEncerrarLote.value.anexos
        );
        const { data } = await ApiService.nosUnificadosOperacional(
            props.demandaId,
            body,
            multipart
        );
        emit('success', data);
        fecharEncerrarLote();
        limparFormulario();
    } catch (err) {
        emit(
            'error',
            err?.response?.data?.detail || 'Não foi possível encerrar os nós equivalentes.'
        );
    } finally {
        enviandoEncerrarLote.value = false;
    }
}

function onAnexoInvalidoEncerrar(msg) {
    emit('error', msg);
}

function validarAntesEnvio() {
    if (!form.value.no_id && !nosSelecionadosIds.value.length) {
        emit('error', 'Selecione o nó operacional.');
        return false;
    }
    const texto = formTramitacao.value.descricao?.trim() || '';
    const rotulo = ehModoEncerrar.value ? 'encerramento' : 'despacho';
    if (texto.length < 10) {
        emit('error', `Informe a descrição do ${rotulo} (mínimo 10 caracteres).`);
        return false;
    }
    if (!ehModoEncerrar.value && podeDespachar.value) {
        const linhas = (form.value.destinos || []).filter((d) => d.secretaria_id);
        if (!linhas.length && !podeEncerrar.value) {
            emit('error', 'Informe ao menos um órgão/setor de destino.');
            return false;
        }
        const validacao = editorDestinosRef.value?.validarSetores?.();
        if (validacao && !validacao.ok) {
            emit('error', validacao.mensagem || 'Selecione o setor de cada órgão de destino.');
            return false;
        }
    }
    return true;
}

function solicitarEnvio() {
    if (!validarAntesEnvio()) return;

    if (ehModoEncerrar.value) {
        abrirConfirmacaoOperacao(ACAO_SCATTER_ENCERRAR);
        return;
    }

    const linhasDestino = (form.value.destinos || []).filter((d) => d.secretaria_id);
    if (!linhasDestino.length && podeEncerrar.value && podeEncerrarSelecionados.value) {
        abrirConfirmacaoOperacao(ACAO_SCATTER_ENCERRAR);
        return;
    }

    if (podeDespachar.value && podeEncerrarAposDespacho.value) {
        dialogEncerrarParticipacao.value = true;
        return;
    }

    const acao = podeDespachar.value ? ACAO_SCATTER_DESPACHAR : ACAO_SCATTER_ENCERRAR;
    abrirConfirmacaoOperacao(acao);
}

function confirmarDespacho(encerrarParticipacao) {
    dialogEncerrarParticipacao.value = false;
    if (encerrarParticipacao) {
        const ids = idsOperacaoAtivos.value;
        if (!validarEncerramentoPermitido(ids.length ? ids : [form.value.no_id])) return;
    }
    const acao = encerrarParticipacao ? ACAO_SCATTER_DESPACHAR_ENCERRAR : ACAO_SCATTER_DESPACHAR;
    abrirConfirmacaoOperacao(acao);
}

const labelBotao = computed(() => {
    const qtd = idsOperacaoAtivos.value.length;
    if (ehModoEncerrar.value) {
        if (qtd > 1) return `Encerrar ${qtd} nós`;
        return 'Encerrar participação';
    }
    if (usarDespachoUnificado.value && podeDespachoUnificado.value) {
        return 'Despachar como nó único';
    }
    if (podeDespachar.value && qtd > 1) return `Registrar despacho (${qtd} nós)`;
    if (podeDespachar.value) return 'Registrar despacho';
    return 'Registrar operação';
});

const iconeBotao = computed(() =>
    ehModoEncerrar.value ? 'pi pi-times-circle' : 'pi pi-share-alt'
);

watch(
    opcoesModoOperacao,
    (opcoes) => {
        if (!opcoes.some((o) => o.value === modoOperacao.value) && opcoes.length) {
            modoOperacao.value = opcoes[0].value;
        }
    },
    { immediate: true }
);

</script>

<template>
    <div class="flex flex-col gap-4">
        <FormularioTramitacao
            v-model="formTramitacao"
            :modo="MODO_ANDAMENTO"
            :regras-assinatura="regrasAssinaturaScatterAtual"
            :demanda-id="demandaId"
            :demanda-context="demandaContext"
            :grupos-nos-painel="gruposPainel"
            :no-ativo-id="form.no_id"
            :responder-todos="responderTodos"
            :nos-selecionados-ids="nosSelecionadosIds"
            :acoes-nos-equivalentes="acoesDisponiveis"
            :orgaos="orgaos"
            :orgao-fixo-id="orgaoFixoId"
            :exibir-destinos="false"
            :exibir-tipo-andamento="false"
            :label-descricao="labelDescricaoForm"
            @update:responder-todos="(v) => (responderTodos = v)"
            @update:nos-selecionados-ids="(v) => (nosSelecionadosIds = v)"
            @nos-equivalentes-success="onPainelSuccess"
            @nos-equivalentes-error="(msg) => emit('error', msg)"
            @usar-no-canonico="onSelecionarNo"
            @encerrar-lote="onEncerrarLote"
            @encerrar-selecionados="onEncerrarSelecionados"
            @anexos-rejeitados="(msg) => emit('error', msg)"
            @anexo-invalido="(msg) => emit('error', msg)"
        >
            <template #prepend>
                <div v-if="opcoesModoOperacao.length > 1" class="flex flex-col gap-2">
                    <label class="font-medium text-sm">Tipo de operação</label>
                    <SelectButton
                        v-model="modoOperacao"
                        :options="opcoesModoOperacao"
                        option-label="label"
                        option-value="value"
                        class="w-full scatter-modo-operacao"
                    />
                    <Message
                        v-if="ehModoEncerrar && !encerrarBloqueado"
                        severity="info"
                        :closable="false"
                        class="m-0 text-sm"
                    >
                        Encerramento sem despacho — não é necessário informar secretaria ou setor
                        de destino.
                    </Message>
                    <Message
                        v-if="encerrarBloqueado && mensagemBloqueioEncerrar"
                        severity="warn"
                        :closable="false"
                        class="m-0 text-sm"
                    >
                        {{ mensagemBloqueioEncerrar }}
                    </Message>
                </div>

                <div v-if="exibirSeletorNo" class="flex flex-col gap-2">
                    <label for="scatter-no" class="font-medium text-sm">
                        Seu(s) nó(s) operacional(is)
                    </label>
                    <MultiSelect
                        id="scatter-no"
                        :model-value="nosSelecionadosIds"
                        :options="opcoesNo"
                        option-label="label"
                        option-value="value"
                        placeholder="Selecione um ou mais nós"
                        display="chip"
                        class="w-full"
                        @update:model-value="sincronizarNoPrincipal"
                    />
                    <p v-if="nosSelecionadosIds.length > 1" class="m-0 text-xs text-muted-color">
                        A mesma operação será aplicada a cada nó selecionado.
                    </p>
                </div>
                <div v-else-if="noAtivoResumo && !exibirPainelEquivalentes" class="flex flex-col gap-1">
                    <p class="m-0 text-sm text-muted-color">
                        Nó ativo: <strong>{{ noAtivoResumo.label }}</strong>
                    </p>
                </div>

                <Message
                    v-if="podeDespachoUnificado"
                    severity="info"
                    :closable="false"
                    class="m-0 text-sm"
                >
                    <label class="flex align-items-start gap-2 cursor-pointer">
                        <input v-model="usarDespachoUnificado" type="checkbox" class="mt-1" />
                        <span>
                            <strong>Despachar como nó único</strong> — consolida
                            {{ grupoDoNoSelecionado.quantidade }} encaminhamentos equivalentes e executa
                            uma única operação pelo nó principal ({{
                                grupoDoNoSelecionado.nos?.find(
                                    (n) => n.id === grupoDoNoSelecionado.no_canonico_id
                                )?.origem_label || 'Protocolo'
                            }}).
                        </span>
                    </label>
                </Message>

                <DestinosTramitacaoEditor
                    v-if="exibirEditorDestinos"
                    ref="editorDestinosRef"
                    v-model="form.destinos"
                    :modo="MODO_DESPACHO"
                    :orgaos="orgaos"
                    :orgao-competente-id="null"
                    :permitir-integrados="true"
                    :destinos-ocupados="destinosOcupados"
                    contexto-scatter
                />

                <FormularioResultadoOperacional
                    v-if="ehModoEncerrar"
                    v-model="resultadoOperacional"
                    :endereco-sugerido="enderecoSugerido"
                />
            </template>

            <template #extra>
                <Button
                    :label="labelBotao"
                    :icon="iconeBotao"
                    :loading="enviando"
                    :disabled="
                        (!form.no_id && !nosSelecionadosIds.length) ||
                        (ehModoEncerrar && !podeEncerrarSelecionados)
                    "
                    @click="solicitarEnvio"
                />
            </template>
        </FormularioTramitacao>

        <Dialog
            v-model:visible="dialogEncerrarParticipacao"
            header="Encerrar participação?"
            modal
            :style="{ width: 'min(520px, 95vw)' }"
        >
            <p class="mt-0 mb-3 text-sm">
                Deseja encerrar sua participação neste nó após registrar o despacho?
            </p>
            <Message severity="info" :closable="false" class="m-0 text-sm">
                Se optar por <strong>não encerrar</strong>, o despacho será registrado e o nó
                permanece aberto para novas operações.
            </Message>
            <template #footer>
                <Button
                    label="Cancelar"
                    icon="pi pi-times"
                    text
                    @click="dialogEncerrarParticipacao = false"
                />
                <Button
                    label="Não, manter nó aberto"
                    icon="pi pi-share-alt"
                    severity="secondary"
                    outlined
                    :loading="enviando"
                    @click="confirmarDespacho(false)"
                />
                <Button
                    label="Sim, despachar e encerrar"
                    icon="pi pi-check"
                    :loading="enviando"
                    @click="confirmarDespacho(true)"
                />
            </template>
        </Dialog>

        <Dialog
            v-model:visible="dialogConflito"
            header="Encaminhamento redundante"
            modal
            :style="{ width: 'min(560px, 95vw)' }"
            @hide="cancelarConflito"
        >
            <Message severity="warn" :closable="false" class="mb-3">
                Um ou mais destinos já possuem nó operacional aberto. Confira o encaminhamento
                anterior antes de prosseguir.
            </Message>

            <div
                v-for="(conflito, idx) in conflitosPendentes"
                :key="`${conflito.secretaria_id}-${conflito.unidade_administrativa_id}-${idx}`"
                class="mb-3 p-3 border border-surface-200 dark:border-surface-700 rounded-lg"
            >
                <p class="mt-0 mb-2 font-semibold text-sm">
                    {{ rotuloDestinoOcupado(conflito) }}
                </p>
                <div
                    v-for="no in conflito.nos_existentes"
                    :key="no.id"
                    class="text-sm text-muted-color mb-2"
                >
                    <Tag :value="no.origem_label || 'Encaminhamento'" severity="info" class="mr-2" />
                    <span v-if="no.resumo_abertura">{{ no.resumo_abertura }}</span>
                    <span v-else class="italic">Sem resumo do despacho anterior.</span>
                </div>
            </div>

            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="cancelarConflito" />
                <Button
                    label="Prosseguir mesmo assim"
                    icon="pi pi-check"
                    severity="warn"
                    :loading="enviando"
                    @click="confirmarConflito"
                />
            </template>
        </Dialog>

        <Dialog
            v-model:visible="dialogEncerrarLote"
            header="Encerrar todos os nós equivalentes"
            modal
            :style="{ width: 'min(640px, 95vw)' }"
            @hide="fecharEncerrarLote"
        >
            <p v-if="grupoEncerrarLote" class="mt-0 text-sm text-muted-color mb-3">
                {{ rotuloDestinoOcupado(grupoEncerrarLote) }} —
                {{ grupoEncerrarLote.quantidade }} nó(s) serão encerrados de uma vez.
            </p>
            <FormularioTramitacao
                v-model="formEncerrarLote"
                :modo="MODO_ANDAMENTO"
                :demanda-id="demandaId"
                :demanda-context="demandaContext"
                :orgaos="orgaos"
                :orgao-fixo-id="orgaoFixoId"
                :exibir-destinos="false"
                :exibir-tipo-andamento="false"
                label-descricao="Descrição do encerramento"
                @anexo-invalido="onAnexoInvalidoEncerrar"
                @anexos-rejeitados="onAnexoInvalidoEncerrar"
            />
            <FormularioResultadoOperacional
                v-model="resultadoEncerrarLote"
                :endereco-sugerido="enderecoSugerido"
            />
            <p class="text-xs text-muted-color mb-0 mt-2">
                O texto e os anexos ficam registrados na timeline operacional da demanda.
            </p>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="fecharEncerrarLote" />
                <Button
                    label="Encerrar todos"
                    icon="pi pi-check-circle"
                    severity="help"
                    :loading="enviandoEncerrarLote"
                    @click="confirmarEncerrarLote"
                />
            </template>
        </Dialog>

        <DialogConfirmacaoTramitacao
            v-model:visible="confirmOperacaoVisible"
            :titulo="tituloConfirmacaoOperacao"
            :mensagem="mensagemConfirmacaoOperacao"
            :resumo-destinos="acaoOperacaoPendente === ACAO_SCATTER_ENCERRAR ? [] : resumoDestinosOperacao"
            :regras-assinatura="regrasAssinaturaScatter(acaoOperacaoPendente || ACAO_SCATTER_DESPACHAR)"
            :assinar-no-formulario="formTramitacao.assinar_eletronicamente"
            :label-confirmar="labelConfirmarOperacao"
            @confirmar="executarOperacaoConfirmada"
        />
    </div>
</template>
