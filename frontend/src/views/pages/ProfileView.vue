<script setup>
import { ref, onMounted, computed } from 'vue';
import { useToast } from 'primevue/usetoast';
import ApiService from '@/service/ApiService.js';
import { useUserStore } from '@/stores/userStore';

import 'cropperjs/dist/cropper.css';
import VueCropper from 'vue-cropperjs';

import Dialog from 'primevue/dialog';
import InputText from 'primevue/inputtext';
import Button from 'primevue/button';
import Avatar from 'primevue/avatar';
import FileUpload from 'primevue/fileupload';
import Password from 'primevue/password';
import Editor from 'primevue/editor';
import Message from 'primevue/message';
import Card from 'primevue/card';
import Tag from 'primevue/tag';

const toast = useToast();
const userStore = useUserStore();

const profile = ref({
    first_name: '',
    last_name: '',
    email: '',
    cargo: '',
    telefone: '',
    ramal: '',
    assinatura: '',
    avatar: null,
    assinatura_imagem: null
});

const passwords = ref({
    old_password: '',
    new_password: '',
    confirm_password: ''
});

const cropModalVisible = ref(false);
const imageToCrop = ref(null);
const cropper = ref(null);
const newAvatarFile = ref(null);
const avatarPreview = ref(null);

const newAssinaturaFile = ref(null);
const assinaturaPreview = ref(null);
const savingProfile = ref(false);
const savingPassword = ref(false);

const nomeExibicao = computed(() => {
    const nome = `${profile.value.first_name || ''} ${profile.value.last_name || ''}`.trim();
    return nome || profile.value.username || 'Usuário';
});

const iniciaisAvatar = computed(() => {
    const partes = nomeExibicao.value.split(/\s+/).filter(Boolean);
    if (partes.length >= 2) {
        return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
    }
    return (partes[0]?.[0] || 'U').toUpperCase();
});

onMounted(async () => {
    try {
        const response = await ApiService.getUserProfile();
        profile.value = response.data;
        avatarPreview.value = response.data.avatar;
        assinaturaPreview.value = response.data.assinatura_imagem || null;
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível carregar os dados do perfil.', life: 3000 });
    }
});

const onFileSelect = (event) => {
    const file = event.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            imageToCrop.value = e.target.result;
            cropModalVisible.value = true;
        };
        reader.readAsDataURL(file);
    }
    event.files.length = 0;
};

const onAssinaturaFileSelect = (event) => {
    const file = event.files[0];
    if (!file) return;
    if (file.size > 500000) {
        toast.add({ severity: 'warn', summary: 'Arquivo grande', detail: 'Use imagem de até 500 KB.', life: 4000 });
        event.files.length = 0;
        return;
    }
    newAssinaturaFile.value = file;
    assinaturaPreview.value = URL.createObjectURL(file);
    event.files.length = 0;
};

const gerarAssinaturaCanvas = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 420;
    canvas.height = 110;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const nome =
        `${profile.value.first_name || ''} ${profile.value.last_name || ''}`.trim() ||
        profile.value.username ||
        'Vereador';
    const cargo = (profile.value.cargo || 'Vereador').trim();

    ctx.strokeStyle = '#213a8f';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(24, 88);
    ctx.lineTo(396, 88);
    ctx.stroke();

    ctx.fillStyle = '#213a8f';
    ctx.font = 'italic 26px "DejaVu Serif", Georgia, serif';
    ctx.fillText(nome, 24, 52);

    ctx.fillStyle = '#444444';
    ctx.font = '14px "DejaVu Sans", Arial, sans-serif';
    ctx.fillText(cargo, 24, 78);

    canvas.toBlob((blob) => {
        if (!blob) return;
        newAssinaturaFile.value = new File([blob], 'assinatura_gerada.png', { type: 'image/png' });
        assinaturaPreview.value = URL.createObjectURL(blob);
        toast.add({
            severity: 'info',
            summary: 'Assinatura gerada',
            detail: 'Clique em Salvar alterações para aplicar no ofício.',
            life: 4000
        });
    }, 'image/png');
};

const cropImage = () => {
    if (!cropper.value) return;

    cropper.value.getCroppedCanvas().toBlob((blob) => {
        newAvatarFile.value = new File([blob], 'avatar.png', { type: 'image/png' });
        avatarPreview.value = URL.createObjectURL(blob);
        cropModalVisible.value = false;
    }, 'image/png');
};

