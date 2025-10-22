<script setup>
import { ref, onMounted, nextTick } from 'vue';
import ApiService from '@/service/ApiService.js';
import { useRouter, useRoute } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import axios from 'axios';
import { useUserStore } from '@/stores/userStore'; 

import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

import Editor from 'primevue/editor';
import InputText from 'primevue/inputtext';
import AutoComplete from 'primevue/autocomplete';
import Button from 'primevue/button';
import FileUpload from 'primevue/fileupload';
import InputMask from 'primevue/inputmask';
import Tag from 'primevue/tag';

const toast = useToast();
const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const map = ref(null);
const marker = ref(null);
const defaultCoords = [-23.523, -46.18];

const anexos = ref([]);
const todosServicos = ref([]);
const filteredServicos = ref([]);
const selectedServico = ref(null);
const demandaId = ref(null);
const showMap = ref(false);
const isGeoPendente = ref(false);

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

const reverseGeocode = async (coords) => {
    try {
        const response = await axios.get('https://nominatim.openstreetmap.org/reverse', {
            params: { lat: coords[0], lon: coords[1], format: 'json', addressdetails: 1 }
        });
        if (response.data && response.data.address) {
            const address = response.data.address;
            demanda.value.logradouro = address.road || address.pedestrian || (demanda.value.logradouro || '');
            demanda.value.bairro = address.suburb || address.city_district || (demanda.value.bairro || '');
            toast.add({ severity: 'info', summary: 'Endereço Atualizado', detail: 'Rua e bairro preenchidos pelo mapa.', life: 3000 });

            await nextTick();
            if (map.value) {
                map.value.invalidateSize();
            }
        }
    } catch (error) {
        console.error("Erro na geocodificação reversa:", error);
    }
};

const initMap = (coords) => {
    nextTick(() => {
        if (map.value) {
            map.value.setView(coords, 16);
            return;
        }
        map.value = L.map('demanda-map').setView(coords, 16);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap'
        }).addTo(map.value);

        const isInitialDraggable = !(demanda.value.latitude && demanda.value.longitude);
        updateMarker(coords, isInitialDraggable);

        map.value.on('click', (event) => { // Ouvinte de clique
            const position = event.latlng;
            demanda.value.latitude = position.lat.toFixed(6);
            demanda.value.longitude = position.lng.toFixed(6);

            updateMarker([position.lat, position.lng], false);

            reverseGeocode([position.lat, position.lng]);
        });
    });
};

const updateMarker = (coords, isDraggable = false) => { 
    if (!map.value) {
        return;
    }

    if (marker.value) {
        marker.value.setLatLng(coords);
        if (isDraggable && !marker.value.dragging.enabled()) {
             marker.value.dragging.enable();
        } else if (!isDraggable && marker.value.dragging.enabled()) {
             marker.value.dragging.disable();
        }
    } else {
        marker.value = L.marker(coords, { draggable: isDraggable }).addTo(map.value);
    }
    if(map.value) map.value.setView(coords, 17);
};

onMounted(async () => {
    try {
        const responseServicos = await ApiService.getServicos();
        todosServicos.value = responseServicos.data;

        const idDaRota = route.params.id;
        if (idDaRota) {
            demandaId.value = idDaRota;
            const responseDemanda = await ApiService.getDemandaById(idDaRota);
            demanda.value = responseDemanda.data;
            anexos.value = responseDemanda.data.anexos;
            selectedServico.value = todosServicos.value.find(s => s.id === responseDemanda.data.servico.id);

            if (demanda.value.latitude && demanda.value.longitude) {
                const savedCoords = [demanda.value.latitude, demanda.value.longitude];
                showMap.value = true;
                await nextTick();
                initMap(savedCoords);
                isGeoPendente.value = false;
            } else {
                 isGeoPendente.value = true;
                 showMap.value = false;
            }
        } else {
            showMap.value = false;
             isGeoPendente.value = true;
        }
    } catch (error) { console.error("Erro ao carregar dados:", error); }
});

const searchServico = (event) => {
  if (!event.query.trim().length) {
    filteredServicos.value = [...todosServicos.value];
  } else {
    filteredServicos.value = todosServicos.value.filter((servico) => {
      return servico.nome.toLowerCase().includes(event.query.toLowerCase());
    });
  }
};

const buscarCep = async () => {
  const cepLimpo = demanda.value.cep ? demanda.value.cep.replace(/\D/g, '') : '';
  if (cepLimpo.length === 8) {
    try {
      const response = await axios.get(`https://viacep.com.br/ws/${cepLimpo}/json/`);
      if (!response.data.erro) {
        demanda.value.logradouro = response.data.logradouro;
        demanda.value.bairro = response.data.bairro;
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Endereço preenchido.', life: 3000 });
        
        await geocodeAddress();
      } else {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'CEP não encontrado.', life: 3000 });
      }
    } catch (error) { console.error("Erro ao buscar CEP:", error); }
  }
};

