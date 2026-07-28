<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';
import { useUserStore } from '@/stores/userStore';
import { extrairPaginaResposta, paramsPagina } from '@/utils/serverTable';

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

const podeGerirGestores = computed(() => userStore.isGestorGeral);

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
        escopo: 'Sem vínculo = Gestor Geral (admin pleno). Com órgão/setor = Gestor Setorial (escopo + tramitações).',
        orgao: 'opcional',
        setor: 'opcional',
        orgaoFixo: null,
        setorFixo: null
    }
};

const tipoGestorFormulario = computed(() => {
    if (form.value.perfil !== 'GESTOR') return null;
    if (form.value.sinapse_orgao_id || form.value.unidade_ids?.length) return 'SETORIAL';
    return 'GERAL';
});

const labelTipoGestor = (row) => {
    if (row?.perfil !== 'GESTOR') return null;
    const tipo = row?.vinculo_gestor?.tipo_gestor || row?.atuacao_sgdl?.tipo_gestor;
    if (tipo === 'SETORIAL') return 'Setorial';
    if (tipo === 'GERAL') return 'Geral';
    return row?.sinapse_orgao_id || row?.unidade_ids?.length ? 'Setorial' : 'Geral';
};

const severityTipoGestor = (row) => (labelTipoGestor(row) === 'Geral' ? 'danger' : 'warn');

const regraAtuacaoAtual = computed(() => REGRAS_ATUACAO[form.value.perfil] || REGRAS_ATUACAO.VEREADOR);

const exigeOrgaoSetor = computed(() => form.value.perfil === 'SECRETARIA');
const mostraBlocoOrgaoSetor = computed(() => form.value.perfil !== 'VEREADOR');

const loading = ref(false);
const salvando = ref(false);
const usuarios = ref([]);
const totalUsuarios = ref(0);
const tablePagination = ref({ first: 0, rows: 20 });
const tabelaJaCarregada = ref(false);
const orgaos = ref([]);
const setoresOrgao = ref([]);
const vinculosExistentes = ref([]);
const dialogAberto = ref(false);
const editando = ref(null);
const alterarSenha = ref(false);
const filtroPerfil = ref('');
const busca = ref('');
const somenteIncompletos = ref(false);
/** Snapshot da busca ao abrir o modal — evita autofill do navegador após salvar/fechar. */
let buscaAntesDialog = '';

const restaurarBuscaPosDialog = () => {
    if (busca.value !== buscaAntesDialog) {
        busca.value = buscaAntesDialog;
        return true;
    }
    return false;
};

const limparEstadoDialogBusca = () => {
    buscaAntesDialog = '';
};

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
    alterarSenha.value = false;
    vinculosExistentes.value = [];
    setoresOrgao.value = [];
};

const formatUnidadeLabel = (u) => {
    const sigla = (u.sigla || '').trim();
    const nome = (u.nome || u.rotulo || '').trim();
    if (sigla && nome && sigla !== nome) return `${sigla} — ${nome}`;
    return sigla || nome || `UA #${u.id}`;
};

const mapUnidadeToOption = (u) => ({
    label: formatUnidadeLabel(u),
    value: u.id,
    sigla: u.sigla || '',
    nome: u.nome || u.rotulo || '',
    orgaoId: u.sinapse_orgao_id ?? u.orgao_id ?? null
});

const mergeOpcoesSetor = (opcoesApi, extras = []) => {
    const map = new Map();
    for (const item of extras) {
        if (!item?.id) continue;
        const opt = mapUnidadeToOption(item);
        map.set(opt.value, opt);
    }
    for (const opt of opcoesApi) {
        if (!map.has(opt.value)) map.set(opt.value, opt);
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, 'pt-BR'));
};

const extrairVinculosDaLinha = (row) => {
    if (row?.unidades?.length) return row.unidades;
    if (row?.atuacao_sgdl?.setores?.length) {
        return row.atuacao_sgdl.setores.map((s) => ({
            id: s.id,
            sigla: s.sigla,
            nome: s.nome || s.rotulo,
            sinapse_orgao_id: row.sinapse_orgao_id ?? row.atuacao_sgdl?.orgao_id
        }));
    }
    return [];
};

