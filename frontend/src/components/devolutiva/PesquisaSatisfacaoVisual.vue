<script setup>
import Divider from 'primevue/divider';
import Message from 'primevue/message';
import Rating from 'primevue/rating';
import Textarea from 'primevue/textarea';
import { ref } from 'vue';

defineProps({
    readonly: { type: Boolean, default: false },
    encerrado: { type: Boolean, default: false }
});

const notaGeral = ref(null);
const notaAtendimento = ref(null);
const notaPrazo = ref(null);
const comentario = ref('');
</script>

<template>
    <div class="flex flex-col gap-4">
        <Message severity="secondary" :closable="false" class="text-sm m-0">
            Pesquisa de satisfação — visualização piloto. O registro oficial será habilitado após as
            rodadas de homologação do fluxo transversal.
        </Message>

        <div class="flex flex-col gap-2 p-3 surface-ground dark:bg-surface-800 border-round">
            <span class="text-sm font-medium">Como você avalia a conclusão deste processo?</span>
            <Rating v-model="notaGeral" :readonly="readonly || encerrado" :cancel="false" :stars="5" />
        </div>

        <div class="flex flex-col gap-2 p-3 surface-ground border-round">
            <span class="text-sm font-medium">Qualidade do atendimento pela secretaria executora</span>
            <Rating v-model="notaAtendimento" :readonly="readonly || encerrado" :cancel="false" :stars="5" />
        </div>

        <div class="flex flex-col gap-2 p-3 surface-ground border-round">
            <span class="text-sm font-medium">Cumprimento de prazo e retorno do Protocolo</span>
            <Rating v-model="notaPrazo" :readonly="readonly || encerrado" :cancel="false" :stars="5" />
        </div>

        <div>
            <label class="block mb-2 text-sm font-medium">Comentário (opcional)</label>
            <Textarea
                v-model="comentario"
                rows="3"
                class="w-full"
                :readonly="readonly || encerrado"
                placeholder="Sugestões ou observações sobre o atendimento..."
            />
        </div>

        <Divider />

    </div>
</template>
