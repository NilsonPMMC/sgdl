<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import MultiSelect from 'primevue/multiselect';
import Password from 'primevue/password';
import Select from 'primevue/select';
import Tag from 'primevue/tag';
import ToggleSwitch from 'primevue/toggleswitch';

const toast = useToast();

const loading = ref(false);
const salvando = ref(false);
const usuarios = ref([]);
const orgaos = ref([]);
const setoresOrgao = ref([]);
const dialogAberto = ref(false);
const editando = ref(null);

const form = ref({
    username: '',
    password: '',
    first_name: '',
    last_name: '',
    email: '',
    is_active: true,
    sinapse_orgao_id: null,
    unidade_ids: []
});

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    if (typeof data === 'object' && data) {
        const first = Object.values(data).flat()[0];
        if (first) return String(first);
    }
    return 'Operação não concluída.';
};

const resetForm = () => {
    form.value = {
        username: '',
        password: '',
        first_name: '',
        last_name: '',
        email: '',
        is_active: true,
        sinapse_orgao_id: null,
        unidade_ids: []
    };
    editando.value = null;
    setoresOrgao.value = [];
};

const loadOrgaos = async () => {
    try {
        const { data } = await ApiService.listarOrgaosSetores();
        orgaos.value = (data?.results || []).map((o) => ({
            label: o.nome || o.label || `Órgão ${o.id}`,
            value: o.id
        }));
    } catch {
        orgaos.value = [];
    }
};

const loadSetoresOrgao = async (orgaoId) => {
    if (!orgaoId) {
        setoresOrgao.value = [];
        return;
    }
    try {
        const { data } = await ApiService.listarUnidadesAdministrativas({
            sinapse_orgao_id: orgaoId
        });
        const lista = Array.isArray(data) ? data : data?.results || [];
        setoresOrgao.value = lista.map((s) => ({
            label: s.sigla ? `${s.sigla} — ${s.nome}` : s.nome,
            value: s.id
        }));
    } catch {
        setoresOrgao.value = [];
    }
};

