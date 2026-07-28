<script setup>
import Button from 'primevue/button';
import Divider from 'primevue/divider';
import Message from 'primevue/message';
import MultiSelect from 'primevue/multiselect';
import Select from 'primevue/select';
import Tag from 'primevue/tag';
import { computed, ref, watch } from 'vue';
import ApiService from '@/service/ApiService';
import {
    MAX_INTEGRADOS_DESPACHO,
    MAX_PERNAS_DESPACHO,
    MODO_ANDAMENTO,
    MODO_DESPACHO,
    contarPernasDestinos,
    novoDestino,
    validarSetoresObrigatoriosDestinos
} from '@/constants/tramitacaoFormulario';
import { destinoScatterOcupado, rotuloDestinoOcupado } from '@/constants/scatterGather';

const props = defineProps({
    modo: { type: String, required: true },
    modelValue: { type: Array, default: () => [] },
    orgaos: { type: Array, default: () => [] },
    orgaoCompetenteId: { type: Number, default: null },
    orgaoCompetenteNome: { type: String, default: '' },
    orgaosIntegraveis: { type: Array, default: () => [] },
    /** Andamento: órgão fixo da secretaria logada */
    orgaoFixoId: { type: Number, default: null },
    orgaosEditaveis: { type: Boolean, default: false },
    /** Andamento da secretaria líder: permite abrir órgãos integrados (C1/C2) */
    permitirIntegrados: { type: Boolean, default: false },
    /** Nós operacionais abertos por destino (scatter-gather — aviso de redundância) */
    destinosOcupados: { type: Array, default: () => [] },
    /** Despacho scatter-gather na etapa operacional (multi-órgão livre) */
    contextoScatter: { type: Boolean, default: false }
});

const emit = defineEmits(['update:modelValue', 'change']);

const unidadesPorOrgao = ref({});
const carregandoOrgao = ref({});

const destinos = computed({
    get: () => props.modelValue,
    set: (v) => emit('update:modelValue', v)
});

const totalPernas = computed(() => contarPernasDestinos(destinos.value, unidadesPorOrgao.value));

const errosSetorObrigatorio = computed(() => {
    const destinosValidar =
        props.modo === MODO_ANDAMENTO
            ? destinos.value.filter((d) => !d.fixo)
            : destinos.value;
    return validarSetoresObrigatoriosDestinos(
        destinosValidar,
        unidadesPorOrgao.value,
        props.orgaos
    );
});

const pernasExcedidas = computed(() => totalPernas.value > MAX_PERNAS_DESPACHO);

function destinoExigeSetor(destino) {
    if (!destino?.secretaria_id) return false;
    if (props.modo === MODO_ANDAMENTO && destino.fixo) return false;
    return opcoesUnidades(destino.secretaria_id).length > 0;
}

function destinoSemSetorObrigatorio(destino) {
    if (!destinoExigeSetor(destino)) return false;
    const setores = destino.unidade_administrativa_ids?.length
        ? destino.unidade_administrativa_ids
        : destino.unidade_administrativa_id
          ? [destino.unidade_administrativa_id]
          : [];
    return !setores.length;
}

function validarSetores() {
    const destinosValidar =
        props.modo === MODO_ANDAMENTO
            ? destinos.value.filter((d) => !d.fixo)
            : destinos.value;
    const erros = validarSetoresObrigatoriosDestinos(
        destinosValidar,
        unidadesPorOrgao.value,
        props.orgaos
    );
    return {
        ok: !erros.length,
        erros,
        mensagem: erros[0]?.mensagem || null
    };
}

defineExpose({
    validarSetores,
    unidadesPorOrgao
});

function opcoesOrgaoIntegrado(destino) {
    const usados = new Set(
        destinos.value
            .filter((d) => !d.fixo && d.secretaria_id && d !== destino)
            .map((d) => Number(d.secretaria_id))
    );
    const base =
        props.orgaosIntegraveis.length > 0
            ? props.orgaosIntegraveis
            : props.orgaos.filter(
                  (o) => !props.orgaoFixoId || Number(o.id) !== Number(props.orgaoFixoId)
              );
    const lista = base.filter((o) => !usados.has(Number(o.id)));
    if (destino.secretaria_id) {
        const sid = Number(destino.secretaria_id);
        if (!lista.some((o) => Number(o.id) === sid)) {
            const atual =
                props.orgaos.find((o) => Number(o.id) === sid) ||
                props.orgaosIntegraveis.find((o) => Number(o.id) === sid);
            if (atual) lista.push(atual);
        }
    }
    return lista;
}

