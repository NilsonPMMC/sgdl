<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';
import { useUserStore } from '@/stores/userStore';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import Dropdown from 'primevue/dropdown';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import Select from 'primevue/select';
import Tag from 'primevue/tag';
import DialogVincularDemandaCluster from '@/components/cluster/DialogVincularDemandaCluster.vue';
import { formatarProtocoloLegislativo } from '@/utils/protocoloLegislativo';

const toast = useToast();
const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const STATUS_OPCOES = [
    { label: 'Abertos e em andamento', value: 'ativos' },
    { label: 'Aberto', value: 'ABERTO' },
    { label: 'Em andamento', value: 'EM_ANDAMENTO' },
    { label: 'Resolvido', value: 'RESOLVIDO' },
    { label: 'Todos', value: 'todos' }
];

const STATUS_META = {
    ABERTO: { label: 'Aberto', severity: 'info' },
    EM_ANDAMENTO: { label: 'Em andamento', severity: 'warn' },
    RESOLVIDO: { label: 'Resolvido', severity: 'success' }
};

const loadingLista = ref(false);
const loadingDetalhe = ref(false);
const loadingDemandas = ref(false);
const loadingResumo = ref(false);

const resumo = ref(null);
const clusters = ref([]);
const clusterSelecionado = ref(null);
const detalhe = ref(null);
const demandasCluster = ref([]);

const filtros = ref({ status: 'ativos' });

const todasSecretarias = ref([]);
const superOsDialog = ref(false);
const vincularDialog = ref(false);
const vinculandoDemanda = ref(false);
const desvinculandoId = ref(null);
const despachandoSuperOs = ref(false);
const despachoData = ref({
    secretaria_id: null
});

const perfil = computed(() => userStore.currentUser?.perfil);

const podeGerirCluster = computed(() =>
    ['PROTOCOLO', 'GESTOR', 'SECRETARIA'].includes(perfil.value)
);

const podeDespacharSuperOs = computed(
    () =>
        perfil.value === 'PROTOCOLO' &&
        detalhe.value?.id &&
        (detalhe.value?.pendentes_protocolo ?? 0) > 0
);

const extrairLista = (response) => {
    const data = response?.data;
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.results)) return data.results;
    return [];
};

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    return 'Operação não concluída.';
};

const statusTag = (status) => STATUS_META[status] || { label: status, severity: 'secondary' };

const paramsLista = computed(() => {
    const s = filtros.value.status;
    if (s === 'ativos' || !s) return {};
    if (s === 'todos') return { status: undefined };
    return { status: s };
});

const kpis = computed(() => {
    const lista = resumo.value?.clusters || [];
    const totalDemandas = lista.reduce((acc, c) => acc + (c.demandas_count || 0), 0);
    const multiAutor = lista.filter((c) => (c.autores_distintos || 0) > 1).length;
    return {
        clustersAtivos: lista.length,
        totalDemandas,
        superOs: multiAutor,
        threshold: resumo.value?.semantic_threshold,
        raio: resumo.value?.radius_meters,
        janelaDias: resumo.value?.janela_agregacao_dias
    };
});

const formatarData = (iso) => {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
    } catch {
        return iso;
    }
};

const loadResumo = async () => {
    loadingResumo.value = true;
    try {
        const { data } = await ApiService.getClustersResumo({ limit: 50 });
        resumo.value = data;
    } catch {
        resumo.value = null;
    } finally {
        loadingResumo.value = false;
    }
};

const loadClusters = async () => {
    loadingLista.value = true;
    try {
        const params = { ...paramsLista.value };
        if (filtros.value.status === 'ativos') {
            delete params.status;
        }
        if (route.query?.id) {
            params.id = route.query.id;
        }
        const { data } = await ApiService.listarClusters(params);
        let lista = extrairLista({ data });
        if (filtros.value.status === 'ativos') {
            lista = lista.filter((c) => c.status === 'ABERTO' || c.status === 'EM_ANDAMENTO');
        }
        clusters.value = lista.filter((c) => (c.demandas_count ?? 0) >= 2);
    } catch (error) {
        clusters.value = [];
        toast.add({ severity: 'error', summary: 'Clusters', detail: extrairErro(error), life: 4000 });
    } finally {
        loadingLista.value = false;
    }
};

