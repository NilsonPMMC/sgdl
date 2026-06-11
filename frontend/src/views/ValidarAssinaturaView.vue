<script setup>
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import ApiService from '@/service/ApiService';

import Card from 'primevue/card';
import Tag from 'primevue/tag';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';

const route = useRoute();
const loading = ref(true);
const resultado = ref(null);
const erro = ref('');

const formatarData = (iso) => {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString('pt-BR');
    } catch {
        return iso;
    }
};

onMounted(async () => {
    const codigo = route.params.codigo;
    if (!codigo) {
        erro.value = 'Código de validação não informado.';
        loading.value = false;
        return;
    }
    try {
        const { data } = await ApiService.validarAssinatura(codigo);
        resultado.value = data;
    } catch (e) {
        erro.value = e?.response?.data?.detail || 'Assinatura não encontrada.';
    } finally {
        loading.value = false;
    }
});
</script>

<template>
    <div class="min-h-screen flex items-center justify-center p-6 bg-[var(--surface-ground)]">
        <Card class="w-full max-w-lg">
            <template #title>Validação de assinatura eletrônica</template>
            <template #content>
                <div v-if="loading" class="flex justify-center py-8">
                    <ProgressSpinner style="width: 40px; height: 40px" />
                </div>
                <Message v-else-if="erro" severity="error" :closable="false">{{ erro }}</Message>
                <div v-else-if="resultado?.valido" class="flex flex-col gap-3 text-sm">
                    <Tag value="Assinatura válida" severity="success" class="w-fit" />
                    <p class="m-0"><strong>Ofício:</strong> {{ resultado.demanda_titulo }}</p>
                    <p class="m-0"><strong>Protocolo legislativo:</strong> {{ resultado.protocolo_legislativo || '—' }}</p>
                    <p class="m-0"><strong>Vereador:</strong> {{ resultado.vereador }}</p>
                    <p class="m-0"><strong>Assinado em:</strong> {{ formatarData(resultado.assinado_em) }}</p>
                    <p class="m-0 text-xs text-muted-color break-all">
                        Código: {{ resultado.codigo_validacao }}
                    </p>
                </div>
            </template>
        </Card>
    </div>
</template>