const catalogoIntegraveisCarregado = computed(() => {
    const base =
        props.orgaosIntegraveis.length > 0
            ? props.orgaosIntegraveis
            : props.orgaos.filter(
                  (o) => !props.orgaoFixoId || Number(o.id) !== Number(props.orgaoFixoId)
              );
    return base.length > 0;
});

const orgaoAndamentoLabel = computed(() => {
    if (props.modo !== MODO_ANDAMENTO) return '';
    const id = props.orgaoFixoId || destinos.value[0]?.secretaria_id;
    if (props.orgaoCompetenteNome) return props.orgaoCompetenteNome;
    if (!id) return '—';
    const o = props.orgaos.find((item) => Number(item.id) === Number(id));
    return o?.nome || `Órgão #${id}`;
});

const setorAndamentoId = computed({
    get: () => destinos.value[0]?.unidade_administrativa_id ?? null,
    set: (uid) => {
        if (!destinos.value.length) return;
        onSetorUnicoChange(0, uid);
    }
});

const orgaoIdAndamento = computed(
    () => props.orgaoFixoId || destinos.value[0]?.secretaria_id || null
);

const podeAdicionarIntegrado = computed(
    () =>
        ((props.modo === MODO_DESPACHO) ||
            (props.modo === MODO_ANDAMENTO && props.permitirIntegrados)) &&
        destinos.value.filter((d) => !d.fixo).length < MAX_INTEGRADOS_DESPACHO &&
        catalogoIntegraveisCarregado.value
);

const destinosIntegrados = computed(() => destinos.value.filter((d) => !d.fixo));

const totalPernasIntegradas = computed(() =>
    contarPernasDestinos(destinosIntegrados.value, unidadesPorOrgao.value)
);

function avisosDestinoOcupado(destino) {
    if (!destino?.secretaria_id || !props.destinosOcupados?.length) return [];
    const avisos = [];
    const setores = destino.unidade_administrativa_ids?.length
        ? destino.unidade_administrativa_ids
        : destino.unidade_administrativa_id
          ? [destino.unidade_administrativa_id]
          : [null];
    for (const uid of setores) {
        const ocupado = destinoScatterOcupado(
            props.destinosOcupados,
            destino.secretaria_id,
            uid
        );
        if (ocupado && !avisos.some((a) => a.secretaria_id === ocupado.secretaria_id && a.unidade_administrativa_id === ocupado.unidade_administrativa_id)) {
            avisos.push(ocupado);
        }
    }
    return avisos;
}

function emitChange() {
    emit('change', destinos.value);
}

function atualizarDestinos(lista) {
    destinos.value = lista;
    emitChange();
}

function patchDestino(index, partial) {
    const next = destinos.value.map((d, i) => (i === index ? { ...d, ...partial } : d));
    atualizarDestinos(next);
}

async function carregarUnidades(orgaoId) {
    const oid = Number(orgaoId);
    if (!oid || unidadesPorOrgao.value[oid]) return;
    carregandoOrgao.value = { ...carregandoOrgao.value, [oid]: true };
    try {
        const { data } = await ApiService.listarUnidadesAdministrativas({
            sinapse_orgao_id: oid,
            ativo: true
        });
        const lista = Array.isArray(data) ? data : data?.results || [];
        unidadesPorOrgao.value = {
            ...unidadesPorOrgao.value,
            [oid]: lista.map((u) => ({
                id: u.id,
                label: u.sigla ? `${u.sigla} — ${u.nome}` : u.nome
            }))
        };
    } catch {
        unidadesPorOrgao.value = { ...unidadesPorOrgao.value, [oid]: [] };
    } finally {
        carregandoOrgao.value = { ...carregandoOrgao.value, [oid]: false };
    }
}

function opcoesUnidades(orgaoId) {
    return unidadesPorOrgao.value[Number(orgaoId)] || [];
}

function onOrgaoChange(index, orgaoId) {
    patchDestino(index, {
        secretaria_id: orgaoId ? Number(orgaoId) : null,
        unidade_administrativa_id: null,
        unidade_administrativa_ids: [],
        unidade_labels: []
    });
    if (orgaoId) carregarUnidades(orgaoId);
}

