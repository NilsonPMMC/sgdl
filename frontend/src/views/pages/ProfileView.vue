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

const toast = useToast();
const userStore = useUserStore();

// Objeto para os dados do perfil
const profile = ref({
    first_name: '',
    last_name: '',
    email: '',
    cargo: '',
    telefone: '',
    ramal: '',
    assinatura: '',
    avatar: null
});

// Objeto para a troca de senha
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

onMounted(async () => {
    try {
        const response = await ApiService.getUserProfile();
        profile.value = response.data;
        avatarPreview.value = response.data.avatar;
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível carregar os dados do perfil.', life: 3000 });
    }
});

const onFileSelect = (event) => {
    const file = event.files[0];
    if (file) {
        // Usa o FileReader para ler o arquivo e passar para o cropper
        const reader = new FileReader();
        reader.onload = (e) => {
            imageToCrop.value = e.target.result;
            cropModalVisible.value = true;
        };
        reader.readAsDataURL(file);
    }
    // Limpa o FileUpload para permitir selecionar o mesmo arquivo novamente
    event.files.length = 0;
};

const cropImage = () => {
    if (!cropper.value) return;

    cropper.value.getCroppedCanvas().toBlob((blob) => {
        newAvatarFile.value = new File([blob], "avatar.png", { type: "image/png" });
        avatarPreview.value = URL.createObjectURL(blob);
        cropModalVisible.value = false;
    }, 'image/png');
};

const saveProfile = async () => {
    const formData = new FormData();
    Object.keys(profile.value).forEach(key => {
        if (key !== 'avatar') {
            formData.append(key, profile.value[key] || '');
        }
    });

    if (newAvatarFile.value) {
        formData.append('avatar', newAvatarFile.value);
    }

    try {
        const response = await ApiService.updateUserProfile(formData);
        userStore.updateCurrentUser(response.data);
        
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Perfil atualizado!', life: 3000 });
        newAvatarFile.value = null; // Limpa o arquivo após o sucesso
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
        // Limpa os campos
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
                    <div class="grid col-span-4 gap-8">
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
                        <div class="flex flex-col gap-2">
                            <label for="assinatura">Assinatura</label>
                            <Editor id="assinatura" v-model="profile.assinatura" editorStyle="height: 120px">
                                <template v-slot:toolbar>
                                    <span class="ql-formats">
                                        <button v-tooltip.bottom="'Bold'" class="ql-bold"></button>
                                        <button v-tooltip.bottom="'Italic'" class="ql-italic"></button>
                                        <button v-tooltip.bottom="'Underline'" class="ql-underline"></button>
                                    </span>
                                </template>
                        </Editor>
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
        <div style="max-height: 60vh;">
            <VueCropper
                ref="cropper"
                :src="imageToCrop"
                :aspect-ratio="1 / 1"
                alt="Recortar Imagem"
            />
            </div>
        <template #footer>
            <Button label="Cancelar" icon="pi pi-times" @click="cropModalVisible = false" class="p-button-text" />
            <Button label="Confirmar Recorte" icon="pi pi-check" @click="cropImage" />
        </template>
    </Dialog>
</template>