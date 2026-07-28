<script setup>
import Button from 'primevue/button';
import Checkbox from 'primevue/checkbox';
import Dialog from 'primevue/dialog';
import { ref, watch, computed } from 'vue';
import { REGRAS_ASSINATURA } from '@/constants/tramitacaoFormulario';

const props = defineProps({
    visible: { type: Boolean, default: false },
    titulo: { type: String, default: 'Confirmar envio' },
    mensagem: { type: String, default: '' },
    resumoDestinos: { type: Array, default: () => [] },
    modo: { type: String, default: 'andamento' },
    assinarNoFormulario: { type: Boolean, default: false },
    mostrarAssinatura: { type: Boolean, default: true },
    /** Sobrescreve REGRAS_ASSINATURA[modo] — ex.: scatter encerrar obrigatório. */
    regrasAssinatura: { type: Object, default: null },
    labelConfirmar: { type: String, default: 'Confirmar envio' }
});

const emit = defineEmits(['update:visible', 'confirmar', 'cancelar']);

const assinarConfirmacao = ref(false);

const regras = computed(() => props.regrasAssinatura || REGRAS_ASSINATURA[props.modo] || {});

watch(
    () => props.visible,
    (v) => {
        if (v) {
            assinarConfirmacao.value = props.assinarNoFormulario;
        }
    }
);

function fechar() {
    emit('update:visible', false);
    emit('cancelar');
}

function confirmar() {
    emit('confirmar', {
        assinar_eletronicamente: assinarConfirmacao.value
    });
    emit('update:visible', false);
}
</script>

<template>
    <Dialog
        :visible="visible"
        :header="titulo"
        :modal="true"
        :closable="true"
        style="width: min(520px, 96vw)"
        @update:visible="(v) => !v && fechar()"
    >
        <div class="flex flex-col gap-3">
            <p class="m-0 text-sm">{{ mensagem }}</p>

            <ul v-if="resumoDestinos.length" class="m-0 pl-4 text-sm">
                <li v-for="(linha, i) in resumoDestinos" :key="i">{{ linha }}</li>
            </ul>

            <div
                v-if="mostrarAssinatura && regras.perguntaConfirmacao !== false && (regras.opcionalCheckbox || regras.obrigatoria)"
                class="flex items-start gap-2 p-3 surface-50 border-round"
            >
                <Checkbox v-model="assinarConfirmacao" binary input-id="assinar_confirm" />
                <label for="assinar_confirm" class="text-sm cursor-pointer leading-normal">
                    <span class="font-medium">Assinar eletronicamente</span>
                    <span class="text-muted-color block text-xs mt-1">
                        {{
                            assinarNoFormulario
                                ? 'Confirmado no formulário — você pode desmarcar aqui se preferir.'
                                : 'Opcional neste tipo de tramitação. Marque para incluir assinatura eletrônica.'
                        }}
                    </span>
                </label>
            </div>
        </div>
        <template #footer>
            <Button label="Revisar" icon="pi pi-pencil" severity="secondary" text @click="fechar" />
            <Button :label="labelConfirmar" icon="pi pi-send" @click="confirmar" />
        </template>
    </Dialog>
</template>
