<script setup>
import { ref, computed, watch } from 'vue';
import Button from 'primevue/button';
import Checkbox from 'primevue/checkbox';
import Tag from 'primevue/tag';
import Message from 'primevue/message';
import Dialog from 'primevue/dialog';
import DescricaoTramitacaoEditor from '@/components/tramitacao/DescricaoTramitacaoEditor.vue';
import { rotuloNoOperacional, rotuloDestinoOcupado } from '@/constants/scatterGather';
import { descricaoTramitacaoParaExibicao } from '@/utils/tramitacaoTexto';
import ApiService from '@/service/ApiService.js';

function resumoAberturaExibicao(texto) {
    return descricaoTramitacaoParaExibicao(texto);
}

const props = defineProps({
    demandaId: { type: [Number, String], required: true },
    grupos: { type: Array, default: () => [] },
    acoesDisponiveis: { type: Array, default: () => [] },
    noAtivoId: { type: [Number, String], default: null },
    responderTodos: { type: Boolean, default: false },
    nosSelecionadosIds: { type: Array, default: () => [] }
});

const emit = defineEmits([
    'success',
    'error',
    'usar-canonico',
    'encerrar-lote',
    'encerrar-selecionados',
    'update:responderTodos',
    'update:nosSelecionadosIds'
]);

const enviando = ref(false);
const dialogVisible = ref(false);
const dialogAcao = ref(null);
const grupoSelecionado = ref(null);
const observacao = ref('');

const podeConsolidar = computed(() => props.acoesDisponiveis.includes('scatter_consolidar'));
const podeEncerrarLote = computed(() => props.acoesDisponiveis.includes('scatter_encerrar_lote'));
const podeEncerrar = computed(
    () =>
        props.acoesDisponiveis.includes('scatter_encerrar') ||
        props.acoesDisponiveis.includes('scatter_encerrar_lote')
);

const idsSelecionadosSet = computed(
    () => new Set((props.nosSelecionadosIds || []).map((id) => Number(id)))
);

function noEstaSelecionado(noId) {
    return idsSelecionadosSet.value.has(Number(noId));
}

function sincronizarSelecao(grupo, ids, todos) {
    emit('update:nosSelecionadosIds', ids);
    emit('update:responderTodos', todos);
    const canonId = grupo?.no_canonico_id ?? ids[0] ?? null;
    if (canonId != null) {
        emit('usar-canonico', { noId: canonId, todos, ids, grupo });
    }
}

function alternarResponderTodos(grupo, valor) {
    if (!grupo) return;
    if (valor) {
        sincronizarSelecao(
            grupo,
            grupo.no_ids.map((id) => Number(id)),
            true
        );
        return;
    }
    const ativo = props.noAtivoId ?? grupo.no_canonico_id;
    sincronizarSelecao(grupo, [Number(ativo)], false);
}

function selecionarNo(grupo, noId) {
    if (!grupo) return;
    if (props.responderTodos) {
        alternarResponderTodos(grupo, false);
    }
    sincronizarSelecao(grupo, [Number(noId)], false);
}

function alternarNoNaSelecao(grupo, noId) {
    if (!grupo) return;
    const id = Number(noId);
    let ids = [...idsSelecionadosSet.value];
    if (ids.includes(id)) {
        ids = ids.filter((i) => i !== id);
    } else {
        ids.push(id);
    }
    if (!ids.length) {
        ids = [id];
    }
    const todos = ids.length === grupo.no_ids.length;
    sincronizarSelecao(grupo, ids, todos);
}

function abrirConsolidar(grupo) {
    dialogAcao.value = 'CONSOLIDAR';
    grupoSelecionado.value = grupo;
    dialogVisible.value = true;
    observacao.value =
        'Consolidação dos encaminhamentos equivalentes — mantido o nó principal do Protocolo.';
}

function solicitarEncerrarLote(grupo) {
    emit('encerrar-lote', grupo);
}

function solicitarEncerrarSelecionados(grupo) {
    const ids = [...idsSelecionadosSet.value];
    if (!ids.length) return;
    emit('encerrar-selecionados', {
        no_ids: ids,
        no_canonico_id: grupo.no_canonico_id,
        quantidade: ids.length,
        nos: grupo.nos.filter((n) => ids.includes(Number(n.id)))
    });
}

function fecharDialog() {
    dialogVisible.value = false;
    dialogAcao.value = null;
    grupoSelecionado.value = null;
    observacao.value = '';
}

