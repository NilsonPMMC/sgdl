<script setup>
import { onMounted } from 'vue';
import { useUserStore } from '@/stores/userStore';

const userStore = useUserStore();

// onMounted é o lugar perfeito para dizer que a store terminou de carregar do localStorage
onMounted(() => {
    userStore.finishLoading();
});
</script>

<template>
    <div v-if="userStore.loading" class="w-screen h-screen flex align-items-center justify-content-center">
        <i class="pi pi-spin pi-spinner" style="font-size: 3rem"></i>
    </div>
    <router-view />
</template>

<style scoped></style>