const saveProfile = async () => {
    savingProfile.value = true;
    const formData = new FormData();
    Object.keys(profile.value).forEach((key) => {
        if (key !== 'avatar' && key !== 'assinatura_imagem') {
            formData.append(key, profile.value[key] || '');
        }
    });

    if (newAvatarFile.value) {
        formData.append('avatar', newAvatarFile.value);
    }
    if (newAssinaturaFile.value) {
        formData.append('assinatura_imagem', newAssinaturaFile.value);
    }

    try {
        const response = await ApiService.updateUserProfile(formData);
        profile.value = response.data;
        userStore.updateCurrentUser(response.data);
        avatarPreview.value = response.data.avatar;
        assinaturaPreview.value = response.data.assinatura_imagem || assinaturaPreview.value;
        newAssinaturaFile.value = null;

        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Perfil atualizado!', life: 3000 });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível atualizar o perfil.', life: 3000 });
    } finally {
        savingProfile.value = false;
    }
};

const savePassword = async () => {
    if (passwords.value.new_password !== passwords.value.confirm_password) {
        toast.add({ severity: 'warn', summary: 'Aviso', detail: 'A nova senha e a confirmação não correspondem.', life: 3000 });
        return;
    }

    savingPassword.value = true;
    try {
        await ApiService.changePassword({
            old_password: passwords.value.old_password,
            new_password: passwords.value.new_password
        });
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Senha alterada com sucesso!', life: 3000 });
        passwords.value = { old_password: '', new_password: '', confirm_password: '' };
    } catch (error) {
        const errorMessage = error.response?.data?.old_password?.[0] || 'Não foi possível alterar a senha.';
        toast.add({ severity: 'error', summary: 'Erro', detail: errorMessage, life: 3000 });
    } finally {
        savingPassword.value = false;
    }
};
</script>

