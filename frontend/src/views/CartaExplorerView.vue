<script setup>
import { computed, onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';
import { useUserStore } from '@/stores/userStore';

import Badge from 'primevue/badge';
import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import Select from 'primevue/select';
import TabPanel from 'primevue/tabpanel';
import TabView from 'primevue/tabview';
import Tag from 'primevue/tag';
import Textarea from 'primevue/textarea';

const toast = useToast();
const userStore = useUserStore();

const podeAdmin = computed(() => userStore.currentUser?.perfil === 'GESTOR');

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.erro) return String(data.erro);
    if (data?.detail) return String(data.detail);
    return 'Operação não concluída.';
};

const formatarScore = (score) => {
    if (score == null || Number.isNaN(Number(score))) return '—';
    return Number(score).toFixed(1);
};

const formatarPercentual = (valor) => {
    if (valor == null || Number.isNaN(Number(valor))) return '—';
    return `${Number(valor).toFixed(1)}%`;
};

const getScoreColor = (score) => {
    if (score >= 8) return 'success';
    if (score >= 6) return 'info';
    if (score >= 4) return 'warning';
    return 'danger';
};

// —— Consulta (todos) ——
const loadingConsulta = ref(false);
const servicosConsulta = ref([]);
const totalConsulta = ref(0);
const catalogoDisponivel = ref(true);
const orgaos = ref([]);

const consultaFiltros = ref({
    q: '',
    orgao_id: null
});
const consultaPaginacao = ref({ first: 0, rows: 15 });

const orgaosOpcoes = computed(() => [
    { label: 'Todos os órgãos', value: null },
    ...orgaos.value
]);

const loadOrgaos = async () => {
    try {
        const { data } = await ApiService.getSecretarias();
        const lista = data?.results || data || [];
        orgaos.value = lista.map((o) => ({ label: o.nome, value: o.id }));
    } catch {
        orgaos.value = [];
    }
};

const loadConsulta = async () => {
    loadingConsulta.value = true;
    try {
        const { first, rows } = consultaPaginacao.value;
        const params = {
            q: consultaFiltros.value.q?.trim() || undefined,
            orgao_id: consultaFiltros.value.orgao_id || undefined,
            limit: rows,
            offset: first
        };
        const { data } = await ApiService.getCartaServicos(params);
        servicosConsulta.value = data?.results || [];
        totalConsulta.value = data?.total ?? servicosConsulta.value.length;
        catalogoDisponivel.value = data?.catalogo_disponivel !== false;
    } catch (error) {
        servicosConsulta.value = [];
        totalConsulta.value = 0;
        toast.add({
            severity: 'error',
            summary: 'Consulta',
            detail: extrairErro(error),
            life: 4000
        });
    } finally {
        loadingConsulta.value = false;
    }
};

const buscarConsulta = () => {
    consultaPaginacao.value.first = 0;
    loadConsulta();
};

const onPageConsulta = (event) => {
    consultaPaginacao.value = { first: event.first, rows: event.rows };
    loadConsulta();
};

const nomeOrgao = (row) =>
    row?.orgao?.nome ||
    row?.secretaria_responsavel?.nome ||
    row?.orgao_nome ||
    '—';

const prazoLabel = (row) => {
    const dias = row?.prazo_efetivo_dias ?? row?.prazo_dias ?? row?.prazo;
    if (dias != null && dias !== '') return `${dias} dias`;
    if (row?.prazo_texto) return row.prazo_texto;
    return '—';
};

const setorLabel = (row) => {
    const u = row?.unidade_administrativa_resumo || row?.unidade_administrativa;
    if (!u) return '—';
    return u.sigla || u.nome || '—';
};

// —— Detalhes (Dialog) ——
const dialogDetalhe = ref(false);
const loadingDetalhe = ref(false);
const detalhe = ref(null);
const detalheOrigem = ref('consulta');

const abrirDetalheConsulta = async (row) => {
    const sid = row?.id ?? row?.sinapse_servico_id;
    if (!sid) return;
    detalheOrigem.value = 'consulta';
    dialogDetalhe.value = true;
    loadingDetalhe.value = true;
    detalhe.value = null;
    try {
        const { data } = await ApiService.getCartaServicoDetalhe(sid);
        detalhe.value = data;
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Detalhe', detail: extrairErro(error), life: 4000 });
        dialogDetalhe.value = false;
    } finally {
        loadingDetalhe.value = false;
    }
};

