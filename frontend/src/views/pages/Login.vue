<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';

const router = useRouter();
const userStore = useUserStore();
const username = ref('');
const password = ref('');
const error = ref(null);

const handleLogin = async () => {
    try {
        await userStore.login(username.value, password.value);
        router.push('/'); // Redireciona para o Dashboard após o login
    } catch (err) {
        error.value = 'Usuário ou senha inválidos.';
    }
};
</script>

<template>
    <div class="surface-ground flex align-items-center justify-content-center min-h-screen min-w-screen overflow-hidden">
        <div class="flex flex-column align-items-center justify-content-center">
            <div style="border-radius: 56px; padding: 0.3rem; background: linear-gradient(180deg, var(--primary-color) 10%, rgba(33, 150, 243, 0) 30%)">
                <div class="w-full surface-card py-8 px-5 sm:px-8" style="border-radius: 53px">
                    <div class="text-center mb-5">
                        <div class="text-900 text-3xl font-medium mb-3">Login SGDL</div>
                    </div>

                    <form @submit.prevent="handleLogin">
                        <label for="username" class="block text-900 text-xl font-medium mb-2">Usuário</label>
                        <InputText id="username" v-model="username" type="text" class="w-full md:w-30rem mb-5" />

                        <label for="password" class="block text-900 text-xl font-medium mb-2">Senha</label>
                        <InputText id="password" v-model="password" type="password" class="w-full md:w-30rem mb-5" />
                        
                        <small v-if="error" class="p-error">{{ error }}</small>

                        <Button label="Entrar" class="w-full p-3 text-xl mt-4" type="submit"></Button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</template>