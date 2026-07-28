<script setup>
import Checkbox from 'primevue/checkbox';
import Select from 'primevue/select';
import { computed } from 'vue';
import {
    DECLARACAO_DESPACHO,
    DECLARACAO_GESTOR_PROTOCOLO,
    MODO_PAINEL_ASSINATURA
} from '@/constants/assinaturaEletronica';
import { formatSignatarioLinha, gestorPorId } from '@/constants/assinaturaEletronica';

const props = defineProps({
    preview: { type: Object, default: null },
    gestores: { type: Array, default: () => [] },
    declaracaoOperador: { type: Boolean, default: false },
    declaracaoGestor: { type: Boolean, default: false },
    gestorProtocoloId: { type: [Number, String], default: null },
    declaracaoOperadorTexto: { type: String, default: DECLARACAO_DESPACHO },
    declaracaoGestorTexto: { type: String, default: DECLARACAO_GESTOR_PROTOCOLO },
    /** operador_apenas | dual_protocolo | gestor_apenas */
    modo: { type: String, default: MODO_PAINEL_ASSINATURA.DUAL_PROTOCOLO },
    rotuloGestor: { type: String, default: 'Gestor do protocolo' }
});

const emit = defineEmits([
    'update:declaracaoOperador',
    'update:declaracaoGestor',
    'update:gestorProtocoloId'
]);

const gestorSelecionado = computed(() => gestorPorId(props.gestores, props.gestorProtocoloId));

const visivel = computed(() => Boolean(props.preview?.hash_documento));

const exibirOperador = computed(
    () =>
        props.modo === MODO_PAINEL_ASSINATURA.OPERADOR_APENAS ||
        props.modo === MODO_PAINEL_ASSINATURA.DUAL_PROTOCOLO
);

const exibirGestorSelect = computed(() => props.modo === MODO_PAINEL_ASSINATURA.DUAL_PROTOCOLO);

const exibirGestorCheckbox = computed(
    () =>
        props.modo === MODO_PAINEL_ASSINATURA.DUAL_PROTOCOLO ||
        props.modo === MODO_PAINEL_ASSINATURA.GESTOR_APENAS
);

const signatarioOperador = computed(() => {
    if (props.modo === MODO_PAINEL_ASSINATURA.GESTOR_APENAS) {
        return props.preview?.signatario_gestor || props.preview?.signatario_operador;
    }
    return props.preview?.signatario_operador || props.preview?.signatario_chefia;
});

const rotuloSignatario = computed(() => {
    if (props.modo === MODO_PAINEL_ASSINATURA.GESTOR_APENAS) return props.rotuloGestor;
    return 'Operador';
});
</script>

<template>
    <template v-if="visivel">
        <p v-if="signatarioOperador" class="m-0 text-sm text-muted-color">
            <i class="pi pi-id-card mr-1" aria-hidden="true" />
            {{ rotuloSignatario }}:
            <strong>{{ formatSignatarioLinha(signatarioOperador) }}</strong>
        </p>
        <p class="text-xs text-muted-color break-all m-0">
            Hash: {{ preview.hash_documento?.slice(0, 16) }}…
        </p>

        <div v-if="exibirOperador" class="flex items-start gap-2">
            <Checkbox
                :model-value="declaracaoOperador"
                binary
                input-id="decl_tram_op"
                @update:model-value="emit('update:declaracaoOperador', $event)"
            />
            <label for="decl_tram_op" class="text-sm cursor-pointer">{{ declaracaoOperadorTexto }}</label>
        </div>

        <Select
            v-if="exibirGestorSelect"
            :model-value="gestorProtocoloId"
            :options="gestores"
            option-label="nome"
            option-value="id"
            placeholder="Gestor setorial do SGAC"
            fluid
            @update:model-value="emit('update:gestorProtocoloId', $event)"
        >
            <template #option="{ option }">
                <div class="flex flex-col py-0.5">
                    <span>{{ option.nome }}</span>
                    <small v-if="option.cargo" class="text-muted-color">{{ option.cargo }}</small>
                </div>
            </template>
        </Select>
        <p
            v-if="exibirGestorSelect && gestorSelecionado?.cargo"
            class="m-0 text-xs text-muted-color"
        >
            Gestor selecionado: {{ formatSignatarioLinha(gestorSelecionado) }}
        </p>

        <div v-if="exibirGestorCheckbox" class="flex items-start gap-2">
            <Checkbox
                :model-value="declaracaoGestor"
                binary
                input-id="decl_tram_gest"
                @update:model-value="emit('update:declaracaoGestor', $event)"
            />
            <label for="decl_tram_gest" class="text-sm cursor-pointer">{{ declaracaoGestorTexto }}</label>
        </div>
    </template>
</template>
