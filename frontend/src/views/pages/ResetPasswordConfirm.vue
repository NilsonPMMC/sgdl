<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import ApiService from '@/service/ApiService';
import Button from 'primevue/button';
import Password from 'primevue/password';
import Message from 'primevue/message';

// Recebe 'uidb64' e 'token' da URL como props
const props = defineProps({
    uidb64: String,
    token: String
});

const router = useRouter();

const password = ref('');
const passwordConfirm = ref('');
const error = ref(null);
const success = ref(false);
const loading = ref(false);

const handleResetConfirm = async () => {
    error.value = null;
    success.value = false;

    // 1. Validação do frontend
    if (!password.value || !passwordConfirm.value) {
        error.value = 'Por favor, preencha ambos os campos.';
        return;
    }
    if (password.value !== passwordConfirm.value) {
        error.value = 'As senhas não coincidem.';
        return;
    }

    loading.value = true;

    try {
        // 2. Envia para a API
        await ApiService.confirmPasswordReset({
            uidb64: props.uidb64,
            token: props.token,
            new_password: password.value
        });
        
        // 3. Sucesso
        success.value = true;
        // Redireciona para o login após 3 segundos
        setTimeout(() => {
            router.push('/login');
        }, 3000);

    } catch (err) {
        // 4. Erro (ex: link expirado)
        error.value = err.response?.data?.error || 'Não foi possível redefinir a senha. O link pode ter expirado.';
    } finally {
        loading.value = false;
    }
};
</script>

<template>
    <div class="grid grid-cols-12 min-h-screen overflow-hidden">
        
        <div id="col-saudacao" class="flex flex-col col-span-6 items-center justify-center text-white p-8">
            <img src="/layout/images/brasao_nome_pmmc.png" alt="Brasão PMMC" style="width: 300px" class="mb-5" />
            <h1 class="text-6xl font-bold mb-3">Quase lá!</h1>
            <p class="text-xl text-center">Defina sua nova senha de acesso.</p>
        </div>

        <div class="flex col-span-6 items-center justify-center p-8">
            <div class="card" style="width: 30rem">

                <div v-if="!success">
                    <h2 class="text-900 text-3xl font-medium mb-4 text-center">Redefinir Senha</h2>
                    
                    <form @submit.prevent="handleResetConfirm">
                        <div class="flex flex-col gap-4">
                            <div>
                                <label for="password" class="block mb-2">Nova Senha</label>
                                <Password 
                                    id="password" 
                                    v-model="password" 
                                    placeholder="Digite a nova senha"
                                    :feedback="true" 
                                    toggleMask 
                                    fluid
                                />
                            </div>
                            <div>
                                <label for="passwordConfirm" class="block mb-2">Confirmar Nova Senha</label>
                                <Password 
                                    id="passwordConfirm" 
                                    v-model="passwordConfirm" 
                                    placeholder="Confirme a nova senha"
                                    :feedback="false" 
                                    toggleMask 
                                    fluid
                                    :invalid="!!error"
                                />
                            </div>
                        </div>

                        <Message v-if="error" severity="error" :closable="false" class="mt-4">{{ error }}</Message>

                        <Button 
                            label="Salvar Nova Senha" 
                            class="w-full p-3 text-xl mt-5" 
                            type="submit"
                            :loading="loading"
                        />
                    </form>
                </div>

                <div v-else>
                     <div class="flex flex-col items-center text-center">
                        <i class="pi pi-check-circle text-8xl text-green-500 mb-4"></i>
                        <h2 class="text-900 text-3xl font-medium mb-3">Senha Redefinida!</h2>
                        <p class="text-600">Sua senha foi alterada com sucesso.</p>
                        <p class="text-600">Redirecionando você para a tela de login...</p>
                    </div>
                </div>

            </div>
        </div>
    </div>
</template>

<style scoped>
/* Puxa o mesmo background do Login.vue */
#col-saudacao {
    background-image: url(/layout/images/bg-mogi-green.png);
    background-position: center;
    background-repeat: no-repeat;
    background-size: cover;
}

/* Garante que o input dentro do Password preencha o espaço */
:deep(.p-password-input) {
    width: 100%;
}
</style>