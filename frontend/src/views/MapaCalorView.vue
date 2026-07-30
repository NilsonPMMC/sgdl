<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import ApiService from '@/service/ApiService';
import { STATUS_CHOICES_REPORTS } from '@/constants';
import { useUserStore } from '@/stores/userStore';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import 'leaflet.heat';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import { formatarProtocoloLegislativo } from '@/utils/protocoloLegislativo';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Chart from 'primevue/chart';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import DatePicker from 'primevue/datepicker';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import MultiSelect from 'primevue/multiselect';
import Select from 'primevue/select';
import SelectButton from 'primevue/selectbutton';
import Tag from 'primevue/tag';
import ToggleSwitch from 'primevue/toggleswitch';
import { SGDL_BRAND } from '@/theme/sgdl-preset';
import { ocultarMetricasSla } from '@/utils/metricasSlaVereador';

const userStore = useUserStore();
const route = useRoute();
const perfil = computed(() => userStore.currentUser?.perfil);
const ocultarSlaVereador = computed(() => ocultarMetricasSla(perfil.value));
const podeFiltrarOrgao = computed(() => ['GESTOR', 'PROTOCOLO', 'CAMARA'].includes(perfil.value));
const podeFiltrarVereador = computed(() => ['GESTOR', 'PROTOCOLO'].includes(perfil.value));
const isCamara = computed(() => perfil.value === 'CAMARA');
const opcoesStatusMapa = computed(() => {
    if (['CAMARA', 'VEREADOR'].includes(perfil.value)) {
        return STATUS_CHOICES_REPORTS;
    }
    return STATUS_CHOICES_REPORTS.filter((s) => s.value !== 'RASCUNHO');
});

const loading = ref(false);
const loadingAgregacao = ref(false);
const map = ref(null);
const tileLayer = ref(null);
const markerClusterGroup = ref(null);
const heatLayer = ref(null);
const ultimaLista = ref([]);
const mapaPronto = ref(false);
let resizeObserver = null;
const resumo = ref({ total: 0, atrasadas: 0, super_os: 0 });
const agregacao = ref({ por_bairro: [], por_mes: [], hotspots: [] });

const modoVisualizacao = ref('pinos');
const modosVisualizacao = [
    { label: 'Pinos', value: 'pinos', icon: 'pi pi-map-marker' },
    { label: 'Heatmap', value: 'heatmap', icon: 'pi pi-sun' },
    { label: 'Ambos', value: 'ambos', icon: 'pi pi-objects-column' }
];

const filtros = ref({
    q: '',
    status: [],
    sinapse_orgao_id: null,
    servico_id: null,
    vereador_id: null,
    data_inicio: null,
    data_fim: null,
    super_os: false
});

const opcoes = ref({
    secretarias: [],
    servicos: [],
    vereadores: []
});

const STATUS_CORES = {
    ATRASADA: { cor: '#ef4444', rotulo: 'Atrasada' },
    AGUARDANDO_PROTOCOLO: { cor: '#f59e0b', rotulo: 'Aguardando protocolo' },
    PROTOCOLADO: { cor: SGDL_BRAND.primary, rotulo: 'Protocolado' },
    EM_EXECUCAO: { cor: '#22c55e', rotulo: 'Em execução' },
    FINALIZADO: { cor: '#64748b', rotulo: 'Finalizado' },
    CANCELADO: { cor: '#991b1b', rotulo: 'Cancelado' },
    AGUARDANDO_TRANSFERENCIA: { cor: '#f97316', rotulo: 'Aguardando transferência' },
    AGUARDANDO_DEVOLUTIVA_PROTOCOLO: { cor: '#a855f7', rotulo: 'Aguardando devolutiva' },
    DEVOLVIDO_VEREADOR: { cor: '#06b6d4', rotulo: 'Devolutiva ao vereador' }
};

