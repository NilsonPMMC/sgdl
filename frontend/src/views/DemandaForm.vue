<script setup>
import { ref, onMounted, nextTick, computed } from 'vue';
import ApiService from '@/service/ApiService.js';
import { useRouter, useRoute } from 'vue-router';
import { useToast } from 'primevue/usetoast';

import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

import markerIconUrl from '/images/marker-icon.png';
import markerIconRetinaUrl from '/images/marker-icon-2x.png';
import markerShadowUrl from '/images/marker-shadow.png';

import Editor from 'primevue/editor';
import InputText from 'primevue/inputtext';
import AutoComplete from 'primevue/autocomplete';
import Button from 'primevue/button';
import FileUpload from 'primevue/fileupload';
import InputMask from 'primevue/inputmask';
import Tag from 'primevue/tag';
import Message from 'primevue/message';
import Dialog from 'primevue/dialog';
import Checkbox from 'primevue/checkbox';
import { descricaoParaHtml } from '@/utils/oficioTexto';
import { filtrarArquivosDuplicados, mensagemAnexosRejeitados, nomeAnexoSalvo } from '@/utils/anexoValidacao';
import { mensagemResumoBackend } from '@/utils/duplicidadeAlerta';
import { aplicarAjusteManualMapa, vincularMarcadorArrastavel } from '@/utils/mapaLocalAjustavel';
import { termoBuscaLogradouroValido } from '@/utils/enderecoCopiloto';

const toast = useToast();
const router = useRouter();
const route = useRoute();

function voltar() {
    if (window.history.length > 1) {
        router.back();
    } else {
        router.push('/demandas');
    }
}

const map = ref(null);
const marker = ref(null);
const defaultCoords = [-23.523, -46.18];

const defaultIcon = L.icon({
    iconUrl: markerIconUrl,
    iconRetinaUrl: markerIconRetinaUrl,
    shadowUrl: markerShadowUrl,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const anexos = ref([]);
const todosServicos = ref([]);
const filteredServicos = ref([]);
const selectedServico = ref(null);
const secretariaDestino = ref(null);
const demandaId = ref(null);
const showMap = ref(false);
const mapaCarregando = ref(false);
const podeEscolherServico = ref(true);

const envioDialog = ref(false);
const previewEnvio = ref(null);
const carregandoPreview = ref(false);
const enviandoOficial = ref(false);
const declaracaoAceita = ref(false);
const DECLARACAO_ENVIO = 'ASSINO E ENVIO';

const ehTrilhaTendencia = computed(() => {
    const d = demanda.value;
    return Boolean(d?.origem_vinculo === 'TENDENCIA' || d?.tendencia?.id || d?.tendencia_id);
});

const tendenciaResumo = computed(() => demanda.value?.tendencia || null);

const orgaoDestinoNome = computed(() => {
    if (ehTrilhaTendencia.value) {
        return tendenciaResumo.value?.sinapse_orgao_nome || secretariaDestino.value?.nome || demanda.value?.secretaria_destino?.nome || '';
    }
    return secretariaCartaNome.value;
});

const podeEnviarOficio = computed(() => {
    if (!demandaId.value) return false;
    if (ehTrilhaTendencia.value) {
        return Boolean(tendenciaResumo.value?.id || demanda.value?.tendencia_id);
    }
    return Boolean(selectedServico.value || demanda.value?.sinapse_servico_id);
});

const podeEnviarOficialmente = computed(() => podeEnviarOficio.value);

const getTagSeverity = (tipo) => {
    switch (tipo) {
        case 'SERVIÇO':
            return 'info';
        case 'IMPLANTAÇÃO':
            return 'success';
        case 'VISTORIA':
            return 'warning';
        case 'EVENTO':
            return 'primary';
        case 'ATENDIMENTO':
            return 'secondary';
        default:
            return 'contrast';
    }
};

const demanda = ref({
    titulo: '',
    descricao: '',
    cep: '',
    logradouro: '',
    numero: '',
    complemento: '',
    bairro: '',
    latitude: null,
    longitude: null
});

const servicoCartaNome = computed(() => selectedServico.value?.nome || demanda.value?.servico?.nome || '');

const secretariaCartaNome = computed(() => secretariaDestino.value?.nome || selectedServico.value?.secretaria_responsavel?.nome || demanda.value?.secretaria_destino?.nome || '');

const temEnderecoParaMapa = computed(() => Boolean((demanda.value.cep && demanda.value.cep.replace(/\D/g, '').length >= 8) || (demanda.value.logradouro && demanda.value.bairro)));

const coordenadasMapaLabel = computed(() => {
    if (demanda.value.latitude && demanda.value.longitude) {
        return `${Number(demanda.value.latitude).toFixed(6)}, ${Number(demanda.value.longitude).toFixed(6)}`;
    }
    return null;
});

const fonteGeocodificacao = ref(null);
const sugLogradouros = ref([]);
const buscandoLogradouros = ref(false);
let debounceLogradouro = null;

const labelFonteGeo = (fonte) => {
    const map = {
        cep: 'CEP (aproximado)',
        bairro_cep: 'Bairro + CEP',
        logradouro: 'Logradouro',
        viacep_logradouro: 'ViaCEP + logradouro',
        aproximada: 'Referência aproximada',
        ajuste_mapa: 'Ajuste manual no mapa',
        gps_dispositivo: 'GPS do dispositivo',
        indisponivel: 'Indisponível'
    };
    return map[fonte] || fonte;
};

const onMarkerDragEnd = (evento) => aplicarAjusteManualMapa(evento, demanda, fonteGeocodificacao, ApiService, toast);

const initMap = (coords) => {
    nextTick(() => {
        if (!document.getElementById('demanda-map')) {
            return;
        }
        if (map.value) {
            map.value.setView(coords, 16);
            updateMarker(coords);
            map.value.invalidateSize();
            return;
        }
        map.value = L.map('demanda-map', { scrollWheelZoom: true }).setView(coords, 16);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap'
        }).addTo(map.value);

        updateMarker(coords);
    });
};