const onDialogHide = () => {
    form.value.password = '';
    alterarSenha.value = false;
    restaurarBuscaPosDialog();
    limparEstadoDialogBusca();
    resetForm(filtroPerfil.value || 'VEREADOR');
    // Autofill do navegador pode ocorrer após o modal sumir (ex.: "admin" no campo de busca).
    nextTick(() => {
        setTimeout(() => {
            if (restaurarBuscaPosDialog()) loadUsuarios();
        }, 120);
    });
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

const loadSetoresOrgao = async (orgaoId, extras = []) => {
    const vinculos = extras.length ? extras : vinculosExistentes.value;
    if (!orgaoId) {
        setoresOrgao.value = mergeOpcoesSetor([], vinculos);
        return;
    }
    try {
        const { data } = await ApiService.listarUnidadesAdministrativas({
            sinapse_orgao_id: orgaoId
        });
        const lista = Array.isArray(data) ? data : data?.results || [];
        const opcoes = lista.map((s) => mapUnidadeToOption(s));
        setoresOrgao.value = mergeOpcoesSetor(opcoes, vinculos);
    } catch {
        setoresOrgao.value = mergeOpcoesSetor([], vinculos);
    }
};

const loadUsuarios = async () => {
    loading.value = true;
    try {
        const params = paramsPagina(tablePagination.value, {
            perfil: filtroPerfil.value || undefined,
            q: busca.value.trim() || undefined,
            incompleto: somenteIncompletos.value ? '1' : undefined
        });
        Object.keys(params).forEach((key) => params[key] == null && delete params[key]);
        const response = await ApiService.listarGestaoUsuarios(params);
        const { rows, total } = extrairPaginaResposta(response);
        usuarios.value = rows;
        totalUsuarios.value = total;
    } catch (error) {
        usuarios.value = [];
        totalUsuarios.value = 0;
        toast.add({ severity: 'error', summary: 'Usuários', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const resetPaginaUsuarios = () => {
    tablePagination.value = { ...tablePagination.value, first: 0 };
};

const aplicarFiltrosUsuarios = () => {
    resetPaginaUsuarios();
    loadUsuarios();
};

const onPageUsuarios = (event) => {
    tablePagination.value = { first: event.first, rows: event.rows };
    tabelaJaCarregada.value = true;
    loadUsuarios();
};

const abrirNovo = () => {
    const perfil = filtroPerfil.value || 'VEREADOR';
    buscaAntesDialog = busca.value;
    resetForm(perfil);
    dialogAberto.value = true;
};

const abrirEditar = async (row) => {
    if (salvando.value) return;

    buscaAntesDialog = busca.value;

    const vinculos = extrairVinculosDaLinha(row);
    vinculosExistentes.value = vinculos;

    const orgaoId =
        row.sinapse_orgao_id ||
        vinculos[0]?.sinapse_orgao_id ||
        row.atuacao_sgdl?.orgao_id ||
        null;

    const unidadeIds = [...(row.unidade_ids?.length ? row.unidade_ids : vinculos.map((u) => u.id))];

    editando.value = row;
    alterarSenha.value = false;
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
        sinapse_orgao_id: orgaoId,
        unidade_ids: unidadeIds
    };

    await loadSetoresOrgao(orgaoId, vinculos);
    dialogAberto.value = true;
};

/** Troca manual de órgão no modal — não usar watch (race com await zerava setores). */
const onOrgaoChange = async (novoOrgaoId) => {
    const orgaoAnterior = form.value.sinapse_orgao_id;
    form.value.sinapse_orgao_id = novoOrgaoId;
    await loadSetoresOrgao(novoOrgaoId);
    if (orgaoAnterior != null && novoOrgaoId !== orgaoAnterior) {
        form.value.unidade_ids = [];
    }
};

const idsSetoresDaLinha = (row) => {
    if (row?.unidade_ids?.length) return [...row.unidade_ids];
    return extrairVinculosDaLinha(row).map((u) => u.id);
};

const salvar = async () => {
    if (salvando.value) return;

    const alvoId = editando.value?.id ?? null;
    const snapshotForm = {
        perfil: form.value.perfil,
        sinapse_orgao_id: form.value.sinapse_orgao_id,
        unidade_ids: [...(form.value.unidade_ids || [])]
    };

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

        if (['SECRETARIA', 'GESTOR'].includes(snapshotForm.perfil)) {
            payload.sinapse_orgao_id = snapshotForm.sinapse_orgao_id;
            let unidadeIds = snapshotForm.unidade_ids;
            if (alvoId && editando.value && unidadeIds.length === 0) {
                const idsOriginais = idsSetoresDaLinha(editando.value);
                const orgInalterado =
                    snapshotForm.sinapse_orgao_id ===
                    (editando.value.sinapse_orgao_id ??
                        editando.value.atuacao_sgdl?.orgao_id ??
                        null);
                if (idsOriginais.length > 0 && orgInalterado) {
                    unidadeIds = idsOriginais;
                }
            }
            payload.unidade_ids = unidadeIds;
        }

        if (editando.value) {
            if (alvoId && editando.value.id !== alvoId) {
                toast.add({
                    severity: 'warn',
                    summary: 'Edição interrompida',
                    detail: 'Outro usuário foi aberto antes de concluir o salvamento. Tente novamente.',
                    life: 4000
                });
                return;
            }
            const novaSenha = (form.value.password || '').trim();
            if (alterarSenha.value && novaSenha) payload.password = novaSenha;
            await ApiService.atualizarGestaoUsuario(alvoId ?? editando.value.id, payload);
            toast.add({ severity: 'success', summary: 'Usuário atualizado', life: 2500 });
        } else {
            payload.perfil = form.value.perfil;
            payload.username = form.value.username;
            payload.password = form.value.password;
            await ApiService.criarGestaoUsuario(payload);
            toast.add({ severity: 'success', summary: 'Usuário criado', life: 2500 });
        }
        dialogAberto.value = false;
        restaurarBuscaPosDialog();
        await loadUsuarios();
        limparEstadoDialogBusca();
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

const orgaoSelecionadoLabel = computed(() => {
    const id = form.value.sinapse_orgao_id;
    if (!id) return null;
    return (
        orgaos.value.find((o) => o.value === id)?.label ||
        editando.value?.secretaria_nome ||
        editando.value?.atuacao_sgdl?.orgao_nome ||
        `Órgão ${id}`
    );
});

const opcoesSetorMap = computed(() => {
    const map = new Map(setoresOrgao.value.map((o) => [o.value, o]));
    for (const v of vinculosExistentes.value) {
        if (v?.id && !map.has(v.id)) map.set(v.id, mapUnidadeToOption(v));
    }
    return map;
});

const vinculosSelecionados = computed(() =>
    (form.value.unidade_ids || []).map((id) => opcoesSetorMap.value.get(id) || { value: id, label: `UA #${id}` })
);

const vinculosProtocoloAtuais = computed(() => {
    if (form.value.perfil !== 'PROTOCOLO') return [];
    const setores = editando.value?.atuacao_sgdl?.setores || editando.value?.unidades || [];
    return setores.map((s) => mapUnidadeToOption(s));
});

const orgaoProtocoloAtual = computed(() =>
    editando.value?.atuacao_sgdl?.orgao_nome || regraAtuacaoAtual.value.orgaoFixo
);

watch([filtroPerfil, somenteIncompletos], () => aplicarFiltrosUsuarios());

onMounted(async () => {
    const qsPerfil = route.query?.perfil;
    if (typeof qsPerfil === 'string' && qsPerfil) {
        filtroPerfil.value = qsPerfil.toUpperCase();
    }
    await loadOrgaos();
    setTimeout(() => {
        if (!tabelaJaCarregada.value) {
            tabelaJaCarregada.value = true;
            loadUsuarios();
        }
    }, 80);
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
            <strong>Gestor Geral</strong> — sem vínculo, acesso e CRUD administrativo plenos.
            <strong>Gestor Setorial</strong> — com órgão e/ou setor, dados e tramitações no escopo vinculado.
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
                            <!--<i class="pi pi-search" />-->
                            <InputText
                                v-model="busca"
                                name="gestao-usuarios-busca"
                                autocomplete="off"
                                autocapitalize="off"
                                spellcheck="false"
                                data-lpignore="true"
                                data-1p-ignore
                                placeholder="Buscar login, nome ou e-mail"
                                class="w-full"
                                @keyup.enter="aplicarFiltrosUsuarios"
                            />
                        </span>
                        <Button label="Buscar" icon="pi pi-search" outlined @click="aplicarFiltrosUsuarios" />
                        <div class="flex items-center gap-2">
                            <Checkbox v-model="somenteIncompletos" inputId="inc" binary />
                            <label for="inc" class="text-sm cursor-pointer">Só atuação incompleta (falta órgão ou setor)</label>
                        </div>
                    </div>
                </div>

                <DataTable
                    :value="usuarios"
                    :loading="loading"
                    lazy
                    stripedRows
                    size="small"
                    paginator
                    :rows="tablePagination.rows"
                    :first="tablePagination.first"
                    :totalRecords="totalUsuarios"
                    :rowsPerPageOptions="[10, 20, 50, 100]"
                    paginatorTemplate="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
                    currentPageReportTemplate="Mostrando {first} a {last} de {totalRecords}"
                    responsiveLayout="scroll"
                    class="sgdl-table-scroll"
                    @page="onPageUsuarios"
                >
                    <Column field="username" header="Login" />
                    <Column header="Nome">
                        <template #body="{ data }">
                            {{ data.first_name || data.last_name ? `${data.first_name || ''} ${data.last_name || ''}`.trim() : '—' }}
                        </template>
                    </Column>
                    <Column header="Perfil (papel)">
                        <template #body="{ data }">
                            <div class="flex flex-wrap items-center gap-1">
                                <Tag :value="data.perfil_display || data.perfil" :severity="perfilTagSeverity(data.perfil)" />
                                <Tag
                                    v-if="data.perfil === 'GESTOR'"
                                    :value="labelTipoGestor(data)"
                                    :severity="severityTipoGestor(data)"
                                    class="text-xs"
                                />
                            </div>
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
                            <Button
                                icon="pi pi-pencil"
                                text
                                rounded
                                :disabled="salvando"
                                @click="abrirEditar(data)"
                            />
                        </template>
                    </Column>
                </DataTable>
            </template>
        </Card>

        <Dialog
            v-model:visible="dialogAberto"
            :header="tituloDialog"
            modal
            class="w-full max-w-2xl"
            :pt="{ root: { autocomplete: 'off' } }"
            @hide="onDialogHide"
        >
            <!-- Decoy: absorve autofill do navegador fora do campo de busca -->
            <input
                type="text"
                tabindex="-1"
                aria-hidden="true"
                class="gestao-dialog-autofill-decoy"
                autocomplete="username"
            />
            <input
                type="password"
                tabindex="-1"
                aria-hidden="true"
                class="gestao-dialog-autofill-decoy"
                autocomplete="new-password"
            />
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
                    <Tag
                        v-if="form.perfil === 'GESTOR' && tipoGestorFormulario"
                        :value="tipoGestorFormulario === 'GERAL' ? 'Gestor Geral' : 'Gestor Setorial'"
                        :severity="tipoGestorFormulario === 'GERAL' ? 'danger' : 'warn'"
                        class="w-fit"
                    />
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
                        <Message v-if="!editando" severity="secondary" :closable="false" class="text-sm m-0">
                            Vínculo fixo aplicado automaticamente ao salvar:
                            <strong>{{ regraAtuacaoAtual.orgaoFixo }}</strong>
                            ›
                            <strong>{{ regraAtuacaoAtual.setorFixo }}</strong>
                        </Message>
                        <div v-else class="flex flex-col gap-3">
                            <div class="rounded-lg bg-surface-50 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-3 flex flex-col gap-2">
                                <span class="text-xs font-semibold uppercase tracking-wide text-muted-color">
                                    Vínculo institucional atual
                                </span>
                                <div class="text-sm">
                                    <span class="text-muted-color">Órgão:</span>
                                    <strong class="ml-1">{{ orgaoProtocoloAtual }}</strong>
                                </div>
                                <div class="flex flex-col gap-1">
                                    <span class="text-xs text-muted-color">Setor(es) vinculado(s):</span>
                                    <div v-if="vinculosProtocoloAtuais.length" class="flex flex-wrap gap-2">
                                        <Tag
                                            v-for="v in vinculosProtocoloAtuais"
                                            :key="v.value"
                                            :value="v.label"
                                            severity="info"
                                        />
                                    </div>
                                    <span v-else class="text-sm">{{ regraAtuacaoAtual.setorFixo }}</span>
                                </div>
                            </div>
                            <Message severity="secondary" :closable="false" class="text-sm m-0">
                                O vínculo de Protocolo é mantido automaticamente pelo sistema — não requer edição manual.
                            </Message>
                        </div>
                    </template>

                    <template v-else>
                        <div
                            v-if="editando && (orgaoSelecionadoLabel || vinculosSelecionados.length)"
                            class="rounded-lg bg-surface-50 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-3 flex flex-col gap-2"
                        >
                            <span class="text-xs font-semibold uppercase tracking-wide text-muted-color">
                                Atuação vinculada hoje
                            </span>
                            <div v-if="orgaoSelecionadoLabel" class="text-sm">
                                <span class="text-muted-color">Órgão:</span>
                                <strong class="ml-1">{{ orgaoSelecionadoLabel }}</strong>
                            </div>
                            <div v-if="vinculosSelecionados.length" class="flex flex-col gap-1">
                                <span class="text-xs text-muted-color">
                                    Setor(es) administrativo(s):
                                    <span v-if="form.perfil === 'SECRETARIA'" class="text-primary">*</span>
                                </span>
                                <div class="flex flex-wrap gap-2">
                                    <Tag
                                        v-for="v in vinculosSelecionados"
                                        :key="v.value"
                                        :value="v.label"
                                        severity="info"
                                    />
                                </div>
                            </div>
                            <span v-else class="text-sm text-muted-color">Nenhum setor vinculado — selecione abaixo.</span>
                        </div>

                        <div class="flex flex-col gap-2">
                            <label class="text-sm font-medium">
                                Órgão (Sinapse)
                                <span v-if="exigeOrgaoSetor" class="text-primary">*</span>
                                <span v-else-if="form.perfil === 'GESTOR'" class="text-muted-color font-normal"> (opcional)</span>
                            </label>
                            <Select
                                :modelValue="form.sinapse_orgao_id"
                                :options="orgaos"
                                optionLabel="label"
                                optionValue="value"
                                :placeholder="exigeOrgaoSetor ? 'Selecione a secretaria' : 'Referência institucional'"
                                filter
                                showClear
                                class="w-full"
                                @update:modelValue="onOrgaoChange"
                            />
                            <span v-if="orgaoSelecionadoLabel" class="text-xs text-primary">
                                Selecionado: {{ orgaoSelecionadoLabel }}
                            </span>
                            <span v-else class="text-xs text-muted-color">Nível superior — secretaria executiva no catálogo Sinapse</span>
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
                                :placeholder="form.sinapse_orgao_id ? 'Selecione ou ajuste o(s) setor(es) RM' : 'Escolha o órgão para listar setores'"
                                filter
                                display="chip"
                                class="w-full"
                                :disabled="!form.sinapse_orgao_id && !vinculosSelecionados.length"
                            />
                            <span v-if="vinculosSelecionados.length" class="text-xs text-muted-color">
                                {{ vinculosSelecionados.length }} setor(es) selecionado(s) — sigla e nome exibidos nos chips acima.
                            </span>
                            <span v-else class="text-xs text-muted-color">Unidade administrativa importada (RM271698) — fila «Meu setor»</span>
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
                        <InputText
                            v-model="form.username"
                            class="w-full"
                            autocomplete="off"
                            autocapitalize="off"
                            data-lpignore="true"
                        />
                    </div>
                    <div v-if="!editando" class="flex flex-col gap-2">
                        <label class="text-sm font-medium">Senha inicial</label>
                        <Password
                            v-model="form.password"
                            toggleMask
                            :feedback="false"
                            class="w-full"
                            inputClass="w-full"
                            autocomplete="new-password"
                        />
                    </div>
                    <template v-else>
                        <div class="flex items-center gap-2">
                            <Checkbox v-model="alterarSenha" inputId="alterar-senha" binary />
                            <label for="alterar-senha" class="text-sm cursor-pointer">Alterar senha</label>
                        </div>
                        <div v-if="alterarSenha" class="flex flex-col gap-2">
                            <label class="text-sm font-medium">Nova senha</label>
                            <Password
                                v-model="form.password"
                                toggleMask
                                :feedback="false"
                                class="w-full"
                                inputClass="w-full"
                                autocomplete="new-password"
                            />
                        </div>
                    </template>

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

<style scoped>
.gestao-dialog-autofill-decoy {
    position: absolute;
    width: 0;
    height: 0;
    opacity: 0;
    pointer-events: none;
    overflow: hidden;
}
</style>
