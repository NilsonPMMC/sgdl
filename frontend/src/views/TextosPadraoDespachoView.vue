<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import ApiService from '@/service/ApiService';
import {
    CATEGORIAS_TEXTO_PADRAO,
    PLACEHOLDERS_TEXTO_PADRAO,
    inserirPlaceholderNoHtml,
    rotuloCategoriaTextoPadrao
} from '@/constants/textoPadraoDespacho';
import PlaceholdersTextoPadraoChips from '@/components/tramitacao/PlaceholdersTextoPadraoChips.vue';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import Editor from 'primevue/editor';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import MultiSelect from 'primevue/multiselect';
import Select from 'primevue/select';
import Tag from 'primevue/tag';

const toast = useToast();

const loading = ref(false);
const salvando = ref(false);
const modelos = ref([]);
const metaEscopo = ref(null);
const dialogEditor = ref(false);
const dialogPreview = ref(false);
const modeloEdicao = ref(null);
const previewCorpo = ref('');

const filtroCategoria = ref(null);

const extrairErro = (error) => error?.response?.data?.detail || 'Operação não concluída.';

const loadModelos = async () => {
    loading.value = true;
    try {
        const params = { todos: 1 };
        if (filtroCategoria.value) params.categoria = filtroCategoria.value;
        const { data } = await ApiService.listarTextosPadraoDespacho(params);
        modelos.value = Array.isArray(data) ? data : data?.results || [];
    } catch (error) {
        modelos.value = [];
        toast.add({ severity: 'error', summary: 'Modelos', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const loadMeta = async () => {
    try {
        const { data } = await ApiService.metaCriacaoTextoPadraoDespacho();
        metaEscopo.value = data;
    } catch {
        metaEscopo.value = null;
    }
};

const novoModelo = () => {
    const setores = metaEscopo.value?.setores_disponiveis || [];
    modeloEdicao.value = {
        id: null,
        titulo: '',
        categoria: metaEscopo.value?.categoria_padrao || 'OPERACIONAL',
        corpo: '<p></p>',
        ordem: 0,
        ativo: true,
        unidades_administrativas_ids: setores.length === 1 ? [setores[0].id] : []
    };
    dialogEditor.value = true;
};

const editarModelo = (row) => {
    const ids = (row.unidades_administrativas_ids || row.unidades_resumo || []).map((u) =>
        typeof u === 'object' ? u.id : u
    );
    modeloEdicao.value = {
        ...row,
        unidades_administrativas_ids: ids
    };
    dialogEditor.value = true;
};

const salvarModelo = async () => {
    if (!modeloEdicao.value?.titulo?.trim()) {
        toast.add({ severity: 'warn', summary: 'Título obrigatório', life: 2500 });
        return;
    }
    const corpoLimpo = (modeloEdicao.value.corpo || '').replace(/<[^>]+>/g, '').trim();
    if (!corpoLimpo) {
        toast.add({ severity: 'warn', summary: 'Corpo obrigatório', detail: 'Escreva o texto do modelo.', life: 3000 });
        return;
    }
    if (
        exigeSelecaoSetores.value &&
        !(modeloEdicao.value.unidades_administrativas_ids || []).length
    ) {
        toast.add({
            severity: 'warn',
            summary: 'Selecione setor(es)',
            detail: 'Escolha para quais unidades o modelo ficará disponível.',
            life: 3500
        });
        return;
    }
    salvando.value = true;
    try {
        const payload = {
            titulo: modeloEdicao.value.titulo.trim(),
            categoria: modeloEdicao.value.categoria,
            corpo: modeloEdicao.value.corpo,
            ordem: modeloEdicao.value.ordem ?? 0,
            ativo: modeloEdicao.value.ativo !== false
        };
        const ids = modeloEdicao.value.unidades_administrativas_ids || [];
        if (ids.length) {
            payload.unidades_administrativas_ids = ids;
        }
        if (modeloEdicao.value.id) {
            const { data } = await ApiService.atualizarTextoPadraoDespacho(modeloEdicao.value.id, payload);
            const idx = modelos.value.findIndex((m) => m.id === data.id);
            if (idx >= 0) modelos.value[idx] = data;
            toast.add({ severity: 'success', summary: 'Modelo atualizado', detail: data.titulo, life: 2500 });
        } else {
            const { data } = await ApiService.criarTextoPadraoDespacho(payload);
            modelos.value.unshift(data);
            toast.add({ severity: 'success', summary: 'Modelo criado', detail: data.titulo, life: 2500 });
        }
        dialogEditor.value = false;
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvando.value = false;
    }
};

const excluirModelo = async (row) => {
    if (!row.pode_editar) return;
    salvando.value = true;
    try {
        await ApiService.excluirTextoPadraoDespacho(row.id);
        row.ativo = false;
        modelos.value = modelos.value.filter((m) => m.id !== row.id || m.ativo);
        toast.add({ severity: 'success', summary: 'Modelo desativado', detail: row.titulo, life: 2500 });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvando.value = false;
    }
};

const previewModelo = (row) => {
    previewCorpo.value = row.corpo || '';
    dialogPreview.value = true;
};

function inserirPlaceholder(token) {
    if (!modeloEdicao.value) return;
    modeloEdicao.value.corpo = inserirPlaceholderNoHtml(modeloEdicao.value.corpo, token);
    toast.add({
        severity: 'info',
        summary: 'Placeholder inserido',
        detail: token,
        life: 1500
    });
}

const escopoResumo = computed(() => metaEscopo.value?.escopo?.escopo_tipo || '—');

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

const exibirSeletorCategoria = computed(
    () => (metaEscopo.value?.categorias_disponiveis || []).length > 1
);

const categoriasFormulario = computed(() => {
    const ids = metaEscopo.value?.categorias_disponiveis || ['OPERACIONAL'];
    return CATEGORIAS_TEXTO_PADRAO.filter((c) => ids.includes(c.value));
});

onMounted(async () => {
    await Promise.all([loadMeta(), loadModelos()]);
});

watch(filtroCategoria, loadModelos);
</script>

<template>
    <div class="flex flex-col gap-6">
        <div class="flex flex-wrap align-items-start justify-content-between gap-3">
            <div>
                <h2 class="text-2xl font-semibold m-0">Textos padrão de despacho</h2>
                <p class="text-surface-600 mt-1 mb-0 text-sm">
                    Modelos reutilizáveis com formatação rica para despachos e andamentos.
                    O escopo de uso é definido automaticamente pelo seu perfil.
                </p>
            </div>
            <Button label="Novo modelo" icon="pi pi-plus" @click="novoModelo" />
        </div>

        <Message severity="info" :closable="false" class="text-sm m-0">
            Dois tipos de modelo: <strong>Protocolo</strong> (despacho inicial e final) e
            <strong>Operacional</strong> (tramitações da secretaria/setores). Seu perfil define
            qual família você gerencia. Use placeholders como
            <code v-pre>{{protocolo_executivo}}</code> no texto.
        </Message>

        <Card>
            <template #content>
                <div class="flex flex-wrap gap-3 mb-3 align-items-end">
                    <div class="flex flex-col gap-1">
                        <label class="text-sm font-medium">Filtrar categoria</label>
                        <Select
                            v-model="filtroCategoria"
                            :options="[{ label: 'Todas do meu perfil', value: null }, ...categoriasFormulario]"
                            option-label="label"
                            option-value="value"
                            placeholder="Todas do meu perfil"
                            class="w-14rem"
                            show-clear
                        />
                    </div>
                </div>

                <DataTable
                    :value="modelos.filter((m) => m.ativo !== false)"
                    :loading="loading"
                    striped-rows
                    size="small"
                    paginator
                    :rows="15"
                    responsive-layout="scroll"
                    class="sgdl-table-scroll"
                >
                    <Column field="titulo" header="Título" style="min-width: 12rem" />
                    <Column header="Categoria" style="width: 9rem">
                        <template #body="{ data }">
                            <Tag
                                :value="
                                    CATEGORIAS_TEXTO_PADRAO.find((c) => c.value === data.categoria)?.label ||
                                    data.categoria
                                "
                                severity="secondary"
                            />
                        </template>
                    </Column>
                    <Column field="escopo_resumo" header="Escopo" style="min-width: 10rem" />
                    <Column field="criado_por_nome" header="Autor" style="width: 8rem" />
                    <Column header="" style="width: 10rem">
                        <template #body="{ data }">
                            <div class="flex gap-1 flex-wrap">
                                <Button
                                    icon="pi pi-eye"
                                    size="small"
                                    text
                                    rounded
                                    v-tooltip.top="'Visualizar'"
                                    @click="previewModelo(data)"
                                />
                                <Button
                                    v-if="data.pode_editar"
                                    icon="pi pi-pencil"
                                    size="small"
                                    text
                                    rounded
                                    v-tooltip.top="'Editar'"
                                    @click="editarModelo(data)"
                                />
                                <Button
                                    v-if="data.pode_editar"
                                    icon="pi pi-trash"
                                    size="small"
                                    text
                                    rounded
                                    severity="danger"
                                    v-tooltip.top="'Desativar'"
                                    @click="excluirModelo(data)"
                                />
                            </div>
                        </template>
                    </Column>
                </DataTable>
            </template>
        </Card>

        <Card>
            <template #title>Placeholders disponíveis</template>
            <template #content>
                <div class="flex flex-wrap gap-2">
                    <Tag
                        v-for="p in PLACEHOLDERS_TEXTO_PADRAO"
                        :key="p.chave"
                        :value="`{{${p.chave}}}`"
                        severity="info"
                        v-tooltip.top="p.rotulo"
                    />
                </div>
            </template>
        </Card>
    </div>

    <Dialog
        v-model:visible="dialogEditor"
        :header="modeloEdicao?.id ? 'Editar modelo' : 'Novo modelo'"
        :modal="true"
        style="width: min(720px, 96vw)"
    >
        <div v-if="modeloEdicao" class="flex flex-col gap-3">
            <div>
                <label class="font-medium text-sm block mb-1">Título</label>
                <InputText v-model="modeloEdicao.titulo" class="w-full" maxlength="160" />
            </div>
            <div class="grid grid-cols-12 gap-3">
                <div v-if="exibirSeletorCategoria" class="col-span-12 md:col-span-6">
                    <label class="font-medium text-sm block mb-1">Família</label>
                    <Select
                        v-model="modeloEdicao.categoria"
                        :options="categoriasFormulario"
                        option-label="label"
                        option-value="value"
                        class="w-full"
                    />
                </div>
                <div v-else class="col-span-12 md:col-span-6">
                    <label class="font-medium text-sm block mb-1">Família</label>
                    <Tag
                        :value="rotuloCategoriaTextoPadrao(modeloEdicao.categoria)"
                        severity="secondary"
                        class="w-full justify-content-start"
                    />
                </div>
                <div v-if="exibirSelecaoSetores" class="col-span-12">
                    <label class="font-medium text-sm block mb-1">
                        Setor(es) de disponibilidade
                        <span v-if="exigeSelecaoSetores" class="text-red-500">*</span>
                    </label>
                    <MultiSelect
                        v-model="modeloEdicao.unidades_administrativas_ids"
                        :options="setoresOpcoes"
                        option-label="label"
                        option-value="value"
                        placeholder="Selecione um ou mais setores"
                        display="chip"
                        class="w-full"
                        :max-selected-labels="4"
                    />
                </div>
            </div>
            <div>
                <label class="font-medium text-sm block mb-1">Texto do modelo</label>
                <Editor v-model="modeloEdicao.corpo" editor-style="min-height: 200px" />
                <PlaceholdersTextoPadraoChips class="mt-2" @inserir="inserirPlaceholder" />
            </div>
        </div>
        <template #footer>
            <Button label="Cancelar" severity="secondary" text @click="dialogEditor = false" />
            <Button label="Salvar" icon="pi pi-check" :loading="salvando" @click="salvarModelo" />
        </template>
    </Dialog>

    <Dialog v-model:visible="dialogPreview" header="Pré-visualização" :modal="true" style="width: min(640px, 96vw)">
        <div class="prose prose-sm max-w-none border-1 surface-border border-round p-3" v-html="previewCorpo" />
        <template #footer>
            <Button label="Fechar" @click="dialogPreview = false" />
        </template>
    </Dialog>
</template>
