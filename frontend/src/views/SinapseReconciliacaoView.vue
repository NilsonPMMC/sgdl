<script setup>
import { computed, onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dropdown from 'primevue/dropdown';
import InputNumber from 'primevue/inputnumber';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import Tag from 'primevue/tag';

const toast = useToast();

const loading = ref(false);
const loadingHealth = ref(false);
const rows = ref([]);
const selectedRows = ref([]);
const servicosCarta = ref([]);
const orgaos = ref([]);
const selectedServicoBulk = ref(null);
const health = ref(null);

const filters = ref({
    match_status: 'UNMATCHED',
    search: '',
    min_confidence: null,
    limit: 100,
    orgao_id: null
});

const statusOptions = [
    { label: 'Sem correspondência', value: 'UNMATCHED' },
    { label: 'Mapeado automaticamente', value: 'AUTO' },
    { label: 'Mapeado manualmente', value: 'MANUAL' }
];

const STATUS_LABEL = {
    UNMATCHED: 'Sem correspondência',
    AUTO: 'Automático',
    MANUAL: 'Manual'
};

const totalSelecionados = computed(() => selectedRows.value.length);

const resumoHealth = computed(() => health.value?.summary || {});

const alertaOperacional = computed(() => health.value?.alert_level === 'ALERT');

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

const labelServicoCarta = (item) => {
    const nome = (item.nome || '').trim();
    const orgao = item.secretaria_responsavel?.nome;
    const base = nome.length > 85 ? `${nome.slice(0, 85)}…` : nome;
    return orgao ? `[${item.id}] ${base} — ${orgao}` : `[${item.id}] ${base}`;
};

const enriquecerLinha = (item) => {
    let catalogId = item.catalog_servico_id ?? null;
    if (catalogId == null && /^\d+$/.test(String(item.sinapse_service_id || ''))) {
        catalogId = parseInt(item.sinapse_service_id, 10);
    }
    return {
        ...item,
        _selectedCatalogId: catalogId,
        match_status_label: STATUS_LABEL[item.match_status] || item.match_status
    };
};

const idNumericoSinapse = (row) => {
    const raw = String(row?.sinapse_service_id || '');
    return /^\d+$/.test(raw) ? parseInt(raw, 10) : null;
};

const podeConfirmarMesmoId = (row) =>
    row.match_status === 'UNMATCHED' && idNumericoSinapse(row) != null;

const loadHealth = async () => {
    loadingHealth.value = true;
    try {
        const response = await ApiService.getSinapseSyncHealth();
        health.value = response.data || null;
    } catch (_error) {
        health.value = null;
    } finally {
        loadingHealth.value = false;
    }
};

const loadOrgaos = async () => {
    try {
        const response = await ApiService.getSecretarias();
        const data = response.data?.results || response.data || [];
        orgaos.value = data.map((o) => ({ label: o.nome, value: o.id }));
    } catch (_error) {
        orgaos.value = [];
    }
};

const loadServicosCarta = async () => {
    try {
        const params = {};
        if (filters.value.orgao_id) {
            params.orgao_id = filters.value.orgao_id;
        }
        const response = await ApiService.getServicos(params);
        const data = response.data?.results || response.data || [];
        servicosCarta.value = data.map((item) => ({
            label: labelServicoCarta(item),
            value: item.id
        }));
    } catch (_error) {
        servicosCarta.value = [];
        toast.add({
            severity: 'warn',
            summary: 'Catálogo',
            detail: 'Não foi possível carregar serviços da carta Sinapse.',
            life: 3500
        });
    }
};

const loadUnmatched = async () => {
    loading.value = true;
    try {
        const params = {
            match_status: filters.value.match_status,
            search: filters.value.search || undefined,
            min_confidence: filters.value.min_confidence ?? undefined,
            limit: filters.value.limit
        };
        const response = await ApiService.getSinapseUnmatched(params);
        const lista = Array.isArray(response.data) ? response.data : [];
        rows.value = lista.map(enriquecerLinha);
    } catch (_error) {
        rows.value = [];
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: 'Falha ao carregar fila de reconciliação.',
            life: 3500
        });
    } finally {
        loading.value = false;
    }
};

