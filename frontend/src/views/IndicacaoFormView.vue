<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
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
import MultiSelect from 'primevue/multiselect';
import Select from 'primevue/select';
import InputNumber from 'primevue/inputnumber';
import { descricaoParaHtml } from '@/utils/oficioTexto';
import {
    filtrarArquivosDuplicados,
    mensagemAnexosRejeitados,
    nomeAnexoSalvo
} from '@/utils/anexoValidacao';

const toast = useToast();
const router = useRouter();
const route = useRoute();

const DECLARACAO_ENVIO = 'ASSINO E ENVIO';

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
const demandaId = ref(null);
const showMap = ref(false);
const mapaCarregando = ref(false);

const vereadores = ref([]);
const numeracao = ref(null);
const vereadoresIds = ref([]);
const autorVereadorId = ref(null);
const numeroIndicacao = ref(null);

const envioDialog = ref(false);
const previewEnvio = ref(null);
const carregandoPreview = ref(false);
const enviandoOficial = ref(false);
const declaracaoAceita = ref(false);

const demanda = ref({
    titulo: '',
    descricao: '',
    cep: '',
    logradouro: '',
    numero: '',
    complemento: '',
    bairro: '',
    latitude: null,
    longitude: null,
    ano_indicacao: null,
    protocolo_legislativo: null,
    tipo_legislativo: 'INDICACAO'
});

const vereadoresOpcoes = computed(() =>
    vereadores.value.map((v) => ({
        label: v.first_name || v.username,
        value: v.id
    }))
);

const autorVereadorOpcoes = computed(() =>
    vereadoresIds.value.map((id) => {
        const v = vereadores.value.find((x) => x.id === id);
        return { label: v?.first_name || v?.username || `#${id}`, value: id };
    })
);

const sequenciaFormatada = computed(() => {
    if (demanda.value.protocolo_legislativo) {
        return demanda.value.protocolo_legislativo;
    }
    const num = numeroIndicacao.value;
    const ano = demanda.value.ano_indicacao || numeracao.value?.ano;
    if (!num || !ano) return null;
    const mascara = numeracao.value?.mascara || '{numero}/{ano}';
    return mascara.replace('{numero}', String(num)).replace('{ano}', String(ano));
});

const temPdfAnexo = computed(() =>
    anexos.value.some((a) => {
        const nome = nomeAnexoSalvo(a).toLowerCase();
        return nome.endsWith('.pdf');
    })
);

const temEnderecoParaMapa = computed(
    () =>
        Boolean(
            (demanda.value.cep && demanda.value.cep.replace(/\D/g, '').length >= 8) ||
                (demanda.value.logradouro && demanda.value.bairro)
        )
);

const coordenadasMapaLabel = computed(() => {
    if (demanda.value.latitude && demanda.value.longitude) {
        return `${Number(demanda.value.latitude).toFixed(6)}, ${Number(demanda.value.longitude).toFixed(6)}`;
    }
    return null;
});

const podeEnviarOficialmente = computed(() => {
    if (!demandaId.value) return false;
    if (!vereadoresIds.value.length) return false;
    if (!numeroIndicacao.value || numeroIndicacao.value < 1) return false;
    if (!temPdfAnexo.value) return false;
    if (!(demanda.value.titulo || '').trim()) return false;
    return Boolean(descricaoTextoPuro(demanda.value.descricao));
});

const fonteGeocodificacao = ref(null);
const sugLogradouros = ref([]);
const buscandoLogradouros = ref(false);
let debounceLogradouro = null;

function descricaoTextoPuro(html) {
    if (!html) return '';
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return (tmp.textContent || tmp.innerText || '').trim();
}

const labelFonteGeo = (fonte) => {
    const mapa = {
        cep: 'CEP (aproximado)',
        bairro_cep: 'Bairro + CEP',
        logradouro: 'Logradouro',
        viacep_logradouro: 'ViaCEP + logradouro',
        aproximada: 'Referência aproximada',
        indisponivel: 'Indisponível'
    };
    return mapa[fonte] || fonte;
};

const initMap = (coords) => {
    nextTick(() => {
        if (!document.getElementById('indicacao-map')) {
            return;
        }
        if (map.value) {
            map.value.setView(coords, 16);
            updateMarker(coords);
            map.value.invalidateSize();
            return;
        }
        map.value = L.map('indicacao-map', { scrollWheelZoom: true }).setView(coords, 16);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap'
        }).addTo(map.value);
        updateMarker(coords);
    });
};