const abrirClusterPorId = async (clusterId) => {
    const id = parseInt(String(clusterId), 10);
    if (Number.isNaN(id)) return;
    let row = clusters.value.find((c) => c.id === id);
    if (!row) {
        try {
            const { data } = await ApiService.obterCluster(id);
            row = data;
            if (row) {
                clusters.value = [row, ...clusters.value.filter((c) => c.id !== id)];
            }
        } catch {
            toast.add({
                severity: 'warn',
                summary: 'Cluster',
                detail: `Cluster #${id} não encontrado ou sem permissão de acesso.`,
                life: 4000
            });
            return;
        }
    }
    if (row) {
        clusterSelecionado.value = row;
        await Promise.all([loadDetalhe(row.id), loadDemandas(row.id)]);
    }
};

const loadDetalhe = async (id) => {
    loadingDetalhe.value = true;
    try {
        const { data } = await ApiService.obterCluster(id);
        detalhe.value = data;
    } catch (error) {
        detalhe.value = null;
        toast.add({ severity: 'error', summary: 'Detalhe', detail: extrairErro(error), life: 4000 });
    } finally {
        loadingDetalhe.value = false;
    }
};

const loadDemandas = async (id) => {
    loadingDemandas.value = true;
    try {
        const { data } = await ApiService.listarClusterDemandas(id);
        demandasCluster.value = Array.isArray(data) ? data : extrairLista({ data });
    } catch {
        demandasCluster.value = [];
    } finally {
        loadingDemandas.value = false;
    }
};

const selecionarCluster = async (event) => {
    const row = event?.data;
    if (!row?.id) return;
    clusterSelecionado.value = row;
    await Promise.all([loadDetalhe(row.id), loadDemandas(row.id)]);
};

const irDemanda = (id) => {
    if (id) router.push({ name: 'demandas-detalhes', params: { id } });
};

const recarregar = async () => {
    await Promise.all([loadResumo(), loadClusters()]);
};

const abrirDialogoSuperOs = () => {
    if (!detalhe.value?.id) return;
    despachoData.value = {
        secretaria_id: detalhe.value.orgao_competente_id || null
    };
    superOsDialog.value = true;
};

const abrirDialogoVincular = () => {
    vincularDialog.value = true;
};

const confirmarVincularDemanda = async (demandaId) => {
    const clusterId = detalhe.value?.id;
    if (!clusterId || !demandaId) return;
    vinculandoDemanda.value = true;
    try {
        await ApiService.vincularDemandaCluster(clusterId, demandaId);
        toast.add({
            severity: 'success',
            summary: 'Vinculado',
            detail: 'Ofício adicionado ao grupo Super OS.',
            life: 4000
        });
        vincularDialog.value = false;
        await Promise.all([loadResumo(), loadClusters(), loadDetalhe(clusterId), loadDemandas(clusterId)]);
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        vinculandoDemanda.value = false;
    }
};

const rotuloDemanda = (item) =>
    formatarProtocoloLegislativo(item?.protocolo_legislativo) ||
    item?.protocolo_executivo ||
    (item?.id ? `#${item.id}` : '—');

const desvincularDemanda = async (demandaId) => {
    const clusterId = detalhe.value?.id;
    if (!clusterId || !demandaId) return;
    desvinculandoId.value = demandaId;
    try {
        await ApiService.desvincularDemandaCluster(clusterId, demandaId);
        toast.add({ severity: 'success', summary: 'Desvinculado', detail: `Demanda #${demandaId} removida do cluster.`, life: 4000 });
        await Promise.all([loadResumo(), loadClusters(), loadDetalhe(clusterId), loadDemandas(clusterId)]);
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        desvinculandoId.value = null;
    }
};

const confirmarDespachoSuperOs = async () => {
    if (!despachoData.value.secretaria_id) {
        toast.add({ severity: 'warn', summary: 'Atenção', detail: 'Selecione a secretaria de destino.', life: 3000 });
        return;
    }
    const clusterId = detalhe.value?.id;
    if (!clusterId) return;

    despachandoSuperOs.value = true;
    try {
        const { data } = await ApiService.despacharClusterSuperOs(clusterId, despachoData.value);
        const n = data?.total ?? data?.demandas_protocoladas?.length ?? 0;
        toast.add({
            severity: 'success',
            summary: 'Super OS despachada',
            detail: `${data?.protocolo_super_os || 'Lote'} — ${n} demanda(s) protocolada(s).`,
            life: 5000
        });
        superOsDialog.value = false;
        await Promise.all([loadResumo(), loadClusters(), loadDetalhe(clusterId), loadDemandas(clusterId)]);
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        despachandoSuperOs.value = false;
    }
};