const aplicarFiltros = async () => {
    await loadServicosCarta();
    await loadUnmatched();
};

const bindSingle = async (item, catalogServicoId) => {
    const servicoId = catalogServicoId ?? item._selectedCatalogId;
    if (!servicoId) {
        toast.add({
            severity: 'warn',
            summary: 'Atenção',
            detail: 'Selecione o serviço da carta Sinapse que corresponde a este registro.',
            life: 3000
        });
        return;
    }
    try {
        const response = await ApiService.bindSinapseManual({
            sinapse_service_id: item.sinapse_service_id,
            servico_local_id: servicoId
        });
        const titulo = response.data?.catalog_titulo;
        toast.add({
            severity: 'success',
            summary: 'Vinculado',
            detail: titulo
                ? `ID externo ${item.sinapse_service_id} → carta #${servicoId} (${titulo})`
                : `ID externo ${item.sinapse_service_id} vinculado à carta #${servicoId}.`,
            life: 4000
        });
        await Promise.all([loadUnmatched(), loadHealth()]);
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro ao vincular',
            detail: extrairErro(error),
            life: 4500
        });
    }
};

const confirmarMesmoId = async (item) => {
    const id = idNumericoSinapse(item);
    if (id == null) return;
    item._selectedCatalogId = id;
    await bindSingle(item, id);
};

const bindBulk = async () => {
    if (!selectedServicoBulk.value || selectedRows.value.length === 0) {
        toast.add({
            severity: 'warn',
            summary: 'Atenção',
            detail: 'Selecione itens da fila e um serviço da carta para ação em lote.',
            life: 3000
        });
        return;
    }
    try {
        const bindings = selectedRows.value.map((row) => ({
            sinapse_service_id: row.sinapse_service_id,
            servico_local_id: selectedServicoBulk.value
        }));
        const response = await ApiService.bindSinapseManualBulk(bindings);
        const totalBound = response.data?.total_bound || 0;
        const totalErrors = response.data?.total_errors || 0;
        toast.add({
            severity: totalErrors > 0 ? 'warn' : 'success',
            summary: 'Lote processado',
            detail: `${totalBound} vínculo(s) confirmado(s)${totalErrors > 0 ? `, ${totalErrors} erro(s)` : ''}.`,
            life: 4000
        });
        selectedRows.value = [];
        await Promise.all([loadUnmatched(), loadHealth()]);
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Erro no lote',
            detail: extrairErro(error),
            life: 4500
        });
    }
};

const getStatusSeverity = (status) => {
    if (status === 'UNMATCHED') return 'danger';
    if (status === 'MANUAL') return 'warn';
    return 'success';
};

const formatarData = (iso) => {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString('pt-BR');
    } catch {
        return iso;
    }
};

onMounted(async () => {
    await Promise.all([loadOrgaos(), loadHealth(), loadServicosCarta(), loadUnmatched()]);
});
</script>

