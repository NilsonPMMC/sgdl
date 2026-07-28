<script setup>
import { onBeforeMount } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

onBeforeMount(() => {
    router.replace({ name: 'login-vereador' });
});
</script>

<template>
    <div class="min-h-screen flex items-center justify-center bg-surface-ground">
        <i class="pi pi-spin pi-spinner text-3xl text-primary" />
    </div>
</template>