const loadUsuarios = async () => {
    loading.value = true;
    try {
        const { data } = await ApiService.listarGestaoUsuariosSecretaria();
        usuarios.value = Array.isArray(data) ? data : data?.results || [];
    } catch (error) {
        usuarios.value = [];
        toast.add({ severity: 'error', summary: 'Usuários', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const abrirNovo = () => {
    resetForm();
    dialogAberto.value = true;
};

const abrirEditar = async (row) => {
    editando.value = row;
    form.value = {
        username: row.username,
        password: '',
        first_name: row.first_name || '',
        last_name: row.last_name || '',
        email: row.email || '',
        is_active: row.is_active !== false,
        sinapse_orgao_id: row.sinapse_orgao_id || null,
        unidade_ids: [...(row.unidade_ids || [])]
    };
    await loadSetoresOrgao(form.value.sinapse_orgao_id);
    dialogAberto.value = true;
};

const salvar = async () => {
    salvando.value = true;
    try {
        const payload = {
            first_name: form.value.first_name,
            last_name: form.value.last_name,
            email: form.value.email,
            is_active: form.value.is_active,
            sinapse_orgao_id: form.value.sinapse_orgao_id,
            unidade_ids: form.value.unidade_ids
        };
        if (editando.value) {
            if (form.value.password) payload.password = form.value.password;
            await ApiService.atualizarGestaoUsuarioSecretaria(editando.value.id, payload);
            toast.add({ severity: 'success', summary: 'Usuário atualizado', life: 2500 });
        } else {
            payload.username = form.value.username;
            payload.password = form.value.password;
            await ApiService.criarGestaoUsuarioSecretaria(payload);
            toast.add({ severity: 'success', summary: 'Usuário criado', life: 2500 });
        }
        dialogAberto.value = false;
        await loadUsuarios();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 5000 });
    } finally {
        salvando.value = false;
    }
};

const tituloDialog = computed(() =>
    editando.value ? `Editar — ${editando.value.username}` : 'Novo usuário de secretaria'
);

const formValido = computed(() => {
    if (!form.value.sinapse_orgao_id || !form.value.unidade_ids?.length) return false;
    if (editando.value) return true;
    return Boolean(form.value.username && form.value.password);
});

watch(
    () => form.value.sinapse_orgao_id,
    async (novo, antigo) => {
        await loadSetoresOrgao(novo);
        if (antigo && novo !== antigo) {
            form.value.unidade_ids = [];
        }
    }
);

onMounted(async () => {
    await loadOrgaos();
    await loadUsuarios();
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div class="flex flex-wrap justify-between items-start gap-3">
            <div>
                <h2 class="text-2xl font-semibold m-0">Usuários de secretaria</h2>
                <p class="text-surface-600 mt-1 mb-0 text-sm">
                    Crie operadores com órgão Sinapse e setor(es) RM. A fila «Meu setor» exige vínculo
                    completo.
                </p>
            </div>
            <Button label="Novo usuário" icon="pi pi-user-plus" @click="abrirNovo" />
        </div>

        <Message severity="info" :closable="false" class="text-sm m-0">
            Usuários sem órgão ou sem setor veem aviso no login e não acessam a fila «Meu setor».
        </Message>

        <Card>
            <template #content>
                <DataTable
                    :value="usuarios"
                    :loading="loading"
                    stripedRows
                    size="small"
                    paginator
                    :rows="15"
                    responsiveLayout="scroll"
                    class="sgdl-table-scroll"
                >
                    <Column field="username" header="Login" />
                    <Column header="Nome">
                        <template #body="{ data }">
                            {{ data.first_name || data.last_name ? `${data.first_name || ''} ${data.last_name || ''}`.trim() : '—' }}
                        </template>
                    </Column>
                    <Column field="secretaria_nome" header="Órgão" />
                    <Column header="Setores">
                        <template #body="{ data }">
                            <span v-if="data.unidades?.length">
                                {{ data.unidades.map((u) => u.sigla || u.nome).join(', ') }}
                            </span>
                            <span v-else class="text-muted-color">—</span>
                        </template>
                    </Column>
                    <Column header="Vínculo">
                        <template #body="{ data }">
                            <Tag
                                :value="data.vinculo_secretaria?.completo ? 'Completo' : 'Incompleto'"
                                :severity="data.vinculo_secretaria?.completo ? 'success' : 'warn'"
                            />
                        </template>
                    </Column>
                    <Column header="Ativo">
                        <template #body="{ data }">
                            <Tag :value="data.is_active ? 'Sim' : 'Não'" :severity="data.is_active ? 'success' : 'secondary'" />
                        </template>
                    </Column>
                    <Column header="" style="width: 6rem">
                        <template #body="{ data }">
                            <Button icon="pi pi-pencil" text rounded @click="abrirEditar(data)" />
                        </template>
                    </Column>
                </DataTable>
            </template>
        </Card>

        <Dialog v-model:visible="dialogAberto" :header="tituloDialog" modal class="w-full max-w-2xl">
            <div class="flex flex-col gap-4">
                <div v-if="!editando" class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Login (username)</label>
                    <InputText v-model="form.username" class="w-full" autocomplete="off" />
                </div>
                <div v-if="!editando" class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Senha inicial</label>
                    <Password v-model="form.password" toggleMask :feedback="false" class="w-full" inputClass="w-full" />
                </div>
                <div v-else class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Nova senha (opcional)</label>
                    <Password v-model="form.password" toggleMask :feedback="false" class="w-full" inputClass="w-full" />
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="flex flex-col gap-2">
                        <label class="text-sm font-medium">Nome</label>
                        <InputText v-model="form.first_name" class="w-full" />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label class="text-sm font-medium">Sobrenome</label>
                        <InputText v-model="form.last_name" class="w-full" />
                    </div>
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">E-mail</label>
                    <InputText v-model="form.email" type="email" class="w-full" />
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Órgão (secretaria Sinapse)</label>
                    <Select
                        v-model="form.sinapse_orgao_id"
                        :options="orgaos"
                        optionLabel="label"
                        optionValue="value"
                        placeholder="Selecione o órgão"
                        filter
                        class="w-full"
                    />
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Setor(es) RM</label>
                    <MultiSelect
                        v-model="form.unidade_ids"
                        :options="setoresOrgao"
                        optionLabel="label"
                        optionValue="value"
                        placeholder="Selecione um ou mais setores"
                        filter
                        display="chip"
                        class="w-full"
                        :disabled="!form.sinapse_orgao_id"
                    />
                </div>
                <div class="flex items-center gap-2">
                    <ToggleSwitch v-model="form.is_active" />
                    <span class="text-sm">Usuário ativo</span>
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" text @click="dialogAberto = false" />
                <Button label="Salvar" icon="pi pi-check" :loading="salvando" :disabled="!formValido" @click="salvar" />
            </template>
        </Dialog>
    </div>
</template>