async function confirmarAcao() {
    const grupo = grupoSelecionado.value;
    if (!grupo || !dialogAcao.value) return;
    const texto = observacao.value?.trim() || '';
    if (texto.length < 10) {
        emit('error', 'Informe a justificativa (mínimo 10 caracteres).');
        return;
    }
    enviando.value = true;
    try {
        const payload = {
            acao: dialogAcao.value,
            no_ids: grupo.no_ids,
            no_canonico_id: grupo.no_canonico_id,
            observacao: texto,
            descricao: texto
        };
        const { data } = await ApiService.nosUnificadosOperacional(props.demandaId, payload, false);
        emit('success', data);
        fecharDialog();
    } catch (err) {
        emit('error', err?.response?.data?.detail || 'Não foi possível concluir a ação unificada.');
    } finally {
        enviando.value = false;
    }
}

watch(
    () => props.grupos,
    (grupos) => {
        const grupo = grupos?.[0];
        if (!grupo) return;

        const idsValidos = new Set((grupo.no_ids || []).map((id) => Number(id)));
        const selecionados = (props.nosSelecionadosIds || [])
            .map((id) => Number(id))
            .filter((id) => idsValidos.has(id));

        if (!selecionados.length) {
            sincronizarSelecao(grupo, [Number(grupo.no_canonico_id)], false);
            return;
        }

        if (selecionados.length !== (props.nosSelecionadosIds || []).length) {
            sincronizarSelecao(
                grupo,
                selecionados,
                selecionados.length === grupo.no_ids.length
            );
        }
    },
    { immediate: true, deep: true }
);

function rotuloFilhoExterno(filho) {
    if (!filho) return '';
    const org = filho.orgao_nome || `Órgão #${filho.id}`;
    return filho.setor_nome ? `${org} › ${filho.setor_nome}` : org;
}

function filhosInternosBloqueantes(no) {
    if (!no) return [];
    if (Array.isArray(no.filhos_abertos_internos) && no.filhos_abertos_internos.length) {
        return no.filhos_abertos_internos;
    }
    return no.pode_encerrar === false ? no.filhos_abertos_externos || [] : [];
}

const noSelecionadoPodeEncerrar = computed(() => {
    const grupo = props.grupos?.[0];
    if (!grupo?.nos?.length) return true;
    const mapa = new Map(grupo.nos.map((n) => [Number(n.id), n]));
    return (props.nosSelecionadosIds || []).every((id) => {
        const no = mapa.get(Number(id));
        return !no || no.pode_encerrar !== false;
    });
});
</script>

