<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';
import { useUserStore } from '@/stores/userStore';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Checkbox from 'primevue/checkbox';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import MultiSelect from 'primevue/multiselect';
import Password from 'primevue/password';
import Select from 'primevue/select';
import SelectButton from 'primevue/selectbutton';
import Tag from 'primevue/tag';
import ToggleSwitch from 'primevue/toggleswitch';

const toast = useToast();
const userStore = useUserStore();
const route = useRoute();
const router = useRouter();

const podeGerirGestores = computed(
    () => userStore.currentUser?.perfil === 'GESTOR' && userStore.currentUser?.is_staff
);

const PERFIS_BASE = [
    { label: 'Todos', value: '' },
    { label: 'Vereador', value: 'VEREADOR' },
    { label: 'Protocolo', value: 'PROTOCOLO' },
    { label: 'Secretaria', value: 'SECRETARIA' }
];

const perfisFiltro = computed(() =>
    podeGerirGestores.value
        ? [...PERFIS_BASE, { label: 'Gestor', value: 'GESTOR' }]
        : PERFIS_BASE
);

const PERFIS_CRIACAO = computed(() => {
    const base = [
        { label: 'Vereador', value: 'VEREADOR' },
        { label: 'Protocolo', value: 'PROTOCOLO' },
        { label: 'Secretaria', value: 'SECRETARIA' }
    ];
    if (podeGerirGestores.value) {
        base.push({ label: 'Gestor', value: 'GESTOR' });
    }
    return base;
});

/** Perfil + Órgão (Sinapse) › Setor (UA) = onde atua no SGDL */
const REGRAS_ATUACAO = {
    VEREADOR: {
        escopo: 'Copiloto e demandas próprias — não usa órgão/setor',
        orgao: false,
        setor: false,
        orgaoFixo: null,
        setorFixo: null
    },
    PROTOCOLO: {
        escopo: 'Protocolo geral — triagem, clusters e filas institucionais',
        orgao: true,
        setor: true,
        orgaoFixo: 'SMGOV (órgão 12 — automático)',
        setorFixo: 'MCRUZ-SMGOV-SGAC / UA 754 (automático)'
    },
    SECRETARIA: {
        escopo: 'Operação da secretaria — fila «Meu setor» e demandas do órgão',
        orgao: true,
        setor: true,
        orgaoFixo: null,
        setorFixo: null
    },
    GESTOR: {
        escopo: 'Administração plena — todo o SGDL (órgão/setor só referência)',
        orgao: 'opcional',
        setor: 'opcional',
        orgaoFixo: null,
        setorFixo: null
    }
};

const regraAtuacaoAtual = computed(() => REGRAS_ATUACAO[form.value.perfil] || REGRAS_ATUACAO.VEREADOR);

const exigeOrgaoSetor = computed(() => form.value.perfil === 'SECRETARIA');
const mostraBlocoOrgaoSetor = computed(() => form.value.perfil !== 'VEREADOR');

const loading = ref(false);
const salvando = ref(false);
const usuarios = ref([]);
const orgaos = ref([]);
const setoresOrgao = ref([]);
const dialogAberto = ref(false);
const editando = ref(null);
const filtroPerfil = ref('');
const busca = ref('');
const somenteIncompletos = ref(false);

