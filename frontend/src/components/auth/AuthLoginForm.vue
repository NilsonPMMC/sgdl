<script setup>
import Button from 'primevue/button';
import Checkbox from 'primevue/checkbox';
import Dialog from 'primevue/dialog';
import InputText from 'primevue/inputtext';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import Message from 'primevue/message';
import Password from 'primevue/password';
import { RouterLink } from 'vue-router';

defineProps({
    variant: {
        type: String,
        default: 'prefeitura',
        validator: (v) => ['vereador', 'prefeitura'].includes(v)
    },
    username: { type: String, required: true },
    password: { type: String, required: true },
    error: { type: String, default: null },
    portalRedirect: { type: String, default: null },
    portalRedirectLabel: { type: String, default: null },
    perfisAceitos: { type: Array, default: () => [] },
    rememberMe: { type: Boolean, required: true },
    submitting: { type: Boolean, default: false },
    showResetPasswordDialog: { type: Boolean, required: true },
    resetEmail: { type: String, required: true },
    resetSuccess: { type: Boolean, required: true },
    resetError: { type: String, default: null },
    resetLoading: { type: Boolean, default: false },
    title: { type: String, required: true },
    subtitle: { type: String, default: '' }
});

const emit = defineEmits([
    'update:username',
    'update:password',
    'update:rememberMe',
    'update:showResetPasswordDialog',
    'update:resetEmail',
    'submit',
    'reset',
    'reset-hide'
]);
</script>

<template>
    <div class="auth-form-card" :class="`auth-form-card--${variant}`">
        <div class="auth-form-card__header">
            <span class="auth-form-card__eyebrow">{{ variant === 'vereador' ? 'Gabinete' : 'Operacional' }}</span>
            <h2 class="auth-form-card__title">{{ title }}</h2>
            <p v-if="subtitle" class="auth-form-card__subtitle">{{ subtitle }}</p>
            <p v-if="perfisAceitos.length" class="auth-form-card__perfis">
                Perfis: {{ perfisAceitos.map((p) => p.charAt(0) + p.slice(1).toLowerCase()).join(', ') }}
            </p>
        </div>

        <form class="auth-form-card__body" @submit.prevent="emit('submit')">
            <Message v-if="error" severity="error" :closable="false" class="mb-0 auth-form-card__error">
                <div class="flex flex-col gap-2">
                    <span>{{ error }}</span>
                    <RouterLink
                        v-if="portalRedirect"
                        :to="portalRedirect"
                        class="auth-form-card__portal-link"
                    >
                        Ir para {{ portalRedirectLabel }}
                        <i class="pi pi-external-link text-xs" />
                    </RouterLink>
                </div>
            </Message>

            <div class="field">
                <label for="auth-username">Usuário</label>
                <IconField class="w-full">
                    <InputIcon class="pi pi-user" />
                    <InputText
                        id="auth-username"
                        :model-value="username"
                        type="text"
                        placeholder="Seu usuário institucional"
                        autocomplete="username"
                        fluid
                        @update:model-value="emit('update:username', $event)"
                    />
                </IconField>
            </div>

            <div class="field">
                <label for="auth-password">Senha</label>
                <Password
                    id="auth-password"
                    :model-value="password"
                    placeholder="Sua senha"
                    :feedback="false"
                    toggle-mask
                    fluid
                    autocomplete="current-password"
                    @update:model-value="emit('update:password', $event)"
                />
            </div>

            <div class="auth-form-card__actions">
                <div class="flex items-center gap-2">
                    <Checkbox
                        :model-value="rememberMe"
                        input-id="auth-remember"
                        binary
                        @update:model-value="emit('update:rememberMe', $event)"
                    />
                    <label for="auth-remember" class="cursor-pointer text-sm">Lembrar-me</label>
                </div>
                <button
                    type="button"
                    class="auth-form-card__link"
                    @click="emit('update:showResetPasswordDialog', true)"
                >
                    Esqueceu a senha?
                </button>
            </div>

            <Button
                :label="submitting ? 'Entrando…' : 'Entrar'"
                type="submit"
                class="w-full auth-form-card__submit"
                :class="`auth-form-card__submit--${variant}`"
                :loading="submitting"
                icon="pi pi-sign-in"
            />
        </form>
    </div>

    <Dialog
        :visible="showResetPasswordDialog"
        header="Redefinir senha"
        modal
        class="p-fluid"
        style="width: min(100%, 28rem)"
        @update:visible="emit('update:showResetPasswordDialog', $event)"
        @hide="emit('reset-hide')"
    >
        <div v-if="!resetSuccess">
            <p class="mt-0 mb-4 text-sm text-muted-color">
                Informe seu e-mail cadastrado. Enviaremos um link para redefinir a senha.
            </p>
            <div class="field">
                <label for="auth-reset-email" class="block mb-2">E-mail</label>
                <InputText
                    id="auth-reset-email"
                    :model-value="resetEmail"
                    type="email"
                    placeholder="seuemail@dominio.com"
                    fluid
                    :invalid="!!resetError"
                    @update:model-value="emit('update:resetEmail', $event)"
                />
                <small v-if="resetError" class="p-error mt-1 block">{{ resetError }}</small>
            </div>
        </div>
        <div v-else class="flex flex-col items-center text-center py-2">
            <i class="pi pi-check-circle text-5xl text-green-500 mb-3" />
            <h4 class="font-semibold m-0 mb-2">Verifique seu e-mail</h4>
            <p class="m-0 text-sm text-muted-color">
                Se existir uma conta com este e-mail, enviamos instruções para redefinição.
            </p>
        </div>
        <template #footer>
            <Button label="Fechar" text @click="emit('update:showResetPasswordDialog', false)" />
            <Button
                v-if="!resetSuccess"
                label="Enviar link"
                icon="pi pi-send"
                :loading="resetLoading"
                @click="emit('reset')"
            />
        </template>
    </Dialog>