const legendaItens = computed(() => {
    const itens = Object.values(STATUS_CORES).filter((x) => x !== STATUS_CORES.ATRASADA);
    if (!ocultarSlaVereador.value) {
        itens.unshift(STATUS_CORES.ATRASADA);
    }
    itens.push({ cor: '#7c3aed', rotulo: 'Super OS (contorno)', superOs: true });
    return itens;
});

const chartMeses = computed(() => {
    const meses = agregacao.value.por_mes || [];
    return {
        labels: meses.map((m) => m.mes),
        datasets: [
            {
                label: 'Demandas',
                data: meses.map((m) => m.total),
                backgroundColor: 'color-mix(in srgb, var(--p-primary-500) 60%, transparent)',
                borderColor: SGDL_BRAND.primary,
                borderWidth: 1
            }
        ]
    };
});

const chartOptions = {
    plugins: { legend: { display: false } },
    scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
        x: { ticks: { maxRotation: 45, minRotation: 45 } }
    },
    maintainAspectRatio: false
};

const estiloMarcador = (loc) => {
    if (!ocultarSlaVereador.value && loc.is_atrasada) return STATUS_CORES.ATRASADA;
    return STATUS_CORES[loc.status] || { cor: '#64748b', rotulo: loc.status_display || loc.status };
};

