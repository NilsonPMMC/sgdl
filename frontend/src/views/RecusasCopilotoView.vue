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
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import Tag from 'primevue/tag';

const toast = useToast();
const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const isGestor = computed(() => userStore.currentUser?.perfil === 'GESTOR');

const loading = ref(false);
const recusas = ref([]);
const buscaMotivo = ref('');

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    return 'Não foi possível carregar as recusas do Copiloto.';
};

const formatarData = (iso) => {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString('pt-BR');
    } catch {
        return iso;
    }
};

async function carregarRecusas() {
    loading.value = true;
    try {
        const params = {};
        const motivoQs = route.query?.motivo;
        if (typeof motivoQs === 'string' && motivoQs.trim()) {
            params.motivo = motivoQs.trim();
            buscaMotivo.value = motivoQs.trim();
        } else if (buscaMotivo.value.trim()) {
            params.motivo = buscaMotivo.value.trim();
        }
        const { data } = await ApiService.listarRecusasCopiloto(params);
        recusas.value = data?.recusas || [];
    } catch (error) {
        recusas.value = [];
        toast.add({
            severity: 'error',
            summary: 'Erro ao carregar',
            detail: extrairErro(error),
            life: 5000
        });
    } finally {
        loading.value = false;
    }
}

const recusasFiltradas = computed(() => {
    const q = buscaMotivo.value.trim().toLowerCase();
    if (!q) return recusas.value;
    return recusas.value.filter(
        (r) =>
            (r.motivo_recusa || '').toLowerCase().includes(q) ||
            (r.titulo || '').toLowerCase().includes(q) ||
            (r.autor_nome || '').toLowerCase().includes(q)
    );
});

const limparBusca = () => {
    buscaMotivo.value = '';
    if (route.query?.motivo) {
        router.replace({ name: 'gestao-recusas-copiloto' });
    }
    carregarRecusas();
};

const irFaqCopiloto = () => router.push({ name: 'admin-faq-copiloto' });

onMounted(carregarRecusas);

watch(
    () => route.query?.motivo,
    () => {
        carregarRecusas();
    }
);
</script>

<template>
    <div class="grid min-w-0">
        <div class="col-12 min-w-0">
            <Card>
                <template #title>
                    <div class="flex flex-wrap items-center justify-between gap-3">
                        <span>Recusas no Copiloto</span>
                        <Button
                            label="Voltar ao dashboard"
                            icon="pi pi-arrow-left"
                            text
                            size="small"
                            @click="router.push({ name: 'dashboard' })"
                        />
                    </div>
                </template>
                <template #content>
                    <Message severity="info" :closable="false" class="mb-4 text-sm">
                        Pedidos barrados <strong>antes</strong> de virar ofício — fora de competência municipal ou
                        descartados pelo vereador no chat. Não entram na fila do Protocolo.
                    </Message>

                    <div class="flex flex-wrap gap-2 mb-4">
                        <IconField class="flex-1" style="min-width: 14rem">
                            <InputIcon class="pi pi-search" />
                            <InputText
                                v-model="buscaMotivo"
                                placeholder="Filtrar por motivo, título ou vereador"
                                class="w-full"
                                @keyup.enter="carregarRecusas"
                            />
                        </IconField>
                        <Button label="Buscar" icon="pi pi-search" @click="carregarRecusas" />
                        <Button label="Limpar" icon="pi pi-filter-slash" outlined @click="limparBusca" />
                        <Button
                            v-if="isGestor"
                            label="FAQ Copiloto"
                            icon="pi pi-sparkles"
                            outlined
                            severity="secondary"
                            @click="irFaqCopiloto"
                        />
                    </div>

                    <div v-if="loading" class="flex justify-center py-8">
                        <ProgressSpinner style="width: 2.5rem; height: 2.5rem" />
                    </div>
                    <div v-else-if="!recusasFiltradas.length" class="text-sm text-muted-color py-4">
                        Nenhuma recusa encontrada para os filtros atuais.
                    </div>
                    <DataTable
                        v-else
                        :value="recusasFiltradas"
                        stripedRows
                        paginator
                        :rows="15"
                        :rowsPerPageOptions="[15, 30, 50]"
                        sortField="atualizado_em"
                        :sortOrder="-1"
                        responsiveLayout="scroll"
                        class="p-datatable-sm"
                    >
                        <Column field="atualizado_em" header="Data" sortable style="min-width: 10rem">
                            <template #body="{ data }">
                                {{ formatarData(data.atualizado_em) }}
                            </template>
                        </Column>
                        <Column field="autor_nome" header="Vereador" sortable style="min-width: 9rem" />
                        <Column field="titulo" header="Pedido" sortable style="min-width: 12rem" />
                        <Column field="motivo_recusa" header="Motivo da recusa" sortable style="min-width: 16rem">
                            <template #body="{ data }">
                                <span class="text-sm">{{ data.motivo_recusa }}</span>
                            </template>
                        </Column>
                        <Column header="Tipo" style="width: 8rem">
                            <template #body="{ data }">
                                <Tag
                                    :value="data.descartada ? 'Descartado' : 'Fora competência'"
                                    :severity="data.descartada ? 'secondary' : 'warn'"
                                />
                            </template>
                        </Column>
                    </DataTable>
                </template>
            </Card>
        </div>
    </div>
</template>