const updateMarker = (coords) => {
    if (!map.value) {
        return;
    }
    if (marker.value) {
        marker.value.setLatLng(coords);
    } else {
        marker.value = L.marker(coords, { icon: defaultIcon, draggable: true }).addTo(map.value);
    }
    vincularMarcadorArrastavel(marker, onMarkerDragEnd);
    map.value.setView(coords, 17);
};

const consultarMapa = async () => {
    if (!temEnderecoParaMapa.value && !(demanda.value.latitude && demanda.value.longitude)) {
        toast.add({
            severity: 'warn',
            summary: 'Endereço',
            detail: 'Informe CEP ou logradouro e bairro para consultar o mapa.',
            life: 4000
        });
        return;
    }

    mapaCarregando.value = true;
    showMap.value = true;

    try {
        if (demanda.value.latitude && demanda.value.longitude) {
            const savedCoords = [Number(demanda.value.latitude), Number(demanda.value.longitude)];
            await nextTick();
            initMap(savedCoords);
            return;
        }
        await geocodeAddress();
    } finally {
        mapaCarregando.value = false;
        await nextTick();
        if (map.value) {
            map.value.invalidateSize();
        }
    }
};

onMounted(async () => {
    const idDaRota = route.params.id;
    if (!idDaRota) {
        router.replace({ name: 'copiloto' });
        return;
    }

    try {
        const responseServicos = await ApiService.getServicos();
        todosServicos.value = responseServicos.data;

        demandaId.value = idDaRota;
        const responseDemanda = await ApiService.getDemandaById(idDaRota);
        const data = responseDemanda.data;

        if (data.status !== 'RASCUNHO') {
            toast.add({
                severity: 'info',
                summary: 'Somente rascunho',
                detail: 'Este ofício já foi enviado. Use a visualização de detalhes.',
                life: 4000
            });
            router.replace({ name: 'demandas-detalhes', params: { id: idDaRota } });
            return;
        }

        demanda.value = {
            ...data,
            descricao: descricaoParaHtml(data.descricao)
        };
        anexos.value = data.anexos || [];
        selectedServico.value = data.servico || null;
        secretariaDestino.value = data.secretaria_destino || data.servico?.secretaria_responsavel || null;
        const trilhaTend = data.origem_vinculo === 'TENDENCIA' || data.tendencia?.id || data.tendencia_id;
        podeEscolherServico.value = !trilhaTend && !data.sinapse_servico_id;
        if (trilhaTend && data.tendencia?.sinapse_orgao_id && !secretariaDestino.value) {
            secretariaDestino.value = {
                id: data.tendencia.sinapse_orgao_id,
                nome: data.tendencia.sinapse_orgao_nome || 'Órgão sugerido'
            };
        }

        if (data.latitude && data.longitude) {
            showMap.value = true;
            await nextTick();
            initMap([Number(data.latitude), Number(data.longitude)]);
        }
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível carregar a demanda.', life: 4000 });
    }
});

