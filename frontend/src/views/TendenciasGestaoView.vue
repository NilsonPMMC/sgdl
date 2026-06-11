<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import Dropdown from 'primevue/dropdown';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import Tag from 'primevue/tag';
import Textarea from 'primevue/textarea';

const toast = useToast();
const router = useRouter();
const route = useRoute();

const STATUS_OPCOES = [
    { label: 'Todos', value: null },
    { label: 'Aberta', value: 'ABERTA' },
    { label: 'Em análise', value: 'EM_ANALISE' },
    { label: 'Vinculada à carta', value: 'VINCULADA_CARTA' },
    { label: 'Arquivada', value: 'ARQUIVADA' }
];

const STATUS_META = {
    ABERTA: { label: 'Aberta', severity: 'info' },
    EM_ANALISE: { label: 'Em análise', severity: 'warn' },
    VINCULADA_CARTA: { label: 'Vinculada à carta', severity: 'success' },
    ARQUIVADA: { label: 'Arquivada', severity: 'secondary' }
};

const loadingLista = ref(false);
const loadingDetalhe = ref(false);
const loadingOcorrencias = ref(false);
const salvando = ref(false);
const promovendo = ref(false);

const tendencias = ref([]);
const tendenciaSelecionada = ref(null);
const detalhe = ref(null);
const ocorrencias = ref([]);

const orgaos = ref([]);
const servicosCarta = ref([]);

const filtros = ref({
    q: '',
    status: null
});

const dialogEditar = ref(false);
const dialogPromover = ref(false);
const formEdicao = ref({
    titulo: '',
    descricao_resumo: '',
    status: 'ABERTA',
    sinapse_orgao_id: null
});
const servicoPromoverId = ref(null);

const extrairLista = (response) => {
    const data = response?.data;
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.results)) return data.results;
    return [];
};

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    if (typeof data === 'object' && data) {
        return Object.entries(data)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join('; ');
    }
    return 'Operação não concluída.';
};

const statusTag = (status) => STATUS_META[status] || { label: status, severity: 'secondary' };

const podePromover = computed(
    () =>
        detalhe.value &&
        detalhe.value.status !== 'VINCULADA_CARTA' &&
        detalhe.value.status !== 'ARQUIVADA'
);

const formatarData = (iso) => {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString('pt-BR', {
            dateStyle: 'short',
            timeStyle: 'short'
        });
    } catch {
        return iso;
    }
};

const loadOrgaos = async () => {
    try {
        const { data } = await ApiService.getSecretarias();
        const lista = extrairLista({ data });
        orgaos.value = [{ label: '— Não definido —', value: null }, ...lista.map((o) => ({ label: o.nome, value: o.id }))];
    } catch {
        orgaos.value = [{ label: '— Não definido —', value: null }];
    }
};

const loadServicosCarta = async () => {
    try {
        const params = detalhe.value?.sinapse_orgao_id ? { orgao_id: detalhe.value.sinapse_orgao_id } : {};
        const { data } = await ApiService.getServicos(params);
        const lista = extrairLista({ data });
        servicosCarta.value = lista.map((s) => ({
            label: s.secretaria_responsavel?.nome
                ? `[${s.id}] ${s.nome} — ${s.secretaria_responsavel.nome}`
                : `[${s.id}] ${s.nome}`,
            value: s.id
        }));
    } catch {
        servicosCarta.value = [];
    }
};

const loadTendencias = async () => {
    loadingLista.value = true;
    try {
        const params = {
            ordering: '-volume_total',
            q: filtros.value.q?.trim() || undefined,
            status: filtros.value.status || undefined
        };
        const response = await ApiService.listarTendencias(params);
        tendencias.value = extrairLista(response);
    } catch (error) {
        tendencias.value = [];
        toast.add({ severity: 'error', summary: 'Tendências', detail: extrairErro(error), life: 4000 });
    } finally {
        loadingLista.value = false;
    }
};

const loadDetalhe = async (id) => {
    loadingDetalhe.value = true;
    try {
        const { data } = await ApiService.obterTendencia(id);
        detalhe.value = data;
    } catch (error) {
        detalhe.value = null;
        toast.add({ severity: 'error', summary: 'Detalhe', detail: extrairErro(error), life: 4000 });
    } finally {
        loadingDetalhe.value = false;
    }
};

