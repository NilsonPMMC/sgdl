<script setup>
import { computed, onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';
import { useUserStore } from '@/stores/userStore';
import { extrairPaginaResposta, paramsPagina } from '@/utils/serverTable';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import Divider from 'primevue/divider';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import Select from 'primevue/select';
import TabPanel from 'primevue/tabpanel';
import TabView from 'primevue/tabview';
import Tag from 'primevue/tag';
import ToggleSwitch from 'primevue/toggleswitch';
import { useConfirm } from 'primevue/useconfirm';

const toast = useToast();
const confirm = useConfirm();
const userStore = useUserStore();
const podeGerir = computed(() =>
    ['GESTOR'].includes(userStore.currentUser?.perfil)
);

const loading = ref(false);
const loadingDepara = ref(false);
const setores = ref([]);
const totalSetores = ref(0);
const tablePagination = ref({ first: 0, rows: 25 });
const tabelaJaCarregada = ref(false);
const depara = ref([]);
const orgaos = ref([]);
const usuariosSecretaria = ref([]);

const busca = ref('');
const buscaAplicada = ref('');
const filtroOrgao = ref(null);
const filtroOrgaoAplicado = ref(null);
const filtroAtivo = ref(null);
const filtroAtivoAplicado = ref(null);

const dialogGerenciar = ref(false);
const salvando = ref(false);
const carregandoModal = ref(false);
const modoModal = ref('novo');
const vinculos = ref(null);

const formSetor = ref({
    id: null,
    sinapse_orgao_id: null,
    nome: '',
    sigla: '',
    ativo: true
});
const responsaveis = ref([]);
const novoResponsavelId = ref(null);
const excluirDestinoId = ref(null);

const ATIVO_OPCOES = [
    { label: 'Todos', value: null },
    { label: 'Ativos', value: true },
    { label: 'Inativos', value: false }
];

const tituloModal = computed(() =>
    modoModal.value === 'novo' ? 'Novo setor' : `Gerenciar setor — ${formSetor.value.sigla || formSetor.value.nome || ''}`
);

const orgaosFiltro = computed(() => [
    { label: 'Todos os órgãos', value: null },
    ...orgaos.value
]);

const resetPaginaSetores = () => {
    tablePagination.value = { ...tablePagination.value, first: 0 };
};

const aplicarFiltrosSetores = () => {
    buscaAplicada.value = (busca.value || '').trim();
    filtroOrgaoAplicado.value = filtroOrgao.value;
    filtroAtivoAplicado.value = filtroAtivo.value;
    resetPaginaSetores();
    loadSetores();
};

const onPageSetores = (event) => {
    tablePagination.value = { first: event.first, rows: event.rows };
    tabelaJaCarregada.value = true;
    loadSetores();
};

const opcoesDestinoExclusao = computed(() => {
    if (!formSetor.value.id) return [];
    return setores.value
        .filter((s) => s.id !== formSetor.value.id && s.ativo)
        .map((s) => ({
            label: s.sigla ? `${s.sigla} — ${s.nome}` : s.nome,
            value: s.id,
            orgao: s.orgao_nome
        }));
});

const precisaDestinoExclusao = computed(() => {
    if (!vinculos.value) return false;
    return (vinculos.value.demandas || 0) > 0 || (vinculos.value.servicos_carta || 0) > 0;
});

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    return 'Operação não concluída.';
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

const loadDepara = async () => {
    if (!podeGerir.value) return;
    loadingDepara.value = true;
    try {
        const { data } = await ApiService.listarDeParaRmSinapse();
        depara.value = Array.isArray(data) ? data : data?.results || [];
    } catch {
        depara.value = [];
    } finally {
        loadingDepara.value = false;
    }
};

const salvarDepara = async (row) => {
    try {
        await ApiService.atualizarDeParaRmSinapse(row.id, {
            sinapse_orgao_id: row.sinapse_orgao_id || null,
            ativo: row.ativo,
            observacao: row.observacao || ''
        });
        toast.add({ severity: 'success', summary: 'De-para salvo', detail: row.cod_rm, life: 2000 });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'De-para', detail: extrairErro(error), life: 4000 });
    }
};

