<script setup>
import { computed } from 'vue';
import { useUserStore } from '@/stores/userStore';
import Message from 'primevue/message';

const userStore = useUserStore();

const alerta = computed(() => {
    const user = userStore.currentUser;
    if (!user || user.perfil !== 'SECRETARIA') return null;
    const atuacao = user.atuacao_sgdl;
    if (atuacao?.completa) return null;
    const vinculo = user.vinculo_secretaria;
    const avisos = vinculo?.avisos || [];
    const resumo = atuacao?.resumo;
    if (resumo && resumo !== 'Definir órgão › setor') {
        return `Atuação incompleta (${resumo}): ${avisos.join(' ') || 'falta órgão ou setor'}.`;
    }
    return avisos.join(' ') || 'Defina órgão (Sinapse) e setor (UA) para operar no SGDL.';
});
</script>

<template>
    <Message
        v-if="alerta"
        severity="warn"
        :closable="false"
        class="mx-4 mt-3 mb-0 text-sm"
    >
        {{ alerta }}
        Peça ao Protocolo ou Gestor para concluir em «Gestão de usuários» (Órgão › Setor).
        A fila «Meu setor» permanece indisponível até a atuação estar definida.
    </Message>
</template>