const form = ref({
    perfil: 'VEREADOR',
    username: '',
    password: '',
    first_name: '',
    last_name: '',
    email: '',
    cargo: '',
    telefone: '',
    ramal: '',
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

const resetForm = (perfil = 'VEREADOR') => {
    form.value = {
        perfil,
        username: '',
        password: '',
        first_name: '',
        last_name: '',
        email: '',
        cargo: '',
        telefone: '',
        ramal: '',
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
        const params = {};
        if (filtroPerfil.value) params.perfil = filtroPerfil.value;
        if (busca.value.trim()) params.q = busca.value.trim();
        if (somenteIncompletos.value) params.incompleto = '1';
        const { data } = await ApiService.listarGestaoUsuarios(params);
        usuarios.value = Array.isArray(data) ? data : data?.results || [];
    } catch (error) {
        usuarios.value = [];
        toast.add({ severity: 'error', summary: 'Usuários', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const abrirNovo = () => {
    const perfil = filtroPerfil.value || 'VEREADOR';
    resetForm(perfil);
    dialogAberto.value = true;
};

const abrirEditar = async (row) => {
    editando.value = row;
    form.value = {
        perfil: row.perfil,
        username: row.username,
        password: '',
        first_name: row.first_name || '',
        last_name: row.last_name || '',
        email: row.email || '',
        cargo: row.cargo || '',
        telefone: row.telefone || '',
        ramal: row.ramal || '',
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
            is_active: form.value.is_active
        };

        if (form.value.perfil === 'VEREADOR') {
            payload.cargo = form.value.cargo;
            payload.telefone = form.value.telefone;
            payload.ramal = form.value.ramal;
        }

        if (['SECRETARIA', 'GESTOR'].includes(form.value.perfil)) {
            payload.sinapse_orgao_id = form.value.sinapse_orgao_id;
            payload.unidade_ids = form.value.unidade_ids || [];
        }

        if (editando.value) {
            if (form.value.password) payload.password = form.value.password;
            await ApiService.atualizarGestaoUsuario(editando.value.id, payload);
            toast.add({ severity: 'success', summary: 'Usuário atualizado', life: 2500 });
        } else {
            payload.perfil = form.value.perfil;
            payload.username = form.value.username;
            payload.password = form.value.password;
            await ApiService.criarGestaoUsuario(payload);
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

const tituloDialog = computed(() => {
    if (editando.value) return `Editar — ${editando.value.username}`;
    const p = PERFIS_CRIACAO.value.find((x) => x.value === form.value.perfil);
    return `Novo usuário — ${p?.label || form.value.perfil}`;
});

const formValido = computed(() => {
    if (form.value.perfil === 'SECRETARIA') {
        if (!form.value.sinapse_orgao_id || !form.value.unidade_ids?.length) return false;
    }
    if (editando.value) return true;
    if (!form.value.username || !form.value.password) return false;
    if (form.value.perfil === 'GESTOR' && form.value.unidade_ids?.length && !form.value.sinapse_orgao_id) {
        return false;
    }
    return true;
});

const perfilTagSeverity = (perfil) => {
    const m = {
        VEREADOR: 'info',
        PROTOCOLO: 'primary',
        SECRETARIA: 'warn',
        GESTOR: 'danger'
    };
    return m[perfil] || 'secondary';
};

watch(
    () => form.value.sinapse_orgao_id,
    async (novo, antigo) => {
        await loadSetoresOrgao(novo);
        if (antigo && novo !== antigo) form.value.unidade_ids = [];
    }
);

watch([filtroPerfil, somenteIncompletos], () => loadUsuarios());

onMounted(async () => {
    const qsPerfil = route.query?.perfil;
    if (typeof qsPerfil === 'string' && qsPerfil) {
        filtroPerfil.value = qsPerfil.toUpperCase();
    }
    await loadOrgaos();
    await loadUsuarios();
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div class="flex flex-wrap justify-between items-start gap-3">
            <div>
                <h2 class="text-2xl font-semibold m-0">Gestão de usuários</h2>
                <p class="text-surface-600 mt-1 mb-0 text-sm">
                    Cada login combina <strong>Perfil</strong> (papel no SGDL) com
                    <strong>Órgão (Sinapse) › Setor (UA)</strong> — isso define
                    <em>onde</em> a pessoa atua no sistema.
                </p>
            </div>
            <Button label="Novo usuário" icon="pi pi-user-plus" @click="abrirNovo" />
        </div>

        <Message severity="info" :closable="false" class="text-sm m-0">
            <strong>Perfil</strong> define menus e permissões.
            <strong>Órgão › Setor</strong> define a unidade institucional de atuação
            (obrigatório para Secretaria; fixo para Protocolo; ausente para Vereador).
            Gestor opera em todo o sistema — órgão/setor são referência opcional.
        </Message>

        <Card>
            <template #content>
                <div class="flex flex-col gap-4 mb-4">
                    <SelectButton
                        v-model="filtroPerfil"
                        :options="perfisFiltro"
                        optionLabel="label"
                        optionValue="value"
                    />
                    <div class="flex flex-wrap gap-3 items-center">
                        <span class="p-input-icon-left flex-1 min-w-64">
                            <i class="pi pi-search" />
                            <InputText
                                v-model="busca"
                                placeholder="Buscar login, nome ou e-mail"
                                class="w-full"
                                @keyup.enter="loadUsuarios"
                            />
                        </span>
                        <Button label="Buscar" icon="pi pi-search" outlined @click="loadUsuarios" />
                        <div class="flex items-center gap-2">
                            <Checkbox v-model="somenteIncompletos" inputId="inc" binary />
                            <label for="inc" class="text-sm cursor-pointer">Só atuação incompleta (falta órgão ou setor)</label>
                        </div>
                    </div>
                </div>

                <DataTable
                    :value="usuarios"
                    :loading="loading"
                    stripedRows
                    size="small"
                    paginator
                    :rows="20"
                    responsiveLayout="scroll"
                    class="sgdl-table-scroll"
                >
                    <Column field="username" header="Login" />
                    <Column header="Nome">
                        <template #body="{ data }">
                            {{ data.first_name || data.last_name ? `${data.first_name || ''} ${data.last_name || ''}`.trim() : '—' }}
                        </template>
                    </Column>
                    <Column header="Perfil (papel)">
                        <template #body="{ data }">
                            <Tag :value="data.perfil_display || data.perfil" :severity="perfilTagSeverity(data.perfil)" />
                        </template>
                    </Column>
                    <Column header="Onde atua no SGDL" style="min-width: 14rem">
                        <template #body="{ data }">
                            <div class="text-sm">
                                <div class="font-medium">{{ data.atuacao_sgdl?.resumo || '—' }}</div>
                                <div v-if="data.atuacao_sgdl?.escopo" class="text-muted-color text-xs mt-0.5">
                                    {{ data.atuacao_sgdl.escopo }}
                                </div>
                            </div>
                        </template>
                    </Column>
                    <Column header="Atuação">
                        <template #body="{ data }">
                            <Tag
                                :value="data.atuacao_sgdl?.completa ? 'Definida' : 'Pendente'"
                                :severity="data.atuacao_sgdl?.completa ? 'success' : 'warn'"
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
            <div class="flex flex-col gap-5">
                <!-- 1. Perfil -->
                <div class="border border-surface-200 dark:border-surface-700 rounded-lg p-4 flex flex-col gap-3">
                    <div class="font-semibold text-sm uppercase tracking-wide text-muted-color">1. Perfil — papel no SGDL</div>
                    <div v-if="!editando" class="flex flex-col gap-2">
                        <Select
                            v-model="form.perfil"
                            :options="PERFIS_CRIACAO"
                            optionLabel="label"
                            optionValue="value"
                            class="w-full"
                        />
                    </div>
                    <div v-else class="flex items-center gap-2">
                        <Tag :value="editando.perfil_display || editando.perfil" />
                        <span class="text-sm text-muted-color">Perfil não alterável após criação</span>
                    </div>
                    <p class="text-sm text-surface-600 m-0">{{ regraAtuacaoAtual.escopo }}</p>
                </div>

                <!-- 2. Onde atua: Órgão > Setor -->
                <div
                    v-if="mostraBlocoOrgaoSetor"
                    class="border border-surface-200 dark:border-surface-700 rounded-lg p-4 flex flex-col gap-3"
                >
                    <div class="font-semibold text-sm uppercase tracking-wide text-muted-color">
                        2. Onde atua — Órgão (Sinapse) › Setor (UA)
                    </div>

                    <template v-if="form.perfil === 'PROTOCOLO'">
                        <Message severity="secondary" :closable="false" class="text-sm m-0">
                            Vínculo fixo aplicado automaticamente ao salvar:
                            <strong>{{ regraAtuacaoAtual.orgaoFixo }}</strong>
                            ›
                            <strong>{{ regraAtuacaoAtual.setorFixo }}</strong>
                        </Message>
                    </template>

                    <template v-else>
                        <div class="flex flex-col gap-2">
                            <label class="text-sm font-medium">
                                Órgão (Sinapse)
                                <span v-if="exigeOrgaoSetor" class="text-primary">*</span>
                                <span v-else-if="form.perfil === 'GESTOR'" class="text-muted-color font-normal"> (opcional)</span>
                            </label>
                            <Select
                                v-model="form.sinapse_orgao_id"
                                :options="orgaos"
                                optionLabel="label"
                                optionValue="value"
                                :placeholder="exigeOrgaoSetor ? 'Selecione a secretaria' : 'Referência institucional'"
                                filter
                                showClear
                                class="w-full"
                            />
                            <span class="text-xs text-muted-color">Nível superior — secretaria executiva no catálogo Sinapse</span>
                        </div>

                        <div class="flex items-center gap-2 text-muted-color text-xs pl-1">
                            <i class="pi pi-angle-down" />
                            <span>Setor depende do órgão selecionado</span>
                        </div>

                        <div class="flex flex-col gap-2">
                            <label class="text-sm font-medium">
                                Setor (UA)
                                <span v-if="exigeOrgaoSetor" class="text-primary">*</span>
                                <span v-else-if="form.perfil === 'GESTOR'" class="text-muted-color font-normal"> (opcional)</span>
                            </label>
                            <MultiSelect
                                v-model="form.unidade_ids"
                                :options="setoresOrgao"
                                optionLabel="label"
                                optionValue="value"
                                :placeholder="form.sinapse_orgao_id ? 'Selecione o(s) setor(es) RM' : 'Escolha o órgão primeiro'"
                                filter
                                display="chip"
                                class="w-full"
                                :disabled="!form.sinapse_orgao_id"
                            />
                            <span class="text-xs text-muted-color">Unidade administrativa importada (RM271698) — fila «Meu setor»</span>
                        </div>
                    </template>
                </div>

                <div
                    v-else
                    class="border border-surface-200 dark:border-surface-700 rounded-lg p-4"
                >
                    <div class="font-semibold text-sm uppercase tracking-wide text-muted-color mb-2">
                        2. Onde atua
                    </div>
                    <p class="text-sm text-surface-600 m-0">
                        Vereador não possui órgão/setor — atua apenas como autor legislativo (Copiloto e demandas próprias).
                    </p>
                </div>

                <!-- 3. Conta -->
                <div class="border border-surface-200 dark:border-surface-700 rounded-lg p-4 flex flex-col gap-3">
                    <div class="font-semibold text-sm uppercase tracking-wide text-muted-color">3. Dados da conta</div>
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

                    <template v-if="form.perfil === 'VEREADOR'">
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div class="flex flex-col gap-2">
                                <label class="text-sm font-medium">Cargo</label>
                                <InputText v-model="form.cargo" class="w-full" />
                            </div>
                            <div class="flex flex-col gap-2">
                                <label class="text-sm font-medium">Telefone</label>
                                <InputText v-model="form.telefone" class="w-full" />
                            </div>
                            <div class="flex flex-col gap-2">
                                <label class="text-sm font-medium">Ramal</label>
                                <InputText v-model="form.ramal" class="w-full" />
                            </div>
                        </div>
                    </template>

                    <div class="flex items-center gap-2">
                        <ToggleSwitch v-model="form.is_active" />
                        <span class="text-sm">Usuário ativo</span>
                    </div>
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" text @click="dialogAberto = false" />
                <Button label="Salvar" icon="pi pi-check" :loading="salvando" :disabled="!formValido" @click="salvar" />
            </template>
        </Dialog>
    </div>
</template>
