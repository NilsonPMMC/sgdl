<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import Checkbox from 'primevue/checkbox';
import Password from 'primevue/password';
import Divider from 'primevue/divider';
import FloatingConfigurator from '@/components/FloatingConfigurator.vue';
import Dialog from 'primevue/dialog';

const router = useRouter();
const userStore = useUserStore();
const username = ref('');
const password = ref('');
const error = ref(null);
const rememberMe = ref(false);

const showResetPasswordDialog = ref(false);
const resetEmail = ref('');
const resetSuccess = ref(false);
const resetError = ref(null);
const resetLoading = ref(false);

onMounted(() => {
    if (localStorage.getItem('sgdlRememberMePref') === 'true') {
        rememberMe.value = true;

        const rememberedUser = localStorage.getItem('sgdlRememberedUser');
        if (rememberedUser) {
            username.value = rememberedUser;
        }
    }
});

const handleLogin = async () => {
    if (rememberMe.value) {
        localStorage.setItem('sgdlRememberMePref', 'true');
        localStorage.setItem('sgdlRememberedUser', username.value);
    } else {
        localStorage.removeItem('sgdlRememberMePref');
        localStorage.removeItem('sgdlRememberedUser');
    }

    try {
        await userStore.login(username.value, password.value, rememberMe.value);
        router.push('/');
    } catch (err) {
        error.value = 'Usuário ou senha inválidos.';
    }
};

const handlePasswordReset = async () => {
    resetError.value = null;
    resetSuccess.value = false;
    resetLoading.value = true;
    try {
        await ApiService.requestPasswordReset({ email: resetEmail.value });
        resetSuccess.value = true;
    } catch (err) {
        resetError.value = 'Não foi possível encontrar um usuário com este e-mail.';
    } finally {
        resetLoading.value = false;
    }
};

const onResetDialogHide = () => {
    resetEmail.value = '';
    resetError.value = null;
    resetSuccess.value = false;
    resetLoading.value = false;
};
</script>

<template>
    <div class="grid grid-cols-12 min-h-screen overflow-hidden">
        
        <div id="col-saudacao" class="flex flex-col col-span-6 items-center justify-center p-8">
            <img src="/layout/images/brasao_nome_pmmc.png" alt="Brasão PMMC" style="width: 300px" class="mb-5" />
            <h1 class="text-6xl font-bold text-white">Bem-vindo!</h1>
            <p class="text-xl text-white">Sistema de Gestão de Demandas do Legislativo</p>
        </div>

        <div class="flex col-span-6 items-center justify-center p-8">
            <div class="card" style="width: 30rem">                
                <div class="flex flex-row items-center justify-center mb-5">
                    <h1 class="text-900 text-4xl font-bold m-0 text-primary">SGDL</h1>
                    <Divider layout="vertical" />
                    <span class="text-600">Sistema de Gestão de<br>Demandas do Legislativo</span>
                </div>
                <Divider/>
                <form @submit.prevent="handleLogin">
                    <div class="flex flex-col gap-4">
                        <div>
                            <label for="username" class="block mb-2">Usuário</label>
                            <span class="p-input-icon-left w-full mb-5">
                                <InputText id="username" v-model="username" type="text" placeholder="Seu usuário" fluid />
                            </span>
                        </div>
                        <div>
                            <label for="password" class="block mb-2">Senha</label>
                            <Password 
                                id="password" 
                                v-model="password" 
                                placeholder="Sua senha"
                                :feedback="false" 
                                toggleMask 
                                fluid
                            />
                            <small v-if="error" class="p-error mb-3">{{ error }}</small>
                        </div>
                    </div>
                    <div class="flex items-center justify-between my-5">
                        <div class="flex items-center">
                            <Checkbox v-model="rememberMe" inputId="rememberMe" binary class="mr-2" />
                            <label for="rememberMe">Lembrar-me</label>
                        </div>
                        <a class="font-medium text-primary-500 no-underline cursor-pointer" 
                           @click="showResetPasswordDialog = true">
                           Esqueceu a senha?
                        </a>
                    </div>

                    <Button label="Entrar" class="w-full p-3 text-xl" type="submit"></Button>
                
                </form>
            </div>
        </div>
    </div>
    <Dialog v-model:visible="showResetPasswordDialog" 
            header="Redefinir Senha" 
            :modal="true" 
            class="p-fluid" 
            style="width: 450px;"
            @hide="onResetDialogHide">
        
        <div v-if="!resetSuccess">
            <p class="mb-4">Digite seu e-mail e enviaremos um link para redefinir sua senha.</p>
            <div class="field">
                <label for="email" class="block mb-2">E-mail</label>
                <InputText id="email" v-model="resetEmail" type="email" placeholder="seuemail@dominio.com" fluid :invalid="!!resetError" />
                <small v-if="resetError" class="p-error mt-1">{{ resetError }}</small>
            </div>
        </div>
        
        <div v-else>
            <div class="flex flex-col items-center text-center">
                <i class="pi pi-check-circle text-6xl text-green-500 mb-3"></i>
                <h4 class="font-bold">Verifique seu e-mail!</h4>
                <p>Se uma conta com este e-mail existir, enviamos um link para redefinição de senha.</p>
            </div>
        </div>
        
        <template #footer>
            <Button label="Cancelar" icon="pi pi-times" text @click="showResetPasswordDialog = false" />
            <Button v-if="!resetSuccess" 
                    label="Enviar Link" 
                    icon="pi pi-send" 
                    @click="handlePasswordReset"
                    :loading="resetLoading" />
        </template>
    </Dialog>
    <FloatingConfigurator />
</template>

<style scoped>
/* Garante que o input dentro do Password preencha o espaço */
:deep(.p-password-input) {
    width: 100%;
}
#col-saudacao{
    background-image: url(/layout/images/bg-mogi-green.png);
    background-position: center;
    background-repeat: no-repeat;
    background-size: cover;
}
</style>