const updateMarker = (coords) => {
    if (!map.value) return;
    if (marker.value) {
        marker.value.setLatLng(coords);
    } else {
        marker.value = L.marker(coords, { icon: defaultIcon, draggable: false }).addTo(map.value);
    }
    map.value.setView(coords, 17);
};

function hidratarVinculos(data) {
    if (Array.isArray(data.vereadores_vinculados_ids) && data.vereadores_vinculados_ids.length) {
        vereadoresIds.value = [...data.vereadores_vinculados_ids];
    } else if (Array.isArray(data.vereadores_vinculados)) {
        vereadoresIds.value = data.vereadores_vinculados.map((v) => v.id);
    } else {
        vereadoresIds.value = [];
    }
    const autorVinculo = (data.vereadores_vinculados || []).find((v) => v.papel === 'AUTOR');
    autorVereadorId.value =
        data.autor_vereador_id ?? autorVinculo?.id ?? vereadoresIds.value[0] ?? null;
    numeroIndicacao.value =
        data.numero_indicacao ?? numeracao.value?.proximo_numero ?? null;
}

watch(vereadoresIds, (ids) => {
    if (ids.length && !ids.includes(autorVereadorId.value)) {
        autorVereadorId.value = ids[0];
    }
});

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
        const [respVer, respNum, responseDemanda] = await Promise.all([
            ApiService.getUsuarios({ perfil: 'VEREADOR' }),
            ApiService.getNumeracaoIndicacao(),
            ApiService.getDemandaById(idDaRota)
        ]);

        vereadores.value = respVer.data?.results || respVer.data || [];
        numeracao.value = respNum.data;

        demandaId.value = idDaRota;
        const data = responseDemanda.data;

        if (data.tipo_legislativo && data.tipo_legislativo !== 'INDICACAO') {
            toast.add({
                severity: 'warn',
                summary: 'Tipo incorreto',
                detail: 'Esta demanda não é uma indicação legislativa.',
                life: 4000
            });
            router.replace({ name: 'demandas-detalhes', params: { id: idDaRota } });
            return;
        }

        if (data.status !== 'RASCUNHO') {
            toast.add({
                severity: 'info',
                summary: 'Somente rascunho',
                detail: 'Esta indicação já foi protocolada. Use a visualização de detalhes.',
                life: 4000
            });
            router.replace({ name: 'demandas-detalhes', params: { id: idDaRota } });
            return;
        }

        demanda.value = {
            ...data,
            descricao: descricaoParaHtml(data.descricao),
            tipo_legislativo: 'INDICACAO'
        };
        anexos.value = data.anexos || [];
        hidratarVinculos(data);

        if (data.latitude && data.longitude) {
            showMap.value = true;
            await nextTick();
            initMap([Number(data.latitude), Number(data.longitude)]);
        }
    } catch (error) {
        console.error('Erro ao carregar indicação:', error);
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: 'Não foi possível carregar a indicação.',
            life: 4000
        });
    }
});

