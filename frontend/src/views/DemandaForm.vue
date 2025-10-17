<script setup>
import { ref, onMounted } from 'vue';
import ApiService from '@/service/ApiService.js';
import { useRouter, useRoute } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import axios from 'axios';
import { useUserStore } from '@/stores/userStore'; 

// Componentes do PrimeVue
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

const anexos = ref([]);
const todosServicos = ref([]);
const filteredServicos = ref([]);
const selectedServico = ref(null);
const demandaId = ref(null);

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

// Objeto principal do formulário
const demanda = ref({
  titulo: '',
  descricao: '',
  cep: '',
  logradouro: '',
  numero: '',
  complemento: '',
  bairro: ''
});

// Busca a lista de serviços quando a página carrega
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
    }
  } catch (error) {
    console.error("Erro ao carregar dados:", error);
    toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível carregar os dados da página.', life: 3000 });
  }
});

// Filtra os serviços para o AutoComplete
const searchServico = (event) => {
  if (!event.query.trim().length) {
    filteredServicos.value = [...todosServicos.value];
  } else {
    filteredServicos.value = todosServicos.value.filter((servico) => {
      return servico.nome.toLowerCase().includes(event.query.toLowerCase());
    });
  }
};

// Busca o endereço a partir do CEP
const buscarCep = async () => {
  const cepLimpo = demanda.value.cep ? demanda.value.cep.replace(/\D/g, '') : ''; // ✅ CORREÇÃO: Limpando a máscara do CEP
  if (cepLimpo.length === 8) {
    try {
      const response = await axios.get(`https://viacep.com.br/ws/${cepLimpo}/json/`);
      if (response.data.erro) {
        toast.add({ severity: 'error', summary: 'Erro', detail: 'CEP não encontrado.', life: 3000 });
      } else {
        demanda.value.logradouro = response.data.logradouro;
        demanda.value.bairro = response.data.bairro;
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Endereço preenchido.', life: 3000 });
      }
    } catch (error) {
      console.error("Erro ao buscar CEP:", error);
      toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível buscar o CEP.', life: 3000 });
    }
  }
};

// Gera o texto do ofício
const gerarDescricao = () => {
  const nomeServico = selectedServico.value ? selectedServico.value.nome : '[Serviço não selecionado]';
  
  let local = 'não especificado';
  if (demanda.value.logradouro) {
    local = `${demanda.value.logradouro}, Nº ${demanda.value.numero || 'S/N'}, ${demanda.value.bairro}.`;
  }
  
  const nomeVereador = "Vereador(a) [Nome do Vereador]";

  demanda.value.descricao = 
    `<p>Exmo(a). Sr(a). Prefeito(a),</p>` +
    `<p>Pelo presente, o(a) ${nomeVereador}, no uso de suas atribuições legais, vem respeitosamente solicitar a Vossa Excelência que determine à secretaria competente a execução do seguinte serviço:</p>` +
    `<p>- Serviço Solicitado: ${nomeServico}<br>- Local da Solicitação: ${local}</p>` +
    `<p>A referida solicitação se faz necessária para atender às demandas da comunidade local e garantir a melhoria da infraestrutura e bem-estar dos cidadãos.</p>` +
    `<p>Contando com a vossa valiosa atenção, renovo os protestos de estima e consideração.</p>` +
    `<p><br></p>` + // Parágrafo em branco para mais espaço
    `<p>Atenciosamente,</p>` +
    `<p><strong>${nomeVereador}</strong></p>`; // Podemos até usar <strong> para negrito!
};

// Salva a demanda
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
            // Se já tem ID, atualiza o rascunho
            await ApiService.updateDemanda(demandaId.value, payload);
            toast.add({ severity: 'info', summary: 'Salvo', detail: 'Rascunho atualizado com sucesso.', life: 3000 });
        } else {
            // Se não tem ID, cria um novo rascunho
            const response = await ApiService.createDemanda(payload);
            demandaId.value = response.data.id;
            // Atualiza a URL para o modo de edição sem recarregar a página
            router.replace({ name: 'demandas-editar', params: { id: demandaId.value } });
            toast.add({ severity: 'info', summary: 'Salvo', detail: 'Rascunho salvo. Agora você pode anexar arquivos.', life: 3000 });
        }
    } catch (error) {
        console.error("Erro ao salvar rascunho:", error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível salvar o rascunho.', life: 3000 });
    }
};

const enviarOficialmente = async () => {
    if (!demandaId.value) {
        toast.add({ severity: 'warn', summary: 'Aviso', detail: 'Por favor, salve como rascunho antes de enviar.', life: 3000 });
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
        anexos.value.splice(index, 1); // Remove o anexo da lista na tela
        toast.add({ severity: 'success', summary: 'Sucesso', detail: 'Anexo removido.', life: 3000 });
    } catch (error) {
        console.error("Erro ao remover anexo:", error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível remover o anexo.', life: 3000 });
    }
};
</script>

<template>
  <Fluid>
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

      <div>
        <label for="name" class="block mb-3">Descrição Completa</label>
        <Editor id="descricao" v-model="demanda.descricao" editorStyle="height: 320px" />
      </div>
      
      <div>
        <Button label="Gerar texto" icon="pi pi-bolt" class="p-button-text" @click="gerarDescricao" :fluid="false" />
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
  </Fluid>
</template>