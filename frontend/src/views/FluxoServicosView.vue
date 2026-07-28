<script setup>
import { onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';
import { extrairPaginaResposta, paramsPagina } from '@/utils/serverTable';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import Select from 'primevue/select';
import Tag from 'primevue/tag';
import ToggleSwitch from 'primevue/toggleswitch';

const toast = useToast();

const SEM_VINCULO = 0;
const SEM_ASSUNTO = 0;

const MODO_OPCOES = [
    { label: 'Triagem manual (Protocolo)', value: 'MANUAL' },
    { label: 'Despacho automático', value: 'AUTOMATICO' }
];

const MODO_UTILIZACAO_OPCOES = [
    { label: '— Herdar do assunto —', value: '' },
    { label: 'Protocolável', value: 'PROTOCOLAVEL' },
    { label: 'Somente orientação', value: 'INFORMATIVO' },
    { label: 'Protocolável com condição', value: 'PROTOCOLAVEL_CONDICIONAL' }
];

const loading = ref(false);
const salvandoModal = ref(false);
const servicos = ref([]);
const totalServicos = ref(0);
const assuntosCarta = ref([]);
const busca = ref('');
const buscaAplicada = ref('');
const filtroOrgao = ref(null);
const filtroOrgaoAplicado = ref(null);
const orgaosOpcoes = ref([{ label: 'Todos os órgãos', value: null }]);
const tablePagination = ref({ first: 0, rows: 25 });
const tabelaJaCarregada = ref(false);
const unidadesPorOrgao = ref({});
const dialogGerenciar = ref(false);
const linhaAtiva = ref(null);

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    return 'Operação não concluída.';
};

const loadOrgaos = async () => {
    try {
        const { data } = await ApiService.listarOrgaosSetores();
        const lista = data?.results || data || [];
        orgaosOpcoes.value = [
            { label: 'Todos os órgãos', value: null },
            ...lista.map((o) => ({
                label: o.nome || o.label || `Órgão ${o.id}`,
                value: o.id
            }))
        ];
    } catch {
        orgaosOpcoes.value = [{ label: 'Todos os órgãos', value: null }];
    }
};

const resetPaginaServicos = () => {
    tablePagination.value = { ...tablePagination.value, first: 0 };
};

const aplicarFiltrosServicos = () => {
    buscaAplicada.value = (busca.value || '').trim();
    filtroOrgaoAplicado.value = filtroOrgao.value;
    resetPaginaServicos();
    loadServicos();
};

const onPageServicos = (event) => {
    tablePagination.value = { first: event.first, rows: event.rows };
    tabelaJaCarregada.value = true;
    loadServicos();
};

const normalizarLinha = (s) => ({
    ...s,
    assunto_id: s.utilizacao_sgdl?.assunto_id ?? s.assunto_id ?? SEM_ASSUNTO,
    unidade_administrativa_id: s.unidade_administrativa_id ?? SEM_VINCULO,
    modo_utilizacao_sgdl: s.utilizacao_sgdl?.modo_servico ?? ''
});

const garantirUnidadesOrgao = async (orgaoId) => {
    if (!orgaoId || unidadesPorOrgao.value[orgaoId]) return;
    try {
        const { data } = await ApiService.listarUnidadesAdministrativas({
            sinapse_orgao_id: orgaoId
        });
        unidadesPorOrgao.value[orgaoId] = data?.results || data || [];
    } catch {
        unidadesPorOrgao.value[orgaoId] = [];
    }
};