const searchServico = (event) => {
    if (!event.query.trim().length) {
        filteredServicos.value = [...todosServicos.value];
    } else {
        const q = event.query.toLowerCase();
        filteredServicos.value = todosServicos.value.filter((servico) => {
            const nome = (servico.nome || '').toLowerCase();
            const sec = (servico.secretaria_responsavel?.nome || '').toLowerCase();
            return nome.includes(q) || sec.includes(q);
        });
    }
};

const onServicoSelecionado = () => {
    secretariaDestino.value = selectedServico.value?.secretaria_responsavel || null;
};

const buscarCep = async () => {
    const cepLimpo = demanda.value.cep ? demanda.value.cep.replace(/\D/g, '') : '';
    if (cepLimpo.length !== 8) {
        return;
    }
    try {
        const response = await ApiService.buscarCepGeocoding(cepLimpo);
        demanda.value.logradouro = response.data.logradouro || demanda.value.logradouro;
        demanda.value.bairro = response.data.bairro || demanda.value.bairro;
        toast.add({
            severity: 'success',
            summary: 'CEP',
            detail: 'Endereço preenchido via ViaCEP.',
            life: 3000
        });
    } catch (error) {
        const detail = error?.response?.data?.detail || 'CEP não encontrado.';
        toast.add({ severity: 'error', summary: 'CEP', detail, life: 3500 });
    }
};

const searchLogradouro = (event) => {
    const termo = event.query ?? '';
    if (debounceLogradouro) {
        clearTimeout(debounceLogradouro);
    }
    if (!termoBuscaLogradouroValido(termo)) {
        sugLogradouros.value = [];
        return;
    }
    const termoBusca = termo.trim();
    debounceLogradouro = setTimeout(async () => {
        buscandoLogradouros.value = true;
        try {
            const bairro = (demanda.value.bairro || '').trim() || null;
            const { data } = await ApiService.buscarLogradouros(termoBusca, bairro);
            sugLogradouros.value = data.resultados || [];
        } catch {
            sugLogradouros.value = [];
        } finally {
            buscandoLogradouros.value = false;
        }
    }, 350);
};

const onLogradouroSelecionado = (event) => {
    const item = event.value;
    if (!item || typeof item === 'string') {
        return;
    }
    demanda.value.logradouro = item.logradouro || item.label || demanda.value.logradouro;
    if (item.bairro) {
        demanda.value.bairro = item.bairro;
    }
    if (item.cep) {
        demanda.value.cep = item.cep;
    }
    if (item.latitude != null && item.longitude != null) {
        demanda.value.latitude = item.latitude;
        demanda.value.longitude = item.longitude;
        fonteGeocodificacao.value = 'logradouro';
    }
};

