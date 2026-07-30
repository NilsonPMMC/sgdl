<script setup>
import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import Editor from 'primevue/editor';
import InputText from 'primevue/inputtext';
import MultiSelect from 'primevue/multiselect';
import Select from 'primevue/select';
import { computed, onMounted, ref, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import ApiService from '@/service/ApiService';
import PlaceholdersTextoPadraoChips from '@/components/tramitacao/PlaceholdersTextoPadraoChips.vue';
import {
    aplicarPlaceholdersTextoPadrao,
    inserirPlaceholderNoHtml
} from '@/constants/textoPadraoDespacho';

const props = defineProps({
    modelValue: { type: String, default: '' },
    label: { type: String, default: 'Descrição' },
    contexto: { type: String, default: 'andamento' },
    editorStyle: { type: String, default: 'min-height: 160px' },
    demandaContext: { type: Object, default: () => ({}) },
    demandaId: { type: [Number, String], default: null },
    exibirTextosPadrao: { type: Boolean, default: true },
    exibirPlaceholders: { type: Boolean, default: true }
});

const emit = defineEmits(['update:modelValue', 'modelo-aplicado']);

const toast = useToast();
const dialogIa = ref(false);
const dialogSalvarModelo = ref(false);
const carregandoIa = ref(false);
const carregandoModelos = ref(false);
const salvandoModelo = ref(false);
const textoOriginal = ref('');
const textoSugerido = ref('');
const modelos = ref([]);
const modeloSelecionado = ref(null);
const metaEscopo = ref(null);
const formModelo = ref({
    titulo: '',
    corpo: '',
    unidades_administrativas_ids: []
});

function patch(val) {
    emit('update:modelValue', val);
}

const categoriaPadrao = computed(() => metaEscopo.value?.categoria_padrao || 'OPERACIONAL');

const setoresOpcoes = computed(() =>
    (metaEscopo.value?.setores_disponiveis || []).map((s) => ({
        label: s.rotulo || s.sigla || s.nome,
        value: s.id
    }))
);

const exibirSelecaoSetores = computed(() => {
    const tipo = metaEscopo.value?.escopo?.escopo_tipo;
    if (tipo === 'GERAL') return false;
    return setoresOpcoes.value.length > 0;
});

const exigeSelecaoSetores = computed(
    () => Boolean(metaEscopo.value?.exige_selecao_setores) && exibirSelecaoSetores.value
);

const opcoesModelos = computed(() =>
    modelos.value.map((m) => ({
        label: m.titulo,
        value: m.id,
        escopo: m.escopo_resumo
    }))
);

function inserirPlaceholder(token) {
    patch(inserirPlaceholderNoHtml(props.modelValue, token));
    toast.add({
        severity: 'info',
        summary: 'Placeholder inserido',
        detail: token,
        life: 1500
    });
}

async function carregarModelos() {
    if (!props.exibirTextosPadrao) return;
    carregandoModelos.value = true;
    try {
        const { data } = await ApiService.listarTextosPadraoDespacho();
        modelos.value = Array.isArray(data) ? data : data?.results || [];
    } catch {
        modelos.value = [];
    } finally {
        carregandoModelos.value = false;
    }
}

async function carregarMeta() {
    try {
        const { data } = await ApiService.metaCriacaoTextoPadraoDespacho();
        metaEscopo.value = data;
    } catch {
        metaEscopo.value = null;
    }
}

function setoresPadraoForm() {
    const setores = metaEscopo.value?.setores_disponiveis || [];
    if (setores.length === 1) return [setores[0].id];
    return [];
}

async function aplicarModelo(id) {
    if (!id) return;
    const modelo = modelos.value.find((m) => m.id === id);
    if (!modelo) return;
    const ctx = { ...(props.demandaContext || {}) };
    try {
        let corpo = modelo.corpo;
        if (props.demandaId) {
            const { data } = await ApiService.aplicarTextoPadraoDespacho(id, {
                demanda_id: props.demandaId,
                contexto: ctx
            });
            corpo = data.corpo;
        } else {
            corpo = aplicarPlaceholdersTextoPadrao(corpo, ctx);
        }
        patch(corpo);
        emit('modelo-aplicado', { id, titulo: modelo.titulo });
        toast.add({
            severity: 'success',
            summary: 'Modelo aplicado',
            detail: modelo.titulo,
            life: 2500
        });
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro ao aplicar',
            detail: error?.response?.data?.detail || 'Não foi possível aplicar o modelo.',
            life: 4000
        });
    }
}