const geocodeAddress = async () => {
    const query = demanda.value.cep || `${demanda.value.logradouro}, ${demanda.value.bairro}, Mogi das Cruzes`;
    if (!query.trim()) return;

    try {
        const response = await axios.get('https://nominatim.openstreetmap.org/search', {
            params: { q: query, format: 'json', limit: 1, countrycodes: 'br' }
        });
        if (response.data && response.data.length > 0) {
            const location = response.data[0];
            const coords = [parseFloat(location.lat), parseFloat(location.lon)];
            demanda.value.latitude = coords[0].toFixed(6);
            demanda.value.longitude = coords[1].toFixed(6);
            isGeoPendente.value = false;

            if (!map.value) {
                showMap.value = true;
                await nextTick();
                initMap(coords);
            } else {
                map.value.setView(coords, 17);
                updateMarker(coords, false);
            }

            toast.add({ severity: 'info', summary: 'Localização Encontrada', detail: 'Pino posicionado. Clique para refinar.', life: 4000 });
        } else {
            isGeoPendente.value = true;
            if (!map.value) {
                showMap.value = true;
                await nextTick();
                initMap(defaultCoords);
            } else {
                 map.value.setView(defaultCoords, 16);
                 if(marker.value) {
                     map.value.removeLayer(marker.value);
                     marker.value = null;
                 }
            }
            toast.add({ severity: 'warn', summary: 'Aviso', detail: 'Endereço não encontrado. Clique no mapa para definir.', life: 5000 });
        }
    } catch (error) {
        console.error("Erro na geocodificação:", error);
        isGeoPendente.value = true;
        if (!map.value) {
            showMap.value = true;
            await nextTick();
            initMap(defaultCoords);
        }
    }
};

const gerarDescricao = () => {
  const nomeServico = selectedServico.value ? selectedServico.value.nome : '[Serviço não selecionado]';
  
  let local = 'não especificado';
  if (demanda.value.logradouro) {
    local = `${demanda.value.logradouro}, Nº ${demanda.value.numero || 'S/N'}, ${demanda.value.bairro}.`;
  }
  
  const user = userStore.currentUser;
  const assinaturaUsuario = user?.assinatura || `${user?.first_name || ''} ${user?.last_name || ''}`.trim();

  demanda.value.descricao = 
    `<p>Exma. Sra. Prefeita,</p>` +
    `<p>Pelo presente, no uso de suas atribuições legais, vem respeitosamente solicitar a Vossa Excelência que determine à secretaria competente a execução do seguinte serviço:</p>` +
    `<p>- Serviço Solicitado: ${nomeServico}<br>- Local da Solicitação: ${local}</p>` +
    `<p>A referida solicitação se faz necessária para atender às demandas da comunidade local e garantir a melhoria da infraestrutura e bem-estar dos cidadãos.</p>` +
    `<p>Contando com a vossa valiosa atenção, renovo os protestos de estima e consideração.</p>` +
    `<p><br></p>` + // Parágrafo em branco para mais espaço
    `<p>Atenciosamente,</p>` +
    `${assinaturaUsuario}`;
};

const salvarRascunho = async () => {
    const payload = {
        ...demanda.value,
        servico_id: selectedServico.value ? selectedServico.value.id : null
    };

    if (!payload.servico_id) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Selecione um serviço.', life: 3000 });
        return;
    }

    try {
        if (demandaId.value) {
            await ApiService.updateDemanda(demandaId.value, payload);
            toast.add({ severity: 'info', summary: 'Salvo', detail: 'Rascunho atualizado.', life: 3000 });
        } else {
            const response = await ApiService.createDemanda(payload);
            demandaId.value = response.data.id;
            router.replace({ name: 'demandas-editar', params: { id: demandaId.value } });
            toast.add({ severity: 'info', summary: 'Salvo', detail: 'Rascunho salvo. Anexe arquivos.', life: 3000 });

            await nextTick();
            if (map.value) {
                console.log('Forcing invalidateSize after saving draft');
                map.value.invalidateSize();
            }
        }

    } catch (error) {
        console.error("Erro ao salvar rascunho:", error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível salvar.', life: 3000 });
    }
};

const enviarOficialmente = async () => {
    if (!demandaId.value) {
        toast.add({ severity: 'warn', summary: 'Aviso', detail: 'Por favor, salve como rascunho antes de enviar.', life: 3000 });
        return;
    }

    if (!demanda.value.latitude || !demanda.value.longitude) {
        isGeoPendente.value = true;
        if (!showMap.value) {
            showMap.value = true;
            await nextTick();
            initMap(defaultCoords);
        }
        toast.add({
            severity: 'error',
            summary: 'Localização Pendente',
            detail: 'Localização obrigatória. Clique no mapa para definir.',
            life: 5000
        });
        const mapElement = document.getElementById('demanda-map');
        if (mapElement) {
            mapElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return;
    }

    try {
        await ApiService.enviarDemanda(demandaId.value);
        toast.add({ severity: 'success', summary: 'Sucesso!', detail: 'Ofício enviado oficialmente.', life: 3000 });
        router.push('/demandas');
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível enviar o ofício.', life: 3000 });
    }
};

const onUpload = async (event) => {
    const formData = new FormData();
    formData.append('demanda', demandaId.value);
    formData.append('arquivo', event.files[0]);

    try {
        const response = await ApiService.createAnexo(formData);
        anexos.value.push(response.data);
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Anexo enviado!', life: 3000 });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha no upload do anexo.', life: 3000 });
    }
};

