<script setup>
import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import Tag from 'primevue/tag';
import Message from 'primevue/message';
import { formatarProtocoloLegislativo } from '@/utils/protocoloLegislativo';

defineProps({
    visible: { type: Boolean, default: false },
    demanda: { type: Object, default: null },
    situacao: { type: Object, default: null },
    carregando: { type: Boolean, default: false }
});

const emit = defineEmits(['update:visible', 'aderir', 'desvincular', 'cancelar']);

function fechar() {
    emit('update:visible', false);
    emit('cancelar');
}
</script>

<template>
    <Dialog
        :visible="visible"
        header="Demanda em cluster — decisão do Protocolo"
        :modal="true"
        :closable="!carregando"
        style="width: min(560px, 96vw)"
        @update:visible="(v) => !v && fechar()"
    >
        <div v-if="demanda && situacao?.lider" class="flex flex-col gap-4">
            <p class="m-0 text-sm">
                A demanda
                <strong>{{ formatarProtocoloLegislativo(demanda.protocolo_legislativo) || `#${demanda.id}` }}</strong>
                está vinculada a um cluster cujo processo líder já foi despachado.
            </p>

            <div class="p-3 surface-50 border-round flex flex-col gap-2">
                <div class="flex flex-wrap items-center gap-2">
                    <span class="font-medium text-sm">Processo líder</span>
                    <Tag
                        :value="situacao.lider.status_display || situacao.lider.status"
                        severity="success"
                    />
                </div>
                <div class="text-sm text-muted-color">
                    <div>
                        Ofício:
                        <strong>{{ formatarProtocoloLegislativo(situacao.lider.protocolo_legislativo) || `#${situacao.lider.id}` }}</strong>
                    </div>
                    <div v-if="situacao.lider.protocolo_executivo">
                        Protocolo executivo:
                        <strong>{{ situacao.lider.protocolo_executivo }}</strong>
                    </div>
                    <div v-if="situacao.lider.autor_nome">Vereador: {{ situacao.lider.autor_nome }}</div>
                </div>
            </div>

            <Message severity="info" :closable="false" class="m-0 text-sm">
                <strong>Integrar ao líder:</strong> espelha protocolo executivo, tramitações operacionais,
                pernas e nós — a demanda segue o mesmo fluxo sem novo despacho individual.
            </Message>

            <Message severity="warn" :closable="false" class="m-0 text-sm">
                <strong>Despachar individualmente:</strong> remove a demanda do cluster e abre o formulário
                de despacho unitário habitual.
            </Message>
        </div>

        <template #footer>
            <Button label="Cancelar" icon="pi pi-times" text :disabled="carregando" @click="fechar" />
            <Button
                label="Despachar individualmente"
                icon="pi pi-unlink"
                severity="warn"
                outlined
                :loading="carregando"
                @click="emit('desvincular')"
            />
            <Button
                label="Integrar ao processo líder"
                icon="pi pi-link"
                :loading="carregando"
                @click="emit('aderir')"
            />
        </template>
    </Dialog>
</template>