const loadOcorrencias = async (id) => {
    loadingOcorrencias.value = true;
    try {
        const { data } = await ApiService.listarTendenciaOcorrencias(id);
        ocorrencias.value = Array.isArray(data) ? data : [];
    } catch {
        ocorrencias.value = [];
    } finally {
        loadingOcorrencias.value = false;
    }
};

const selecionarTendencia = async (event) => {
    const row = event?.data;
    if (!row?.id) return;
    tendenciaSelecionada.value = row;
    await Promise.all([loadDetalhe(row.id), loadOcorrencias(row.id)]);
};

const abrirEdicao = () => {
    if (!detalhe.value) return;
    formEdicao.value = {
        titulo: detalhe.value.titulo || '',
        descricao_resumo: detalhe.value.descricao_resumo || '',
        status: detalhe.value.status || 'ABERTA',
        sinapse_orgao_id: detalhe.value.sinapse_orgao_id ?? null
    };
    dialogEditar.value = true;
};

const salvarEdicao = async () => {
    if (!detalhe.value?.id) return;
    salvando.value = true;
    try {
        const { data } = await ApiService.atualizarTendencia(detalhe.value.id, {
            titulo: formEdicao.value.titulo.trim(),
            descricao_resumo: formEdicao.value.descricao_resumo.trim(),
            status: formEdicao.value.status,
            sinapse_orgao_id: formEdicao.value.sinapse_orgao_id
        });
        detalhe.value = data;
        dialogEditar.value = false;
        toast.add({ severity: 'success', summary: 'Salvo', detail: 'Tendência atualizada.', life: 3000 });
        await loadTendencias();
        const idx = tendencias.value.findIndex((t) => t.id === data.id);
        if (idx >= 0) tendencias.value[idx] = { ...tendencias.value[idx], ...data };
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvando.value = false;
    }
};

const abrirPromover = async () => {
    servicoPromoverId.value = null;
    await loadServicosCarta();
    dialogPromover.value = true;
};

const confirmarPromocao = async () => {
    if (!detalhe.value?.id || !servicoPromoverId.value) {
        toast.add({
            severity: 'warn',
            summary: 'Promover',
            detail: 'Selecione o serviço da carta Sinapse.',
            life: 3500
        });
        return;
    }
    promovendo.value = true;
    try {
        const { data } = await ApiService.promoverTendenciaCarta(detalhe.value.id, servicoPromoverId.value);
        detalhe.value = data;
        dialogPromover.value = false;
        toast.add({
            severity: 'success',
            summary: 'Promovida',
            detail: 'Tendência vinculada ao serviço da carta.',
            life: 3500
        });
        await loadTendencias();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Promover', detail: extrairErro(error), life: 4000 });
    } finally {
        promovendo.value = false;
    }
};

const irDemanda = (demandaId) => {
    if (demandaId) router.push({ name: 'demandas-detalhes', params: { id: demandaId } });
};

const buscar = () => loadTendencias();

onMounted(async () => {
    await loadOrgaos();
    await loadTendencias();
    const tid = route.query?.id;
    if (tid) {
        const id = parseInt(String(tid), 10);
        if (!Number.isNaN(id)) {
            const row = tendencias.value.find((t) => t.id === id);
            if (row) {
                await selecionarTendencia({ data: row });
            } else {
                tendenciaSelecionada.value = { id };
                await Promise.all([loadDetalhe(id), loadOcorrencias(id)]);
            }
        }
    }
});

watch(
    () => filtros.value.status,
    () => loadTendencias()
);
</script>