const abrirDetalheOtimizado = async (row) => {
    detalheOrigem.value = 'otimizacao';
    dialogDetalhe.value = true;
    loadingDetalhe.value = true;
    detalhe.value = null;
    try {
        const { data } = await ApiService.getCartaOtimizadaServico(row.id);
        detalhe.value = data;
    } catch (error) {
        detalhe.value = row;
        toast.add({
            severity: 'warn',
            summary: 'Detalhe',
            detail: 'Exibindo dados da listagem. ' + extrairErro(error),
            life: 3500
        });
    } finally {
        loadingDetalhe.value = false;
    }
};

const tituloDetalhe = computed(() => {
    if (!detalhe.value) return 'Detalhes do serviço';
    if (detalheOrigem.value === 'otimizacao') {
        return detalhe.value.titulo_otimizado || 'Serviço otimizado';
    }
    return detalhe.value.titulo || detalhe.value.nome || 'Serviço';
});

// —— Simulador (todos) ——
const simulacao = ref({ texto: 'Cratera na rua em frente à escola', top_k: 5 });
const resultadoSimulacao = ref(null);
const loadingSimulacao = ref(false);

const executarSimulacao = async () => {
    const texto = (simulacao.value.texto || '').trim();
    if (texto.length < 4) {
        toast.add({
            severity: 'warn',
            summary: 'Simulação',
            detail: 'Descreva o pedido com pelo menos 4 caracteres.',
            life: 3500
        });
        return;
    }
    loadingSimulacao.value = true;
    resultadoSimulacao.value = null;
    try {
        const { data } = await ApiService.simularTriagemCarta({
            texto,
            top_k: simulacao.value.top_k || 5
        });
        resultadoSimulacao.value = data;
        if (!data?.ok) {
            toast.add({
                severity: 'warn',
                summary: 'Simulação',
                detail: data?.erro || 'Nenhum serviço encontrado.',
                life: 4000
            });
        }
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Simulação', detail: extrairErro(error), life: 4000 });
    } finally {
        loadingSimulacao.value = false;
    }
};

const scoreSimulacaoLabel = (score) => {
    if (score == null) return '—';
    const pct = score <= 1 ? score * 100 : score;
    return `${Number(pct).toFixed(1)}%`;
};

// —— Admin: Otimização ——
const loadingOtimizacao = ref(false);
const servicosOtimizados = ref([]);
const totalOtimizacao = ref(0);
const otimizacaoFiltros = ref({
    search: '',
    score_min: null,
    tem_embedding: null
});
const otimizacaoPaginacao = ref({ first: 0, rows: 15 });

const SCORE_OPCOES = [
    { label: 'Todos os scores', value: null },
    { label: 'Score ≥ 8 (Excelente)', value: 8 },
    { label: 'Score ≥ 6 (Bom)', value: 6 },
    { label: 'Score ≥ 4 (Regular)', value: 4 }
];

const EMBEDDING_OPCOES = [
    { label: 'Todos', value: null },
    { label: 'Com embedding', value: true },
    { label: 'Sem embedding', value: false }
];

const loadOtimizacao = async () => {
    if (!podeAdmin.value) return;
    loadingOtimizacao.value = true;
    try {
        const { first, rows } = otimizacaoPaginacao.value;
        const params = {
            search: otimizacaoFiltros.value.search?.trim() || undefined,
            score_min: otimizacaoFiltros.value.score_min ?? undefined,
            tem_embedding:
                otimizacaoFiltros.value.tem_embedding === true
                    ? 'true'
                    : otimizacaoFiltros.value.tem_embedding === false
                      ? 'false'
                      : undefined,
            limit: rows,
            offset: first
        };
        const { data } = await ApiService.getCartaOtimizadaServicos(params);
        servicosOtimizados.value = Array.isArray(data) ? data : data?.results ?? [];
        totalOtimizacao.value = data?.count ?? servicosOtimizados.value.length;
    } catch (error) {
        servicosOtimizados.value = [];
        totalOtimizacao.value = 0;
        toast.add({ severity: 'error', summary: 'Otimização', detail: extrairErro(error), life: 4000 });
    } finally {
        loadingOtimizacao.value = false;
    }
};

const buscarOtimizacao = () => {
    otimizacaoPaginacao.value.first = 0;
    loadOtimizacao();
};