const criarIcone = (loc) => {
    const { cor } = estiloMarcador(loc);
    const superAtivo = loc.super_os?.ativo;
    const lider = loc.super_os?.eh_lider;
    const classe = superAtivo ? 'map-marker map-marker--super' : 'map-marker';
    const icone = superAtivo ? (lider ? 'pi-star-fill' : 'pi-clone') : 'pi-map-marker';
    return L.divIcon({
        className: 'custom-map-icon',
        html: `<div class="${classe}" style="--marker-color:${cor}"><i class="pi ${icone}"></i></div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -28]
    });
};

const popupHtml = (loc) => {
    const { cor, rotulo } = estiloMarcador(loc);
    const superHtml = loc.super_os?.ativo
        ? `<div class="mt-2">
            <span class="map-popup-badge map-popup-badge--super">Super OS ${loc.super_os.protocolo_super_os || ''}</span>
            ${loc.super_os.eh_lider ? '<span class="map-popup-badge map-popup-badge--lider">Líder</span>' : ''}
            <span class="text-xs text-muted">${loc.super_os.total_vinculados} vinculada(s)</span>
           </div>`
        : '';
    const setor = loc.unidade_sigla || loc.unidade_nome;
    return `
        <div class="map-popup">
            <div class="font-semibold">${loc.protocolo || formatarProtocoloLegislativo(loc.protocolo_legislativo) || 'Sem protocolo'}</div>
            <div class="text-sm mt-1">${loc.titulo}</div>
            <div class="mt-2">
                <span class="map-popup-badge" style="background:${cor}">${!ocultarSlaVereador.value && loc.is_atrasada ? 'Atrasada' : rotulo}</span>
            </div>
            ${loc.bairro ? `<div class="text-xs mt-2">${loc.bairro}</div>` : ''}
            ${setor ? `<div class="text-xs">Setor: ${setor}</div>` : ''}
            ${superHtml}
            <a class="text-primary text-sm mt-2 inline-block" href="/demandas/detalhes/${loc.id}">Ver detalhes →</a>
        </div>
    `;
};

const formatarDataParaAPI = (data) => {
    if (!data) return null;
    const d = new Date(data);
    d.setMinutes(d.getMinutes() + d.getTimezoneOffset());
    return d.toISOString().split('T')[0];
};

const montarParams = () => {
    const params = {
        q: filtros.value.q?.trim() || undefined,
        sinapse_orgao_id: filtros.value.sinapse_orgao_id || undefined,
        servico_id: filtros.value.servico_id || undefined,
        data_inicio: formatarDataParaAPI(filtros.value.data_inicio),
        data_fim: formatarDataParaAPI(filtros.value.data_fim),
        super_os: filtros.value.super_os ? '1' : undefined,
        demanda_id: route.query.demanda_id || undefined
    };
    if (filtros.value.status?.length) {
        params.status__in = filtros.value.status.join(',');
    }
    if (podeFiltrarVereador.value && filtros.value.vereador_id) {
        params.vereador_id = filtros.value.vereador_id;
    }
    Object.keys(params).forEach((k) => {
        if (params[k] == null || params[k] === '') delete params[k];
    });
    return params;
};

const pontosHeatmap = (lista) =>
    lista.map((loc) => {
        let peso = 0.45;
        if (!ocultarSlaVereador.value && loc.is_atrasada) peso = 1;
        else if (loc.super_os?.ativo) peso = 0.75;
        return [parseFloat(loc.lat), parseFloat(loc.lng), peso];
    });

const refreshMapView = () => {
    if (!map.value) return;
    map.value.invalidateSize({ animate: false });
    tileLayer.value?.redraw?.();
};

const initMapa = () => {
    const el = document.getElementById('map-container');
    if (!el || map.value) return;

    map.value = L.map(el, { scrollWheelZoom: true, preferCanvas: false }).setView([-23.523, -46.18], 13);
    tileLayer.value = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap',
        maxZoom: 19
    });
    tileLayer.value.addTo(map.value);

    markerClusterGroup.value = L.markerClusterGroup({
        maxClusterRadius: 50,
        iconCreateFunction(cluster) {
            const markers = cluster.getAllChildMarkers();
            let atrasadas = 0;
            let superOs = 0;
            markers.forEach((m) => {
                const d = m.options.customData;
                if (!ocultarSlaVereador.value && d?.is_atrasada) atrasadas++;
                if (d?.super_os?.ativo) superOs++;
            });
            let cssClass = 'marker-cluster-blue';
            if (!ocultarSlaVereador.value && atrasadas > 0) cssClass = 'marker-cluster-red';
            else if (superOs > 0) cssClass = 'marker-cluster-purple';
            return L.divIcon({
                html: `<div><span>${cluster.getChildCount()}</span></div>`,
                className: `marker-cluster ${cssClass}`,
                iconSize: new L.Point(42, 42)
            });
        }
    });
    map.value.addLayer(markerClusterGroup.value);
    mapaPronto.value = true;
    refreshMapView();
};

const limparCamadas = () => {
    markerClusterGroup.value?.clearLayers();
    if (heatLayer.value && map.value) {
        map.value.removeLayer(heatLayer.value);
        heatLayer.value = null;
    }
};

const renderizarCamadas = async (lista) => {
    if (!map.value) return;
    limparCamadas();
    const modo = modoVisualizacao.value;

    if (lista.length && (modo === 'pinos' || modo === 'ambos')) {
        const markers = lista.map((loc) => {
            const marker = L.marker([parseFloat(loc.lat), parseFloat(loc.lng)], { icon: criarIcone(loc) });
            marker.options.customData = loc;
            marker.bindPopup(popupHtml(loc), { maxWidth: 280 });
            return marker;
        });
        markerClusterGroup.value.addLayers(markers);
    }

    if (lista.length && (modo === 'heatmap' || modo === 'ambos')) {
        heatLayer.value = L.heatLayer(pontosHeatmap(lista), {
            radius: 30,
            blur: 24,
            maxZoom: 16,
            minOpacity: 0.35,
            gradient: {
                0.25: SGDL_BRAND.primaryLight,
                0.5: '#f59e0b',
                0.75: '#ef4444',
                1.0: '#7f1d1d'
            }
        });
        map.value.addLayer(heatLayer.value);
    }

    await nextTick();
    refreshMapView();

    if (lista.length) {
        requestAnimationFrame(() => {
            if (!map.value) return;
            const bounds = L.latLngBounds(lista.map((l) => [parseFloat(l.lat), parseFloat(l.lng)]));
            map.value.fitBounds(bounds.pad(0.12), { animate: false });
            refreshMapView();
        });
    }
};

const carregarAgregacao = async () => {
    loadingAgregacao.value = true;
    try {
        const { data } = await ApiService.getMapaAgregacao(montarParams());
        agregacao.value = data || { por_bairro: [], por_mes: [], hotspots: [] };
    } catch (error) {
        console.error('Erro agregação mapa:', error);
        agregacao.value = { por_bairro: [], por_mes: [], hotspots: [] };
    } finally {
        loadingAgregacao.value = false;
    }
};

const carregarLocalizacoes = async () => {
    loading.value = true;
    try {
        const params = montarParams();
        const [locRes] = await Promise.all([
            ApiService.getDemandaLocations(params),
            carregarAgregacao()
        ]);
        const data = locRes.data;
        const lista = Array.isArray(data) ? data : data?.results ?? [];
        ultimaLista.value = lista;
        resumo.value = data?.resumo || {
            total: lista.length,
            atrasadas: ocultarSlaVereador.value ? 0 : lista.filter((x) => x.is_atrasada).length,
            super_os: lista.filter((x) => x.super_os?.ativo).length
        };
        if (ocultarSlaVereador.value && resumo.value) {
            resumo.value = { ...resumo.value, atrasadas: 0 };
        }
        renderizarCamadas(lista);
        const focoId = route.query.demanda_id;
        if (focoId && markerClusterGroup.value) {
            await nextTick();
            markerClusterGroup.value.eachLayer((layer) => {
                if (String(layer.options?.customData?.id) === String(focoId)) {
                    const latlng = layer.getLatLng?.();
                    if (latlng && map.value) {
                        map.value.setView(latlng, 16, { animate: true });
                    }
                    layer.openPopup?.();
                }
            });
        }
    } catch (error) {
        console.error('Erro ao carregar localizações:', error);
        ultimaLista.value = [];
        resumo.value = { total: 0, atrasadas: 0, super_os: 0 };
        limparCamadas();
    } finally {
        loading.value = false;
    }
};

watch(modoVisualizacao, () => {
    renderizarCamadas(ultimaLista.value);
});

watch(
    () => agregacao.value.por_mes?.length,
    () => {
        nextTick(() => refreshMapView());
    }
);

const limparFiltros = () => {
    filtros.value = {
        q: '',
        status: [],
        sinapse_orgao_id: null,
        servico_id: null,
        vereador_id: null,
        data_inicio: null,
        data_fim: null,
        super_os: false
    };
    carregarLocalizacoes();
};

const servicosFiltrados = computed(() => {
    if (!filtros.value.sinapse_orgao_id) return opcoes.value.servicos;
    const orgaoId = filtros.value.sinapse_orgao_id;
    return opcoes.value.servicos.filter(
        (s) => !s.secretaria_responsavel?.id || s.secretaria_responsavel.id === orgaoId
    );
});

const extrairListaApi = (resultado) => {
    if (resultado?.status !== 'fulfilled') return [];
    const payload = resultado.value?.data;
    return payload?.results || payload || [];
};

const carregarOpcoesFiltros = async () => {
    try {
        const [secRes, srvRes] = await Promise.allSettled([
            ApiService.getSecretarias(),
            ApiService.getServicos()
        ]);
        opcoes.value.secretarias = extrairListaApi(secRes);
        opcoes.value.servicos = extrairListaApi(srvRes);
        if (podeFiltrarVereador.value) {
            const { data } = await ApiService.getUsuarios({ perfil: 'VEREADOR' });
            const vereadores = data?.results || data || [];
            opcoes.value.vereadores = vereadores.map((user) => ({
                ...user,
                nome_formatado: `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username
            }));
        }
    } catch (error) {
        console.error('Erro ao carregar opções do mapa:', error);
    }
};