const geocodeAddress = async () => {
    if (!temEnderecoParaMapa.value) {
        return;
    }

    try {
        const response = await ApiService.resolverGeocodingEndereco({
            logradouro: demanda.value.logradouro,
            bairro: demanda.value.bairro,
            cep: demanda.value.cep
        });
        const data = response.data || {};
        fonteGeocodificacao.value = data.fonte || null;

        if (data.latitude != null && data.longitude != null) {
            const coords = [Number(data.latitude), Number(data.longitude)];
            demanda.value.latitude = data.latitude;
            demanda.value.longitude = data.longitude;
            await nextTick();
            initMap(coords);
            toast.add({
                severity: 'info',
                summary: 'Mapa',
                detail: `Ponto localizado (${labelFonteGeo(data.fonte)}). Conferência opcional — não bloqueia o envio.`,
                life: 4500
            });
            return;
        }

        await nextTick();
        initMap(defaultCoords);
        toast.add({
            severity: 'warn',
            summary: 'Mapa',
            detail: data.detail || 'Endereço não localizado em Mogi das Cruzes. Mapa exibido na região do município.',
            life: 5000
        });
    } catch (error) {
        console.error('Erro na geocodificação:', error);
        await nextTick();
        initMap(defaultCoords);
        toast.add({
            severity: 'warn',
            summary: 'Mapa',
            detail: 'Serviço de geocodificação indisponível no momento.',
            life: 4000
        });
    }
};

const salvarRascunho = async (silent = false) => {
    const payload = { ...demanda.value };

    if (ehTrilhaTendencia.value) {
        delete payload.servico_id;
        payload.sinapse_servico_id = null;
    } else {
        payload.servico_id = selectedServico.value ? selectedServico.value.id : demanda.value.sinapse_servico_id || null;
        if (!payload.servico_id) {
            if (!silent) {
                toast.add({
                    severity: 'error',
                    summary: 'Erro',
                    detail: 'Selecione um serviço da carta.',
                    life: 3000
                });
            }
            return false;
        }
    }

    try {
        await ApiService.updateDemanda(demandaId.value, payload);
        if (!silent) {
            toast.add({ severity: 'info', summary: 'Salvo', detail: 'Rascunho atualizado.', life: 3000 });
        }
        return true;
    } catch (error) {
        console.error('Erro ao salvar rascunho:', error);
        if (!silent) {
            toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível salvar.', life: 3000 });
        }
        return false;
    }
};

const enviarOficialmente = async () => {
    if (!demandaId.value) {
        toast.add({ severity: 'warn', summary: 'Aviso', detail: 'Salve como rascunho antes de enviar.', life: 3000 });
        return;
    }

    if (!podeEnviarOficialmente.value) {
        return;
    }

    if (!podeEnviarOficio.value) {
        toast.add({
            severity: 'error',
            summary: ehTrilhaTendencia.value ? 'Tendência' : 'Serviço',
            detail: ehTrilhaTendencia.value ? 'Esta demanda precisa estar vinculada a uma tendência antes do envio.' : 'Selecione o serviço da carta antes de enviar.',
            life: 4000
        });
        return;
    }

    declaracaoAceita.value = false;
    previewEnvio.value = null;
    envioDialog.value = true;
    carregandoPreview.value = true;
    try {
        const { data } = await ApiService.previewEnvioOficial(demandaId.value);
        previewEnvio.value = data;
    } catch (error) {
        envioDialog.value = false;
        const detalhe = error?.response?.data?.detail || 'Não foi possível gerar a pré-visualização do ofício.';
        toast.add({ severity: 'error', summary: 'Pré-visualização', detail: String(detalhe), life: 5000 });
    } finally {
        carregandoPreview.value = false;
    }
};

const abrirPreviewPdf = async () => {
    if (!demandaId.value) return;
    try {
        const { data } = await ApiService.previewEnvioOficialPdf(demandaId.value);
        const blob = new Blob([data], { type: 'application/pdf' });
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank');
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
        toast.add({
            severity: 'error',
            summary: 'Pré-visualização',
            detail: 'Não foi possível abrir o PDF do ofício.',
            life: 4000
        });
    }
};