<template>
    <div v-if="grupos.length" class="flex flex-col gap-3">
        <div
            v-for="grupo in grupos"
            :key="`${grupo.secretaria_id}-${grupo.unidade_administrativa_id}`"
            class="flex flex-col gap-3"
        >
            <Message severity="warn" :closable="false" class="m-0">
                <template v-if="grupo.equivalentes">
                    Encaminhamentos redundantes na mesma secretaria. Marque os nós ou responda por
                    todos de uma vez.
                </template>
                <template v-else>
                    {{ grupo.quantidade }} nós abertos nesta secretaria. Selecione em qual(is)
                    operar ou encerre a participação.
                </template>
            </Message>

            <div
                class="p-3 border border-surface-200 dark:border-surface-700 rounded-lg flex flex-col gap-3"
            >
                <div
                    class="flex flex-wrap align-items-center justify-content-between gap-3 pb-2 border-bottom-1 surface-border"
                >
                    <div class="flex flex-wrap align-items-center gap-2">
                        <Tag :value="`${grupo.quantidade} nós abertos`" severity="warn" />
                        <Tag
                            v-if="grupo.equivalentes"
                            value="Redundantes"
                            severity="secondary"
                            class="text-xs"
                        />
                    </div>
                    <label
                        v-if="grupo.quantidade > 1"
                        class="flex align-items-center gap-2 cursor-pointer text-sm m-0"
                    >
                        <Checkbox
                            :model-value="responderTodos"
                            binary
                            :input-id="`responder-todos-${grupo.secretaria_id}`"
                            @update:model-value="alternarResponderTodos(grupo, $event)"
                        />
                        <span :for="`responder-todos-${grupo.secretaria_id}`">
                            Responder por todos
                        </span>
                    </label>
                </div>

                <ul class="m-0 pl-0 list-none flex flex-col gap-2">
                    <li v-for="no in grupo.nos" :key="no.id">
                        <button
                            type="button"
                            class="w-full text-left p-3 border rounded-lg text-sm transition-colors cursor-pointer bg-transparent"
                            :class="
                                noEstaSelecionado(no.id)
                                    ? 'border-primary surface-100 dark:surface-800 shadow-sm'
                                    : 'border-surface-200 dark:border-surface-700 hover:surface-50'
                            "
                            @click="selecionarNo(grupo, no.id)"
                        >
                            <div class="flex align-items-start gap-3">
                                <Checkbox
                                    v-if="grupo.quantidade > 1"
                                    :model-value="noEstaSelecionado(no.id)"
                                    binary
                                    class="mt-1 shrink-0"
                                    @click.stop
                                    @update:model-value="
                                        () => alternarNoNaSelecao(grupo, no.id)
                                    "
                                />
                                <div class="flex-1 min-w-0">
                                    <div class="flex flex-wrap align-items-center gap-2 mb-1">
                                        <Tag
                                            v-if="no.id === grupo.no_canonico_id"
                                            value="Principal"
                                            severity="success"
                                            class="text-xs"
                                        />
                                        <Tag
                                            :value="no.origem_label"
                                            severity="info"
                                            class="text-xs"
                                        />
                                        <Tag
                                            v-if="Number(noAtivoId) === Number(no.id)"
                                            value="Em operação"
                                            severity="warn"
                                            class="text-xs"
                                        />
                                    </div>
                                    <p class="m-0 font-medium text-color">
                                        {{ rotuloNoOperacional(no) }}
                                    </p>
                                    <div
                                        v-if="
                                            no.resumo_abertura &&
                                            resumoAberturaExibicao(no.resumo_abertura).modo ===
                                                'html'
                                        "
                                        class="block text-xs mt-2 text-muted-color tramitacao-html"
                                        v-html="resumoAberturaExibicao(no.resumo_abertura).html"
                                    />
                                    <p
                                        v-else-if="
                                            no.resumo_abertura &&
                                            resumoAberturaExibicao(no.resumo_abertura).modo ===
                                                'texto'
                                        "
                                        class="m-0 text-xs mt-2 text-muted-color line-clamp-3"
                                    >
                                        {{ resumoAberturaExibicao(no.resumo_abertura).texto }}
                                    </p>
                                    <Message
                                        v-if="no.pode_encerrar === false && filhosInternosBloqueantes(no).length"
                                        severity="warn"
                                        :closable="false"
                                        class="m-0 mt-2 text-xs"
                                    >
                                        Encerramento bloqueado — encaminhamentos internos pendentes:
                                        <span
                                            v-for="(filho, fi) in filhosInternosBloqueantes(no)"
                                            :key="filho.id"
                                        >
                                            {{ fi > 0 ? '; ' : ' ' }}#{{ filho.id }}
                                            ({{ rotuloFilhoExterno(filho) }})
                                        </span>
                                    </Message>
                                    <Message
                                        v-else-if="no.filhos_abertos_externos?.length"
                                        severity="info"
                                        :closable="false"
                                        class="m-0 mt-2 text-xs"
                                    >
                                        Encaminhamentos em andamento em outras secretarias:
                                        <span
                                            v-for="(filho, fi) in no.filhos_abertos_externos"
                                            :key="filho.id"
                                        >
                                            {{ fi > 0 ? '; ' : ' ' }}#{{ filho.id }}
                                            ({{ rotuloFilhoExterno(filho) }})
                                        </span>
                                    </Message>
                                </div>
                            </div>
                        </button>
                    </li>
                </ul>

                <div class="flex flex-wrap gap-2 pt-1">
                    <Button
                        v-if="podeEncerrar && nosSelecionadosIds.length >= 1 && noSelecionadoPodeEncerrar"
                        :label="
                            nosSelecionadosIds.length > 1
                                ? `Encerrar ${nosSelecionadosIds.length} selecionados`
                                : 'Encerrar selecionado'
                        "
                        icon="pi pi-times-circle"
                        size="small"
                        severity="danger"
                        outlined
                        @click="solicitarEncerrarSelecionados(grupo)"
                    />
                    <template v-if="grupo.equivalentes">
                        <Button
                            v-if="podeConsolidar"
                            label="Manter principal"
                            icon="pi pi-compress"
                            size="small"
                            severity="secondary"
                            outlined
                            @click="abrirConsolidar(grupo)"
                        />
                        <Button
                            v-if="podeEncerrarLote"
                            label="Encerrar todos"
                            icon="pi pi-check-circle"
                            size="small"
                            severity="help"
                            outlined
                            @click="solicitarEncerrarLote(grupo)"
                        />
                    </template>
                </div>
            </div>
        </div>

        <Dialog
            v-model:visible="dialogVisible"
            header="Consolidar nós equivalentes"
            modal
            :style="{ width: 'min(560px, 95vw)' }"
            @hide="fecharDialog"
        >
            <p v-if="grupoSelecionado" class="mt-0 text-sm text-muted-color">
                {{ rotuloDestinoOcupado(grupoSelecionado) }} —
                {{ grupoSelecionado.quantidade }} nó(s): o principal será mantido e os demais
                encerrados.
            </p>
            <DescricaoTramitacaoEditor
                v-model="observacao"
                contexto="operacional"
                label="Justificativa da consolidação"
            />
            <p class="text-xs text-muted-color mb-0 mt-2">
                Registrada na timeline operacional como tramitação scatter-gather.
            </p>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="fecharDialog" />
                <Button
                    label="Confirmar"
                    icon="pi pi-check"
                    :loading="enviando"
                    @click="confirmarAcao"
                />
            </template>
        </Dialog>
    </div>
</template>