function onModeloChange(id) {
    if (id) aplicarModelo(id);
}

function abrirSalvarModelo() {
    const corpo = props.modelValue || '<p></p>';
    const textoLimpo = corpo.replace(/<[^>]+>/g, '').trim();
    if (!textoLimpo) {
        toast.add({
            severity: 'warn',
            summary: 'Texto vazio',
            detail: 'Escreva o texto antes de salvar como modelo.',
            life: 3000
        });
        return;
    }
    formModelo.value = {
        titulo: '',
        corpo,
        unidades_administrativas_ids: setoresPadraoForm()
    };
    dialogSalvarModelo.value = true;
}

async function salvarComoModelo() {
    if (!formModelo.value.titulo?.trim()) {
        toast.add({ severity: 'warn', summary: 'Informe um título', life: 2500 });
        return;
    }
    if (
        exigeSelecaoSetores.value &&
        !(formModelo.value.unidades_administrativas_ids || []).length
    ) {
        toast.add({
            severity: 'warn',
            summary: 'Selecione setor(es)',
            detail: 'Escolha para quais unidades o modelo ficará disponível.',
            life: 3500
        });
        return;
    }
    salvandoModelo.value = true;
    try {
        const payload = {
            titulo: formModelo.value.titulo.trim(),
            corpo: formModelo.value.corpo,
            categoria: categoriaPadrao.value
        };
        const ids = formModelo.value.unidades_administrativas_ids || [];
        if (ids.length) {
            payload.unidades_administrativas_ids = ids;
        }
        const { data } = await ApiService.criarTextoPadraoDespacho(payload);
        modelos.value = [data, ...modelos.value.filter((m) => m.id !== data.id)];
        modeloSelecionado.value = data.id;
        dialogSalvarModelo.value = false;
        toast.add({
            severity: 'success',
            summary: 'Modelo salvo',
            detail: 'Disponível para os setores selecionados.',
            life: 3500
        });
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro ao salvar',
            detail: error?.response?.data?.detail || 'Não foi possível salvar o modelo.',
            life: 4000
        });
    } finally {
        salvandoModelo.value = false;
    }
}

async function otimizarComIa() {
    const texto = (props.modelValue || '').replace(/<[^>]+>/g, ' ').trim();
    if (texto.length < 10) {
        toast.add({
            severity: 'warn',
            summary: 'Texto curto',
            detail: 'Escreva ao menos 10 caracteres antes de otimizar com IA.',
            life: 3500
        });
        return;
    }
    carregandoIa.value = true;
    textoOriginal.value = props.modelValue;
    try {
        const { data } = await ApiService.otimizarTextoTramitacao({
            texto: props.modelValue,
            contexto: props.contexto
        });
        textoSugerido.value = data.texto_otimizado || '';
        dialogIa.value = true;
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'IA indisponível',
            detail: error?.response?.data?.detail || 'Não foi possível otimizar o texto.',
            life: 4000
        });
    } finally {
        carregandoIa.value = false;
    }
}

function aceitarSugestao() {
    const sugestao = textoSugerido.value;
    const paragrafos = sugestao
        .split(/\n{2,}/)
        .map((p) => p.trim())
        .filter(Boolean)
        .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
        .join('');
    patch(paragrafos || `<p>${sugestao}</p>`);
    dialogIa.value = false;
    toast.add({ severity: 'success', summary: 'Texto atualizado', detail: 'Versão otimizada aplicada.', life: 2500 });
}

function manterOriginal() {
    dialogIa.value = false;
    toast.add({ severity: 'info', summary: 'Original mantido', life: 2000 });
}

onMounted(async () => {
    if (props.exibirTextosPadrao || props.exibirPlaceholders) {
        await carregarMeta();
    }
    if (props.exibirTextosPadrao) {
        await carregarModelos();
    }
});

watch(
    () => props.demandaId,
    () => {
        modeloSelecionado.value = null;
    }
);
</script>

