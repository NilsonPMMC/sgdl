<script setup>
import { onBeforeMount } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

onBeforeMount(() => {
    router.replace({ name: 'login' });
});
</script>

<template>
    <div class="min-h-screen flex items-center justify-center">
        <i class="pi pi-spin pi-spinner text-3xl text-primary" />
    </div>
</template>