<template>
    <div class="profile-page">
        <header class="profile-page__header">
            <div>
                <h1 class="profile-page__title">Meu perfil</h1>
                <p class="profile-page__subtitle">
                    Dados pessoais, foto, assinatura de ofício e segurança da conta.
                </p>
            </div>
        </header>

        <div v-if="profile.atuacao_sgdl" class="profile-page__alerts">
            <Message severity="secondary" :closable="false" class="w-full text-sm">
                <div class="flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-2">
                    <span><strong>Perfil:</strong> {{ profile.perfil }}</span>
                    <span class="hidden sm:inline text-muted-color">·</span>
                    <span><strong>Onde atua:</strong> {{ profile.atuacao_sgdl.resumo }}</span>
                </div>
                <span v-if="profile.atuacao_sgdl.escopo" class="block mt-2 text-muted-color">
                    {{ profile.atuacao_sgdl.escopo }}
                </span>
            </Message>
        </div>

        <Message
            v-if="profile.perfil === 'GESTOR' && profile.is_staff"
            severity="info"
            :closable="false"
            class="profile-page__alerts w-full text-sm"
        >
            Acesso administrativo pleno:
            <router-link to="/gestao-usuarios" class="text-primary font-medium ml-1">Gestão de usuários</router-link>
            <span class="mx-1 text-muted-color">·</span>
            <a href="/admin/" target="_blank" rel="noopener" class="text-primary font-medium">Django Admin</a>
        </Message>

        <div class="profile-page__grid">
            <!-- Coluna principal: dados -->
            <Card class="profile-card profile-card--dados">
                <template #title>Dados pessoais</template>
                <template #subtitle>Informações exibidas em ofícios e comunicações internas</template>
                <template #content>
                    <div class="profile-fields">
                        <div class="profile-field">
                            <label for="firstname">Nome</label>
                            <InputText id="firstname" v-model="profile.first_name" fluid />
                        </div>
                        <div class="profile-field">
                            <label for="lastname">Sobrenome</label>
                            <InputText id="lastname" v-model="profile.last_name" fluid />
                        </div>
                        <div class="profile-field profile-field--full">
                            <label for="email">E-mail</label>
                            <InputText id="email" v-model="profile.email" type="email" fluid />
                        </div>
                        <div class="profile-field">
                            <label for="cargo">Cargo</label>
                            <InputText id="cargo" v-model="profile.cargo" fluid />
                        </div>
                        <div class="profile-field">
                            <label for="telefone">Telefone</label>
                            <InputText id="telefone" v-model="profile.telefone" fluid />
                        </div>
                        <div class="profile-field">
                            <label for="ramal">Ramal</label>
                            <InputText id="ramal" v-model="profile.ramal" fluid />
                        </div>
                    </div>
                </template>
                <template #footer>
                    <div class="profile-card__footer">
                        <Button
                            label="Salvar alterações"
                            icon="pi pi-check"
                            :loading="savingProfile"
                            @click="saveProfile"
                        />
                    </div>
                </template>
            </Card>

            <!-- Coluna lateral: avatar -->
            <Card class="profile-card profile-card--avatar">
                <template #title>Foto de perfil</template>
                <template #content>
                    <div class="profile-avatar">
                        <Avatar
                            :image="avatarPreview"
                            :label="avatarPreview ? undefined : iniciaisAvatar"
                            shape="circle"
                            class="profile-avatar__image"
                        />
                        <div class="profile-avatar__info">
                            <p class="profile-avatar__name">{{ nomeExibicao }}</p>
                            <Tag v-if="profile.perfil" :value="profile.perfil" severity="secondary" class="text-xs" />
                            <p v-if="profile.email" class="profile-avatar__email">{{ profile.email }}</p>
                        </div>
                        <FileUpload
                            mode="basic"
                            name="avatar"
                            accept="image/*"
                            :maxFileSize="1000000"
                            :auto="true"
                            :customUpload="true"
                            @uploader="onFileSelect"
                            chooseLabel="Trocar foto"
                            class="profile-avatar__upload p-button-outlined w-full sm:w-auto"
                        />
                        <p class="profile-avatar__hint">PNG ou JPG, até 1 MB. A imagem será recortada em formato quadrado.</p>
                    </div>
                </template>
            </Card>

            <!-- Assinatura -->
            <Card class="profile-card profile-card--assinatura">
                <template #title>Assinatura no ofício (PDF)</template>
                <template #subtitle>Rodapé dos ofícios gerados pelo Copiloto</template>
                <template #content>
                    <Message severity="info" :closable="false" class="mb-4 text-sm w-full">
                        Envie uma imagem ou gere automaticamente a partir do seu nome e cargo.
                    </Message>

                    <div
                        v-if="assinaturaPreview"
                        class="profile-assinatura-preview"
                    >
                        <img :src="assinaturaPreview" alt="Pré-visualização da assinatura" />
                    </div>
                    <div v-else class="profile-assinatura-preview profile-assinatura-preview--empty">
                        <i class="pi pi-image text-2xl text-muted-color" />
                        <span class="text-sm text-muted-color">Nenhuma assinatura cadastrada</span>
                    </div>

                    <div class="profile-assinatura-actions">
                        <FileUpload
                            mode="basic"
                            name="assinatura_imagem"
                            accept="image/png,image/jpeg"
                            :maxFileSize="500000"
                            :auto="true"
                            :customUpload="true"
                            @uploader="onAssinaturaFileSelect"
                            chooseLabel="Enviar imagem"
                            class="p-button-outlined flex-1 sm:flex-none"
                        />
                        <Button
                            label="Gerar assinatura"
                            icon="pi pi-pencil"
                            severity="secondary"
                            outlined
                            class="flex-1 sm:flex-none"
                            @click="gerarAssinaturaCanvas"
                        />
                    </div>

                    <div class="profile-field profile-field--full mt-4">
                        <label for="assinatura">Texto complementar (opcional)</label>
                        <Editor id="assinatura" v-model="profile.assinatura" editorStyle="min-height: 100px">
                            <template #toolbar>
                                <span class="ql-formats">
                                    <button v-tooltip.bottom="'Negrito'" class="ql-bold" type="button" />
                                    <button v-tooltip.bottom="'Itálico'" class="ql-italic" type="button" />
                                    <button v-tooltip.bottom="'Sublinhado'" class="ql-underline" type="button" />
                                </span>
                            </template>
                        </Editor>
                        <small class="text-muted-color">
                            Usado no PDF quando não houver imagem, ou como legenda abaixo da imagem.
                        </small>
                    </div>
                </template>
            </Card>

            <!-- Senha -->
            <Card class="profile-card profile-card--senha">
                <template #title>Alterar senha</template>
                <template #subtitle>Mantenha sua conta segura com senha forte e exclusiva</template>
                <template #content>
                    <div class="profile-fields profile-fields--senha">
                        <div class="profile-field profile-field--full">
                            <label for="old_password">Senha atual</label>
                            <Password
                                id="old_password"
                                v-model="passwords.old_password"
                                :feedback="false"
                                toggle-mask
                                fluid
                                autocomplete="current-password"
                            />
                        </div>
                        <div class="profile-field">
                            <label for="new_password">Nova senha</label>
                            <Password
                                id="new_password"
                                v-model="passwords.new_password"
                                toggle-mask
                                fluid
                                autocomplete="new-password"
                            />
                        </div>
                        <div class="profile-field">
                            <label for="confirm_password">Confirmar nova senha</label>
                            <Password
                                id="confirm_password"
                                v-model="passwords.confirm_password"
                                :feedback="false"
                                toggle-mask
                                fluid
                                autocomplete="new-password"
                            />
                        </div>
                    </div>
                </template>
                <template #footer>
                    <div class="profile-card__footer">
                        <Button
                            label="Alterar senha"
                            icon="pi pi-key"
                            severity="warn"
                            :loading="savingPassword"
                            @click="savePassword"
                        />
                    </div>
                </template>
            </Card>
        </div>
    </div>

    <Dialog
        v-model:visible="cropModalVisible"
        modal
        header="Recortar imagem"
        :style="{ width: 'min(calc(100vw - 2rem), 560px)' }"
        :draggable="false"
        class="profile-crop-dialog"
    >
        <div class="profile-crop-dialog__body">
            <VueCropper ref="cropper" :src="imageToCrop" :aspect-ratio="1 / 1" alt="Recortar imagem" />
        </div>
        <template #footer>
            <Button label="Cancelar" icon="pi pi-times" text @click="cropModalVisible = false" />
            <Button label="Confirmar recorte" icon="pi pi-check" @click="cropImage" />
        </template>
    </Dialog>
