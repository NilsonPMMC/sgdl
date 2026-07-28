<script setup>
import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import { computed, ref, watch } from 'vue';
import AssinaturaDespachoPanel from '@/components/tramitacao/AssinaturaDespachoPanel.vue';
import {
    DECLARACAO_DESPACHO,
    DECLARACAO_GESTOR_PROTOCOLO,
    MODO_PAINEL_ASSINATURA,
    mensagemErroAssinatura,
    payloadAssinaturaProtocolo,
    validarAssinaturaFormulario
} from '@/constants/assinaturaEletronica';

const props = defineProps({
    visible: { type: Boolean, default: false },
    titulo: { type: String, default: 'Assinatura eletrônica' },
    preview: { type: Object, default: null },
    gestores: { type: Array, default: () => [] },
    modo: { type: String, default: MODO_PAINEL_ASSINATURA.OPERADOR_APENAS },
    declaracaoOperadorTexto: { type: String, default: DECLARACAO_DESPACHO },
    declaracaoGestorTexto: { type: String, default: DECLARACAO_GESTOR_PROTOCOLO },
    labelConfirmar: { type: String, default: 'Assinar e confirmar' },
    loading: { type: Boolean, default: false },
    loadingPreview: { type: Boolean, default: false },
    mensagemIntro: { type: String, default: '' }
});

const emit = defineEmits(['update:visible', 'confirmar', 'cancelar', 'gerar-preview']);

const declaracaoOperador = ref(false);
const declaracaoGestor = ref(false);
const gestorProtocoloId = ref(null);
const erroLocal = ref('');

const hashDocumento = computed(() => props.preview?.hash_documento || '');

const podeConfirmar = computed(() => {
    if (props.loading || props.loadingPreview) return false;
    if (!hashDocumento.value) return false;
    const erros = validarAssinaturaFormulario(
        props.modo,
        {
            hash_documento: hashDocumento.value,
            declaracaoOperador: declaracaoOperador.value,
            declaracaoGestor: declaracaoGestor.value,
            gestor_protocolo_id: gestorProtocoloId.value
        },
        props.gestores
    );
    return erros.length === 0;
});

watch(
    () => props.visible,
    (aberto) => {
        if (aberto) {
            declaracaoOperador.value = false;
            declaracaoGestor.value = false;
            gestorProtocoloId.value = props.gestores?.[0]?.id ?? null;
            erroLocal.value = '';
        }
    }
);

watch(
    () => props.preview,
    (p) => {
        if (p?.signatario_gestor && props.modo === MODO_PAINEL_ASSINATURA.GESTOR_APENAS) {
            gestorProtocoloId.value = p.signatario_gestor.id;
        }
    }
);

function fechar() {
    emit('update:visible', false);
    emit('cancelar');
}

function confirmar() {
    const erros = validarAssinaturaFormulario(
        props.modo,
        {
            hash_documento: hashDocumento.value,
            declaracaoOperador: declaracaoOperador.value,
            declaracaoGestor: declaracaoGestor.value,
            gestor_protocolo_id: gestorProtocoloId.value
        },
        props.gestores
    );
    if (erros.length) {
        erroLocal.value = mensagemErroAssinatura(erros);
        return;
    }
    erroLocal.value = '';
    const payload = payloadAssinaturaProtocolo(
        props.modo,
        {
            declaracaoOperador: declaracaoOperador.value,
            declaracaoGestor: declaracaoGestor.value,
            gestor_protocolo_id: gestorProtocoloId.value
        },
        hashDocumento.value,
        {
            declaracaoOperadorText: props.declaracaoOperadorTexto,
            declaracaoGestorText: props.declaracaoGestorTexto
        }
    );
    emit('confirmar', payload);
}
</script>

<template>
    <Dialog
        :visible="visible"
        :header="titulo"
        :modal="true"
        :closable="!loading"
        style="width: min(560px, 96vw)"
        @update:visible="(v) => !v && fechar()"
    >
        <div class="flex flex-col gap-3">
            <p v-if="mensagemIntro" class="m-0 text-sm">{{ mensagemIntro }}</p>

            <div v-if="loadingPreview" class="flex justify-center py-4">
                <ProgressSpinner style="width: 36px; height: 36px" />
            </div>

            <template v-else>
                <Message v-if="!hashDocumento" severity="warn" :closable="false" class="m-0">
                    Gere a prévia de assinatura antes de confirmar.
                </Message>

                <AssinaturaDespachoPanel
                    :preview="preview"
                    :gestores="gestores"
                    :modo="modo"
                    :declaracao-operador="declaracaoOperador"
                    :declaracao-gestor="declaracaoGestor"
                    :gestor-protocolo-id="gestorProtocoloId"
                    :declaracao-operador-texto="declaracaoOperadorTexto"
                    :declaracao-gestor-texto="declaracaoGestorTexto"
                    @update:declaracao-operador="declaracaoOperador = $event"
                    @update:declaracao-gestor="declaracaoGestor = $event"
                    @update:gestor-protocolo-id="gestorProtocoloId = $event"
                />

                <Message v-if="erroLocal" severity="error" :closable="false" class="m-0">
                    {{ erroLocal }}
                </Message>
            </template>
        </div>

        <template #footer>
            <Button
                label="Cancelar"
                icon="pi pi-times"
                severity="secondary"
                text
                :disabled="loading"
                @click="fechar"
            />
            <Button
                v-if="!hashDocumento && !loadingPreview"
                label="Gerar prévia"
                icon="pi pi-refresh"
                severity="secondary"
                :loading="loadingPreview"
                @click="emit('gerar-preview')"
            />
            <Button
                :label="labelConfirmar"
                icon="pi pi-check"
                :loading="loading"
                :disabled="!podeConfirmar"
                @click="confirmar"
            />
        </template>
    </Dialog>
</template>
