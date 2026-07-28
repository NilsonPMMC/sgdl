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
} = useAuthLogin('prefeitura');

const features = [
    {
        icon: 'pi pi-inbox',
        label: 'Protocolo e filas',
        detail: 'Despacho, devolutivas e tramitação com trilha de auditoria.'
    },
    {
        icon: 'pi pi-sitemap',
        label: 'Secretarias e setores',
        detail: 'Operação por unidade administrativa e escopo de competência.'
    },
    {
        icon: 'pi pi-chart-bar',
        label: 'Gestão e indicadores',
        detail: 'Dashboards, clusters, carta de serviços e configurações.'
    }
];
</script>

<template>
    <AuthPortalLayout
        variant="prefeitura"
        eyebrow="Prefeitura · SGDL"
        title="Portal Operacional"
        subtitle="Acesso institucional para protocolo, secretarias e gestores municipais • execução, monitoramento e governança."
        :features="features"
        :alternate-portal="alternatePortal"
    >
        <AuthLoginForm
            variant="prefeitura"
            title="Entrar na prefeitura"
            subtitle="Credenciais de protocolo, secretaria ou gestão municipal."
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
