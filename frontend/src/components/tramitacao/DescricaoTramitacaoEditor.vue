<script setup>
import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import Editor from 'primevue/editor';
import ProgressSpinner from 'primevue/progressspinner';
import { ref } from 'vue';
import { useToast } from 'primevue/usetoast';
import ApiService from '@/service/ApiService';

const props = defineProps({
    modelValue: { type: String, default: '' },
    label: { type: String, default: 'Descrição' },
    contexto: { type: String, default: 'andamento' },
    editorStyle: { type: String, default: 'min-height: 160px' }
});

const emit = defineEmits(['update:modelValue']);

const toast = useToast();
const dialogIa = ref(false);
const carregandoIa = ref(false);
const textoOriginal = ref('');
const textoSugerido = ref('');

function patch(val) {
    emit('update:modelValue', val);
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
</script>

<template>
    <div class="flex flex-col gap-2">
        <div class="flex align-items-center justify-content-between gap-2 flex-wrap">
            <label class="font-medium m-0">{{ label }}</label>
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
        <Editor
            :model-value="modelValue"
            :editor-style="editorStyle"
            @update:model-value="patch"
        />
    </div>

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