function onSetoresChange(index, unidadeIds) {
    const ids = (unidadeIds || []).map(Number).filter(Boolean);
    const opts = opcoesUnidades(destinos.value[index]?.secretaria_id);
    const labels = ids.map((id) => opts.find((u) => u.id === id)?.label || `Setor #${id}`);
    patchDestino(index, {
        unidade_administrativa_ids: ids,
        unidade_administrativa_id: ids[0] || null,
        unidade_labels: labels
    });
}

function onSetorUnicoChange(index, unidadeId) {
    onSetoresChange(index, unidadeId ? [unidadeId] : []);
}

function adicionarIntegrado() {
    if (!podeAdicionarIntegrado.value) return;
    atualizarDestinos([...destinos.value, novoDestino()]);
}

function removerIntegrado(index) {
    const d = destinos.value[index];
    if (!d || d.fixo) return;
    atualizarDestinos(destinos.value.filter((_, i) => i !== index));
}

watch(
    () => props.orgaoCompetenteId,
    (id) => {
        if (props.modo !== MODO_DESPACHO || !id) return;
        const idx = destinos.value.findIndex((d) => d.fixo);
        if (idx >= 0 && Number(destinos.value[idx].secretaria_id) !== Number(id)) {
            patchDestino(idx, { secretaria_id: Number(id) });
        }
    }
);

watch(
    () => props.orgaoCompetenteId,
    (id) => {
        if (props.modo !== MODO_DESPACHO || !id) return;
        const idx = destinos.value.findIndex((d) => d.fixo);
        if (idx >= 0 && Number(destinos.value[idx].secretaria_id) !== Number(id)) {
            patchDestino(idx, { secretaria_id: Number(id) });
        }
    }
);

watch(
    () => props.modelValue,
    (lista) => {
        for (const d of lista || []) {
            if (d.secretaria_id) carregarUnidades(d.secretaria_id);
        }
    },
    { immediate: true, deep: true }
);

watch(
    () => [props.modo, props.orgaoCompetenteId, props.orgaoFixoId],
    () => {
        if (destinos.value.length) return;
        if (props.modo === MODO_DESPACHO && props.orgaoCompetenteId) {
            atualizarDestinos([
                novoDestino({ secretaria_id: Number(props.orgaoCompetenteId), fixo: true })
            ]);
        } else if (props.modo === MODO_ANDAMENTO) {
            atualizarDestinos([
                novoDestino({
                    secretaria_id: props.orgaoFixoId ? Number(props.orgaoFixoId) : null,
                    fixo: Boolean(props.orgaoFixoId)
                })
            ]);
        }
    },
    { immediate: true }
);
</script>