const onPageOtimizacao = (event) => {
    otimizacaoPaginacao.value = { first: event.first, rows: event.rows };
    loadOtimizacao();
};

// —— Admin: Scores ——
const loadingEstatisticas = ref(false);
const loadingComparacao = ref(false);
const estatisticas = ref({});
const comparacaoScores = ref({});

const loadAdminScores = async () => {
    if (!podeAdmin.value) return;
    loadingEstatisticas.value = true;
    loadingComparacao.value = true;
    try {
        const [statsRes, compRes] = await Promise.all([
            ApiService.getCartaOtimizadaEstatisticas(),
            ApiService.getCartaOtimizadaComparacaoScores()
        ]);
        estatisticas.value = statsRes.data || {};
        comparacaoScores.value = compRes.data || {};
    } catch (error) {
        toast.add({ severity: 'warn', summary: 'Scores', detail: extrairErro(error), life: 4000 });
    } finally {
        loadingEstatisticas.value = false;
        loadingComparacao.value = false;
    }
};

// —— Admin: Problemas ——
const loadingProblemas = ref(false);
const problemasComuns = ref([]);

const loadProblemas = async () => {
    if (!podeAdmin.value) return;
    loadingProblemas.value = true;
    try {
        const { data } = await ApiService.getCartaOtimizadaProblemasComuns();
        problemasComuns.value = data?.problemas_comuns ?? data?.problemas_mais_frequentes ?? [];
    } catch (error) {
        problemasComuns.value = [];
        toast.add({ severity: 'warn', summary: 'Problemas', detail: extrairErro(error), life: 4000 });
    } finally {
        loadingProblemas.value = false;
    }
};

const adminCarregado = ref({ scores: false, problemas: false, otimizacao: false });

const onTabChange = (event) => {
    const idx = event.index;
    if (!podeAdmin.value) {
        return;
    }
    const adminOffset = 2;
    if (idx === adminOffset && !adminCarregado.value.otimizacao) {
        adminCarregado.value.otimizacao = true;
        loadOtimizacao();
    } else if (idx === adminOffset + 1 && !adminCarregado.value.scores) {
        adminCarregado.value.scores = true;
        loadAdminScores();
    } else if (idx === adminOffset + 2 && !adminCarregado.value.problemas) {
        adminCarregado.value.problemas = true;
        loadProblemas();
    }
};

