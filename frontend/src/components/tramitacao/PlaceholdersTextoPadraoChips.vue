<script setup>
import Chip from 'primevue/chip';
import { PLACEHOLDERS_TEXTO_PADRAO } from '@/constants/textoPadraoDespacho';

defineProps({
    compacto: { type: Boolean, default: false }
});

const emit = defineEmits(['inserir']);

function clicar(chave) {
    emit('inserir', `{{${chave}}}`);
}
</script>

<template>
    <div
        class="flex flex-col gap-1"
        :class="compacto ? '' : 'p-2 surface-ground border-round border-1 surface-border'"
    >
        <span class="text-xs font-medium text-muted-color">
            Placeholders — clique para inserir no texto
        </span>
        <div class="flex flex-wrap gap-1">
            <Chip
                v-for="p in PLACEHOLDERS_TEXTO_PADRAO"
                :key="p.chave"
                :label="`{{${p.chave}}}`"
                class="cursor-pointer text-xs"
                v-tooltip.top="p.rotulo"
                @click="clicar(p.chave)"
            />
        </div>
    </div>
</template>