</template>

<style scoped>
.auth-form-card {
    padding: clamp(1.5rem, 4vw, 2.25rem);
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--auth-accent, var(--p-primary-500)), transparent 70%);
    background: color-mix(in srgb, var(--surface-card, #fff), transparent 4%);
    box-shadow:
        0 24px 48px -12px rgba(0, 0, 0, 0.18),
        0 0 0 1px rgba(255, 255, 255, 0.04) inset;
    backdrop-filter: blur(12px);
}

.auth-form-card--vereador {
    --auth-accent: #c9a227;
}

.auth-form-card--prefeitura {
    --auth-accent:  #38bdf8;
}

.auth-form-card__header {
    margin-bottom: 1.5rem;
}

.auth-form-card__eyebrow {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--auth-accent);
    margin-bottom: 0.5rem;
}

.auth-form-card__title {
    margin: 0;
    font-size: clamp(1.5rem, 3vw, 1.85rem);
    font-weight: 700;
    line-height: 1.15;
    color: var(--text-color);
}

.auth-form-card__subtitle {
    margin: 0.65rem 0 0;
    font-size: 0.92rem;
    color: var(--text-color-secondary);
    line-height: 1.5;
}

.auth-form-card__perfis {
    margin: 0.5rem 0 0;
    font-size: 0.78rem;
    color: var(--text-color-secondary);
    opacity: 0.9;
}

.auth-form-card__portal-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-weight: 700;
    color: inherit;
    text-decoration: underline;
}

.auth-form-card__error :deep(.p-message-text) {
    width: 100%;
}

.auth-form-card__body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.field label {
    display: block;
    margin-bottom: 0.45rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-color);
}

.auth-form-card__actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.auth-form-card__link {
    border: 0;
    padding: 0;
    background: transparent;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--auth-accent);
    cursor: pointer;
}

.auth-form-card__link:hover {
    text-decoration: underline;
}

.auth-form-card__submit {
    margin-top: 0.25rem;
    font-size: 1rem;
    padding-block: 0.85rem;
}

.auth-form-card__submit--vereador {
    background: linear-gradient(135deg, #c9a227 0%, #d4af37 55%, #b8921f 100%) !important;
    border-color: #c9a227 !important;
    color: #0a1628 !important;
}

.auth-form-card__submit--prefeitura {
    background: linear-gradient(135deg, #1b3178 0%, #213a8f 55%, #152861 100%) !important;
    border-color: #213a8f !important;
    color: #94a3b8 !important;
}

:deep(.p-password-input) {
    width: 100%;
}
</style>
