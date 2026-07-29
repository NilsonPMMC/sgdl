<script setup>
import AuthLoginForm from '@/components/auth/AuthLoginForm.vue';
import AuthPortalLayout from '@/components/auth/AuthPortalLayout.vue';
import { useAuthLogin } from '@/composables/useAuthLogin';

const {
    username,
    password,
    error,
    portalRedirect,
    portalRedirectLabel,
    rememberMe,
    submitting,
    showResetPasswordDialog,
    resetEmail,
    resetSuccess,
    resetError,
    resetLoading,
    alternatePortal,
    perfisAceitos,
    handleLogin,
    handlePasswordReset,
    onResetDialogHide
} = useAuthLogin('vereador');

const features = [
    {
        icon: 'pi pi-comments',
        label: 'Copiloto assistivo',
        detail: 'Registre ofícios em linguagem natural com validação humana.'
    },
    {
        icon: 'pi pi-send',
        label: 'Protocolo legislativo',
        detail: 'Acompanhe envios, devolutivas e prazos do seu gabinete.'
    },
    {
        icon: 'pi pi-map-marker',
        label: 'Demandas territoriais',
        detail: 'Visualize solicitações por bairro e acompanhe respostas.'
    }
];
</script>

<template>
    <AuthPortalLayout
        variant="vereador"
        eyebrow="Câmara Municipal · Mogi das Cruzes"
        title="Portal dos Vereadores"
        subtitle="Gabinetes legislativos e Câmara Municipal — ofícios, indicações e acompanhamento de protocolos."
        :features="features"
        :alternate-portal="alternatePortal"
    >
        <AuthLoginForm
            variant="vereador"
            title="Entrar no portal"
            subtitle="Vereador, assessor ou Câmara Municipal (indicações)."
            v-model:username="username"
            v-model:password="password"
            v-model:remember-me="rememberMe"
            v-model:show-reset-password-dialog="showResetPasswordDialog"
            v-model:reset-email="resetEmail"
            :error="error"
            :portal-redirect="portalRedirect"
            :portal-redirect-label="portalRedirectLabel"
            :perfis-aceitos="perfisAceitos"
            :submitting="submitting"
            :reset-success="resetSuccess"
            :reset-error="resetError"
            :reset-loading="resetLoading"
            @submit="handleLogin"
            @reset="handlePasswordReset"
            @reset-hide="onResetDialogHide"
        />
    </AuthPortalLayout>
</template>