const loadSetores = async () => {
    loading.value = true;
    try {
        const extra = paramsPagina(tablePagination.value, {
            q: buscaAplicada.value || undefined,
            sinapse_orgao_id: filtroOrgaoAplicado.value || undefined
        });
        if (podeGerir.value) {
            extra.incluir_inativos = '1';
            if (filtroAtivoAplicado.value === true) extra.ativo = '1';
            if (filtroAtivoAplicado.value === false) extra.ativo = '0';
        } else if (filtroAtivoAplicado.value === false) {
            extra.ativo = '0';
        }
        const { data } = await ApiService.listarUnidadesAdministrativas(extra);
        const { rows, total } = extrairPaginaResposta({ data });
        setores.value = rows;
        totalSetores.value = total;
    } catch (error) {
        setores.value = [];
        totalSetores.value = 0;
        toast.add({ severity: 'error', summary: 'Setores', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const carregarUsuariosSecretaria = async (orgaoId) => {
    try {
        const params = { perfil: 'SECRETARIA' };
        const { data } = await ApiService.getUsuarios(params);
        const lista = data?.results || data || [];
        usuariosSecretaria.value = lista
            .filter((u) => !orgaoId || u.sinapse_orgao_id === orgaoId)
            .map((u) => ({
                label: u.first_name ? `${u.first_name} ${u.last_name || ''}`.trim() : u.username,
                value: u.id
            }));
    } catch {
        usuariosSecretaria.value = [];
    }
};

const abrirNovo = async () => {
    modoModal.value = 'novo';
    formSetor.value = { id: null, sinapse_orgao_id: null, nome: '', sigla: '', ativo: true };
    responsaveis.value = [];
    vinculos.value = null;
    novoResponsavelId.value = null;
    excluirDestinoId.value = null;
    dialogGerenciar.value = true;
};

const abrirGerenciar = async (row) => {
    modoModal.value = 'editar';
    formSetor.value = {
        id: row.id,
        sinapse_orgao_id: row.sinapse_orgao_id,
        nome: row.nome,
        sigla: row.sigla || '',
        ativo: row.ativo !== false
    };
    responsaveis.value = [...(row.responsaveis || [])];
    novoResponsavelId.value = null;
    excluirDestinoId.value = null;
    vinculos.value = null;
    dialogGerenciar.value = true;
    carregandoModal.value = true;
    await Promise.all([
        carregarUsuariosSecretaria(row.sinapse_orgao_id),
        ApiService.getVinculosSetor(row.id)
            .then(({ data }) => {
                vinculos.value = data;
            })
            .catch(() => {
                vinculos.value = null;
            })
    ]);
    carregandoModal.value = false;
};

const salvarSetor = async () => {
    if (!formSetor.value.sinapse_orgao_id || !formSetor.value.nome?.trim()) {
        toast.add({ severity: 'warn', summary: 'Campos obrigatórios', detail: 'Órgão e nome são obrigatórios.', life: 3000 });
        return;
    }
    salvando.value = true;
    try {
        if (modoModal.value === 'novo') {
            const { data } = await ApiService.criarUnidadeAdministrativa({
                sinapse_orgao_id: formSetor.value.sinapse_orgao_id,
                nome: formSetor.value.nome.trim(),
                sigla: formSetor.value.sigla?.trim() || ''
            });
            toast.add({ severity: 'success', summary: 'Setor criado', detail: data.nome, life: 2500 });
            dialogGerenciar.value = false;
        } else {
            await ApiService.atualizarUnidadeAdministrativa(formSetor.value.id, {
                nome: formSetor.value.nome.trim(),
                sigla: formSetor.value.sigla?.trim() || '',
                ativo: formSetor.value.ativo
            });
            toast.add({ severity: 'success', summary: 'Setor atualizado', life: 2500 });
        }
        await loadSetores();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvando.value = false;
    }
};

const vincularResponsavel = async () => {
    if (!formSetor.value.id || !novoResponsavelId.value) return;
    salvando.value = true;
    try {
        const { data } = await ApiService.vincularResponsavelSetor(formSetor.value.id, {
            usuario_id: novoResponsavelId.value
        });
        responsaveis.value = [
            ...responsaveis.value.filter((r) => r.usuario_id !== data.usuario_id),
            data
        ];
        novoResponsavelId.value = null;
        toast.add({ severity: 'success', summary: 'Responsável vinculado', life: 2000 });
        await loadSetores();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvando.value = false;
    }
};

const desvincularResponsavel = async (resp) => {
    if (!formSetor.value.id || !resp?.usuario_id) return;
    salvando.value = true;
    try {
        await ApiService.desvincularResponsavelSetor(formSetor.value.id, {
            usuario_id: resp.usuario_id
        });
        responsaveis.value = responsaveis.value.filter((r) => r.usuario_id !== resp.usuario_id);
        toast.add({ severity: 'info', summary: 'Responsável removido', life: 2000 });
        await loadSetores();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvando.value = false;
    }
};

const confirmarExclusao = () => {
    if (precisaDestinoExclusao.value && !excluirDestinoId.value) {
        toast.add({
            severity: 'warn',
            summary: 'Destino obrigatório',
            detail: 'Selecione para qual setor redirecionar os processos vinculados.',
            life: 4000
        });
        return;
    }
    confirm.require({
        message: precisaDestinoExclusao.value
            ? `Demandas e vínculos da carta serão redirecionados antes da exclusão de «${formSetor.value.nome}».`
            : `Excluir permanentemente o setor «${formSetor.value.nome}»?`,
        header: 'Confirmar exclusão',
        icon: 'pi pi-exclamation-triangle',
        rejectLabel: 'Cancelar',
        acceptLabel: 'Excluir',
        acceptClass: 'p-button-danger',
        accept: excluirSetor
    });
};

const excluirSetor = async () => {
    if (!formSetor.value.id) return;
    salvando.value = true;
    try {
        const payload = precisaDestinoExclusao.value
            ? { unidade_destino_id: excluirDestinoId.value }
            : {};
        const { data } = await ApiService.excluirUnidadeAdministrativa(formSetor.value.id, payload);
        toast.add({
            severity: 'success',
            summary: 'Setor excluído',
            detail: data.demandas_redirecionadas
                ? `${data.demandas_redirecionadas} demanda(s) → ${data.unidade_destino_nome}`
                : formSetor.value.nome,
            life: 4000
        });
        dialogGerenciar.value = false;
        await loadSetores();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Exclusão', detail: extrairErro(error), life: 5000 });
    } finally {
        salvando.value = false;
    }
};

onMounted(async () => {
    if (podeGerir.value) {
        await loadOrgaos();
        await loadDepara();
    }
    setTimeout(() => {
        if (!tabelaJaCarregada.value) {
            tabelaJaCarregada.value = true;
            loadSetores();
        }
    }, 80);
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
                <h1 class="text-2xl font-semibold m-0">Setores (unidades administrativas)</h1>
                <p class="text-muted-color m-0 mt-1">
                    Cadastro de setores por órgão, responsáveis e redirecionamento de processos na exclusão.
                </p>
            </div>
            <div class="flex flex-wrap gap-2">
                <Button v-if="podeGerir" label="Novo setor" icon="pi pi-plus" @click="abrirNovo" />
            </div>
        </div>

        <Message v-if="!podeGerir" severity="info" :closable="false">
            Visualização dos setores do seu órgão. Encaminhamentos operacionais usam estes cadastros.
        </Message>

        <TabView class="sgdl-setores-tabs">
            <TabPanel header="Setores">
                <Card>
                    <template #content>
                        <div class="flex flex-wrap gap-3 mb-4">
                            <IconField class="flex-1 min-w-[14rem]">
                                <InputIcon class="pi pi-search" />
                                <InputText
                                    v-model="busca"
                                    placeholder="Buscar sigla, nome ou órgão..."
                                    fluid
                                    @keyup.enter="aplicarFiltrosSetores"
                                />
                            </IconField>
                            <Select
                                v-model="filtroOrgao"
                                :options="orgaosFiltro"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Órgão"
                                filter
                                showClear
                                class="min-w-[12rem]"
                                @change="aplicarFiltrosSetores"
                            />
                            <Select
                                v-model="filtroAtivo"
                                :options="ATIVO_OPCOES"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Status"
                                class="min-w-[10rem]"
                                @change="aplicarFiltrosSetores"
                            />
                            <Button label="Filtrar" icon="pi pi-filter" outlined @click="aplicarFiltrosSetores" />
                        </div>
                        <DataTable
                            :value="setores"
                            :loading="loading"
                            lazy
                            stripedRows
                            paginator
                            :rows="tablePagination.rows"
                            :first="tablePagination.first"
                            :totalRecords="totalSetores"
                            :rowsPerPageOptions="[15, 25, 50, 100]"
                            paginatorTemplate="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
                            currentPageReportTemplate="Mostrando {first} a {last} de {totalRecords}"
                            dataKey="id"
                            responsiveLayout="scroll"
                            class="sgdl-table-scroll"
                            @page="onPageSetores"
                        >
                            <Column field="sigla" header="Sigla" style="width: 6rem" />
                            <Column field="nome" header="Nome" />
                            <Column field="orgao_nome" header="Órgão" />
                            <Column header="Responsáveis" style="width: 10rem">
                                <template #body="{ data }">
                                    <Tag
                                        :value="String((data.responsaveis || []).length)"
                                        :severity="(data.responsaveis || []).length ? 'info' : 'secondary'"
                                    />
                                </template>
                            </Column>
                            <Column header="Ativo" style="width: 6rem">
                                <template #body="{ data }">
                                    <Tag :value="data.ativo ? 'Sim' : 'Não'" :severity="data.ativo ? 'success' : 'danger'" />
                                </template>
                            </Column>
                            <Column v-if="podeGerir" header="" style="width: 8rem">
                                <template #body="{ data }">
                                    <Button
                                        label="Gerenciar"
                                        icon="pi pi-cog"
                                        size="small"
                                        outlined
                                        @click="abrirGerenciar(data)"
                                    />
                                </template>
                            </Column>
                        </DataTable>
                    </template>
                </Card>
            </TabPanel>

            <TabPanel v-if="podeGerir" header="De-para RM ↔ Sinapse">
                <Card>
                    <template #content>
                        <Message severity="info" :closable="false" class="text-sm mb-3">
                            Mapeie o código da secretaria na planilha RM (ex.: SMSBE) para o órgão Sinapse.
                            Importação de planilhas e carga inicial ficam no Django Admin.
                        </Message>
                        <DataTable
                            :value="depara"
                            :loading="loadingDepara"
                            stripedRows
                            size="small"
                            paginator
                            :rows="15"
                            responsiveLayout="scroll"
                        >
                            <Column field="cod_rm" header="COD_RM" />
                            <Column header="Órgão Sinapse">
                                <template #body="{ data }">
                                    <Select
                                        v-model="data.sinapse_orgao_id"
                                        :options="orgaos"
                                        optionLabel="label"
                                        optionValue="value"
                                        placeholder="Pendente"
                                        showClear
                                        filter
                                        class="w-full"
                                        @change="salvarDepara(data)"
                                    />
                                </template>
                            </Column>
                            <Column field="orgao_nome" header="Nome Sinapse" />
                            <Column header="Ativo" style="width: 6rem">
                                <template #body="{ data }">
                                    <ToggleSwitch v-model="data.ativo" @change="salvarDepara(data)" />
                                </template>
                            </Column>
                            <Column field="observacao" header="Obs." />
                        </DataTable>
                    </template>
                </Card>
            </TabPanel>
        </TabView>

        <Dialog
            v-model:visible="dialogGerenciar"
            :header="tituloModal"
            modal
            style="width: min(40rem, 96vw)"
            :closable="!salvando"
        >
            <div v-if="carregandoModal" class="flex justify-center py-8">
                <i class="pi pi-spin pi-spinner text-2xl" />
            </div>
            <div v-else class="flex flex-col gap-4">
                <div class="flex flex-col gap-2">
                    <label class="font-medium text-sm">Órgão (Sinapse)</label>
                    <Select
                        v-model="formSetor.sinapse_orgao_id"
                        :options="orgaos"
                        optionLabel="label"
                        optionValue="value"
                        placeholder="Selecione o órgão"
                        filter
                        class="w-full"
                        :disabled="modoModal === 'editar'"
                        @change="carregarUsuariosSecretaria(formSetor.sinapse_orgao_id)"
                    />
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div class="flex flex-col gap-2">
                        <label class="font-medium text-sm">Nome</label>
                        <InputText v-model="formSetor.nome" placeholder="Nome do setor" />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label class="font-medium text-sm">Sigla</label>
                        <InputText v-model="formSetor.sigla" placeholder="Sigla" maxlength="32" />
                    </div>
                </div>
                <div v-if="modoModal === 'editar'" class="flex items-center justify-between gap-3">
                    <span class="font-medium text-sm">Setor ativo</span>
                    <ToggleSwitch v-model="formSetor.ativo" />
                </div>

                <template v-if="modoModal === 'editar'">
                    <Divider />

                    <div>
                        <h4 class="font-semibold m-0 mb-2">Responsáveis</h4>
                        <ul v-if="responsaveis.length" class="list-none p-0 m-0 mb-3 flex flex-col gap-2">
                            <li
                                v-for="r in responsaveis"
                                :key="r.id"
                                class="flex items-center justify-between gap-2 py-1 border-b border-surface-200 dark:border-surface-700 last:border-0"
                            >
                                <span class="text-sm">{{ r.usuario_nome || r.usuario_id }}</span>
                                <Button
                                    icon="pi pi-times"
                                    text
                                    rounded
                                    severity="danger"
                                    size="small"
                                    :disabled="salvando"
                                    @click="desvincularResponsavel(r)"
                                />
                            </li>
                        </ul>
                        <p v-else class="text-sm text-muted-color m-0 mb-3">Nenhum responsável vinculado.</p>
                        <div class="flex flex-wrap gap-2">
                            <Select
                                v-model="novoResponsavelId"
                                :options="usuariosSecretaria"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Usuário (Secretaria / Protocolo)"
                                filter
                                showClear
                                class="flex-1 min-w-[14rem]"
                            />
                            <Button
                                label="Vincular"
                                icon="pi pi-user-plus"
                                :disabled="!novoResponsavelId || salvando"
                                :loading="salvando"
                                @click="vincularResponsavel"
                            />
                        </div>
                    </div>

                    <Divider />

                    <div>
                        <h4 class="font-semibold m-0 mb-2">Excluir setor</h4>
                        <Message v-if="vinculos" severity="warn" :closable="false" class="text-sm mb-3">
                            Vínculos: {{ vinculos.demandas }} demanda(s)
                            <span v-if="vinculos.demandas_abertas"> ({{ vinculos.demandas_abertas }} em aberto)</span>,
                            {{ vinculos.servicos_carta }} serviço(s) na carta.
                        </Message>
                        <div v-if="precisaDestinoExclusao" class="flex flex-col gap-2 mb-3">
                            <label class="font-medium text-sm">Redirecionar processos para</label>
                            <Select
                                v-model="excluirDestinoId"
                                :options="opcoesDestinoExclusao"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Setor de destino"
                                filter
                                class="w-full"
                            />
                            <p class="text-xs text-muted-color m-0">
                                Demandas operacionais e vínculos da carta serão transferidos antes da exclusão.
                            </p>
                        </div>
                        <Button
                            label="Excluir setor"
                            icon="pi pi-trash"
                            severity="danger"
                            outlined
                            :loading="salvando"
                            @click="confirmarExclusao"
                        />
                    </div>
                </template>
            </div>
            <template #footer>
                <Button label="Cancelar" text :disabled="salvando" @click="dialogGerenciar = false" />
                <Button
                    :label="modoModal === 'novo' ? 'Criar' : 'Salvar'"
                    icon="pi pi-check"
                    :loading="salvando"
                    @click="salvarSetor"
                />
            </template>
        </Dialog>
    </div>
</template>
