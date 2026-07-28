<script setup>
import Card from 'primevue/card';
import PainelAssinaturasPendentesGestor from '@/components/tramitacao/PainelAssinaturasPendentesGestor.vue';
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const validacaoQuery = computed(() => route.query.validacao_assinatura || null);
</script>

<template>
    <div class="grid">
        <div class="col-12">
            <Card>
                <template #title>Assinaturas pendentes de validação</template>
                <template #content>
                    <PainelAssinaturasPendentesGestor :auto-abrir-validacao-id="validacaoQuery" />
                </template>
            </Card>
        </div>
    </div>
</template>