const removerAnexo = async (anexoId, index) => {
    try {
        await ApiService.deleteAnexo(anexoId);
        anexos.value.splice(index, 1);
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Anexo removido.', life: 3000 });
    } catch (error) {
        console.error("Erro ao remover anexo:", error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível remover o anexo.', life: 3000 });
    }
};
</script>

<template>
  <div>
    <div class="card flex flex-col gap-4 w-full">
      <h5 class="mb-4">Novo Ofício</h5>
      <div>
        <label class="block mb-3" for="titulo">Título do Ofício</label>
        <InputText id="titulo" v-model="demanda.titulo" fluid />
      </div>

      <div>
        <label class="block mb-3" for="servico">Serviço Solicitado</label>
        <AutoComplete
            id="servico"
            v-model="selectedServico"
            :suggestions="filteredServicos"
            @complete="searchServico"
            optionLabel="nome"
            forceSelection
            placeholder="Comece a digitar o nome do serviço..."
            dropdown
            fluid
        >
          <template #option="{ option }">
            <div class="flex items-center justify-between w-full">
              <span>{{ option.nome }}</span>
              <Tag :value="option.tipo" :severity="getTagSeverity(option.tipo)" />
            </div>
          </template>
        </AutoComplete>
      </div>

      <div class="grid grid-cols-12 gap-8">
        <div class="col-span-full lg:col-span-3">
          <label class="block mb-3" for="cep">CEP</label>
          <InputMask id="cep" v-model="demanda.cep" mask="99999-999" placeholder="99999-999" @blur="buscarCep" fluid />
        </div>
        <div class="col-span-full lg:col-span-9">
          <label class="block mb-3" for="logradouro">Logradouro</label>
          <InputText id="logradouro" v-model="demanda.logradouro" fluid />
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

      <div class="field" v-if="showMap">
          <label class="block mb-3">Localização no Mapa</label>
          <small class="block mb-2 text-muted-color">
              <span v-if="!isGeoPendente">Pino posicionado para conferência.</span>
              <span v-else>Não foi possível encontrar o endereço automaticamente.</span>
              <strong>Clique no mapa</strong> para adicionar ou refinar a posição exata.
          </small>
          <div id="demanda-map"
               style="height: 350px; border-radius: 6px; transition: box-shadow 0.3s; cursor: pointer;"
               :class="{ 'shadow-md border-2 border-red-500': isGeoPendente }">
          </div>
      </div>

      <div>
        <div class="flex flex-row items-center gap-2 mb-3">
          <label for="name">Descrição Completa</label>
          <Button label="Gerar texto" icon="pi pi-bolt" class="p-button-text" @click="gerarDescricao" :fluid="false" />
        </div>
        <Editor id="descricao" v-model="demanda.descricao" editorStyle="height: 320px" />
      </div>            

      <div class="flex justify-content-end gap-2 mt-4">
          <Button label="Cancelar" severity="secondary" outlined @click="router.push('/demandas')"></Button>
          <Button label="Salvar Rascunho" icon="pi pi-save" severity="info" @click="salvarRascunho"></Button>
          <Button label="Enviar Oficialmente" icon="pi pi-send" @click="enviarOficialmente" :disabled="!demandaId"></Button>
      </div>

      <div v-if="anexos.length > 0" class="mb-3">
          <div class="font-semibold text-xl mb-3">Anexos Salvos</div>
          <div class="flex flex-column gap-2">
            <div v-for="(anexo, index) in anexos" :key="anexo.id" class="flex items-center p-2 border-1 surface-border border-round">
                <a :href="anexo.arquivo" target="_blank" class="no-underline text-color hover:text-primary flex align-items-center">
                    <i class="pi pi-file mr-2"></i>
                    <span>{{ anexo.arquivo.split('/').pop() }}</span>
                </a>
                <Button icon="pi pi-times" severity="danger" text rounded class="ml-2" @click="removerAnexo(anexo.id, index)" />
            </div>
          </div>
      </div>

      <div class="mb-3">
          <div class="font-semibold text-xl mb-4">Anexar Documentos ou Fotos</div>
          <FileUpload 
            name="arquivo"  
            :multiple="true" 
            accept="image/*,application/pdf" 
            :maxFileSize="2000000"
            @uploader="onUpload" :customUpload="true" :disabled="!demandaId" >
            <template #empty>
              <p>Salve um rascunho para poder anexar arquivos.</p>
            </template>
          </FileUpload>
      </div>

    </div>
  </div>
</template>