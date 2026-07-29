<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';

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
import { filtrarAtalhosConsultaSemSla, ocultarMetricasSla } from '@/utils/metricasSlaVereador';

const router = useRouter();
const userStore = useUserStore();
const toast = useToast();

const carregando = ref(true);
const buscando = ref(false);
const atalhos = ref([]);
const perfilHub = ref('');
const termoBusca = ref('');
const resultadoBusca = ref(null);

let debounceTimer = null;

const perfilLabel = computed(() => {
    const map = {
        VEREADOR: 'Vereador',
        PROTOCOLO: 'Protocolo',
        SECRETARIA: 'Secretaria',
        GESTOR: 'Gestão'
    };
    return map[perfilHub.value] || userStore.currentUser?.perfil || '';
});

const ocultarSlaVereador = computed(() => ocultarMetricasSla(userStore.currentUser?.perfil));

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    return 'Não foi possível carregar o hub de consultas.';
};

const carregarHub = async () => {
    carregando.value = true;
    try {
        const { data } = await ApiService.getConsultaHub();
        atalhos.value = filtrarAtalhosConsultaSemSla(data?.atalhos || [], userStore.currentUser?.perfil);
        perfilHub.value = data?.perfil || userStore.currentUser?.perfil || '';
    } catch (error) {
        atalhos.value = [];
        toast.add({
            severity: 'error',
            summary: 'Consulta',
            detail: extrairErro(error),
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
};

const executarBusca = async (texto) => {
    const q = (texto || '').trim();
    if (q.length < 2) {
        resultadoBusca.value = null;
        return;
    }
    buscando.value = true;
    try {
        const { data } = await ApiService.buscarConsultaHub({ q, limit: 15 });
        resultadoBusca.value = data;
    } catch (error) {
        resultadoBusca.value = { demandas: [], servicos_carta: [], q };
        toast.add({
            severity: 'warn',
            summary: 'Busca',
            detail: extrairErro(error),
            life: 4000
        });
    } finally {
        buscando.value = false;
    }
};

watch(termoBusca, (val) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => executarBusca(val), 400);
});

const abrirAtalho = (atalho) => {
    if (!atalho?.rota) return;
    router.push({ path: atalho.rota, query: { ...(atalho.query || {}) } });
};

const abrirDemanda = (row) => {
    if (row?.status === 'RASCUNHO' && userStore.currentUser?.perfil !== 'VEREADOR') {
        toast.add({
            severity: 'warn',
            summary: 'Acesso restrito',
            detail: 'Rascunhos só podem ser abertos pelo autor vereador.',
            life: 4000
        });
        return;
    }
    router.push({ name: 'demandas-detalhes', params: { id: row.id } });
};

const abrirCarta = () => {
    router.push({ name: 'carta-servicos' });
};

const formatarContagem = (n) => {
    if (n == null) return null;
    return n > 99 ? '99+' : String(n);
};

const severityStatus = (status) => {
    const map = {
        RASCUNHO: 'info',
        AGUARDANDO_PROTOCOLO: 'warn',
        PROTOCOLADO: 'primary',
        EM_EXECUCAO: 'success',
        FINALIZADO: 'success'
    };
    return map[status] || 'secondary';
};

onMounted(carregarHub);
</script>

<template>
    <div class="flex flex-col gap-6 max-w-6xl mx-auto">
        <div>
            <h2 class="text-2xl font-semibold m-0">Consulta rápida</h2>
            <p class="text-surface-600 mt-1 mb-0 text-sm">
                Hub operacional para <strong>{{ perfilLabel }}</strong> — atalhos às filas e busca
                unificada em demandas e carta de serviços.
            </p>
        </div>

        <IconField class="w-full">
            <InputIcon class="pi pi-search" />
            <InputText
                v-model="termoBusca"
                placeholder="Buscar por protocolo, assunto, endereço ou serviço..."
                fluid
                autocomplete="off"
            />
        </IconField>

        <div v-if="buscando" class="flex justify-center py-4">
            <ProgressSpinner style="width: 2rem; height: 2rem" />
        </div>

        <template v-if="resultadoBusca && termoBusca.trim().length >= 2 && !buscando">
            <Card v-if="resultadoBusca.demandas?.length">
                <template #title>Demandas</template>
                <template #content>
                    <DataTable
                        :value="resultadoBusca.demandas"
                        size="small"
                        stripedRows
                        class="sgdl-table-scroll"
                        @row-click="(e) => abrirDemanda(e.data)"
                        rowHover
                    >
                        <Column field="titulo" header="Assunto">
                            <template #body="{ data }">
                                <span class="font-medium cursor-pointer">{{ data.titulo }}</span>
                            </template>
                        </Column>
                        <Column header="Protocolo">
                            <template #body="{ data }">
                                <span class="text-sm">
                                    {{ data.protocolo_executivo || data.protocolo_legislativo || '—' }}
                                </span>
                            </template>
                        </Column>
                        <Column header="Local">
                            <template #body="{ data }">
                                <span class="text-sm">{{ data.bairro || data.endereco || '—' }}</span>
                            </template>
                        </Column>
                        <Column header="Status">
                            <template #body="{ data }">
                                <Tag :value="data.status" :severity="severityStatus(data.status)" />
                            </template>
                        </Column>
                    </DataTable>
                </template>
            </Card>

            <Card v-if="resultadoBusca.servicos_carta?.length">
                <template #title>Carta de serviços</template>
                <template #content>
                    <ul class="list-none p-0 m-0 flex flex-col gap-2">
                        <li
                            v-for="svc in resultadoBusca.servicos_carta"
                            :key="svc.id"
                            class="flex justify-between items-center gap-3 p-3 rounded-border border border-surface-200 cursor-pointer hover:bg-surface-50"
                            @click="abrirCarta"
                        >
                            <div>
                                <span class="font-medium">{{ svc.nome }}</span>
                                <p v-if="svc.orgao" class="text-xs text-surface-500 m-0">{{ svc.orgao }}</p>
                            </div>
                            <Tag v-if="svc.prazo_dias && !ocultarSlaVereador" :value="`${svc.prazo_dias}d`" severity="info" />
                        </li>
                    </ul>
                </template>
            </Card>

            <Message
                v-if="!resultadoBusca.demandas?.length && !resultadoBusca.servicos_carta?.length"
                severity="info"
                :closable="false"
            >
                Nenhum resultado para «{{ resultadoBusca.q }}».
            </Message>
        </template>

        <div v-if="carregando" class="flex justify-center py-12">
            <ProgressSpinner />
        </div>

        <div v-else-if="!termoBusca.trim()" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <button
                v-for="atalho in atalhos"
                :key="atalho.id"
                type="button"
                class="text-left p-0 border-0 bg-transparent cursor-pointer"
                @click="abrirAtalho(atalho)"
            >
                <Card class="h-full transition-shadow hover:shadow-md">
                    <template #content>
                        <div class="flex items-start gap-3">
                            <span
                                class="inline-flex items-center justify-center w-10 h-10 rounded-full bg-primary-50 text-primary"
                            >
                                <i :class="atalho.icone" />
                            </span>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 flex-wrap">
                                    <span class="font-semibold">{{ atalho.titulo }}</span>
                                    <Tag
                                        v-if="formatarContagem(atalho.contagem) != null"
                                        :value="formatarContagem(atalho.contagem)"
                                        severity="secondary"
                                        rounded
                                    />
                                </div>
                                <p class="text-sm text-surface-600 m-0 mt-1">{{ atalho.descricao }}</p>
                            </div>
                            <i class="pi pi-chevron-right text-surface-400 shrink-0" />
                        </div>
                    </template>
                </Card>
            </button>
        </div>
    </div>
</template>