const confirmarEnvioOficial = async () => {
    if (!declaracaoAceita.value) {
        toast.add({
            severity: 'warn',
            summary: 'Assinatura',
            detail: 'Marque a declaração de assinatura eletrônica para continuar.',
            life: 4000
        });
        return;
    }
    enviandoOficial.value = true;
    try {
        const { data } = await ApiService.enviarDemanda(demandaId.value, {
            declaracao: DECLARACAO_ENVIO,
            hash_documento: previewEnvio.value?.hash_documento
        });
        envioDialog.value = false;
        const codigo = data?.assinatura_eletronica?.codigo_validacao;
        toast.add({
            severity: 'success',
            summary: 'Ofício enviado',
            detail: codigo ? `Assinatura eletrônica registrada (${codigo.slice(0, 8)}…).` : 'Ofício enviado oficialmente.',
            life: 5000
        });
        router.push('/demandas');
    } catch (error) {
        const detalhe = error?.response?.data?.error || error?.response?.data?.detail || 'Não foi possível enviar o ofício.';
        toast.add({ severity: 'error', summary: 'Erro', detail: String(detalhe), life: 5000 });
    } finally {
        enviandoOficial.value = false;
    }
};

const onUpload = async (event) => {
    if (!demandaId.value) return;

    const existentes = anexos.value.map((a) => nomeAnexoSalvo(a));
    const { aceitos, rejeitados } = filtrarArquivosDuplicados(event.files || [], existentes);

    if (rejeitados.length) {
        toast.add({
            severity: 'warn',
            summary: 'Anexo duplicado',
            detail: mensagemAnexosRejeitados(rejeitados),
            life: 5000
        });
    }
    if (!aceitos.length) {
        return;
    }

    for (const file of aceitos) {
        const formData = new FormData();
        formData.append('demanda', demandaId.value);
        formData.append('arquivo', file);
        try {
            const response = await ApiService.createAnexo(formData);
            anexos.value.push(response.data);
        } catch (error) {
            const detail = error?.response?.data?.arquivo?.[0] || error?.response?.data?.detail || `Falha no upload de «${file.name}».`;
            toast.add({ severity: 'error', summary: 'Erro', detail: String(detail), life: 4000 });
        }
    }

    if (aceitos.length) {
        toast.add({
            severity: 'success',
            summary: 'Sucesso',
            detail: `${aceitos.length} anexo(s) enviado(s).`,
            life: 3000
        });
    }
};