onMounted(async () => {
    await recarregar();
    if (userStore.currentUser?.perfil === 'PROTOCOLO') {
        try {
            const { data } = await ApiService.getSecretarias();
            todasSecretarias.value = data;
        } catch {
            todasSecretarias.value = [];
        }
    }
    if (route.query?.id) {
        await abrirClusterPorId(route.query.id);
    }
});

watch(
    () => filtros.value.status,
    () => loadClusters()
);

watch(
    () => route.query?.id,
    async (id) => {
        if (id) {
            await abrirClusterPorId(id);
        }
    }
);
</script>

<template>
    <div class="flex flex-col gap-6">
        <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
                <h2 class="text-2xl font-semibold text-[var(--text-color)] m-0">Super Ordens de Serviço</h2>
                <p class="text-surface-600 mt-1 mb-0 text-sm">
                    Grupos automáticos do <strong>mesmo serviço</strong> e mesma área. Quando o sistema não reconhecer
                    um ofício relacionado, use <strong>Vincular ofício</strong> para integrá-lo ao grupo existente.
                </p>
            </div>
            <Button label="Atualizar" icon="pi pi-refresh" outlined :loading="loadingLista" @click="recarregar" />
        </div>

        <Message v-if="kpis.threshold != null" severity="info" :closable="false" class="text-sm">
            Critérios ativos: <strong>mesmo serviço Sinapse</strong> · similaridade ≥
            {{ (kpis.threshold * 100).toFixed(0) }}% (desempate) · raio {{ kpis.raio }} m quando exige local (ou mesmo
            bairro)<template v-if="kpis.janelaDias">
                · novos ofícios agregam por até {{ kpis.janelaDias }} dias
            </template>.
        </Message>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card>
                <template #title>Clusters ativos</template>
                <template #content>
                    <div v-if="loadingResumo" class="text-surface-500 text-sm">Carregando…</div>
                    <div v-else class="text-3xl font-semibold text-[var(--text-color)]">{{ kpis.clustersAtivos }}</div>
                </template>
            </Card>
            <Card>
                <template #title>Demandas agrupadas</template>
                <template #content>
                    <div class="text-3xl font-semibold text-[var(--text-color)]">{{ kpis.totalDemandas }}</div>
                </template>
            </Card>
            <Card>
                <template #title>Super OS (multi-vereador)</template>
                <template #content>
                    <div class="text-3xl font-semibold text-[var(--text-color)]">{{ kpis.superOs }}</div>
                    <p class="text-xs text-surface-500 m-0 mt-1">Clusters com mais de um autor</p>
                </template>
            </Card>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-12 gap-6">
            <div class="xl:col-span-7">
                <Card>
                    <template #title>Clusters</template>
                    <template #content>
                        <div class="mb-4">
                            <Dropdown
                                v-model="filtros.status"
                                :options="STATUS_OPCOES"
                                optionLabel="label"
                                optionValue="value"
                                class="w-full sm:w-64"
                            />
                        </div>
                        <DataTable
                            :value="clusters"
                            :loading="loadingLista"
                            selectionMode="single"
                            dataKey="id"
                            stripedRows
                            size="small"
                            :metaKeySelection="false"
                            responsiveLayout="scroll"
                            class="sgdl-table-scroll"
                            @row-select="selecionarCluster"
                        >
                            <Column field="titulo" header="Tema / local">
                                <template #body="{ data }">
                                    <span class="font-medium">{{ data.titulo }}</span>
                                    <p v-if="data.servico_nome" class="text-xs text-primary m-0 mt-0.5">
                                        {{ data.servico_nome }}
                                    </p>
                                    <p v-if="data.bairro_referencia" class="text-xs text-surface-500 m-0">
                                        {{ data.bairro_referencia }}
                                    </p>
                                </template>
                            </Column>
                            <Column header="Status" style="width: 8rem">
                                <template #body="{ data }">
                                    <Tag
                                        :value="statusTag(data.status).label"
                                        :severity="statusTag(data.status).severity"
                                    />
                                </template>
                            </Column>
                            <Column header="Dem." style="width: 4rem">
                                <template #body="{ data }">
                                    {{ data.demandas_count ?? '—' }}
                                </template>
                            </Column>
                            <Column header="Vereadores" style="width: 5rem">
                                <template #body="{ data }">
                                    <Tag
                                        v-if="(data.autores_distintos || 0) > 1"
                                        :value="String(data.autores_distintos)"
                                        severity="warn"
                                        v-tooltip.top="'Super OS — mais de um gabinete'"
                                    />
                                    <span v-else>{{ data.autores_distintos ?? 1 }}</span>
                                </template>
                            </Column>
                            <Column header="Secretaria">
                                <template #body="{ data }">
                                    <span class="text-xs">{{ data.secretaria_responsavel || '—' }}</span>
                                </template>
                            </Column>
                        </DataTable>
                    </template>
                </Card>
            </div>

            <div class="xl:col-span-5">
                <Card class="sticky top-4">
                    <template #title>Detalhe do cluster</template>
                    <template #content>
                        <div v-if="loadingDetalhe" class="flex justify-center py-10">
                            <ProgressSpinner style="width: 40px; height: 40px" />
                        </div>
                        <div v-else-if="detalhe" class="flex flex-col gap-4 text-sm">
                            <div class="flex flex-wrap justify-between gap-2">
                                <h3 class="text-lg font-semibold m-0">{{ detalhe.titulo }}</h3>
                                <div class="flex flex-wrap gap-2">
                                    <Tag
                                        v-if="detalhe.tipo_display"
                                        :value="detalhe.tipo_display"
                                        :severity="detalhe.tipo === 'MULTI_DESTINO' ? 'help' : 'info'"
                                    />
                                    <Tag
                                        :value="statusTag(detalhe.status).label"
                                        :severity="statusTag(detalhe.status).severity"
                                    />
                                </div>
                            </div>
                            <p v-if="detalhe.descricao_resumo" class="m-0 whitespace-pre-wrap text-justify">
                                {{ detalhe.descricao_resumo }}
                            </p>
                            <Message
                                v-if="detalhe.orgaos_envolvidos?.length > 1"
                                severity="info"
                                :closable="false"
                                class="m-0 text-xs"
                            >
                                Órgãos no grupo:
                                {{ detalhe.orgaos_envolvidos.map((o) => o.orgao_nome).join(', ') }}.
                                <span v-if="detalhe.orgao_competente_nome">
                                    Competente (carta): <strong>{{ detalhe.orgao_competente_nome }}</strong>.
                                </span>
                            </Message>
                            <div class="grid grid-cols-2 gap-2 text-xs">
                                <div>
                                    <span class="font-semibold">Bairro ref.</span>
                                    <p class="m-0">{{ detalhe.bairro_referencia || '—' }}</p>
                                </div>
                                <div>
                                    <span class="font-semibold">Serviço</span>
                                    <p class="m-0">{{ detalhe.servico_nome || '—' }}</p>
                                </div>
                                <div>
                                    <span class="font-semibold">Órgão competente</span>
                                    <p class="m-0">{{ detalhe.orgao_competente_nome || detalhe.secretaria_responsavel || '—' }}</p>
                                </div>
                                <div>
                                    <span class="font-semibold">Demandas</span>
                                    <p class="m-0">{{ detalhe.demandas_count }}</p>
                                </div>
                                <div>
                                    <span class="font-semibold">Autores distintos</span>
                                    <p class="m-0">{{ detalhe.autores_distintos }}</p>
                                </div>
                                <div v-if="detalhe.protocolados_count != null">
                                    <span class="font-semibold">Protocoladas</span>
                                    <p class="m-0">{{ detalhe.protocolados_count }}</p>
                                </div>
                                <div v-if="detalhe.lider_demanda_id">
                                    <span class="font-semibold">Demanda líder</span>
                                    <p class="m-0">
                                        <Button
                                            :label="`#${detalhe.lider_demanda_id}`"
                                            link
                                            class="p-0"
                                            @click="irDemanda(detalhe.lider_demanda_id)"
                                        />
                                    </p>
                                </div>
                                <div v-if="detalhe.protocolo_super_os" class="col-span-2">
                                    <span class="font-semibold">Protocolo Super OS</span>
                                    <p class="m-0 font-medium">{{ detalhe.protocolo_super_os }}</p>
                                    <p v-if="detalhe.despachado_em" class="m-0 text-surface-500">
                                        Despachado em {{ formatarData(detalhe.despachado_em) }}
                                    </p>
                                </div>
                                <div v-if="(detalhe.pendentes_protocolo ?? 0) > 0">
                                    <span class="font-semibold">Aguardando protocolo</span>
                                    <p class="m-0">{{ detalhe.pendentes_protocolo }} demanda(s)</p>
                                </div>
                            </div>

                            <div v-if="podeGerirCluster" class="flex flex-wrap gap-2">
                                <Button
                                    v-if="podeDespacharSuperOs"
                                    label="Despachar Super OS"
                                    icon="pi pi-sitemap"
                                    severity="help"
                                    @click="abrirDialogoSuperOs"
                                />
                                <Button
                                    label="Vincular ofício"
                                    icon="pi pi-link"
                                    outlined
                                    @click="abrirDialogoVincular"
                                />
                            </div>

                            <div>
                                <h4 class="font-semibold m-0 mb-2">Demandas no grupo</h4>
                                <div v-if="loadingDemandas" class="flex justify-center py-4">
                                    <ProgressSpinner style="width: 28px; height: 28px" />
                                </div>
                                <p v-else-if="!demandasCluster.length" class="text-surface-500 m-0">
                                    Nenhuma demanda vinculada.
                                </p>
                                <DataTable
                                    v-else
                                    :value="demandasCluster"
                                    size="small"
                                    stripedRows
                                    responsiveLayout="scroll"
                                    class="sgdl-table-scroll"
                                >
                                    <Column header="Ofício" style="min-width: 8rem">
                                        <template #body="{ data }">
                                            <span class="text-xs font-medium">{{ rotuloDemanda(data) }}</span>
                                        </template>
                                    </Column>
                                    <Column header="Status">
                                        <template #body="{ data }">
                                            <Tag :value="data.status_display || data.status" severity="secondary" />
                                        </template>
                                    </Column>
                                    <Column header="Serviço">
                                        <template #body="{ data }">
                                            <span class="text-xs">{{ data.servico_nome || '—' }}</span>
                                        </template>
                                    </Column>
                                    <Column header="" style="width: 6rem">
                                        <template #body="{ data }">
                                            <div class="flex gap-1">
                                                <Button
                                                    icon="pi pi-external-link"
                                                    text
                                                    rounded
                                                    v-tooltip.top="'Ver demanda'"
                                                    @click="irDemanda(data.id)"
                                                />
                                                <Button
                                                    v-if="podeGerirCluster"
                                                    icon="pi pi-times"
                                                    text
                                                    rounded
                                                    severity="danger"
                                                    :loading="desvinculandoId === data.id"
                                                    v-tooltip.top="'Desvincular do cluster'"
                                                    @click="desvincularDemanda(data.id)"
                                                />
                                            </div>
                                        </template>
                                    </Column>
                                </DataTable>
                            </div>
                        </div>
                        <p v-else class="text-surface-500 m-0">
                            Selecione um cluster para ver demandas agrupadas e abrir cada protocolo.
                        </p>
                    </template>
                </Card>
            </div>
        </div>

        <DialogVincularDemandaCluster
            v-model:visible="vincularDialog"
            :cluster="detalhe"
            :vinculando="vinculandoDemanda"
            @vincular="confirmarVincularDemanda"
        />

        <Dialog
            v-model:visible="superOsDialog"
            header="Despachar Super Ordem de Serviço"
            :modal="true"
            style="width: 480px"
        >
            <div v-if="detalhe" class="flex flex-col gap-4">
                <p class="m-0 text-sm text-surface-600">
                    Protocola em lote as
                    <strong>{{ detalhe.pendentes_protocolo }}</strong>
                    demanda(s) aguardando protocolo do cluster
                    <strong>{{ detalhe.titulo }}</strong>
                    (#{{ detalhe.id }}).
                </p>
                <div>
                    <label for="secretaria_super_cl" class="block mb-2 text-sm font-medium">Secretaria de destino</label>
                    <Select
                        id="secretaria_super_cl"
                        v-model="despachoData.secretaria_id"
                        :options="todasSecretarias"
                        optionLabel="nome"
                        optionValue="id"
                        placeholder="Selecione"
                        fluid
                    />
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" icon="pi pi-times" text @click="superOsDialog = false" />
                <Button
                    label="Confirmar Super OS"
                    icon="pi pi-sitemap"
                    :loading="despachandoSuperOs"
                    @click="confirmarDespachoSuperOs"
                />
            </template>
        </Dialog>
    </div>
</template>