const loadServicos = async () => {
    loading.value = true;
    try {
        const params = paramsPagina(tablePagination.value, {
            q: buscaAplicada.value || undefined,
            orgao_id: filtroOrgaoAplicado.value || undefined
        });
        const [servicosResp, assuntosResp] = await Promise.all([
            ApiService.listarFluxoServicosCarta(params),
            assuntosCarta.value.length
                ? Promise.resolve({ data: assuntosCarta.value })
                : ApiService.listarAssuntosCarta()
        ]);
        if (!assuntosCarta.value.length) {
            assuntosCarta.value = assuntosResp.data?.results || assuntosResp.data || [];
        }
        const { rows, total } = extrairPaginaResposta(servicosResp);
        servicos.value = rows.map(normalizarLinha);
        totalServicos.value = total;
        const orgaos = [...new Set(servicos.value.map((s) => s.orgao_id).filter(Boolean))];
        await Promise.all(orgaos.map((id) => garantirUnidadesOrgao(id)));
    } catch (error) {
        servicos.value = [];
        totalServicos.value = 0;
        toast.add({ severity: 'error', summary: 'Fluxo', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const opcoesSetor = (row) => {
    const base = [{ label: '— Sem vínculo explícito —', value: SEM_VINCULO }];
    const lista = unidadesPorOrgao.value[row?.orgao_id] || [];
    return base.concat(
        lista.map((u) => ({
            label: u.sigla ? `${u.sigla} — ${u.nome}` : u.nome,
            value: u.id
        }))
    );
};

const opcoesAssunto = () => {
    const base = [{ label: '— Sem assunto —', value: SEM_ASSUNTO }];
    return base.concat(
        assuntosCarta.value.map((a) => ({
            label: a.nome,
            value: a.id
        }))
    );
};

const rotuloSetorSugerido = (row) => {
    const s = row?.setor_sugerido;
    if (!s) return null;
    return s.sigla || s.nome;
};

const rotuloModoFluxo = (row) => {
    if (row.modo === 'AUTOMATICO' && row.ativo) return { label: 'Automático', severity: 'success' };
    return { label: 'Manual', severity: 'secondary' };
};

const abrirGerenciar = async (row) => {
    linhaAtiva.value = { ...normalizarLinha(row) };
    if (row.orgao_id) await garantirUnidadesOrgao(row.orgao_id);
    dialogGerenciar.value = true;
};

const salvarModal = async () => {
    const row = linhaAtiva.value;
    if (!row?.sinapse_servico_id) return;
    salvandoModal.value = true;
    try {
        await ApiService.upsertFluxoServico({
            sinapse_servico_id: row.sinapse_servico_id,
            modo: row.modo,
            ativo: row.ativo
        });
        await ApiService.upsertCartaSetor({
            sinapse_servico_id: row.sinapse_servico_id,
            unidade_administrativa_id:
                row.unidade_administrativa_id === SEM_VINCULO ? null : row.unidade_administrativa_id
        });
        const assuntoPayload = {
            sinapse_servico_id: row.sinapse_servico_id,
            assunto_id: row.assunto_id === SEM_ASSUNTO ? null : row.assunto_id,
            modo_utilizacao_sgdl: row.modo_utilizacao_sgdl ?? ''
        };
        const { data: assuntoData } = await ApiService.upsertCartaAssunto(assuntoPayload);

        const idx = servicos.value.findIndex((s) => s.sinapse_servico_id === row.sinapse_servico_id);
        const atualizado = normalizarLinha({
            ...row,
            ...assuntoData,
            unidade_administrativa_id:
                row.unidade_administrativa_id === SEM_VINCULO ? null : row.unidade_administrativa_id,
            assunto_id: assuntoPayload.assunto_id ?? SEM_ASSUNTO
        });
        if (idx >= 0) servicos.value[idx] = atualizado;

        toast.add({ severity: 'success', summary: 'Salvo', detail: row.titulo, life: 2500 });
        dialogGerenciar.value = false;
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvandoModal.value = false;
    }
};

onMounted(async () => {
    await loadOrgaos();
    buscaAplicada.value = '';
    filtroOrgaoAplicado.value = null;
    setTimeout(() => {
        if (!tabelaJaCarregada.value) {
            tabelaJaCarregada.value = true;
            loadServicos();
        }
    }, 80);
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div>
            <h2 class="text-2xl font-semibold m-0">Gestão de fluxo por serviço</h2>
            <p class="text-surface-600 dark:text-surface-300 mt-1 mb-0 text-sm">
                Defina despacho automático, setor operacional e classificação temática por serviço da carta.
            </p>
        </div>

        <Message severity="info" :closable="false" class="text-sm m-0">
            Serviços em <strong>Despacho automático</strong> são protocolados ao receber o ofício do vereador.
            Use <strong>Gerenciar</strong> para editar setor, assunto e modo de utilização.
        </Message>

        <Card>
            <template #title>Carta de serviços</template>
            <template #content>
                <div class="flex flex-wrap gap-3 mb-4">
                    <IconField class="flex-1 min-w-[14rem]">
                        <InputIcon class="pi pi-search" />
                        <InputText
                            v-model="busca"
                            placeholder="Buscar serviço, ID ou órgão..."
                            fluid
                            @keyup.enter="aplicarFiltrosServicos"
                        />
                    </IconField>
                    <Select
                        v-model="filtroOrgao"
                        :options="orgaosOpcoes"
                        optionLabel="label"
                        optionValue="value"
                        placeholder="Órgão"
                        filter
                        showClear
                        class="min-w-[14rem]"
                        @change="aplicarFiltrosServicos"
                    />
                    <Button label="Filtrar" icon="pi pi-filter" outlined @click="aplicarFiltrosServicos" />
                    <Button label="Recarregar" icon="pi pi-refresh" outlined @click="loadServicos" />
                </div>

                <DataTable
                    :value="servicos"
                    :loading="loading"
                    lazy
                    stripedRows
                    size="small"
                    paginator
                    :rows="tablePagination.rows"
                    :first="tablePagination.first"
                    :totalRecords="totalServicos"
                    :rowsPerPageOptions="[15, 25, 50, 100]"
                    paginatorTemplate="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
                    currentPageReportTemplate="Mostrando {first} a {last} de {totalRecords}"
                    responsiveLayout="scroll"
                    class="sgdl-table-scroll"
                    @page="onPageServicos"
                >
                    <Column field="titulo" header="Serviço">
                        <template #body="{ data }">
                            <span class="font-medium">{{ data.titulo }}</span>
                            <p class="text-xs text-surface-500 m-0">ID Sinapse {{ data.sinapse_servico_id }}</p>
                        </template>
                    </Column>
                    <Column field="orgao_nome" header="Órgão" />
                    <Column header="Setor">
                        <template #body="{ data }">
                            <span class="text-sm">
                                {{
                                    data.unidade_administrativa_id && data.unidade_administrativa_id !== SEM_VINCULO
                                        ? opcoesSetor(data).find((o) => o.value === data.unidade_administrativa_id)
                                              ?.label || '—'
                                        : rotuloSetorSugerido(data) || '—'
                                }}
                            </span>
                        </template>
                    </Column>
                    <Column header="Fluxo" style="width: 8rem">
                        <template #body="{ data }">
                            <Tag :value="rotuloModoFluxo(data).label" :severity="rotuloModoFluxo(data).severity" />
                        </template>
                    </Column>
                    <Column header="" style="width: 7rem">
                        <template #body="{ data }">
                            <Button label="Gerenciar" icon="pi pi-cog" size="small" outlined @click="abrirGerenciar(data)" />
                        </template>
                    </Column>
                </DataTable>
            </template>
        </Card>

        <Dialog
            v-model:visible="dialogGerenciar"
            :header="linhaAtiva?.titulo || 'Gerenciar serviço'"
            modal
            style="width: min(36rem, 96vw)"
        >
            <div v-if="linhaAtiva" class="flex flex-col gap-4">
                <p class="text-sm text-surface-500 m-0">
                    ID Sinapse {{ linhaAtiva.sinapse_servico_id }}
                    <span v-if="linhaAtiva.orgao_nome"> · {{ linhaAtiva.orgao_nome }}</span>
                </p>

                <div class="flex flex-col gap-2">
                    <label class="font-medium text-sm">Setor (carta)</label>
                    <Select
                        v-model="linhaAtiva.unidade_administrativa_id"
                        :options="opcoesSetor(linhaAtiva)"
                        optionLabel="label"
                        optionValue="value"
                        filter
                        placeholder="Selecione o setor"
                        class="w-full"
                        :disabled="!linhaAtiva.orgao_id"
                    />
                    <p
                        v-if="rotuloSetorSugerido(linhaAtiva) && linhaAtiva.setor_origem === 'ORGAO'"
                        class="text-xs text-surface-500 m-0"
                    >
                        Fallback órgão: {{ rotuloSetorSugerido(linhaAtiva) }}
                    </p>
                </div>

                <div class="flex flex-col gap-2">
                    <label class="font-medium text-sm">Assunto temático</label>
                    <Select
                        v-model="linhaAtiva.assunto_id"
                        :options="opcoesAssunto()"
                        optionLabel="label"
                        optionValue="value"
                        filter
                        placeholder="Classificação"
                        class="w-full"
                    />
                </div>

                <div class="flex flex-col gap-2">
                    <label class="font-medium text-sm">Utilização SGDL</label>
                    <Select
                        v-model="linhaAtiva.modo_utilizacao_sgdl"
                        :options="MODO_UTILIZACAO_OPCOES"
                        optionLabel="label"
                        optionValue="value"
                        class="w-full"
                    />
                </div>

                <div class="flex flex-col gap-2">
                    <label class="font-medium text-sm">Modo de fluxo (Protocolo)</label>
                    <Select
                        v-model="linhaAtiva.modo"
                        :options="MODO_OPCOES"
                        optionLabel="label"
                        optionValue="value"
                        class="w-full"
                    />
                </div>

                <div class="flex items-center justify-between gap-3">
                    <span class="font-medium text-sm">Despacho automático ativo</span>
                    <ToggleSwitch v-model="linhaAtiva.ativo" />
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" text @click="dialogGerenciar = false" />
                <Button label="Salvar" icon="pi pi-check" :loading="salvandoModal" @click="salvarModal" />
            </template>
        </Dialog>
    </div>
</template>