const removerAnexo = async (anexoId, index) => {
    try {
        await ApiService.deleteAnexo(anexoId);
        anexos.value.splice(index, 1);
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Anexo removido.', life: 3000 });
    } catch (error) {
        console.error('Erro ao remover anexo:', error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível remover o anexo.', life: 3000 });
    }
};
</script>

<template>
    <div>
        <div class="card flex flex-col gap-4 w-full">
            <div class="flex flex-wrap items-center justify-between gap-3">
                <h5 class="m-0">Editar rascunho do ofício</h5>
                <Button label="Voltar" icon="pi pi-arrow-left" severity="secondary" outlined @click="voltar" />
            </div>
            <Message severity="info" :closable="false" class="mb-4 w-full"> Novos ofícios são criados pelo <strong>Copiloto</strong>. Revise texto, serviço, endereço e anexos nesta tela antes de assinar e enviar oficialmente ao Protocolo. </Message>
            <div>
                <label class="block mb-3" for="titulo">Título do Ofício</label>
                <InputText id="titulo" v-model="demanda.titulo" fluid />
            </div>

            <div>
                <label class="block mb-3" for="servico">
                    {{ ehTrilhaTendencia ? 'Classificação (tendência — fora da carta)' : 'Serviço solicitado (Carta de Serviços)' }}
                </label>
                <div v-if="ehTrilhaTendencia && tendenciaResumo" class="flex flex-col gap-2 rounded-lg border border-violet-500/35 bg-[var(--surface-ground)] p-4">
                    <div class="flex flex-wrap items-center gap-2">
                        <Tag value="Tendência" severity="secondary" />
                        <span class="font-semibold text-[var(--text-color)]">{{ tendenciaResumo.titulo }}</span>
                        <span v-if="tendenciaResumo.volume_total != null" class="text-sm text-[var(--text-color-secondary)]"> · volume {{ tendenciaResumo.volume_total }} </span>
                    </div>
                    <p class="m-0 text-sm text-[var(--text-color-secondary)]">
                        Esta demanda não está vinculada a um serviço da carta Sinapse. O Protocolo pode promover a tendência à carta depois; o envio oficial gera o ofício legislativo normalmente.
                    </p>
                    <p class="m-0 text-sm text-[var(--text-color-secondary)]">
                        <i class="pi pi-building mr-1" aria-hidden="true" />
                        <template v-if="orgaoDestinoNome">
                            Órgão sugerido:
                            <strong class="text-[var(--text-color)]">{{ orgaoDestinoNome }}</strong>
                        </template>
                        <template v-else> Órgão será definido no despacho do Protocolo. </template>
                    </p>
                </div>
                <Message v-else-if="ehTrilhaTendencia" severity="warn" :closable="false" class="mb-0 w-full"> Demanda marcada como tendência, mas sem vínculo registrado. Reabra pelo Copiloto ou contate o suporte antes de enviar. </Message>
                <div v-else-if="servicoCartaNome && !podeEscolherServico" class="flex flex-col gap-2 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] p-4">
                    <div class="flex flex-wrap items-center gap-2">
                        <span class="font-semibold text-[var(--text-color)]">{{ servicoCartaNome }}</span>
                        <Tag v-if="selectedServico?.tipo" :value="selectedServico.tipo" :severity="getTagSeverity(selectedServico.tipo)" />
                    </div>
                    <p v-if="secretariaCartaNome" class="m-0 text-sm text-[var(--text-color-secondary)]">
                        <i class="pi pi-building mr-1" aria-hidden="true" />
                        Secretaria / órgão responsável:
                        <strong class="text-[var(--text-color)]">{{ secretariaCartaNome }}</strong>
                    </p>
                </div>
                <template v-else-if="!ehTrilhaTendencia">
                    <AutoComplete
                        id="servico"
                        v-model="selectedServico"
                        :suggestions="filteredServicos"
                        @complete="searchServico"
                        @item-select="onServicoSelecionado"
                        optionLabel="nome"
                        forceSelection
                        placeholder="Digite o nome do serviço na carta..."
                        dropdown
                        fluid
                    >
                        <template #option="{ option }">
                            <div class="flex flex-col gap-1 py-1 w-full">
                                <div class="flex items-center justify-between gap-2">
                                    <span class="font-medium">{{ option.nome }}</span>
                                    <Tag :value="option.tipo" :severity="getTagSeverity(option.tipo)" />
                                </div>
                                <span v-if="option.secretaria_responsavel?.nome" class="text-xs text-[var(--text-color-secondary)]">
                                    {{ option.secretaria_responsavel.nome }}
                                </span>
                            </div>
                        </template>
                    </AutoComplete>
                    <p v-if="selectedServico && secretariaCartaNome" class="mt-2 mb-0 text-sm text-[var(--text-color-secondary)]">
                        Órgão responsável:
                        <strong class="text-[var(--text-color)]">{{ secretariaCartaNome }}</strong>
                    </p>
                </template>
            </div>

            <div class="rounded-xl border border-[var(--primary-color)]/25 bg-[var(--surface-ground)] p-4">
                <p class="m-0 mb-1 text-sm font-semibold text-[var(--text-color)]">
                    <i class="pi pi-map-marker mr-1" aria-hidden="true" />
                    Local da solicitação
                </p>
                <p class="m-0 mb-0 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                    Informe o <strong>CEP</strong> (preenche logradouro e bairro via ViaCEP) ou digite <strong>rua e bairro</strong>. Use «Atualizar mapa» para obter latitude e longitude com o mesmo serviço do Copiloto (Nominatim, restrito a Mogi das
                    Cruzes). A georreferência é opcional e não impede o envio.
                </p>
            </div>

            <div class="grid grid-cols-12 gap-8">
                <div class="col-span-full lg:col-span-3">
                    <label class="block mb-3" for="cep">CEP</label>
                    <InputMask id="cep" v-model="demanda.cep" mask="99999-999" placeholder="99999-999" @blur="buscarCep" fluid />
                </div>
                <div class="col-span-full lg:col-span-9">
                    <label class="block mb-3" for="logradouro">Logradouro</label>
                    <AutoComplete
                        id="logradouro"
                        v-model="demanda.logradouro"
                        :suggestions="sugLogradouros"
                        optionLabel="label"
                        :loading="buscandoLogradouros"
                        :completeOnFocus="false"
                        placeholder="Digite ao menos 3 letras (ruas de Mogi das Cruzes)"
                        fluid
                        @complete="searchLogradouro"
                        @item-select="onLogradouroSelecionado"
                    />
                    <p class="mt-1 mb-0 text-xs text-[var(--text-color-secondary)]">Sugestões via Nominatim (Mogi das Cruzes). Você pode digitar manualmente se não encontrar.</p>
                </div>
            </div>

            <div class="grid grid-cols-12 gap-8">
                <div class="col-span-full lg:col-span-3">
                    <label class="block mb-3" for="numero">Número</label>
                    <InputText id="numero" v-model="demanda.numero" fluid />
                </div>
                <div class="col-span-full lg:col-span-3">
                    <label class="block mb-3" for="complemento">Complemento</label>
                    <InputText id="complemento" v-model="demanda.complemento" fluid />
                </div>
                <div class="col-span-full lg:col-span-6">
                    <label class="block mb-3" for="bairro">Bairro</label>
                    <InputText id="bairro" v-model="demanda.bairro" fluid />
                </div>
            </div>

            <div class="field">
                <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <label class="m-0">Consulta no mapa</label>
                    <Button type="button" label="Atualizar mapa" icon="pi pi-map" severity="secondary" outlined size="small" :loading="mapaCarregando" @click="consultarMapa" />
                </div>
                <p v-if="coordenadasMapaLabel" class="mt-0 mb-2 text-sm text-[var(--text-color-secondary)]">
                    Coordenadas de referência: {{ coordenadasMapaLabel }}
                    <span v-if="fonteGeocodificacao"> (fonte: {{ labelFonteGeo(fonteGeocodificacao) }})</span>
                </p>
                <div v-show="showMap" id="demanda-map" class="h-[350px] w-full rounded-md border border-[var(--surface-border)]" />
                <p v-if="showMap" class="m-0 mt-1 text-xs text-[var(--text-color-secondary)]">Arraste o pin para o local exato no mapa.</p>
                <p v-if="!showMap" class="m-0 text-sm text-[var(--text-color-secondary)]">Clique em «Atualizar mapa» após preencher o endereço para conferir a localização.</p>
            </div>

            <div>
                <label class="mb-2 block" for="descricao">Texto do ofício</label>
                <p class="mt-0 mb-3 text-sm text-[var(--text-color-secondary)]">Texto formal em parágrafos, no padrão do ofício institucional. Revise antes do envio.</p>
                <Editor id="descricao" v-model="demanda.descricao" editorStyle="height: 360px" />
            </div>

            <div class="mt-4 flex flex-wrap justify-end gap-2">
                <Button label="Cancelar" severity="secondary" outlined @click="voltar" />
                <Button label="Salvar Rascunho" icon="pi pi-save" severity="info" @click="salvarRascunho" />
                <Button label="Enviar Oficialmente" icon="pi pi-send" @click="enviarOficialmente" :disabled="!podeEnviarOficialmente" />
            </div>

            <Dialog v-model:visible="envioDialog" header="Assinatura eletrônica e envio oficial" :modal="true" style="width: 520px">
                <div class="flex flex-col gap-4">
                    <Message severity="info" :closable="false" class="text-sm m-0"> Revise o PDF do ofício. Ao confirmar, você assina eletronicamente e o protocolo legislativo é gerado. </Message>
                    <div v-if="carregandoPreview" class="text-sm text-muted-color">Gerando pré-visualização…</div>
                    <template v-else-if="previewEnvio">
                        <Message v-if="previewEnvio.duplicidade_resumo?.tem_duplicidade" :severity="previewEnvio.duplicidade_resumo?.sugerir_nao_enviar ? 'error' : 'warn'" :closable="false" class="text-sm m-0">
                            <p class="m-0 font-medium">
                                {{ previewEnvio.duplicidade_resumo?.sugerir_nao_enviar ? 'Atenção — possível duplicidade em tramitação' : 'Possível duplicidade de rascunho' }}
                            </p>
                            <p class="m-0 mt-2">
                                {{ mensagemResumoBackend(previewEnvio.duplicidade_resumo) }}
                            </p>
                            <ul v-if="previewEnvio.alertas_duplicidade?.length" class="m-0 mt-2 list-disc pl-5">
                                <li v-for="a in previewEnvio.alertas_duplicidade" :key="a.demanda_id">
                                    {{ a.mensagem }}
                                </li>
                            </ul>
                            <p v-if="previewEnvio.duplicidade_resumo?.sugerir_nao_enviar" class="m-0 mt-2">Você pode cancelar e acompanhar o processo existente, ou continuar se tiver certeza de que é um pedido diferente.</p>
                        </Message>
                        <div v-if="previewEnvio.preview_pdf_disponivel">
                            <Button label="Abrir pré-visualização (PDF)" icon="pi pi-file-pdf" outlined @click="abrirPreviewPdf" />
                        </div>
                        <p class="m-0 text-xs text-muted-color break-all">Hash do documento: {{ previewEnvio.hash_documento?.slice(0, 16) }}…</p>
                    </template>
                    <div class="flex items-start gap-2">
                        <Checkbox v-model="declaracaoAceita" inputId="declaracao_assinatura" binary />
                        <label for="declaracao_assinatura" class="text-sm cursor-pointer">
                            Declaro que li o ofício, concordo com o conteúdo e
                            <strong>assino eletronicamente</strong> o envio oficial ({{ DECLARACAO_ENVIO }}).
                        </label>
                    </div>
                </div>
                <template #footer>
                    <Button label="Cancelar" icon="pi pi-times" text @click="envioDialog = false" />
                    <Button label="Assino e envio" icon="pi pi-check" :loading="enviandoOficial" :disabled="carregandoPreview || !declaracaoAceita" @click="confirmarEnvioOficial" />
                </template>
            </Dialog>

            <div v-if="anexos.length > 0" class="mb-3">
                <div class="mb-3 text-xl font-semibold">Anexos salvos</div>
                <div class="flex flex-col gap-2">
                    <div v-for="(anexo, index) in anexos" :key="anexo.id" class="surface-border flex items-center rounded border p-2">
                        <a :href="anexo.arquivo" target="_blank" class="text-color hover:text-primary flex items-center no-underline">
                            <i class="pi pi-file mr-2" />
                            <span>{{ anexo.arquivo.split('/').pop() }}</span>
                        </a>
                        <Button icon="pi pi-times" severity="danger" text rounded class="ml-2" @click="removerAnexo(anexo.id, index)" />
                    </div>
                </div>
            </div>

            <div class="mb-3">
                <div class="mb-4 text-xl font-semibold">Anexar documentos ou fotos</div>
                <FileUpload name="arquivo" :multiple="true" accept="image/*,application/pdf" :maxFileSize="2000000" @uploader="onUpload" :customUpload="true" :disabled="!demandaId">
                    <template #empty>
                        <p>Salve um rascunho para poder anexar arquivos.</p>
                    </template>
                </FileUpload>
            </div>
        </div>
    </div>
</template>