</template>

<style scoped>
.profile-page {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    max-width: 72rem;
    margin-inline: auto;
    width: 100%;
}

.profile-page__header {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
}

.profile-page__title {
    margin: 0;
    font-size: clamp(1.5rem, 4vw, 1.875rem);
    font-weight: 700;
    line-height: 1.2;
    color: var(--text-color);
}

.profile-page__subtitle {
    margin: 0.35rem 0 0;
    font-size: 0.925rem;
    color: var(--text-color-secondary);
    line-height: 1.5;
    max-width: 36rem;
}

.profile-page__alerts {
    margin: 0;
}

.profile-page__grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.25rem;
    align-items: start;
}

@media (min-width: 768px) {
    .profile-page__grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .profile-card--dados {
        grid-column: 1;
        grid-row: 1 / span 2;
    }

    .profile-card--avatar {
        grid-column: 2;
        grid-row: 1;
    }

    .profile-card--assinatura {
        grid-column: 1 / -1;
    }

    .profile-card--senha {
        grid-column: 1 / -1;
    }
}

@media (min-width: 1024px) {
    .profile-page__grid {
        grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
    }

    .profile-card--dados {
        grid-column: 1;
        grid-row: 1;
    }

    .profile-card--avatar {
        grid-column: 2;
        grid-row: 1;
    }

    .profile-card--assinatura {
        grid-column: 1 / -1;
    }

    .profile-card--senha {
        grid-column: 1 / -1;
        max-width: 36rem;
    }
}

.profile-card :deep(.p-card-title) {
    font-size: 1.05rem;
    font-weight: 700;
}

.profile-card :deep(.p-card-subtitle) {
    font-size: 0.85rem;
    line-height: 1.45;
}

.profile-card__footer {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 0.75rem;
}

.profile-fields {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
}

@media (min-width: 480px) {
    .profile-fields {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

.profile-fields--senha {
    max-width: 100%;
}

@media (min-width: 640px) {
    .profile-fields--senha {
        grid-template-columns: 1fr;
        max-width: 28rem;
    }
}

@media (min-width: 768px) {
    .profile-fields--senha {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        max-width: none;
    }

    .profile-fields--senha .profile-field--full {
        grid-column: 1 / -1;
        max-width: 28rem;
    }
}

.profile-field {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    min-width: 0;
}

.profile-field--full {
    grid-column: 1 / -1;
}

.profile-field label {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-color);
}

.profile-avatar {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 0.85rem;
}

.profile-avatar__image {
    width: 7.5rem !important;
    height: 7.5rem !important;
    font-size: 2rem !important;
}

.profile-avatar__info {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    width: 100%;
}

.profile-avatar__name {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-color);
    word-break: break-word;
}

.profile-avatar__email {
    margin: 0;
    font-size: 0.82rem;
    color: var(--text-color-secondary);
    word-break: break-all;
}

.profile-avatar__hint {
    margin: 0;
    font-size: 0.78rem;
    color: var(--text-color-secondary);
    line-height: 1.45;
    max-width: 18rem;
}

.profile-assinatura-preview {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 1rem;
    margin-bottom: 1rem;
    border: 1px solid var(--surface-border);
    border-radius: var(--content-border-radius, 0.75rem);
    background: var(--surface-ground);
    min-height: 6.5rem;
}

.profile-assinatura-preview--empty {
    flex-direction: column;
    gap: 0.5rem;
}

.profile-assinatura-preview img {
    max-height: 6rem;
    max-width: 100%;
    object-fit: contain;
}

.profile-assinatura-actions {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
}

@media (min-width: 480px) {
    .profile-assinatura-actions {
        flex-direction: row;
        flex-wrap: wrap;
    }
}

.profile-crop-dialog__body {
    max-height: min(60vh, 28rem);
    overflow: hidden;
}

.profile-crop-dialog__body :deep(.cropper-container) {
    max-height: min(60vh, 28rem);
}

:deep(.p-password),
:deep(.p-password-input) {
    width: 100%;
}
</style>