<template>
    <div class="flex flex-col gap-5 p-4 md:p-6 mx-auto">
        <div>
            <h1 class="text-2xl font-semibold text-surface-900 dark:text-surface-0 m-0">Reconciliação Sinapse</h1>
            <p class="text-surface-600 dark:text-surface-400 mt-2 mb-0 max-w-3xl">
                A sincronização traz identificadores externos de serviços. Aqui você confirma qual entrada da
                <strong>carta municipal Sinapse</strong> corresponde a cada ID — necessário para o Copiloto e o
                protocolo sugerirem o serviço certo.
            </p>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card class="shadow-sm">
                <template #content>
                    <div class="text-sm text-surface-500">Sem correspondência</div>
                    <div class="text-2xl font-semibold text-red-600 dark:text-red-400">
                        {{ resumoHealth.unmatched_mappings ?? '—' }}
                    </div>
                </template>
            </Card>
            <Card class="shadow-sm">
                <template #content>
                    <div class="text-sm text-surface-500">Registros divergentes</div>
                    <div class="text-2xl font-semibold text-orange-600 dark:text-orange-400">
                        {{ resumoHealth.divergent_sync_records ?? '—' }}
                    </div>
                </template>
            </Card>
            <Card class="shadow-sm">
                <template #content>
                    <div class="text-sm text-surface-500">Mapeamentos totais</div>
                    <div class="text-2xl font-semibold">{{ resumoHealth.total_mapping_records ?? '—' }}</div>
                </template>
            </Card>
            <Card class="shadow-sm">
                <template #content>
                    <div class="text-sm text-surface-500">Última sincronização</div>
                    <div class="text-sm font-medium mt-1">{{ formatarData(resumoHealth.last_sync_at) }}</div>
                </template>
            </Card>
        </div>

        <Message v-if="alertaOperacional" severity="warn" :closable="false">
            <span class="font-medium">Atenção operacional:</span>
            {{ (health?.reasons || []).join(' ') || 'Indicadores acima do limiar configurado.' }}
        </Message>

        <Card class="shadow-sm">
            <template #title>Filtros da fila</template>
            <template #content>
                <div
                    class="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-12 lg:items-end"
                >
                    <div class="flex min-w-0 flex-col gap-2 lg:col-span-2">
                        <label class="text-sm font-medium">Status</label>
                        <Dropdown
                            v-model="filters.match_status"
                            :options="statusOptions"
                            optionLabel="label"
                            optionValue="value"
                            class="w-full"
                        />
                    </div>
                    <div class="flex min-w-0 flex-col gap-2 sm:col-span-2 lg:col-span-4">
                        <label class="text-sm font-medium">Busca</label>
                        <InputText
                            v-model="filters.search"
                            placeholder="ID externo, nome ou secretaria"
                            class="w-full"
                            @keyup.enter="aplicarFiltros"
                        />
                    </div>
                    <div class="flex min-w-0 flex-col gap-2 lg:col-span-2">
                        <label class="text-sm font-medium">Conf. mínima</label>
                        <InputNumber
                            v-model="filters.min_confidence"
                            :min="0"
                            :max="1"
                            :step="0.01"
                            mode="decimal"
                            class="w-full"
                            inputClass="w-full"
                        />
                    </div>
                    <div class="flex min-w-0 flex-col gap-2 lg:col-span-1">
                        <label class="text-sm font-medium">Limite</label>
                        <InputNumber
                            v-model="filters.limit"
                            :min="1"
                            :max="500"
                            class="w-full"
                            inputClass="w-full"
                        />
                    </div>
                    <div class="flex min-w-0 flex-col gap-2 sm:col-span-2 lg:col-span-2">
                        <label class="text-sm font-medium">Órgão (carta)</label>
                        <Dropdown
                            v-model="filters.orgao_id"
                            :options="orgaos"
                            optionLabel="label"
                            optionValue="value"
                            filter
                            showClear
                            placeholder="Todos"
                            class="w-full"
                        />
                    </div>
                    <div class="flex min-w-0 flex-col gap-2 sm:col-span-2 lg:col-span-1">
                        <Button
                            label="Filtrar"
                            icon="pi pi-filter"
                            class="w-full shrink-0"
                            :loading="loading"
                            @click="aplicarFiltros"
                        />
                    </div>
                </div>
            </template>
        </Card>

        <Card class="shadow-sm">
            <template #title>Vinculação em lote</template>
            <template #content>
                <p class="text-sm text-surface-600 dark:text-surface-400 mt-0 mb-3">
                    Todos os itens selecionados serão confirmados com o mesmo serviço da carta. Para mapeamentos
                    diferentes, vincule linha a linha na tabela.
                </p>
                <div class="flex flex-wrap gap-3 items-end">
                    <div class="flex-1 min-w-[16rem]">
                        <label class="text-sm font-medium block mb-2">Serviço da carta Sinapse</label>
                        <Dropdown
                            v-model="selectedServicoBulk"
                            :options="servicosCarta"
                            optionLabel="label"
                            optionValue="value"
                            filter
                            showClear
                            placeholder="Selecione o serviço"
                            class="w-full"
                        />
                    </div>
                    <Button
                        label="Vincular selecionados"
                        icon="pi pi-link"
                        :disabled="totalSelecionados === 0"
                        @click="bindBulk"
                    />
                    <Button
                        label="Atualizar"
                        icon="pi pi-refresh"
                        severity="secondary"
                        outlined
                        :loading="loading || loadingHealth"
                        @click="Promise.all([loadHealth(), aplicarFiltros()])"
                    />
                </div>
                <small class="text-surface-500">Selecionados: {{ totalSelecionados }}</small>
            </template>
        </Card>

        <DataTable
            v-model:selection="selectedRows"
            :value="rows"
            dataKey="sinapse_service_id"
            :loading="loading"
            responsiveLayout="scroll"
            class="sgdl-table-scroll"
            paginator
            :rows="20"
            stripedRows
        >
            <Column selectionMode="multiple" headerStyle="width: 3rem" />
            <Column field="sinapse_service_id" header="ID externo (Sinapse)" style="min-width: 8rem" />
            <Column field="service_name" header="Nome na origem" style="min-width: 12rem" />
            <Column field="provider_secretariat" header="Secretaria origem" style="min-width: 10rem" />
            <Column header="Status" style="width: 9rem">
                <template #body="{ data }">
                    <Tag :severity="getStatusSeverity(data.match_status)" :value="data.match_status_label" />
                </template>
            </Column>
            <Column header="Conf." style="width: 4rem">
                <template #body="{ data }">
                    {{ Number(data.confidence || 0).toFixed(2) }}
                </template>
            </Column>
            <Column header="Carta vinculada" style="min-width: 11rem">
                <template #body="{ data }">
                    <template v-if="data.catalog_servico_id">
                        <span class="font-mono text-sm">#{{ data.catalog_servico_id }}</span>
                        <div v-if="data.catalog_titulo" class="text-xs text-surface-500 mt-1 line-clamp-2">
                            {{ data.catalog_titulo }}
                        </div>
                    </template>
                    <span v-else class="text-surface-400 text-sm">—</span>
                </template>
            </Column>
            <Column header="Confirmar vínculo" style="min-width: 18rem">
                <template #body="{ data }">
                    <div class="flex flex-col gap-2">
                        <Dropdown
                            v-model="data._selectedCatalogId"
                            :options="servicosCarta"
                            optionLabel="label"
                            optionValue="value"
                            filter
                            showClear
                            placeholder="Serviço da carta"
                            class="w-full"
                        />
                        <div class="flex flex-wrap gap-1">
                            <Button
                                v-if="podeConfirmarMesmoId(data)"
                                label="Mesmo ID numérico"
                                icon="pi pi-bolt"
                                size="small"
                                severity="help"
                                outlined
                                v-tooltip.top="'Confirma quando o ID externo já é o ID do catálogo'"
                                @click="confirmarMesmoId(data)"
                            />
                            <Button
                                icon="pi pi-check"
                                severity="success"
                                size="small"
                                rounded
                                v-tooltip.top="'Confirmar vínculo'"
                                @click="bindSingle(data)"
                            />
                        </div>
                        <small
                            v-if="data.last_manual_actor"
                            class="text-surface-500"
                        >
                            {{ data.last_manual_actor }} · {{ formatarData(data.last_manual_at) }}
                        </small>
                    </div>
                </template>
            </Column>
            <template #empty>
                <div class="py-8 text-center text-surface-500">Nenhum item para os filtros atuais.</div>
            </template>
        </DataTable>
    </div>
</template>