const initMapaSeguro = () => {
    try {
        initMapa();
        const el = document.getElementById('map-container');
        if (el && typeof ResizeObserver !== 'undefined') {
            resizeObserver = new ResizeObserver(() => refreshMapView());
            resizeObserver.observe(el);
        }
    } catch (error) {
        console.error('Erro ao inicializar mapa:', error);
    }
};

const maxBairroTotal = computed(() =>
    Math.max(1, ...(agregacao.value.por_bairro || []).map((b) => b.total))
);

onMounted(async () => {
    await nextTick();
    await new Promise((resolve) => {
        requestAnimationFrame(() => {
            initMapaSeguro();
            resolve();
        });
    });

    await Promise.all([carregarOpcoesFiltros(), carregarLocalizacoes()]);
    setTimeout(refreshMapView, 150);
});

onUnmounted(() => {
    resizeObserver?.disconnect();
    map.value?.remove();
    map.value = null;
});
</script>

<template>
    <div class="flex flex-col gap-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
                <h1 class="text-2xl font-semibold m-0">Mapa operacional</h1>
                <p class="text-muted-color m-0 mt-1">
                    Demandas georreferenciadas — pinos por status, heatmap de densidade e análise bairro × serviço × mês.
                </p>
            </div>
            <SelectButton
                v-model="modoVisualizacao"
                :options="modosVisualizacao"
                optionLabel="label"
                optionValue="value"
                aria-label="Modo de visualização do mapa"
            />
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card>
                <template #content>
                    <div class="text-center py-1">
                        <div class="text-2xl font-bold">{{ resumo.total }}</div>
                        <div class="text-sm text-muted-color">Pontos no mapa</div>
                    </div>
                </template>
            </Card>
            <Card v-if="!ocultarSlaVereador">
                <template #content>
                    <div class="text-center py-1">
                        <div class="text-2xl font-bold text-red-500">{{ resumo.atrasadas }}</div>
                        <div class="text-sm text-muted-color">Atrasadas</div>
                    </div>
                </template>
            </Card>
            <Card>
                <template #content>
                    <div class="text-center py-1">
                        <div class="text-2xl font-bold text-violet-600">{{ resumo.super_os }}</div>
                        <div class="text-sm text-muted-color">Super OS</div>
                    </div>
                </template>
            </Card>
            <Card>
                <template #content>
                    <div class="text-center py-1">
                        <div class="text-sm text-muted-color mt-2">
                            Perfil: <Tag :value="perfil || '—'" severity="info" />
                        </div>
                    </div>
                </template>
            </Card>
        </div>

        <Card>
            <template #title>Filtros</template>
            <template #content>
                <div class="flex flex-wrap gap-3 mb-3">
                    <IconField class="flex-1 min-w-[14rem]">
                        <InputIcon class="pi pi-search" />
                        <InputText
                            v-model="filtros.q"
                            placeholder="Buscar protocolo, título, bairro..."
                            fluid
                            @keyup.enter="carregarLocalizacoes"
                        />
                    </IconField>
                    <MultiSelect
                        v-model="filtros.status"
                        :options="opcoesStatusMapa"
                        optionLabel="label"
                        optionValue="value"
                        placeholder="Status"
                        filter
                        showClear
                        class="min-w-[12rem]"
                    />
                    <Select
                        v-if="podeFiltrarOrgao"
                        v-model="filtros.sinapse_orgao_id"
                        :options="opcoes.secretarias"
                        optionLabel="nome"
                        optionValue="id"
                        placeholder="Órgão"
                        filter
                        showClear
                        class="min-w-[12rem]"
                        @change="filtros.servico_id = null"
                    />
                    <Select
                        v-model="filtros.servico_id"
                        :options="servicosFiltrados"
                        optionLabel="nome"
                        optionValue="id"
                        placeholder="Serviço Sinapse"
                        filter
                        showClear
                        class="min-w-[12rem]"
                    />
                </div>
                <div class="flex flex-wrap gap-3 items-end">
                    <div class="flex flex-col gap-1">
                        <label class="text-sm font-medium">De</label>
                        <DatePicker v-model="filtros.data_inicio" dateFormat="dd/mm/yy" showIcon />
                    </div>
                    <div class="flex flex-col gap-1">
                        <label class="text-sm font-medium">Até</label>
                        <DatePicker v-model="filtros.data_fim" dateFormat="dd/mm/yy" showIcon />
                    </div>
                    <Select
                        v-if="podeFiltrarVereador"
                        v-model="filtros.vereador_id"
                        :options="opcoes.vereadores"
                        optionLabel="nome_formatado"
                        optionValue="id"
                        placeholder="Vereador"
                        filter
                        showClear
                        class="min-w-[12rem]"
                    />
                    <div class="flex items-center gap-2 pb-1">
                        <ToggleSwitch v-model="filtros.super_os" inputId="filtro-super-os" />
                        <label for="filtro-super-os" class="text-sm">Somente Super OS</label>
                    </div>
                    <Button label="Aplicar" icon="pi pi-filter" :loading="loading" @click="carregarLocalizacoes" />
                    <Button label="Limpar" icon="pi pi-times" severity="secondary" outlined @click="limparFiltros" />
                </div>
            </template>
        </Card>

        <div class="grid grid-cols-1 xl:grid-cols-12 gap-4">
            <div class="xl:col-span-8 mapa-wrapper relative">
                <div id="map-container" class="mapa-container"></div>
                <div v-if="loading" class="mapa-loading-overlay">
                    <i class="pi pi-spin pi-spinner text-2xl" />
                </div>
                <Card class="mapa-legenda absolute bottom-3 left-3 z-[1000] shadow-lg">
                    <template #content>
                        <div class="text-xs font-semibold mb-2">Legenda — pinos</div>
                        <div class="flex flex-col gap-1">
                            <div
                                v-for="(item, idx) in legendaItens"
                                :key="idx"
                                class="flex items-center gap-2 text-xs"
                            >
                                <span
                                    class="legenda-amostra"
                                    :class="{ 'legenda-amostra--super': item.superOs }"
                                    :style="item.superOs ? {} : { background: item.cor }"
                                />
                                {{ item.rotulo }}
                            </div>
                        </div>
                        <div v-if="modoVisualizacao !== 'pinos'" class="text-xs text-muted-color mt-2 pt-2 border-t border-surface-200 dark:border-surface-700">
                            Heatmap: azul (baixa) → laranja → vermelho (alta densidade/atraso)
                        </div>
                    </template>
                </Card>
                <Message
                    v-if="!loading && resumo.total === 0"
                    severity="info"
                    :closable="false"
                    class="absolute top-3 right-3 z-[1000] max-w-xs"
                >
                    <template v-if="isCamara">
                        Nenhuma indicação georreferenciada no mapa. Indicações precisam de endereço ou
                        ponto confirmado no Copiloto para aparecer aqui.
                    </template>
                    <template v-else>
                        Nenhuma demanda com coordenadas para os filtros selecionados.
                    </template>
                </Message>
            </div>

            <div class="xl:col-span-4 flex flex-col gap-4">
                <Card>
                    <template #title>Hotspots (bairro × serviço)</template>
                    <template #content>
                        <div v-if="loadingAgregacao" class="text-center py-6 text-sm text-muted-color">Carregando…</div>
                        <DataTable
                            v-else-if="agregacao.hotspots?.length"
                            :value="agregacao.hotspots"
                            size="small"
                            stripedRows
                            scrollable
                            scrollHeight="220px"
                        >
                            <Column header="Bairro" field="bairro" />
                            <Column header="Serviço">
                                <template #body="{ data }">
                                    <span class="text-xs line-clamp-2">{{ data.servico_nome }}</span>
                                </template>
                            </Column>
                            <Column header="Qtd" field="total" style="width: 3rem" />
                        </DataTable>
                        <Message v-else severity="secondary" :closable="false" class="text-sm">
                            Sem hotspots para os filtros atuais.
                        </Message>
                    </template>
                </Card>

                <Card>
                    <template #title>Top bairros</template>
                    <template #content>
                        <div v-if="loadingAgregacao" class="text-center py-4 text-sm text-muted-color">Carregando…</div>
                        <ul v-else-if="agregacao.por_bairro?.length" class="list-none p-0 m-0 flex flex-col gap-2">
                            <li v-for="b in agregacao.por_bairro" :key="b.bairro">
                                <div class="flex justify-between text-sm mb-1">
                                    <span class="font-medium truncate pr-2">{{ b.bairro }}</span>
                                    <span>{{ b.total }}</span>
                                </div>
                                <div class="h-2 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
                                    <div
                                        class="h-full rounded-full bg-primary"
                                        :style="{ width: `${(b.total / maxBairroTotal) * 100}%` }"
                                    />
                                </div>
                                <div v-if="b.atrasadas && !ocultarSlaVereador" class="text-xs text-red-500 mt-0.5">
                                    {{ b.atrasadas }} atrasada(s)
                                </div>
                            </li>
                        </ul>
                        <Message v-else severity="secondary" :closable="false" class="text-sm">Sem dados por bairro.</Message>
                    </template>
                </Card>

                <Card>
                    <template #title>Sazonalidade (por mês)</template>
                    <template #content>
                        <div v-if="loadingAgregacao" class="text-center py-6 text-sm text-muted-color">Carregando…</div>
                        <div v-else-if="agregacao.por_mes?.length" class="chart-meses-host">
                            <Chart type="bar" :data="chartMeses" :options="chartOptions" />
                        </div>
                        <Message v-else severity="secondary" :closable="false" class="text-sm">
                            Sem série temporal para o período.
                        </Message>
                    </template>
                </Card>
            </div>
        </div>
    </div>
