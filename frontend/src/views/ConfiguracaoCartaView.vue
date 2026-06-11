<script setup>
import { onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import InputNumber from 'primevue/inputnumber';
import Message from 'primevue/message';
import Select from 'primevue/select';

const toast = useToast();

const carregando = ref(true);
const salvando = ref(false);

const opcoesPolitica = [
    {
        label: 'Serviço com fallback para padrão (recomendado)',
        value: 'SERVICO_COM_FALLBACK'
    },
    { label: 'Somente prazo do serviço', value: 'SERVICO' },
    { label: 'Sempre prazo padrão institucional', value: 'PADRAO' }
];

const form = ref({
    prazo_padrao_dias: 30,
    politica_prazo: 'SERVICO_COM_FALLBACK',
    politica_prazo_display: '',
    atualizado_em: null
});

const carregar = async () => {
    carregando.value = true;
    try {
        const { data } = await ApiService.getConfiguracaoCarta();
        form.value = { ...form.value, ...data };
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Configuração SLA',
            detail: error?.response?.data?.detail || 'Não foi possível carregar.',
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
};

const salvar = async () => {
    salvando.value = true;
    try {
        const { data } = await ApiService.updateConfiguracaoCarta({
            prazo_padrao_dias: form.value.prazo_padrao_dias,
            politica_prazo: form.value.politica_prazo
        });
        form.value = { ...form.value, ...data };
        toast.add({
            severity: 'success',
            summary: 'Salvo',
            detail: 'Política de prazo atualizada.',
            life: 3500
        });
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: error?.response?.data?.detail || 'Falha ao salvar.',
            life: 5000
        });
    } finally {
        salvando.value = false;
    }
};

onMounted(carregar);
</script>

<template>
    <div class="card flex flex-col gap-5 max-w-2xl">
        <div>
            <h5 class="m-0">SLA da Carta de Serviços</h5>
            <p class="text-sm text-muted-color m-0 mt-2">
                Define o prazo operacional padrão e como o sistema calcula o SLA das demandas
                (temporizador, atrasos e Explorer).
            </p>
        </div>

        <Message severity="info" :closable="false" class="text-sm">
            Ordem de leitura do prazo do serviço: carta otimizada → Sinapse → metadados
            enriquecidos. Com fallback ativo, serviços sem prazo usam o padrão abaixo.
        </Message>

        <div v-if="carregando" class="flex justify-center py-8">
            <i class="pi pi-spin pi-spinner text-2xl" />
        </div>

        <template v-else>
            <div>
                <label class="block mb-2 font-medium">Prazo padrão (dias)</label>
                <InputNumber
                    v-model="form.prazo_padrao_dias"
                    :min="1"
                    :max="365"
                    showButtons
                    class="w-full"
                />
            </div>

            <div>
                <label class="block mb-2 font-medium">Política de prazo</label>
                <Select
                    v-model="form.politica_prazo"
                    :options="opcoesPolitica"
                    optionLabel="label"
                    optionValue="value"
                    class="w-full"
                />
            </div>

            <div class="flex justify-end gap-2">
                <Button label="Recarregar" icon="pi pi-refresh" outlined @click="carregar" />
                <Button
                    label="Salvar"
                    icon="pi pi-save"
                    :loading="salvando"
                    @click="salvar"
                />
            </div>
        </template>
    </div>
</template>