const buscarCep = async () => {
    const cepLimpo = demanda.value.cep ? demanda.value.cep.replace(/\D/g, '') : '';
    if (cepLimpo.length !== 8) return;
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
    const termo = (event.query || '').trim();
    if (debounceLogradouro) clearTimeout(debounceLogradouro);
    if (termo.length < 3) {
        sugLogradouros.value = [];
        return;
    }
    debounceLogradouro = setTimeout(async () => {
        buscandoLogradouros.value = true;
        try {
            const bairro = (demanda.value.bairro || '').trim() || null;
            const { data } = await ApiService.buscarLogradouros(termo, bairro);
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
    if (!item || typeof item === 'string') return;
    demanda.value.logradouro = item.logradouro || item.label || demanda.value.logradouro;
    if (item.bairro) demanda.value.bairro = item.bairro;
    if (item.cep) demanda.value.cep = item.cep;
    if (item.latitude != null && item.longitude != null) {
        demanda.value.latitude = item.latitude;
        demanda.value.longitude = item.longitude;
        fonteGeocodificacao.value = 'logradouro';
    }
};

const geocodeAddress = async () => {
    if (!temEnderecoParaMapa.value) return;
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
            detail:
                data.detail ||
                'Endereço não localizado em Mogi das Cruzes. Mapa exibido na região do município.',
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

function montarPayload() {
    return {
        titulo: demanda.value.titulo,
        descricao: demanda.value.descricao,
        cep: demanda.value.cep,
        logradouro: demanda.value.logradouro,
        numero: demanda.value.numero,
        complemento: demanda.value.complemento,
        bairro: demanda.value.bairro,
        latitude: demanda.value.latitude,
        longitude: demanda.value.longitude,
        tipo_legislativo: 'INDICACAO',
        numero_indicacao: numeroIndicacao.value,
        vereadores_vinculados_ids: vereadoresIds.value,
        autor_vereador_id: autorVereadorId.value
    };
}

const salvarRascunho = async (silent = false) => {
    if (!vereadoresIds.value.length) {
        if (!silent) {
            toast.add({
                severity: 'error',
                summary: 'Vereadores',
                detail: 'Selecione ao menos um vereador vinculado.',
                life: 4000
            });
        }
        return false;
    }
    if (!numeroIndicacao.value || numeroIndicacao.value < 1) {
        if (!silent) {
            toast.add({
                severity: 'error',
                summary: 'Numeração',
                detail: 'Informe o número da indicação.',
                life: 4000
            });
        }
        return false;
    }

    try {
        await ApiService.updateDemanda(demandaId.value, montarPayload());
        if (!silent) {
            toast.add({ severity: 'info', summary: 'Salvo', detail: 'Rascunho atualizado.', life: 3000 });
        }
        return true;
    } catch (error) {
        console.error('Erro ao salvar rascunho:', error);
        const detail =
            error?.response?.data?.numero_indicacao?.[0] ||
            error?.response?.data?.vereadores_vinculados_ids?.[0] ||
            error?.response?.data?.detail ||
            'Não foi possível salvar.';
        if (!silent) {
            toast.add({ severity: 'error', summary: 'Erro', detail: String(detail), life: 4000 });
        }
        return false;
    }
};

const enviarOficialmente = async () => {
    if (!demandaId.value) {
        toast.add({ severity: 'warn', summary: 'Aviso', detail: 'Salve o rascunho antes de enviar.', life: 3000 });
        return;
    }

    if (!podeEnviarOficialmente.value) {
        if (!temPdfAnexo.value) {
            toast.add({
                severity: 'error',
                summary: 'PDF obrigatório',
                detail: 'Anexe o PDF da indicação antes de protocolar.',
                life: 4500
            });
        } else if (!vereadoresIds.value.length) {
            toast.add({
                severity: 'error',
                summary: 'Vereadores',
                detail: 'Selecione os vereadores vinculados.',
                life: 4000
            });
        }
        return;
    }

    const ok = await salvarRascunho(true);
    if (!ok) return;

    declaracaoAceita.value = false;
    previewEnvio.value = null;
    envioDialog.value = true;
    carregandoPreview.value = true;
    try {
        const { data } = await ApiService.previewEnvioOficial(demandaId.value);
        previewEnvio.value = data;
    } catch (error) {
        envioDialog.value = false;
        const detalhe =
            error?.response?.data?.error ||
            error?.response?.data?.detail ||
            'Não foi possível gerar a pré-visualização do documento.';
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
    } catch {
        toast.add({
            severity: 'error',
            summary: 'Pré-visualização',
            detail: 'Não foi possível abrir o PDF da indicação.',
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
            summary: 'Indicação protocolada',
            detail: codigo
                ? `Assinatura eletrônica da Câmara registrada (${codigo.slice(0, 8)}…).`
                : 'Indicação encaminhada ao Protocolo Executivo.',
            life: 5000
        });
        router.push('/demandas');
    } catch (error) {
        const detalhe =
            error?.response?.data?.error ||
            error?.response?.data?.detail ||
            'Não foi possível protocolar a indicação.';
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
    if (!aceitos.length) return;

    for (const file of aceitos) {
        const formData = new FormData();
        formData.append('demanda', demandaId.value);
        formData.append('arquivo', file);
        try {
            const response = await ApiService.createAnexo(formData);
            anexos.value.push(response.data);
        } catch (error) {
            const detail =
                error?.response?.data?.arquivo?.[0] ||
                error?.response?.data?.detail ||
                `Falha no upload de «${file.name}».`;
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
                <h5 class="m-0">Revisar rascunho da indicação</h5>
                <Button label="Voltar" icon="pi pi-arrow-left" severity="secondary" outlined @click="voltar" />
            </div>
            <Message severity="info" :closable="false" class="mb-4 w-full">
                Novas indicações são criadas pelo <strong>Copiloto</strong>. Revise numeração, vereadores,
                texto, local e anexos nesta tela antes de assinar eletronicamente como
                <strong>Câmara Municipal</strong> e encaminhar ao Protocolo Executivo.
            </Message>

            <div
                class="rounded-xl border border-[var(--primary-color)]/25 bg-[var(--surface-ground)] p-4 flex flex-col gap-4"
            >
                <p class="m-0 text-sm font-semibold text-[var(--text-color)]">
                    <i class="pi pi-hashtag mr-1" aria-hidden="true" />
                    Sequência e vereadores
                </p>
                <div v-if="numeracao" class="flex flex-wrap items-center gap-2 text-sm text-[var(--text-color-secondary)]">
                    <span>Sugestão de protocolo:</span>
                    <Tag severity="info" :value="numeracao.protocolo_sugerido" />
                    <span>Último registrado: {{ numeracao.ultimo_numero }}/{{ numeracao.ano }}</span>
                </div>
                <div v-if="sequenciaFormatada" class="text-sm">
                    Sequência atual:
                    <Tag severity="success" :value="sequenciaFormatada" class="ml-2" />
                </div>
                <div class="grid grid-cols-12 gap-4">
                    <div class="col-span-full lg:col-span-8">
                        <label class="block mb-2 text-sm font-medium">Vereadores vinculados</label>
                        <MultiSelect
                            v-model="vereadoresIds"
                            :options="vereadoresOpcoes"
                            option-label="label"
                            option-value="value"
                            placeholder="Selecione os vereadores"
                            display="chip"
                            fluid
                        />
                    </div>
                    <div class="col-span-full lg:col-span-4">
                        <label class="block mb-2 text-sm font-medium">Número (parte numérica)</label>
                        <InputNumber v-model="numeroIndicacao" :min="1" fluid />
                    </div>
                </div>
                <div>
                    <label class="block mb-2 text-sm font-medium">Autor (vereador)</label>
                    <Select
                        v-model="autorVereadorId"
                        :options="autorVereadorOpcoes"
                        option-label="label"
                        option-value="value"
                        placeholder="Autor da indicação"
                        class="w-full"
                        :disabled="!vereadoresIds.length"
                    />
                </div>
            </div>

            <div>
                <label class="block mb-3" for="titulo">Título da indicação</label>
                <InputText id="titulo" v-model="demanda.titulo" fluid />
            </div>

            <div class="rounded-xl border border-[var(--primary-color)]/25 bg-[var(--surface-ground)] p-4">
                <p class="m-0 mb-1 text-sm font-semibold text-[var(--text-color)]">
                    <i class="pi pi-map-marker mr-1" aria-hidden="true" />
                    Local da indicação
                </p>
                <p class="m-0 mb-0 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                    Informe o <strong>CEP</strong> ou digite <strong>rua e bairro</strong>. Use «Atualizar mapa»
                    para conferir a georreferência (opcional).
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
                        placeholder="Digite ao menos 3 letras (ruas de Mogi das Cruzes)"
                        fluid
                        @complete="searchLogradouro"
                        @item-select="onLogradouroSelecionado"
                    />
                </div>
            </div>

            <div class="grid grid-cols-12 gap-8">
                <div class="col-span-full lg:col-span-3">
                    <label class="block mb-3" for="numero-endereco">Número</label>
                    <InputText id="numero-endereco" v-model="demanda.numero" fluid />
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
                    <Button
                        type="button"
                        label="Atualizar mapa"
                        icon="pi pi-map"
                        severity="secondary"
                        outlined
                        size="small"
                        :loading="mapaCarregando"
                        @click="consultarMapa"
                    />
                </div>
                <p v-if="coordenadasMapaLabel" class="mt-0 mb-2 text-sm text-[var(--text-color-secondary)]">
                    Coordenadas de referência: {{ coordenadasMapaLabel }}
                    <span v-if="fonteGeocodificacao"> (fonte: {{ labelFonteGeo(fonteGeocodificacao) }})</span>
                </p>
                <div
                    v-show="showMap"
                    id="indicacao-map"
                    class="h-[350px] w-full rounded-md border border-[var(--surface-border)]"
                />
                <p v-if="!showMap" class="m-0 text-sm text-[var(--text-color-secondary)]">
                    Clique em «Atualizar mapa» após preencher o endereço para conferir a localização.
                </p>
            </div>

            <div>
                <label class="mb-2 block" for="descricao">Texto da indicação</label>
                <p class="mt-0 mb-3 text-sm text-[var(--text-color-secondary)]">
                    Revise o texto antes do protocolo. O PDF anexado será assinado eletronicamente pela Câmara.
                </p>
                <Editor id="descricao" v-model="demanda.descricao" editorStyle="height: 360px" />
            </div>

            <div v-if="anexos.length > 0" class="mb-3">
                <div class="mb-3 text-xl font-semibold">Anexos salvos</div>
                <Message v-if="!temPdfAnexo" severity="warn" :closable="false" class="mb-3 w-full">
                    É obrigatório anexar o <strong>PDF da indicação</strong> antes de protocolar.
                </Message>
                <div class="flex flex-col gap-2">
                    <div
                        v-for="(anexo, index) in anexos"
                        :key="anexo.id"
                        class="surface-border flex items-center rounded border p-2"
                    >
                        <a
                            :href="anexo.arquivo"
                            target="_blank"
                            class="text-color hover:text-primary flex items-center no-underline"
                        >
                            <i class="pi pi-file mr-2" />
                            <span>{{ anexo.arquivo.split('/').pop() }}</span>
                            <Tag v-if="nomeAnexoSalvo(anexo).toLowerCase().endsWith('.pdf')" value="PDF" severity="info" class="ml-2" />
                        </a>
                        <Button
                            icon="pi pi-times"
                            severity="danger"
                            text
                            rounded
                            class="ml-auto"
                            @click="removerAnexo(anexo.id, index)"
                        />
                    </div>
                </div>
            </div>

            <div class="mb-3">
                <div class="mb-4 text-xl font-semibold">Anexar documentos</div>
                <Message v-if="!anexos.length" severity="info" :closable="false" class="mb-3 w-full">
                    Anexe o PDF assinado ou final da indicação. Este arquivo será usado na assinatura eletrônica
                    da Câmara.
                </Message>
                <FileUpload
                    name="arquivo"
                    :multiple="true"
                    accept="application/pdf,image/*"
                    :maxFileSize="2000000"
                    @uploader="onUpload"
                    :customUpload="true"
                    :disabled="!demandaId"
                >
                    <template #empty>
                        <p>Arraste arquivos ou clique para anexar (PDF recomendado).</p>
                    </template>
                </FileUpload>
            </div>

            <div class="mt-4 flex flex-wrap justify-end gap-2">
                <Button label="Cancelar" severity="secondary" outlined @click="voltar" />
                <Button label="Salvar rascunho" icon="pi pi-save" severity="info" @click="salvarRascunho()" />
                <Button
                    label="Protocolar indicação"
                    icon="pi pi-send"
                    @click="enviarOficialmente"
                    :disabled="!podeEnviarOficialmente"
                    v-tooltip.top="
                        !temPdfAnexo
                            ? 'Anexe o PDF da indicação'
                            : !vereadoresIds.length
                              ? 'Selecione vereadores'
                              : ''
                    "
                />
            </div>

            <Dialog
                v-model:visible="envioDialog"
                header="Assinatura eletrônica — Câmara Municipal"
                :modal="true"
                style="width: 520px"
            >
                <div class="flex flex-col gap-4">
                    <Message severity="info" :closable="false" class="text-sm m-0">
                        Revise o PDF anexado. Ao confirmar, o usuário <strong>Câmara</strong> assina
                        eletronicamente e a indicação é encaminhada ao Protocolo Executivo.
                    </Message>
                    <div v-if="carregandoPreview" class="text-sm text-muted-color">Gerando pré-visualização…</div>
                    <template v-else-if="previewEnvio">
                        <div v-if="previewEnvio.preview_pdf_disponivel">
                            <Button
                                label="Abrir PDF da indicação"
                                icon="pi pi-file-pdf"
                                outlined
                                @click="abrirPreviewPdf"
                            />
                        </div>
                        <p class="m-0 text-xs text-muted-color break-all">
                            Hash do documento: {{ previewEnvio.hash_documento?.slice(0, 16) }}…
                        </p>
                    </template>
                    <div class="flex items-start gap-2">
                        <Checkbox v-model="declaracaoAceita" inputId="declaracao_assinatura_indicacao" binary />
                        <label for="declaracao_assinatura_indicacao" class="text-sm cursor-pointer">
                            Declaro que li o documento, concordo com o conteúdo e
                            <strong>assino eletronicamente</strong> em nome da Câmara Municipal
                            ({{ DECLARACAO_ENVIO }}).
                        </label>
                    </div>
                </div>
                <template #footer>
                    <Button label="Cancelar" icon="pi pi-times" text @click="envioDialog = false" />
                    <Button
                        label="Assino e envio"
                        icon="pi pi-check"
                        :loading="enviandoOficial"
                        :disabled="carregandoPreview || !declaracaoAceita"
                        @click="confirmarEnvioOficial"
                    />
                </template>
            </Dialog>
        </div>
    </div>
</template>