<template>
    <div class="flex flex-col gap-3">
        <!-- Andamento (C1/C2/C4): órgão fixo, setor simples — sem multiselect -->
        <template v-if="modo === MODO_ANDAMENTO">
            <div class="flex align-items-center justify-content-between gap-2 flex-wrap">
                <span class="font-semibold text-base">
                    <i class="pi pi-map-marker mr-2" aria-hidden="true" />
                    Secretaria e setor
                </span>
            </div>
            <div class="p-3 border-1 surface-border border-round-lg surface-50 flex flex-col gap-3">
                <div>
                    <label class="block mb-2 font-medium">Secretaria / órgão</label>
                    <p class="m-0 text-sm py-1 font-medium">{{ orgaoAndamentoLabel }}</p>
                    <small class="text-muted-color">Órgão da sua sessão — não editável no andamento.</small>
                </div>
                <div v-if="orgaoIdAndamento">
                    <label class="block mb-2 font-medium">Setor de destino (opcional)</label>
                    <Select
                        v-if="opcoesUnidades(orgaoIdAndamento).length"
                        v-model="setorAndamentoId"
                        :options="opcoesUnidades(orgaoIdAndamento)"
                        option-label="label"
                        option-value="id"
                        :placeholder="
                            carregandoOrgao[orgaoIdAndamento]
                                ? 'Carregando setores…'
                                : 'Selecione o setor'
                        "
                        show-clear
                        fluid
                        :loading="carregandoOrgao[orgaoIdAndamento]"
                    />
                    <small v-else-if="carregandoOrgao[orgaoIdAndamento]" class="text-muted-color">
                        Carregando setores…
                    </small>
                    <small v-else class="text-muted-color">
                        Nenhum setor cadastrado.
                        <router-link to="/gestao-setores" class="text-primary ml-1">Cadastrar setores</router-link>
                    </small>
                </div>
            </div>

            <!-- Tramitação transversal: órgãos integrados (secretaria líder — C1/C2) -->
            <template v-if="permitirIntegrados">
                <Divider />
                <div class="flex align-items-center justify-content-between gap-2 flex-wrap">
                    <span class="font-semibold text-sm">
                        <i class="pi pi-share-alt mr-2" aria-hidden="true" />
                        Órgãos integrados (tramitação transversal)
                    </span>
                    <small class="text-muted-color">Encaminhe a execução a outras secretarias</small>
                </div>

                <div
                    v-for="(destino, index) in destinosIntegrados"
                    :key="destino._key || `int-${index}`"
                    class="p-3 border-1 surface-border border-round-lg flex flex-col gap-3"
                >
                    <div class="flex align-items-center justify-content-between gap-2">
                        <Tag severity="warn" :value="`Órgão integrado ${index + 1}`" />
                        <Button
                            icon="pi pi-times"
                            severity="danger"
                            text
                            rounded
                            aria-label="Remover órgão integrado"
                            @click="removerIntegrado(destinos.indexOf(destino))"
                        />
                    </div>
                    <div class="grid grid-cols-12 gap-3">
                        <div class="col-span-12 md:col-span-6">
                            <label class="block mb-2 font-medium">Secretaria / órgão</label>
                            <Select
                                :model-value="destino.secretaria_id"
                                :options="opcoesOrgaoIntegrado(destino)"
                                option-label="nome"
                                option-value="id"
                                placeholder="Selecione a secretaria"
                                filter
                                filter-placeholder="Buscar órgão…"
                                fluid
                                @update:model-value="onOrgaoChange(destinos.indexOf(destino), $event)"
                            />
                        </div>
                        <div class="col-span-12 md:col-span-6">
                            <label class="block mb-2 font-medium">
                                Setor(es)
                                <span v-if="destinoExigeSetor(destino)" class="text-red-500">*</span>
                                <span class="font-normal text-muted-color">(um ou mais)</span>
                            </label>
                            <MultiSelect
                                v-if="destino.secretaria_id && opcoesUnidades(destino.secretaria_id).length"
                                :model-value="destino.unidade_administrativa_ids || []"
                                :options="opcoesUnidades(destino.secretaria_id)"
                                option-label="label"
                                option-value="id"
                                :placeholder="
                                    carregandoOrgao[destino.secretaria_id]
                                        ? 'Carregando setores…'
                                        : 'Selecione um ou mais setores'
                                "
                                :invalid="destinoSemSetorObrigatorio(destino)"
                                filter
                                display="chip"
                                fluid
                                :loading="carregandoOrgao[destino.secretaria_id]"
                                @update:model-value="onSetoresChange(destinos.indexOf(destino), $event)"
                            />
                            <small v-else-if="!destino.secretaria_id" class="text-muted-color">
                                Selecione o órgão para listar os setores.
                            </small>
                            <small v-else class="text-muted-color">Nenhum setor cadastrado para este órgão.</small>
                            <small
                                v-if="destinoSemSetorObrigatorio(destino)"
                                class="text-red-500 block mt-1"
                            >
                                Selecione ao menos um setor deste órgão.
                            </small>
                        </div>
                    </div>
                    <Message
                        v-for="(aviso, ai) in avisosDestinoOcupado(destino)"
                        :key="`ocupado-int-${index}-${ai}`"
                        severity="warn"
                        :closable="false"
                        class="m-0 text-sm"
                    >
                        <strong>{{ rotuloDestinoOcupado(aviso) }}</strong> já possui encaminhamento aberto
                        <span v-if="aviso.nos?.[0]?.origem_label"> ({{ aviso.nos[0].origem_label }})</span>.
                        <span v-if="aviso.nos?.[0]?.resumo_abertura" class="block mt-1">
                            “{{ aviso.nos[0].resumo_abertura }}”
                        </span>
                    </Message>
                </div>

                <Button
                    v-if="permitirIntegrados || modo === MODO_DESPACHO"
                    label="Adicionar órgão integrado"
                    icon="pi pi-plus"
                    severity="secondary"
                    outlined
                    size="small"
                    class="align-self-start"
                    :disabled="!podeAdicionarIntegrado"
                    @click="adicionarIntegrado"
                />

                <small
                    v-if="permitirIntegrados && !catalogoIntegraveisCarregado && !destinosIntegrados.length"
                    class="text-muted-color"
                >
                    Carregando lista de secretarias…
                </small>
                <small
                    v-else-if="permitirIntegrados && !podeAdicionarIntegrado && !destinosIntegrados.length"
                    class="text-muted-color"
                >
                    Nenhuma secretaria integrável disponível no momento (limite de órgãos ou catálogo vazio).
                </small>

                <Message
                    v-if="totalPernasIntegradas > 0"
                    :severity="totalPernasIntegradas > MAX_PERNAS_DESPACHO ? 'error' : 'info'"
                    :closable="false"
                    class="m-0 text-sm"
                >
                    Serão abertas <strong>{{ totalPernasIntegradas }}</strong>
                    {{ totalPernasIntegradas === 1 ? 'perna operacional' : 'pernas operacionais' }}
                    para órgãos integrados.
                </Message>
            </template>
        </template>

        <!-- Despacho: multi-órgão + multi-setor -->
        <template v-else>
        <div class="flex align-items-center justify-content-between gap-2 flex-wrap">
            <span class="font-semibold text-base">
                <i class="pi pi-map-marker mr-2" aria-hidden="true" />
                {{
                    contextoScatter
                        ? 'Encaminhar para secretaria(s) e setor(es)'
                        : 'Secretaria(s) e setor(es) de destino'
                }}
            </span>
            <small v-if="contextoScatter" class="text-muted-color">
                Selecione um ou mais órgãos e setores de destino
            </small>
        </div>

        <div
            v-for="(destino, index) in destinos"
            :key="destino._key || index"
            class="p-3 border-1 surface-border border-round-lg flex flex-col gap-3"
            :class="{ 'surface-50': destino.fixo }"
        >
            <div class="flex align-items-center justify-content-between gap-2">
                <Tag v-if="destino.fixo && modo === MODO_DESPACHO" severity="info" value="Órgão competente (carta)" />
                <Tag v-else-if="destino.fixo && modo === MODO_ANDAMENTO" severity="secondary" value="Seu órgão" />
                <Tag v-else severity="warn" :value="`Órgão integrado ${index}`" />
                <Button
                    v-if="!destino.fixo && modo === MODO_DESPACHO"
                    icon="pi pi-times"
                    severity="danger"
                    text
                    rounded
                    aria-label="Remover destino"
                    @click="removerIntegrado(index)"
                />
            </div>

            <div class="grid grid-cols-12 gap-3">
                <div class="col-span-12 md:col-span-6">
                    <label class="block mb-2 font-medium">Secretaria / órgão</label>
                    <template v-if="destino.fixo && (orgaoCompetenteNome || orgaoCompetenteId || orgaoFixoId)">
                        <p class="m-0 text-sm py-2">
                            {{
                                orgaoCompetenteNome ||
                                orgaos.find((o) => o.id === destino.secretaria_id)?.nome ||
                                `Órgão #${destino.secretaria_id}`
                            }}
                        </p>
                    </template>
            <template v-else-if="contextoScatter">
                <Select
                    :model-value="destino.secretaria_id"
                    :options="orgaos"
                    option-label="nome"
                    option-value="id"
                    placeholder="Selecione a secretaria / órgão"
                    filter
                    filter-placeholder="Buscar órgão…"
                    fluid
                    @update:model-value="onOrgaoChange(index, $event)"
                />
            </template>
            <Select
                v-else-if="modo === MODO_DESPACHO"
                        :model-value="destino.secretaria_id"
                        :options="opcoesOrgaoIntegrado(destino)"
                        option-label="nome"
                        option-value="id"
                        placeholder="Selecione a secretaria"
                        filter
                        filter-placeholder="Buscar órgão…"
                        fluid
                        @update:model-value="onOrgaoChange(index, $event)"
                    />
                    <Select
                        v-else-if="orgaosEditaveis"
                        :model-value="destino.secretaria_id"
                        :options="orgaos"
                        option-label="nome"
                        option-value="id"
                        placeholder="Selecione o órgão"
                        filter
                        fluid
                        @update:model-value="onOrgaoChange(index, $event)"
                    />
                    <p v-else class="m-0 text-sm text-muted-color py-2">
                        {{ orgaos.find((o) => o.id === destino.secretaria_id)?.nome || '—' }}
                    </p>
                </div>

                <div class="col-span-12 md:col-span-6">
                    <label class="block mb-2 font-medium">
                        Setor(es) — unidade administrativa
                        <span v-if="modo === MODO_DESPACHO && destinoExigeSetor(destino)" class="text-red-500">*</span>
                        <span v-if="modo === MODO_DESPACHO" class="font-normal text-muted-color">
                            (selecione um ou mais)
                        </span>
                    </label>
                    <MultiSelect
                        v-if="modo === MODO_DESPACHO && destino.secretaria_id && opcoesUnidades(destino.secretaria_id).length"
                        :model-value="destino.unidade_administrativa_ids || []"
                        :options="opcoesUnidades(destino.secretaria_id)"
                        option-label="label"
                        option-value="id"
                        :placeholder="
                            carregandoOrgao[destino.secretaria_id]
                                ? 'Carregando setores…'
                                : 'Selecione um ou mais setores'
                        "
                        :invalid="destinoSemSetorObrigatorio(destino)"
                        filter
                        filter-placeholder="Buscar setor…"
                        display="chip"
                        fluid
                        :loading="carregandoOrgao[destino.secretaria_id]"
                        @update:model-value="onSetoresChange(index, $event)"
                    />
                    <Select
                        v-else-if="modo === MODO_ANDAMENTO && destino.secretaria_id && opcoesUnidades(destino.secretaria_id).length"
                        :model-value="destino.unidade_administrativa_id"
                        :options="opcoesUnidades(destino.secretaria_id)"
                        option-label="label"
                        option-value="id"
                        :placeholder="
                            carregandoOrgao[destino.secretaria_id]
                                ? 'Carregando setores…'
                                : 'Selecione o setor (opcional)'
                        "
                        filter
                        show-clear
                        fluid
                        :loading="carregandoOrgao[destino.secretaria_id]"
                        @update:model-value="onSetorUnicoChange(index, $event)"
                    />
                    <small v-else-if="!destino.secretaria_id" class="text-muted-color">
                        Selecione o órgão para listar os setores.
                    </small>
                    <small v-else class="text-muted-color">
                        Nenhum setor cadastrado para este órgão.
                        <router-link to="/gestao-setores" class="text-primary ml-1">Cadastrar setores</router-link>
                    </small>
                    <small
                        v-if="destinoSemSetorObrigatorio(destino)"
                        class="text-red-500 block mt-1"
                    >
                        Selecione ao menos um setor deste órgão.
                    </small>
                </div>
            </div>
            <Message
                v-for="(aviso, ai) in avisosDestinoOcupado(destino)"
                :key="`ocupado-desp-${index}-${ai}`"
                severity="warn"
                :closable="false"
                class="m-0 text-sm"
            >
                <strong>{{ rotuloDestinoOcupado(aviso) }}</strong> já possui encaminhamento aberto
                <span v-if="aviso.nos?.[0]?.origem_label"> ({{ aviso.nos[0].origem_label }})</span>.
                <span v-if="aviso.nos?.[0]?.resumo_abertura" class="block mt-1">
                    “{{ aviso.nos[0].resumo_abertura }}”
                </span>
            </Message>
        </div>

        <Button
            v-if="podeAdicionarIntegrado"
            :label="contextoScatter ? 'Adicionar outro órgão' : 'Adicionar órgão integrado'"
            icon="pi pi-plus"
            severity="secondary"
            outlined
            size="small"
            class="align-self-start"
            @click="adicionarIntegrado"
        />

        <Message
            v-if="modo === MODO_DESPACHO && errosSetorObrigatorio.length"
            severity="error"
            :closable="false"
            class="m-0 text-sm"
        >
            {{ errosSetorObrigatorio[0].mensagem }}
        </Message>

        <Message
            v-if="modo === MODO_DESPACHO && totalPernas > 0"
            :severity="pernasExcedidas ? 'error' : 'info'"
            :closable="false"
            class="m-0 text-sm"
        >
            <template v-if="pernasExcedidas">
                Máximo de {{ MAX_PERNAS_DESPACHO }} pernas (órgão × setor). Reduza a seleção de setores.
            </template>
            <template v-else>
                Serão abertas <strong>{{ totalPernas }}</strong>
                {{ totalPernas === 1 ? 'perna operacional' : 'pernas operacionais' }}
                neste despacho (órgão × setor).
                Multi-órgão: o processo principal permanece no competente; integrados recebem
                desdobramento (até {{ MAX_INTEGRADOS_DESPACHO }} extras).
            </template>
        </Message>
        </template>
    </div>
</template>
