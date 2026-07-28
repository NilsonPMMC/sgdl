<script setup>
import { computed } from 'vue';
import Select from 'primevue/select';
import InputText from 'primevue/inputtext';
import Checkbox from 'primevue/checkbox';
import Message from 'primevue/message';
import Button from 'primevue/button';
import {
    OPCOES_MOTIVO_NAO_EXECUCAO,
    OPCOES_RESULTADO_OPERACIONAL,
    RESULTADO_SEM_EXECUCAO,
    resultadoPermiteStandBy
} from '@/constants/estudoViabilidade';

const model = defineModel({
    type: Object,
    required: true
});

const props = defineProps({
    enderecoSugerido: { type: String, default: '' }
});

const exigeMotivo = computed(
    () => model.value?.resultado_operacional === RESULTADO_SEM_EXECUCAO
);

const podeStandBy = computed(() => resultadoPermiteStandBy(model.value?.resultado_operacional));

function onResultadoChange() {
    if (!podeStandBy.value) {
        model.value.registrar_stand_by = false;
    }
    if (!exigeMotivo.value) {
        model.value.motivo_nao_execucao = null;
    }
}

function usarEnderecoComoEscopo() {
    const sugestao = (props.enderecoSugerido || '').trim();
    if (sugestao) {
        model.value.escopo_geografico = sugestao;
    }
}
</script>

<template>
    <div class="flex flex-col gap-3 border-t border-surface-200 pt-3">
        <p class="m-0 text-sm font-medium">Resultado operacional</p>
        <div class="flex flex-col gap-1">
            <label class="text-sm text-muted-color" for="resultado_operacional">Como este processo foi encerrado?</label>
            <Select
                id="resultado_operacional"
                v-model="model.resultado_operacional"
                :options="OPCOES_RESULTADO_OPERACIONAL"
                option-label="label"
                option-value="value"
                class="w-full"
                @change="onResultadoChange"
            />
        </div>
        <div v-if="exigeMotivo" class="flex flex-col gap-1">
            <label class="text-sm text-muted-color" for="motivo_nao_execucao">Motivo</label>
            <Select
                id="motivo_nao_execucao"
                v-model="model.motivo_nao_execucao"
                :options="OPCOES_MOTIVO_NAO_EXECUCAO"
                option-label="label"
                option-value="value"
                placeholder="Selecione o motivo"
                class="w-full"
            />
        </div>
        <div v-if="podeStandBy" class="flex flex-col gap-2">
            <div class="flex items-start gap-2">
                <Checkbox v-model="model.registrar_stand_by" binary inputId="registrar_stand_by" />
                <label for="registrar_stand_by" class="text-sm cursor-pointer">
                    Registrar na base stand-by de estudo e viabilidade
                </label>
            </div>
            <div v-if="model.registrar_stand_by" class="flex flex-col gap-1">
                <label class="text-sm text-muted-color" for="escopo_geografico">Escopo geográfico</label>
                <div class="flex gap-2">
                    <InputText
                        id="escopo_geografico"
                        v-model="model.escopo_geografico"
                        class="flex-1"
                        placeholder="Ex.: município inteiro, bairro X, trecho da Av. Y"
                    />
                    <Button
                        v-if="enderecoSugerido"
                        type="button"
                        label="Usar endereço"
                        size="small"
                        severity="secondary"
                        outlined
                        @click="usarEnderecoComoEscopo"
                    />
                </div>
            </div>
            <Message v-if="model.registrar_stand_by" severity="info" :closable="false" class="text-sm m-0">
                O processo segue para devolutiva ao vereador. A base stand-by fica visível para Protocolo,
                secretarias e gestores.
            </Message>
        </div>
    </div>
</template>