<template>
    <div class="flex flex-col gap-2">
        <div class="flex align-items-center justify-content-between gap-2 flex-wrap">
            <label class="font-medium m-0">{{ label }}</label>
            <div class="flex align-items-center gap-2 flex-wrap">
                <Button
                    type="button"
                    label="Otimizar com IA"
                    icon="pi pi-sparkles"
                    size="small"
                    severity="help"
                    outlined
                    :loading="carregandoIa"
                    @click="otimizarComIa"
                />
            </div>
        </div>

        <div
            v-if="exibirTextosPadrao"
            class="flex flex-wrap align-items-end gap-2 p-3 surface-50 border-round border-1 surface-border"
        >
            <div class="flex flex-col gap-1 flex-1 min-w-0" style="min-width: 12rem">
                <span class="text-xs font-medium text-muted-color">Modelo padrão</span>
                <Select
                    v-model="modeloSelecionado"
                    :options="opcoesModelos"
                    option-label="label"
                    option-value="value"
                    placeholder="Escolher modelo existente…"
                    show-clear
                    filter
                    filter-placeholder="Buscar…"
                    class="w-full"
                    :loading="carregandoModelos"
                    :disabled="carregandoModelos && !opcoesModelos.length"
                    @update:model-value="onModeloChange"
                >
                    <template #option="{ option }">
                        <div class="flex flex-col">
                            <span>{{ option.label }}</span>
                            <span v-if="option.escopo" class="text-xs text-muted-color">{{ option.escopo }}</span>
                        </div>
                    </template>
                </Select>
            </div>
            <Button
                type="button"
                label="Salvar como modelo"
                icon="pi pi-bookmark"
                size="small"
                severity="secondary"
                outlined
                @click="abrirSalvarModelo"
            />
            <router-link to="/textos-padrao-despacho" class="text-sm no-underline">
                <Button type="button" label="Gerenciar" icon="pi pi-cog" size="small" text />
            </router-link>
        </div>

        <Editor :model-value="modelValue" :editor-style="editorStyle" @update:model-value="patch" />

        <PlaceholdersTextoPadraoChips v-if="exibirPlaceholders" @inserir="inserirPlaceholder" />
    </div>

    <Dialog
        v-model:visible="dialogSalvarModelo"
        header="Salvar como modelo"
        :modal="true"
        style="width: min(560px, 96vw)"
    >
        <p class="text-sm text-muted-color mt-0">
            Categoria: <strong>{{ categoriaPadrao === 'PROTOCOLO' ? 'Protocolo' : 'Operacional' }}</strong>
            — conforme seu perfil. O modelo ficará disponível para operadores do seu escopo.
        </p>
        <div class="flex flex-col gap-3">
            <div>
                <label class="font-medium text-sm block mb-1">Título do modelo</label>
                <InputText v-model="formModelo.titulo" class="w-full" maxlength="160" autofocus />
            </div>
            <div v-if="exibirSelecaoSetores">
                <label class="font-medium text-sm block mb-1">
                    Setor(es) de disponibilidade
                    <span v-if="exigeSelecaoSetores" class="text-red-500">*</span>
                </label>
                <MultiSelect
                    v-model="formModelo.unidades_administrativas_ids"
                    :options="setoresOpcoes"
                    option-label="label"
                    option-value="value"
                    placeholder="Selecione um ou mais setores"
                    display="chip"
                    class="w-full"
                    :max-selected-labels="4"
                />
                <p class="text-xs text-muted-color mt-1 mb-0">
                    O texto ficará visível apenas para operadores dos setores escolhidos.
                </p>
            </div>
        </div>
        <template #footer>
            <Button label="Cancelar" severity="secondary" text @click="dialogSalvarModelo = false" />
            <Button label="Salvar modelo" icon="pi pi-check" :loading="salvandoModelo" @click="salvarComoModelo" />
        </template>
    </Dialog>

    <Dialog
        v-model:visible="dialogIa"
        header="Revisar texto sugerido pela IA"
        :modal="true"
        style="width: min(640px, 96vw)"
    >
        <p class="text-sm text-muted-color mt-0">
            Compare a sugestão com o original. Você pode aceitar a otimização ou manter seu texto.
        </p>
        <div class="grid grid-cols-12 gap-3">
            <div class="col-span-12 md:col-span-6">
                <span class="font-medium text-sm block mb-2">Original</span>
                <div
                    class="p-3 border-1 surface-border border-round text-sm overflow-auto"
                    style="max-height: 220px"
                    v-html="textoOriginal"
                />
            </div>
            <div class="col-span-12 md:col-span-6">
                <span class="font-medium text-sm block mb-2">Sugestão IA</span>
                <div
                    class="p-3 border-1 border-primary border-round text-sm overflow-auto surface-ground"
                    style="max-height: 220px"
                >
                    {{ textoSugerido }}
                </div>
            </div>
        </div>
        <template #footer>
            <Button label="Manter original" icon="pi pi-undo" severity="secondary" text @click="manterOriginal" />
            <Button label="Usar sugestão" icon="pi pi-check" @click="aceitarSugestao" />
        </template>
    </Dialog>
</template>