onMounted(async () => {
    await Promise.all([loadOrgaos(), loadConsulta()]);
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div>
            <h1 class="text-2xl font-semibold m-0">Carta de Serviços</h1>
            <p class="text-muted-color m-0 mt-1">
                Consulta ao catálogo Sinapse, simulação de triagem semântica
                <template v-if="podeAdmin"> e painéis de otimização da base</template>.
            </p>
        </div>

        <Message v-if="!catalogoDisponivel" severity="warn" :closable="false">
            Catálogo Sinapse indisponível no momento. A listagem pode estar incompleta.
        </Message>

        <TabView class="sgdl-carta-tabs" @tab-change="onTabChange">
            <!-- Consulta — todos -->
            <TabPanel header="Consulta">
                <Card>
                    <template #content>
                        <div class="flex flex-wrap gap-3 mb-4">
                            <IconField class="flex-1 min-w-[14rem]">
                                <InputIcon class="pi pi-search" />
                                <InputText
                                    v-model="consultaFiltros.q"
                                    placeholder="Buscar título, documentos ou texto RAG..."
                                    fluid
                                    @keyup.enter="buscarConsulta"
                                />
                            </IconField>
                            <Select
                                v-model="consultaFiltros.orgao_id"
                                :options="orgaosOpcoes"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Órgão"
                                filter
                                showClear
                                class="min-w-[12rem]"
                            />
                            <Button
                                icon="pi pi-search"
                                label="Buscar"
                                :loading="loadingConsulta"
                                @click="buscarConsulta"
                            />
                        </div>

                        <DataTable
                            :value="servicosConsulta"
                            :loading="loadingConsulta"
                            lazy
                            paginator
                            :rows="consultaPaginacao.rows"
                            :first="consultaPaginacao.first"
                            :totalRecords="totalConsulta"
                            :rowsPerPageOptions="[10, 15, 25, 50]"
                            paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
                            currentPageReportTemplate="{first}–{last} de {totalRecords}"
                            dataKey="id"
                            stripedRows
                            responsiveLayout="scroll"
                            class="sgdl-table-scroll"
                            @page="onPageConsulta"
                        >
                            <Column field="id" header="ID" style="width: 5rem">
                                <template #body="{ data }">
                                    <Badge :value="data.id" severity="secondary" />
                                </template>
                            </Column>
                            <Column header="Serviço" style="min-width: 16rem">
                                <template #body="{ data }">
                                    <div class="font-medium">{{ data.nome || data.titulo }}</div>
                                    <div v-if="data.documentos_resumo" class="text-xs text-muted-color mt-1 line-clamp-2">
                                        {{ data.documentos_resumo }}
                                    </div>
                                </template>
                            </Column>
                            <Column header="Órgão" style="min-width: 10rem">
                                <template #body="{ data }">{{ nomeOrgao(data) }}</template>
                            </Column>
                            <Column header="Prazo" style="width: 7rem">
                                <template #body="{ data }">{{ prazoLabel(data) }}</template>
                            </Column>
                            <Column header="Setor" style="width: 8rem">
                                <template #body="{ data }">{{ setorLabel(data) }}</template>
                            </Column>
                            <Column header="Vector" style="width: 5rem">
                                <template #body="{ data }">
                                    <i
                                        :class="
                                            data.tem_embedding
                                                ? 'pi pi-check-circle text-green-500'
                                                : 'pi pi-minus-circle text-muted-color'
                                        "
                                        v-tooltip.top="data.tem_embedding ? 'Com embedding' : 'Sem embedding'"
                                    />
                                </template>
                            </Column>
                            <Column header="" style="width: 7rem">
                                <template #body="{ data }">
                                    <Button
                                        label="Detalhes"
                                        icon="pi pi-eye"
                                        size="small"
                                        outlined
                                        @click="abrirDetalheConsulta(data)"
                                    />
                                </template>
                            </Column>
                        </DataTable>
                    </template>
                </Card>
            </TabPanel>

            <!-- Simulador — todos -->
            <TabPanel header="Simulador semântico">
                <Card>
                    <template #content>
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="flex flex-col gap-4">
                                <div>
                                    <label class="block text-sm font-medium mb-2">Descreva o pedido do cidadão</label>
                                    <Textarea
                                        v-model="simulacao.texto"
                                        rows="5"
                                        class="w-full"
                                        placeholder="Ex.: Cratera na rua, buraco perigoso em frente à escola..."
                                    />
                                    <small class="text-muted-color">
                                        Usa o mesmo motor de triagem vetorial do Copiloto (embedding + top-K Sinapse).
                                    </small>
                                </div>
                                <div class="flex flex-wrap items-end gap-3">
                                    <div class="flex flex-col gap-1">
                                        <label class="text-sm font-medium">Top-K</label>
                                        <InputText
                                            v-model.number="simulacao.top_k"
                                            type="number"
                                            min="1"
                                            max="10"
                                            class="w-20"
                                        />
                                    </div>
                                    <Button
                                        icon="pi pi-play"
                                        label="Simular triagem"
                                        :loading="loadingSimulacao"
                                        @click="executarSimulacao"
                                    />
                                </div>
                            </div>

                            <div>
                                <div v-if="loadingSimulacao" class="flex justify-center py-10">
                                    <ProgressSpinner />
                                </div>
                                <template v-else-if="resultadoSimulacao">
                                    <div
                                        v-if="resultadoSimulacao.ok"
                                        class="flex flex-col gap-3"
                                    >
                                        <Message severity="info" :closable="false" class="text-sm">
                                            Texto: «{{ resultadoSimulacao.texto }}»
                                            <span v-if="resultadoSimulacao.latencia_total_ms">
                                                — {{ resultadoSimulacao.latencia_total_ms }} ms
                                            </span>
                                        </Message>
                                        <div
                                            v-for="(c, index) in resultadoSimulacao.candidatos"
                                            :key="c.servico_id || index"
                                            class="border border-surface-200 dark:border-surface-700 rounded-lg p-3"
                                        >
                                            <div class="flex justify-between gap-3 items-start">
                                                <div>
                                                    <div class="font-medium flex items-center gap-2">
                                                        <Badge :value="index + 1" severity="secondary" />
                                                        {{ c.titulo || c.nome }}
                                                    </div>
                                                    <div class="text-sm text-muted-color mt-1">
                                                        {{ c.orgao || nomeOrgao(c) }}
                                                        <span v-if="c.prazo_dias"> · {{ c.prazo_dias }} dias</span>
                                                    </div>
                                                </div>
                                                <Tag
                                                    :value="scoreSimulacaoLabel(c.score)"
                                                    :severity="(c.score ?? 0) > 0.7 ? 'success' : (c.score ?? 0) > 0.5 ? 'warning' : 'danger'"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                    <Message v-else severity="warn" :closable="false">
                                        {{ resultadoSimulacao.erro || 'Nenhum serviço adequado encontrado.' }}
                                    </Message>
                                </template>
                                <Message v-else severity="secondary" :closable="false">
                                    Informe um texto e clique em «Simular triagem» para ver os candidatos.
                                </Message>
                            </div>
                        </div>
                    </template>
                </Card>
            </TabPanel>

            <!-- Admin — Gestor -->
            <TabPanel v-if="podeAdmin" header="Otimização">
                <Card>
                    <template #content>
                        <div class="flex flex-wrap gap-3 mb-4">
                            <IconField class="flex-1 min-w-[14rem]">
                                <InputIcon class="pi pi-search" />
                                <InputText
                                    v-model="otimizacaoFiltros.search"
                                    placeholder="Buscar título, intenção ou texto RAG..."
                                    fluid
                                    @keyup.enter="buscarOtimizacao"
                                />
                            </IconField>
                            <Select
                                v-model="otimizacaoFiltros.score_min"
                                :options="SCORE_OPCOES"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Qualidade"
                                showClear
                                class="min-w-[11rem]"
                            />
                            <Select
                                v-model="otimizacaoFiltros.tem_embedding"
                                :options="EMBEDDING_OPCOES"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Embedding"
                                class="min-w-[10rem]"
                            />
                            <Button
                                icon="pi pi-search"
                                label="Buscar"
                                :loading="loadingOtimizacao"
                                @click="buscarOtimizacao"
                            />
                        </div>

                        <DataTable
                            :value="servicosOtimizados"
                            :loading="loadingOtimizacao"
                            lazy
                            paginator
                            :rows="otimizacaoPaginacao.rows"
                            :first="otimizacaoPaginacao.first"
                            :totalRecords="totalOtimizacao"
                            :rowsPerPageOptions="[10, 15, 25, 50]"
                            paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
                            currentPageReportTemplate="{first}–{last} de {totalRecords}"
                            dataKey="id"
                            stripedRows
                            responsiveLayout="scroll"
                            class="sgdl-table-scroll"
                            @page="onPageOtimizacao"
                        >
                            <Column field="sinapse_servico_id" header="ID Sinapse" style="width: 6rem" />
                            <Column header="Serviço otimizado" style="min-width: 16rem">
                                <template #body="{ data }">
                                    <div class="font-medium">{{ data.titulo_otimizado }}</div>
                                    <div class="text-xs text-muted-color mt-1">{{ data.intencao_servico || '—' }}</div>
                                </template>
                            </Column>
                            <Column header="Score" style="width: 8rem">
                                <template #body="{ data }">
                                    <div class="flex flex-col gap-1">
                                        <Tag
                                            :value="formatarScore(data.score_qualidade_otimizado)"
                                            :severity="getScoreColor(data.score_qualidade_otimizado)"
                                        />
                                        <span class="text-xs text-muted-color">
                                            orig. {{ formatarScore(data.score_qualidade_original) }}
                                        </span>
                                    </div>
                                </template>
                            </Column>
                            <Column header="Embedding" style="width: 5rem">
                                <template #body="{ data }">
                                    <Tag
                                        :value="data.tem_embedding ? 'Sim' : 'Não'"
                                        :severity="data.tem_embedding ? 'success' : 'danger'"
                                    />
                                </template>
                            </Column>
                            <Column header="" style="width: 7rem">
                                <template #body="{ data }">
                                    <Button
                                        label="Detalhes"
                                        icon="pi pi-eye"
                                        size="small"
                                        outlined
                                        @click="abrirDetalheOtimizado(data)"
                                    />
                                </template>
                            </Column>
                        </DataTable>
                    </template>
                </Card>
            </TabPanel>

            <TabPanel v-if="podeAdmin" header="Scores">
                <div v-if="loadingEstatisticas || loadingComparacao" class="text-center py-10">
                    <ProgressSpinner />
                </div>
                <div v-else class="flex flex-col gap-4">
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <Card>
                            <template #content>
                                <div class="text-center p-2">
                                    <div class="text-2xl font-bold text-primary">{{ estatisticas.total_servicos ?? '—' }}</div>
                                    <div class="text-sm text-muted-color">Total otimizados</div>
                                </div>
                            </template>
                        </Card>
                        <Card>
                            <template #content>
                                <div class="text-center p-2">
                                    <div class="text-2xl font-bold text-green-500">
                                        {{ formatarPercentual(estatisticas.percentual_cobertura) }}
                                    </div>
                                    <div class="text-sm text-muted-color">Cobertura embedding</div>
                                </div>
                            </template>
                        </Card>
                        <Card>
                            <template #content>
                                <div class="text-center p-2">
                                    <div class="text-2xl font-bold">{{ formatarScore(estatisticas.score_medio) }}</div>
                                    <div class="text-sm text-muted-color">Score médio</div>
                                </div>
                            </template>
                        </Card>
                        <Card>
                            <template #content>
                                <div class="flex justify-center gap-1 text-xs mb-1">
                                    <Tag severity="success" :value="`E: ${estatisticas.distribuicao_scores?.excelente ?? 0}`" />
                                    <Tag severity="info" :value="`B: ${estatisticas.distribuicao_scores?.bom ?? 0}`" />
                                    <Tag severity="warning" :value="`R: ${estatisticas.distribuicao_scores?.regular ?? 0}`" />
                                    <Tag severity="danger" :value="`P: ${estatisticas.distribuicao_scores?.ruim ?? 0}`" />
                                </div>
                                <div class="text-sm text-muted-color text-center">Distribuição</div>
                            </template>
                        </Card>
                    </div>

                    <Card>
                        <template #title>Comparação por faixa de score original</template>
                        <template #content>
                            <DataTable
                                v-if="comparacaoScores.comparacao_por_faixa?.length"
                                :value="comparacaoScores.comparacao_por_faixa"
                                stripedRows
                                size="small"
                            >
                                <Column field="faixa" header="Faixa" />
                                <Column field="quantidade" header="Qtd." />
                                <Column header="Score original">
                                    <template #body="{ data }">{{ formatarScore(data.score_original_medio) }}</template>
                                </Column>
                                <Column header="Score otimizado">
                                    <template #body="{ data }">{{ formatarScore(data.score_otimizado_medio) }}</template>
                                </Column>
                                <Column header="Melhoria">
                                    <template #body="{ data }">
                                        <span class="text-green-600 font-medium">
                                            +{{ formatarScore(data.melhoria_media) }}
                                        </span>
                                    </template>
                                </Column>
                            </DataTable>
                            <Message v-else severity="info" :closable="false">Sem dados de comparação disponíveis.</Message>
                        </template>
                    </Card>
                </div>
            </TabPanel>

            <TabPanel v-if="podeAdmin" header="Problemas">
                <Card>
                    <template #content>
                        <div v-if="loadingProblemas" class="text-center py-10">
                            <ProgressSpinner />
                        </div>
                        <DataTable
                            v-else-if="problemasComuns.length"
                            :value="problemasComuns"
                            stripedRows
                            paginator
                            :rows="15"
                        >
                            <Column field="problema" header="Problema identificado" />
                            <Column field="frequencia" header="Frequência" style="width: 8rem">
                                <template #body="{ data }">
                                    <Badge :value="data.frequencia" severity="secondary" />
                                </template>
                            </Column>
                        </DataTable>
                        <Message v-else severity="info" :closable="false">
                            Nenhum problema recorrente registrado na base otimizada.
                        </Message>
                    </template>
                </Card>
            </TabPanel>
        </TabView>

        <!-- Dialog de detalhes -->
        <Dialog
            v-model:visible="dialogDetalhe"
            :header="tituloDetalhe"
            modal
            style="width: min(44rem, 96vw)"
            :closable="!loadingDetalhe"
        >
            <div v-if="loadingDetalhe" class="flex justify-center py-10">
                <ProgressSpinner />
            </div>
            <div v-else-if="detalhe" class="flex flex-col gap-4 text-sm">
                <!-- Consulta Sinapse -->
                <template v-if="detalheOrigem === 'consulta'">
                    <div class="flex flex-wrap gap-2">
                        <Badge :value="`ID ${detalhe.id}`" severity="secondary" />
                        <Tag v-if="detalhe.tem_embedding" value="Com embedding" severity="success" />
                    </div>
                    <div v-if="detalhe.orgao">
                        <strong>Órgão:</strong> {{ detalhe.orgao.nome }}
                    </div>
                    <div v-if="detalhe.categoria">
                        <strong>Categoria:</strong> {{ detalhe.categoria.nome }}
                    </div>
                    <div v-if="detalhe.prazo_dias != null || detalhe.prazo_texto">
                        <strong>Prazo:</strong>
                        {{ detalhe.prazo_efetivo_dias ?? detalhe.prazo_dias ?? detalhe.prazo_texto }}
                        <span v-if="detalhe.prazo_origem_label" class="text-muted-color">
                            ({{ detalhe.prazo_origem_label }})
                        </span>
                    </div>
                    <div v-if="detalhe.unidade_administrativa_resumo || detalhe.unidade_administrativa">
                        <strong>Setor:</strong>
                        {{
                            (detalhe.unidade_administrativa_resumo || detalhe.unidade_administrativa)?.sigla
                                || (detalhe.unidade_administrativa_resumo || detalhe.unidade_administrativa)?.nome
                        }}
                    </div>
                    <div v-if="detalhe.descricao">
                        <strong>Descrição</strong>
                        <p class="text-muted-color mt-1 mb-0 whitespace-pre-wrap">{{ detalhe.descricao }}</p>
                    </div>
                    <div v-if="detalhe.requisitos">
                        <strong>Requisitos</strong>
                        <p class="text-muted-color mt-1 mb-0 whitespace-pre-wrap">{{ detalhe.requisitos }}</p>
                    </div>
                    <div v-if="detalhe.documentos_necessarios">
                        <strong>Documentos</strong>
                        <p class="text-muted-color mt-1 mb-0 whitespace-pre-wrap">{{ detalhe.documentos_necessarios }}</p>
                    </div>
                    <div v-if="detalhe.observacoes">
                        <strong>Observações</strong>
                        <p class="text-muted-color mt-1 mb-0 whitespace-pre-wrap">{{ detalhe.observacoes }}</p>
                    </div>
                </template>

                <!-- Otimização -->
                <template v-else>
                    <div class="flex flex-wrap gap-2">
                        <Badge :value="`Sinapse ${detalhe.sinapse_servico_id}`" severity="secondary" />
                        <Tag
                            :value="`Score ${formatarScore(detalhe.score_qualidade_otimizado)}`"
                            :severity="getScoreColor(detalhe.score_qualidade_otimizado)"
                        />
                    </div>
                    <div v-if="detalhe.descricao_objetiva">
                        <strong>Descrição objetiva</strong>
                        <p class="text-muted-color mt-1 mb-0">{{ detalhe.descricao_objetiva }}</p>
                    </div>
                    <div v-if="detalhe.intencao_servico">
                        <strong>Intenção</strong>
                        <p class="text-muted-color mt-1 mb-0">{{ detalhe.intencao_servico }}</p>
                    </div>
                    <div v-if="detalhe.problemas_resolve?.length">
                        <strong>Problemas que resolve</strong>
                        <ul class="mt-1 mb-0 pl-4">
                            <li v-for="p in detalhe.problemas_resolve" :key="p">{{ p }}</li>
                        </ul>
                    </div>
                    <div v-if="detalhe.palavras_chave?.length">
                        <strong>Palavras-chave</strong>
                        <div class="flex flex-wrap gap-1 mt-1">
                            <Tag v-for="k in detalhe.palavras_chave" :key="k" :value="k" severity="info" />
                        </div>
                    </div>
                    <div v-if="detalhe.preview_texto_rag">
                        <strong>Texto RAG</strong>
                        <Textarea :modelValue="detalhe.preview_texto_rag" readonly rows="4" class="w-full mt-1 text-xs" />
                    </div>
                    <div v-if="detalhe.melhorias_aplicadas?.length">
                        <strong>Melhorias aplicadas</strong>
                        <ul class="mt-1 mb-0 pl-4 text-green-600">
                            <li v-for="m in detalhe.melhorias_aplicadas" :key="m">{{ m }}</li>
                        </ul>
                    </div>
                </template>
            </div>
            <template #footer>
                <Button label="Fechar" text @click="dialogDetalhe = false" />
            </template>
        </Dialog>
    </div>
</template>