<template>
    <div class="flex flex-col gap-6">
        <div>
            <h2 class="text-2xl font-semibold text-[var(--text-color)] m-0">Gestão de Tendências</h2>
            <p class="text-surface-600 mt-1 mb-0 text-sm">
                Malha fina de inovação: demandas municipais ainda não catalogadas na carta Sinapse. Protocolo analisa,
                ajusta órgão e pode promover a um serviço oficial.
            </p>
        </div>

        <Message severity="info" :closable="false" class="text-sm">
            Origem típica: Copiloto com trilha <strong>Tendência</strong> (<code>origem_vinculo=TENDENCIA</code>). Itens
            promovidos passam ao status <strong>Vinculada à carta</strong>.
        </Message>

        <div class="grid grid-cols-1 xl:grid-cols-12 gap-6">
            <div class="xl:col-span-7">
                <Card>
                    <template #title>Fila de tendências</template>
                    <template #content>
                        <div class="flex flex-col sm:flex-row gap-3 mb-4">
                            <InputText
                                v-model="filtros.q"
                                placeholder="Buscar título ou slug…"
                                class="flex-1"
                                @keyup.enter="buscar"
                            />
                            <Dropdown
                                v-model="filtros.status"
                                :options="STATUS_OPCOES"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Status"
                                class="w-full sm:w-48"
                            />
                            <Button label="Buscar" icon="pi pi-search" @click="buscar" :loading="loadingLista" />
                        </div>

                        <DataTable
                            :value="tendencias"
                            :loading="loadingLista"
                            selectionMode="single"
                            dataKey="id"
                            stripedRows
                            size="small"
                            :metaKeySelection="false"
                            responsiveLayout="scroll"
                            class="sgdl-table-scroll"
                            @row-select="selecionarTendencia"
                        >
                            <Column field="titulo" header="Título">
                                <template #body="{ data }">
                                    <span class="font-medium">{{ data.titulo }}</span>
                                </template>
                            </Column>
                            <Column header="Status" style="width: 9rem">
                                <template #body="{ data }">
                                    <Tag
                                        :value="statusTag(data.status).label"
                                        :severity="statusTag(data.status).severity"
                                    />
                                </template>
                            </Column>
                            <Column field="volume_total" header="Vol." style="width: 4rem" />
                            <Column header="Órgão">
                                <template #body="{ data }">
                                    {{ data.sinapse_orgao_nome || '—' }}
                                </template>
                            </Column>
                            <Column header="Última ocorrência" style="width: 8rem">
                                <template #body="{ data }">
                                    <span class="text-xs">{{ formatarData(data.ultima_ocorrencia) }}</span>
                                </template>
                            </Column>
                        </DataTable>
                    </template>
                </Card>
            </div>

            <div class="xl:col-span-5">
                <Card class="sticky top-4">
                    <template #title>Detalhe</template>
                    <template #content>
                        <div v-if="loadingDetalhe" class="flex justify-center py-10">
                            <ProgressSpinner style="width: 40px; height: 40px" />
                        </div>
                        <div v-else-if="detalhe" class="flex flex-col gap-4 text-sm">
                            <div class="flex flex-wrap items-start justify-between gap-2">
                                <div>
                                    <h3 class="text-lg font-semibold m-0">{{ detalhe.titulo }}</h3>
                                    <p class="text-surface-500 m-0 mt-1 text-xs">slug: {{ detalhe.slug }}</p>
                                </div>
                                <Tag
                                    :value="statusTag(detalhe.status).label"
                                    :severity="statusTag(detalhe.status).severity"
                                />
                            </div>

                            <div class="grid grid-cols-2 gap-2 p-3 rounded-lg bg-surface-50 border border-surface-200">
                                <div>
                                    <span class="font-semibold text-surface-700">Volume</span>
                                    <p class="m-0">{{ detalhe.volume_total ?? 0 }}</p>
                                </div>
                                <div>
                                    <span class="font-semibold text-surface-700">Órgão sugerido</span>
                                    <p class="m-0">{{ detalhe.sinapse_orgao_nome || '—' }}</p>
                                </div>
                                <div v-if="detalhe.sinapse_servico_nome" class="col-span-2">
                                    <span class="font-semibold text-surface-700">Serviço na carta</span>
                                    <p class="m-0">{{ detalhe.sinapse_servico_nome }}</p>
                                </div>
                                <div>
                                    <span class="font-semibold text-surface-700">Primeira</span>
                                    <p class="m-0 text-xs">{{ formatarData(detalhe.primeira_ocorrencia) }}</p>
                                </div>
                                <div>
                                    <span class="font-semibold text-surface-700">Última</span>
                                    <p class="m-0 text-xs">{{ formatarData(detalhe.ultima_ocorrencia) }}</p>
                                </div>
                            </div>

                            <div v-if="detalhe.descricao_resumo">
                                <span class="font-semibold text-surface-700">Resumo</span>
                                <p class="m-0 mt-1 whitespace-pre-wrap">{{ detalhe.descricao_resumo }}</p>
                            </div>

                            <div class="flex flex-wrap gap-2">
                                <Button label="Editar" icon="pi pi-pencil" outlined size="small" @click="abrirEdicao" />
                                <Button
                                    v-if="podePromover"
                                    label="Promover à carta"
                                    icon="pi pi-arrow-up-right"
                                    size="small"
                                    @click="abrirPromover"
                                />
                            </div>

                            <div>
                                <h4 class="font-semibold m-0 mb-2">Ocorrências (demandas)</h4>
                                <div v-if="loadingOcorrencias" class="flex justify-center py-4">
                                    <ProgressSpinner style="width: 28px; height: 28px" />
                                </div>
                                <p v-else-if="!ocorrencias.length" class="text-surface-500 m-0">
                                    Nenhuma demanda vinculada ainda.
                                </p>
                                <ul v-else class="list-none p-0 m-0 flex flex-col gap-2">
                                    <li
                                        v-for="oc in ocorrencias"
                                        :key="oc.id"
                                        class="flex items-center justify-between gap-2 p-2 rounded border border-surface-200"
                                    >
                                        <div class="min-w-0">
                                            <p class="m-0 font-medium truncate">{{ oc.demanda_titulo || `Demanda #${oc.demanda}` }}</p>
                                            <p class="m-0 text-xs text-surface-500">{{ formatarData(oc.criado_em) }}</p>
                                        </div>
                                        <Button
                                            v-if="oc.demanda"
                                            icon="pi pi-external-link"
                                            text
                                            rounded
                                            v-tooltip.top="'Abrir demanda'"
                                            @click="irDemanda(oc.demanda)"
                                        />
                                    </li>
                                </ul>
                            </div>
                        </div>
                        <p v-else class="text-surface-500 m-0">Selecione uma tendência na lista para analisar e editar.</p>
                    </template>
                </Card>
            </div>
        </div>

        <Dialog
            v-model:visible="dialogEditar"
            modal
            header="Editar tendência"
            :style="{ width: '32rem' }"
            :draggable="false"
        >
            <div class="flex flex-col gap-3">
                <div>
                    <label class="font-medium text-sm">Título</label>
                    <InputText v-model="formEdicao.titulo" class="w-full mt-1" />
                </div>
                <div>
                    <label class="font-medium text-sm">Status</label>
                    <Dropdown
                        v-model="formEdicao.status"
                        :options="STATUS_OPCOES.filter((o) => o.value)"
                        optionLabel="label"
                        optionValue="value"
                        class="w-full mt-1"
                    />
                </div>
                <div>
                    <label class="font-medium text-sm">Órgão (Sinapse)</label>
                    <Dropdown
                        v-model="formEdicao.sinapse_orgao_id"
                        :options="orgaos"
                        optionLabel="label"
                        optionValue="value"
                        class="w-full mt-1"
                        filter
                    />
                </div>
                <div>
                    <label class="font-medium text-sm">Resumo / notas</label>
                    <Textarea v-model="formEdicao.descricao_resumo" rows="4" class="w-full mt-1" autoResize />
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" text @click="dialogEditar = false" />
                <Button label="Salvar" icon="pi pi-check" :loading="salvando" @click="salvarEdicao" />
            </template>
        </Dialog>

        <Dialog
            v-model:visible="dialogPromover"
            modal
            header="Promover à carta de serviços"
            :style="{ width: '36rem' }"
            :draggable="false"
        >
            <p class="text-sm text-surface-600 mt-0">
                Vincula esta tendência a um serviço oficial do Sinapse. Demandas futuras podem seguir pela trilha carta
                após revisão do Protocolo.
            </p>
            <Dropdown
                v-model="servicoPromoverId"
                :options="servicosCarta"
                optionLabel="label"
                optionValue="value"
                placeholder="Selecione o serviço na carta"
                class="w-full"
                filter
            />
            <template #footer>
                <Button label="Cancelar" text @click="dialogPromover = false" />
                <Button
                    label="Confirmar promoção"
                    icon="pi pi-check"
                    :loading="promovendo"
                    :disabled="!servicoPromoverId"
                    @click="confirmarPromocao"
                />
            </template>
        </Dialog>
    </div>
</template>
