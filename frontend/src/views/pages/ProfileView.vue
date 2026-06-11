<script setup>
import { ref, onMounted } from 'vue';
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
import Divider from 'primevue/divider';
import Editor from 'primevue/editor';
import Message from 'primevue/message';

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

    ctx.strokeStyle = '#1e3a5f';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(24, 88);
    ctx.lineTo(396, 88);
    ctx.stroke();

    ctx.fillStyle = '#1e3a5f';
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
            detail: 'Clique em Salvar Alterações para aplicar no ofício.',
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
    }
};

const savePassword = async () => {
    if (passwords.value.new_password !== passwords.value.confirm_password) {
        toast.add({ severity: 'warn', summary: 'Aviso', detail: 'A nova senha e a confirmação não correspondem.', life: 3000 });
        return;
    }

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
    }
};
</script>

<template>
    <div class="grid">
        <div class="col-12">
            <div class="card">
                <h5>Meu Perfil</h5>
                <Message
                    v-if="profile.atuacao_sgdl"
                    severity="secondary"
                    :closable="false"
                    class="mb-4 text-sm"
                >
                    <strong>Perfil:</strong> {{ profile.perfil }}
                    ·
                    <strong>Onde atua:</strong> {{ profile.atuacao_sgdl.resumo }}
                    <span v-if="profile.atuacao_sgdl.escopo" class="block mt-1 text-muted-color">
                        {{ profile.atuacao_sgdl.escopo }}
                    </span>
                </Message>
                <Message
                    v-if="profile.perfil === 'GESTOR' && profile.is_staff"
                    severity="info"
                    :closable="false"
                    class="mb-4 text-sm"
                >
                    Acesso administrativo pleno:
                    <router-link to="/gestao-usuarios" class="text-primary ml-1">Gestão de usuários</router-link>
                    ·
                    <a href="/admin/" target="_blank" rel="noopener" class="text-primary">Django Admin</a>
                </Message>
                <div class="grid grid-cols-12 items-start gap-8 mb-4">
                    <div class="grid col-span-4 gap-2">
                        <div class="flex flex-col gap-2">
                            <label for="firstname">Nome</label>
                            <InputText id="firstname" v-model="profile.first_name" />
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="lastname">Sobrenome</label>
                            <InputText id="lastname" v-model="profile.last_name" />
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="email">Email</label>
                            <InputText id="email" v-model="profile.email" />
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="cargo">Cargo</label>
                            <InputText id="cargo" v-model="profile.cargo" />
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="telefone">Telefone</label>
                            <InputText id="telefone" v-model="profile.telefone" />
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="ramal">Ramal</label>
                            <InputText id="ramal" v-model="profile.ramal" />
                        </div>
                    </div>
                    <div class="grid col-span-4 gap-6">
                        <div class="flex items-center">
                            <Avatar :image="avatarPreview" shape="circle" size="xlarge" class="mr-3" />
                            <FileUpload
                                mode="basic"
                                name="avatar"
                                accept="image/*"
                                :maxFileSize="1000000"
                                :auto="true"
                                :customUpload="true"
                                @uploader="onFileSelect"
                                chooseLabel="Trocar Foto"
                                class="p-button-outlined"
                            />
                        </div>
                    </div>
                    <div class="grid col-span-4 gap-4">
                        <div>
                            <h6 class="m-0 mb-2">Assinatura no ofício (PDF)</h6>
                            <Message severity="info" :closable="false" class="mb-3 text-sm">
                                A assinatura aparece no rodapé dos ofícios gerados pelo Copiloto. Envie uma imagem ou gere
                                a partir do seu nome e cargo.
                            </Message>
                        </div>
                        <div
                            v-if="assinaturaPreview"
                            class="flex justify-center items-center p-4 border border-surface-200 rounded-lg bg-surface-50 min-h-[100px]"
                        >
                            <img :src="assinaturaPreview" alt="Pré-visualização da assinatura" class="max-h-24 max-w-full" />
                        </div>
                        <div class="flex flex-wrap gap-2">
                            <FileUpload
                                mode="basic"
                                name="assinatura_imagem"
                                accept="image/png,image/jpeg"
                                :maxFileSize="500000"
                                :auto="true"
                                :customUpload="true"
                                @uploader="onAssinaturaFileSelect"
                                chooseLabel="Enviar imagem"
                                class="p-button-outlined"
                            />
                            <Button
                                label="Gerar assinatura"
                                icon="pi pi-pencil"
                                severity="secondary"
                                outlined
                                @click="gerarAssinaturaCanvas"
                            />
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="assinatura">Texto complementar (opcional)</label>
                            <Editor id="assinatura" v-model="profile.assinatura" editorStyle="height: 100px">
                                <template v-slot:toolbar>
                                    <span class="ql-formats">
                                        <button v-tooltip.bottom="'Bold'" class="ql-bold"></button>
                                        <button v-tooltip.bottom="'Italic'" class="ql-italic"></button>
                                        <button v-tooltip.bottom="'Underline'" class="ql-underline"></button>
                                    </span>
                                </template>
                            </Editor>
                            <small class="text-surface-500">
                                Usado no PDF quando não houver imagem, ou como legenda abaixo da imagem.
                            </small>
                        </div>
                    </div>
                </div>
                <Button label="Salvar Alterações" icon="pi pi-check" @click="saveProfile"></Button>

                <Divider class="my-6" />

                <h5>Alterar Senha</h5>
                <div class="flex flex-row mb-4">
                    <div class="flex flex-col gap-2">
                        <div class="flex flex-col gap-2">
                            <label for="old_password">Senha Atual</label>
                            <Password id="old_password" v-model="passwords.old_password" :feedback="false" toggleMask fluid></Password>
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="new_password">Nova Senha</label>
                            <Password id="new_password" v-model="passwords.new_password" toggleMask fluid></Password>
                        </div>
                        <div class="flex flex-col gap-2">
                            <label for="confirm_password">Confirmar Nova Senha</label>
                            <Password id="confirm_password" v-model="passwords.confirm_password" :feedback="false" toggleMask fluid></Password>
                        </div>
                    </div>
                </div>
                <Button label="Alterar Senha" icon="pi pi-key" @click="savePassword" class="p-button-warning"></Button>
            </div>
        </div>
    </div>
    <Dialog v-model:visible="cropModalVisible" modal header="Recortar Imagem" :style="{ width: '50vw' }" :draggable="false">
        <div style="max-height: 60vh">
            <VueCropper ref="cropper" :src="imageToCrop" :aspect-ratio="1 / 1" alt="Recortar Imagem" />
        </div>
        <template #footer>
            <Button label="Cancelar" icon="pi pi-times" @click="cropModalVisible = false" class="p-button-text" />
            <Button label="Confirmar Recorte" icon="pi pi-check" @click="cropImage" />
        </template>
    </Dialog>
</template>