</template>

<style lang="scss">
.mapa-wrapper {
    min-height: 480px;
}

.mapa-container {
    height: 62vh;
    min-height: 480px;
    width: 100%;
    border-radius: var(--border-radius);
    z-index: 0;
}

.mapa-wrapper :deep(.leaflet-container) {
    height: 100% !important;
    width: 100% !important;
    min-height: 480px;
    background: #e2e8f0 !important;
    font-family: inherit;
}

.mapa-loading-overlay {
    position: absolute;
    inset: 0;
    z-index: 500;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.12);
    border-radius: var(--border-radius);
    pointer-events: none;
}

.chart-meses-host {
    height: 200px;
}

.mapa-legenda {
    max-width: 14rem;
    background: var(--surface-card);
    opacity: 0.95;
}

.legenda-amostra {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;

    &--super {
        border: 2px solid #7c3aed;
        background: transparent;
        border-radius: 2px;
        transform: rotate(45deg);
    }
}

.custom-map-icon {
    background: transparent;
    border: none;
}

.map-marker {
    width: 28px;
    height: 28px;
    border-radius: 50% 50% 50% 0;
    background: var(--marker-color);
    transform: rotate(-45deg);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
    border: 2px solid #fff;

    i {
        transform: rotate(45deg);
        color: #fff;
        font-size: 0.85rem;
    }

    &--super {
        border-radius: 4px;
        border: 3px solid #7c3aed;
        box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.35);
    }
}

.map-popup-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    color: #fff;
    font-size: 11px;
    margin-right: 4px;

    &--super {
        background: #7c3aed;
    }

    &--lider {
        background: #f59e0b;
    }
}

.marker-cluster-red {
    background-color: rgba(239, 68, 68, 0.55);
    div {
        background-color: rgba(239, 68, 68, 0.85);
    }
}

.marker-cluster-blue {
    background-color: rgba(59, 130, 246, 0.55);
    div {
        background-color: rgba(59, 130, 246, 0.85);
    }
}

.marker-cluster-purple {
    background-color: rgba(124, 58, 237, 0.55);
    div {
        background-color: rgba(124, 58, 237, 0.85);
    }
}
</style>
