<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Select from 'primevue/select';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import Tag from 'primevue/tag';
import Textarea from 'primevue/textarea';
import Tabs from 'primevue/tabs';
import TabList from 'primevue/tablist';
import Tab from 'primevue/tab';
import TabPanels from 'primevue/tabpanels';
import TabPanel from 'primevue/tabpanel';
import Panel from 'primevue/panel';
import Badge from 'primevue/badge';

const toast = useToast();

// Estados de loading
const loadingEstatisticas = ref(false);
const loadingServicos = ref(false);
const loadingComparacao = ref(false);
const loadingProblemas = ref(false);
const loadingGeral = ref(true);

// Dados da base otimizada
const estatisticas = ref({});
const servicosOtimizados = ref([]);
const comparacaoScores = ref({});
const problemasComuns = ref([]);
const servicoSelecionado = ref(null);
const totalServicosLista = ref(0);

// Filtros
const filtros = ref({
    search: '',
    score_min: null,
    tem_embedding: null,
    versao_otimizacao: null,
    limit: 20,
    offset: 0
});

// Simulação de busca
const simulacao = ref({
    texto: 'Cratera na rua em frente à escola',
    top_k: 5
});
const resultadoSimulacao = ref(null);
const loadingSimulacao = ref(false);

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.erro) return String(data.erro);
    if (data?.detail) return String(data.detail);
    return 'Operação não concluída.';
};

// Funções utilitárias
const formatarScore = (score) => {
    if (score == null || Number.isNaN(Number(score))) return '—';
    return Number(score).toFixed(1);
};

const formatarPercentual = (valor) => {
    if (valor == null || Number.isNaN(Number(valor))) return '—';
    return `${Number(valor).toFixed(1)}%`;
};

const getScoreColor = (score) => {
    if (score >= 8) return 'success';
    if (score >= 6) return 'info';
    if (score >= 4) return 'warning';
    return 'danger';
};

// Estatísticas da base otimizada (API real)
const loadEstatisticas = async () => {
    loadingEstatisticas.value = true;
    try {
        const { data } = await ApiService.getCartaOtimizadaEstatisticas();
        estatisticas.value = {
            total_servicos: data.total_servicos ?? 0,
            com_embedding: data.com_embedding ?? 0,
            percentual_cobertura: data.percentual_cobertura ?? 0,
            score_medio: data.score_medio ?? 0,
            distribuicao_scores: data.distribuicao_scores ?? {},
            versoes: data.versoes ?? [],
        };
    } catch (error) {
        console.error('Erro estatísticas carta otimizada:', error);
        toast.add({
            severity: 'warn',
            summary: 'Estatísticas',
            detail: extrairErro(error),
            life: 4000
        });
        estatisticas.value = {};
    } finally {
        loadingEstatisticas.value = false;
    }
};

// Listagem da base otimizada (API real)
const loadServicosOtimizados = async () => {
    loadingServicos.value = true;
    try {
        const params = {
            search: filtros.value.search || undefined,
            score_min: filtros.value.score_min ?? undefined,
            tem_embedding:
                filtros.value.tem_embedding === true
                    ? 'true'
                    : filtros.value.tem_embedding === false
                      ? 'false'
                      : undefined,
            limit: filtros.value.limit,
            offset: filtros.value.offset,
        };
        const { data } = await ApiService.getCartaOtimizadaServicos(params);
        const lista = Array.isArray(data) ? data : data?.results ?? [];
        servicosOtimizados.value = lista;
        totalServicosLista.value = data?.count ?? lista.length;
    } catch (error) {
        console.error('Erro ao carregar serviços:', error);
        servicosOtimizados.value = [];
        totalServicosLista.value = 0;
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: 'Falha ao carregar serviços: ' + extrairErro(error),
            life: 4000
        });
    } finally {
        loadingServicos.value = false;
    }
};

const loadComparacaoScores = async () => {
    loadingComparacao.value = true;
    try {
        const { data } = await ApiService.getCartaOtimizadaComparacaoScores();
        comparacaoScores.value = data;
    } catch (error) {
        console.error('Erro comparação scores:', error);
        comparacaoScores.value = {};
    } finally {
        loadingComparacao.value = false;
    }
};

const loadProblemasComuns = async () => {
    loadingProblemas.value = true;
    try {
        const { data } = await ApiService.getCartaOtimizadaProblemasComuns();
        problemasComuns.value =
            data.problemas_comuns ?? data.problemas_mais_frequentes ?? [];
    } catch (error) {
        console.error('Erro problemas comuns:', error);
        problemasComuns.value = [];
    } finally {
        loadingProblemas.value = false;
    }
};

// Seleção de serviço
const selecionarServico = (servico) => {
    servicoSelecionado.value = servico;
};

// Busca
const buscar = () => {
    filtros.value.offset = 0;
    loadServicosOtimizados();
};

// Paginação
const paginaAnterior = () => {
    filtros.value.offset = Math.max(0, filtros.value.offset - filtros.value.limit);
    loadServicosOtimizados();
};

const proximaPagina = () => {
    filtros.value.offset += filtros.value.limit;
    loadServicosOtimizados();
};

const podePaginaAnterior = computed(() => filtros.value.offset > 0);
const podeProximaPagina = computed(
    () => filtros.value.offset + filtros.value.limit < totalServicosLista.value
);

// Simulação de busca semântica
const executarSimulacao = async () => {
    const texto = (simulacao.value.texto || '').trim();
    if (texto.length < 4) {
        toast.add({
            severity: 'warn',
            summary: 'Simulação',
            detail: 'Descreva o pedido com pelo menos 4 caracteres.',
            life: 3500
        });
        return;
    }
    
    loadingSimulacao.value = true;
    resultadoSimulacao.value = null;
    
    try {
        // Simular busca via chat (que usa a base otimizada)
        const { data } = await ApiService.interagirCopiloto({
            mensagem: texto
        });
        
        if (data?.demandas_extraidas?.[0]?.candidatos_sinapse) {
            resultadoSimulacao.value = {
                ok: true,
                candidatos: data.demandas_extraidas[0].candidatos_sinapse,
                texto_processado: data.demandas_extraidas[0].texto_para_embedding
            };
        } else {
            resultadoSimulacao.value = {
                ok: false,
                erro: 'Nenhum serviço encontrado para esta consulta'
            };
        }
    } catch (error) {
        toast.add({ 
            severity: 'error', 
            summary: 'Simulação', 
            detail: extrairErro(error), 
            life: 4000 
        });
    } finally {
        loadingSimulacao.value = false;
    }
};

onMounted(async () => {
    try {
        await Promise.all([
            loadEstatisticas(),
            loadServicosOtimizados(),
            loadComparacaoScores(),
            loadProblemasComuns(),
        ]);
    } catch (error) {
        console.error('Erro durante inicialização:', error);
        toast.add({
            severity: 'error',
            summary: 'Erro de Inicialização',
            detail: 'Falha ao carregar dados da página.',
            life: 5000
        });
    } finally {
        loadingGeral.value = false;
    }
});

// Watchers para filtros
watch(
    () => [filtros.value.search, filtros.value.score_min, filtros.value.tem_embedding],
    () => {
        filtros.value.offset = 0;
        loadServicosOtimizados();
    },
    { deep: true }
);
</script>

<template>
    <div class="flex flex-col gap-6">
        <!-- Loading Global -->
        <div v-if="loadingGeral" class="text-center p-8">
            <ProgressSpinner />
            <p class="text-[var(--text-color-secondary)] mt-4">Carregando dados da base otimizada...</p>
        </div>
        
        <!-- Conteúdo Principal -->
        <template v-else>
        <!-- Header -->
        <div>
            <h2 class="text-3xl font-bold text-[var(--text-color)] m-0 flex items-center gap-3">
                Base Otimizada da Carta de Serviços
                <Badge v-if="estatisticas.total_servicos" :value="estatisticas.total_servicos" severity="info" />
            </h2>
            <p class="text-[var(--text-color-secondary)] mt-2 mb-0">
                Visualização e análise da nova base otimizada com embeddings aprimorados e busca semântica inteligente.
            </p>
        </div>

        <!-- Estatísticas Dashboard -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card class="p-0 text-center">
                <template #content>
                    <div class="p-4">
                        <div class="text-2xl font-bold text-[var(--primary-color)]">
                            {{ estatisticas.total_servicos || '—' }}
                        </div>
                        <div class="text-sm text-[var(--text-color-secondary)]">Total de Serviços</div>
                    </div>
                </template>
            </Card>
            
            <Card class="p-0 text-center">
                <template #content>
                    <div class="p-4">
                        <div class="text-2xl font-bold text-green-500">
                            {{ formatarPercentual(estatisticas.percentual_cobertura) }}
                        </div>
                        <div class="text-sm text-[var(--text-color-secondary)] mt-2">Cobertura Embedding</div>
                    </div>
                </template>
            </Card>

            <Card class="p-0 text-center">
                <template #content>
                    <div class="p-4">
                        <div class="text-2xl font-bold" :class="`text-[var(--${getScoreColor(estatisticas.score_medio)}-500)]`">
                            {{ formatarScore(estatisticas.score_medio) }}
                        </div>
                        <div class="text-sm text-[var(--text-color-secondary)]">Score Médio</div>
                    </div>
                </template>
            </Card>

            <Card class="p-0 text-center">
                <template #content>
                    <div class="p-4">
                        <div class="flex justify-center gap-1 mb-2 text-xs">
                            <span class="px-2 py-1 bg-green-100 text-green-800 rounded" :title="`Excelente: ${estatisticas.distribuicao_scores?.excelente || 0}`">
                                E: {{ estatisticas.distribuicao_scores?.excelente || 0 }}
                            </span>
                            <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded" :title="`Bom: ${estatisticas.distribuicao_scores?.bom || 0}`">
                                B: {{ estatisticas.distribuicao_scores?.bom || 0 }}
                            </span>
                            <span class="px-2 py-1 bg-yellow-100 text-yellow-800 rounded" :title="`Regular: ${estatisticas.distribuicao_scores?.regular || 0}`">
                                R: {{ estatisticas.distribuicao_scores?.regular || 0 }}
                            </span>
                            <span class="px-2 py-1 bg-red-100 text-red-800 rounded" :title="`Precisa Melhorias: ${estatisticas.distribuicao_scores?.ruim || 0}`">
                                P: {{ estatisticas.distribuicao_scores?.ruim || 0 }}
                            </span>
                        </div>
                        <div class="text-sm text-[var(--text-color-secondary)]">Distribuição Qualidade</div>
                    </div>
                </template>
            </Card>
        </div>

        <!-- Tabs principais -->
        <Tabs value="0" class="w-full">
            <TabList>
                <Tab value="0">Serviços Otimizados</Tab>
                <Tab value="1">Comparação de Scores</Tab>
                <Tab value="2">Problemas Comuns</Tab>
                <Tab value="3">Simulador de Triagem Semântica</Tab>
            </TabList>
            
            <TabPanels>
                <TabPanel value="0">
                <div class="flex flex-col gap-4">
                    <!-- Filtros -->
                    <div class="flex gap-3 flex-wrap">
                        <div class="flex-grow">
                            <InputText 
                                v-model="filtros.search" 
                                placeholder="Buscar por título, descrição ou intenção..." 
                                class="w-full" 
                                @keyup.enter="buscar" 
                            />
                        </div>
                        <div class="w-full sm:w-auto">
                            <Select 
                                v-model="filtros.score_min" 
                                :options="[
                                    { label: 'Todos os scores', value: null },
                                    { label: 'Score ≥ 8 (Excelente)', value: 8 },
                                    { label: 'Score ≥ 6 (Bom)', value: 6 },
                                    { label: 'Score ≥ 4 (Regular)', value: 4 }
                                ]" 
                                option-label="label" 
                                option-value="value" 
                                placeholder="Filtrar por qualidade" 
                                class="w-full" 
                                show-clear 
                            />
                        </div>
                        <div class="w-full sm:w-auto">
                            <Select 
                                v-model="filtros.tem_embedding" 
                                :options="[
                                    { label: 'Todos', value: null },
                                    { label: 'Com embedding', value: true },
                                    { label: 'Sem embedding', value: false }
                                ]" 
                                option-label="label" 
                                option-value="value" 
                                placeholder="Embedding" 
                                class="w-full" 
                            />
                        </div>
                        <Button icon="pi pi-search" label="Buscar" @click="buscar" :loading="loadingServicos" />
                    </div>

                    <!-- Loading -->
                    <div v-if="loadingServicos" class="text-center p-6">
                        <ProgressSpinner />
                        <p class="text-[var(--text-color-secondary)] mt-3">Carregando serviços otimizados...</p>
                    </div>
                    
                    <!-- Tabela de serviços -->
                    <DataTable
                        v-else
                        :value="servicosOtimizados"
                        striped
                        responsiveLayout="scroll"
                        class="sgdl-table-scroll border rounded-lg"
                    >
                        <Column field="sinapse_servico_id" header="ID" class="w-16">
                            <template #body="{ data }">
                                <Badge :value="data.sinapse_servico_id" severity="secondary" />
                            </template>
                        </Column>
                        
                        <Column field="titulo_otimizado" header="Serviço Otimizado">
                            <template #body="{ data }">
                                <div class="cursor-pointer" @click="selecionarServico(data)">
                                    <div class="font-semibold text-[var(--primary-color)] hover:underline">
                                        {{ data.titulo_otimizado }}
                                    </div>
                                    <div class="text-sm text-[var(--text-color-secondary)] mt-1">
                                        {{ data.intencao_servico || 'Sem intenção definida' }}
                                    </div>
                                    <div v-if="data.preview_texto_rag" class="text-xs text-[var(--text-color-secondary)] mt-1 italic">
                                        RAG: {{ data.preview_texto_rag }}
                                    </div>
                                </div>
                            </template>
                        </Column>

                        <Column header="Qualidade" class="w-32">
                            <template #body="{ data }">
                                <div class="flex flex-col gap-1">
                                    <div class="flex items-center gap-2">
                                        <Tag 
                                            :value="formatarScore(data.score_qualidade_otimizado)" 
                                            :severity="getScoreColor(data.score_qualidade_otimizado)" 
                                        />
                                        <span v-if="data.percentual_melhoria > 0" class="text-xs text-green-600">
                                            +{{ formatarPercentual(data.percentual_melhoria) }}
                                        </span>
                                    </div>
                                    <div class="text-xs text-[var(--text-color-secondary)]">
                                        Original: {{ formatarScore(data.score_qualidade_original) }}
                                    </div>
                                </div>
                            </template>
                        </Column>

                        <Column header="Status" class="w-24">
                            <template #body="{ data }">
                                <div class="flex flex-col items-center gap-1">
                                    <i :class="data.tem_embedding ? 'pi pi-check-circle text-green-500' : 'pi pi-times-circle text-red-500'" />
                                    <span class="text-xs">{{ data.tem_embedding ? 'Embedding' : 'Sem vector' }}</span>
                                </div>
                            </template>
                        </Column>
                    </DataTable>

                    <!-- Paginação -->
                    <div class="flex justify-between items-center mt-4">
                        <Button 
                            icon="pi pi-angle-left" 
                            label="Anterior" 
                            @click="paginaAnterior" 
                            :disabled="!podePaginaAnterior" 
                            text 
                        />
                        <span class="text-sm text-[var(--text-color-secondary)]">
                            Página {{ Math.floor(filtros.offset / filtros.limit) + 1 }}
                        </span>
                        <Button 
                            icon="pi pi-angle-right" 
                            icon-pos="right" 
                            label="Próxima" 
                            @click="proximaPagina" 
                            :disabled="!podeProximaPagina" 
                            text 
                        />
                    </div>
                </div>
                </TabPanel>

                <!-- Tab 4: Simulador de Busca -->
                <TabPanel value="3">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-[var(--text-color)] mb-2">
                                Teste a Busca Semântica Otimizada
                            </label>
                            <Textarea 
                                v-model="simulacao.texto" 
                                rows="4" 
                                class="w-full" 
                                placeholder="Ex: Cratera gigante na rua, buraco perigoso que precisa ser reparado urgente..." 
                            />
                            <small class="text-[var(--text-color-secondary)]">
                                Dica: Teste palavras como cratera, buraco, poste, iluminação, lixo, mato, etc.
                            </small>
                        </div>
                        
                        <div class="flex items-end gap-3">
                            <div>
                                <label class="block text-sm font-medium text-[var(--text-color)] mb-2">
                                    Resultados
                                </label>
                                <InputText v-model.number="simulacao.top_k" type="number" min="1" max="10" class="w-20" />
                            </div>
                            <Button 
                                icon="pi pi-play" 
                                label="Testar Busca Otimizada" 
                                @click="executarSimulacao" 
                                :loading="loadingSimulacao" 
                                severity="success"
                            />
                        </div>
                    </div>

                    <div v-if="resultadoSimulacao">
                        <h5 class="font-medium text-[var(--text-color)] mb-3 flex items-center gap-2">
                            <i class="pi pi-chart-bar" />
                            Resultado da Busca Otimizada
                        </h5>
                        
                        <div v-if="resultadoSimulacao.ok" class="space-y-3">
                            <div class="text-sm text-[var(--text-color-secondary)] p-3 bg-[var(--surface-100)] rounded">
                                <strong>Texto processado:</strong> {{ resultadoSimulacao.texto_processado || simulacao.texto }}
                            </div>
                            
                            <div 
                                v-for="(candidato, index) in resultadoSimulacao.candidatos" 
                                :key="candidato.servico_id" 
                                class="border border-[var(--surface-border)] rounded-lg p-4 hover:bg-[var(--surface-50)] transition-colors"
                            >
                                <div class="flex justify-between items-start">
                                    <div class="flex-grow">
                                        <div class="font-medium text-[var(--text-color)] flex items-center gap-2">
                                            <Badge :value="index + 1" severity="secondary" />
                                            {{ candidato.titulo }}
                                        </div>
                                        <div class="text-sm text-[var(--text-color-secondary)] mt-1">
                                            {{ candidato.orgao }}
                                        </div>
                                    </div>
                                    <Tag 
                                        :value="formatarPercentual(candidato.score * 100)" 
                                        :severity="candidato.score > 0.7 ? 'success' : candidato.score > 0.5 ? 'warning' : 'danger'" 
                                    />
                                </div>
                            </div>
                        </div>
                        
                        <Message v-else severity="warn" :closable="false">
                            {{ resultadoSimulacao.erro || 'Nenhum serviço adequado foi encontrado.' }}
                        </Message>
                    </div>
                </div>
                </TabPanel>

                <!-- Tab 2: Comparação e Tab 3: Análises -->
                <TabPanel value="1">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <!-- Comparação de Scores -->
                        <Card>
                            <template #title>
                                <div class="flex items-center gap-2">
                                    <i class="pi pi-chart-bar text-xl text-blue-600"></i>
                                    <span>Comparação por Score</span>
                                </div>
                            </template>
                            <template #content>
                                <div v-if="loadingComparacao" class="text-center py-6">
                                    <ProgressSpinner />
                                    <p class="mt-2 text-[var(--text-color-secondary)]">Carregando comparação...</p>
                                </div>
                                <div v-else-if="comparacaoScores?.comparacao_por_faixa" class="space-y-4">
                                    <div v-for="faixa in comparacaoScores.comparacao_por_faixa" :key="faixa.faixa" 
                                        class="p-4 border rounded-lg">
                                        <div class="flex justify-between items-center mb-2">
                                            <span class="font-medium text-[var(--text-color)]">{{ faixa.faixa }}</span>
                                            <span class="text-lg font-bold text-blue-600">{{ faixa.quantidade }}</span>
                                        </div>
                                        <div class="text-sm text-[var(--text-color-secondary)]">
                                            Melhoria média: {{ faixa.melhoria_media }}%
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </Card>
                    </div>
                </TabPanel>

                <TabPanel value="2">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Comparação de Scores -->
                    <Card class="p-0">
                        <template #title>Melhoria por Faixa de Score Original</template>
                        <template #content>
                            <div v-if="loadingComparacao" class="text-center p-4">
                                <ProgressSpinner />
                            </div>
                            <div v-else-if="comparacaoScores.comparacao_por_faixa" class="space-y-3">
                                <div 
                                    v-for="faixa in comparacaoScores.comparacao_por_faixa" 
                                    :key="faixa.faixa"
                                    class="flex justify-between items-center p-3 border border-[var(--surface-border)] rounded"
                                >
                                    <div>
                                        <div class="font-medium">Score {{ faixa.faixa }}</div>
                                        <div class="text-sm text-[var(--text-color-secondary)]">
                                            {{ faixa.quantidade }} serviços
                                        </div>
                                    </div>
                                    <div class="text-right">
                                        <div class="font-bold text-green-600">
                                            +{{ formatarScore(faixa.melhoria_media) }}
                                        </div>
                                        <div class="text-xs text-[var(--text-color-secondary)]">
                                            {{ formatarScore(faixa.score_original_medio) }} → {{ formatarScore(faixa.score_otimizado_medio) }}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </template>
                    </Card>

                    <!-- Problemas Mais Comuns -->
                    <Card class="p-0">
                        <template #title>Problemas Mais Identificados</template>
                        <template #content>
                            <div v-if="loadingProblemas" class="text-center p-4">
                                <ProgressSpinner />
                            </div>
                            <div v-else class="space-y-2">
                                <div 
                                    v-for="problema in problemasComuns.slice(0, 8)" 
                                    :key="problema.problema"
                                    class="flex justify-between items-center p-2 hover:bg-[var(--surface-100)] rounded"
                                >
                                    <span class="text-sm">{{ problema.problema }}</span>
                                    <Badge :value="problema.frequencia" severity="secondary" />
                                </div>
                            </div>
                        </template>
                    </Card>
                </div>
                </TabPanel>
            </TabPanels>
        </Tabs>

        <!-- Detalhes do Serviço Selecionado -->
        <Panel v-if="servicoSelecionado" header="Detalhes do Serviço Otimizado" toggleable>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div class="space-y-4">
                    <div>
                        <h4 class="font-bold text-lg text-[var(--text-color)] mb-2">
                            {{ servicoSelecionado.titulo_otimizado }}
                        </h4>
                        <div class="flex gap-2 flex-wrap mb-3">
                            <Badge :value="`ID: ${servicoSelecionado.sinapse_servico_id}`" severity="secondary" />
                            <Tag 
                                :value="`Score: ${formatarScore(servicoSelecionado.score_qualidade_otimizado)}`" 
                                :severity="getScoreColor(servicoSelecionado.score_qualidade_otimizado)" 
                            />
                            <Badge 
                                v-if="servicoSelecionado.tem_embedding" 
                                value="Com Embedding" 
                                severity="success" 
                            />
                        </div>
                    </div>
                    
                    <div v-if="servicoSelecionado.descricao_objetiva">
                        <h5 class="font-medium text-[var(--text-color)] mb-2">Descrição Objetiva</h5>
                        <p class="text-sm text-[var(--text-color-secondary)]">
                            {{ servicoSelecionado.descricao_objetiva }}
                        </p>
                    </div>

                    <div v-if="servicoSelecionado.intencao_servico">
                        <h5 class="font-medium text-[var(--text-color)] mb-2">Intenção do Serviço</h5>
                        <p class="text-sm text-[var(--text-color-secondary)]">
                            {{ servicoSelecionado.intencao_servico }}
                        </p>
                    </div>

                    <div v-if="servicoSelecionado.problemas_resolve?.length">
                        <h5 class="font-medium text-[var(--text-color)] mb-2">Problemas que Resolve</h5>
                        <ul class="text-sm text-[var(--text-color-secondary)] list-disc list-inside space-y-1">
                            <li v-for="problema in servicoSelecionado.problemas_resolve" :key="problema">
                                {{ problema }}
                            </li>
                        </ul>
                    </div>
                </div>

                <div class="space-y-4">
                    <div v-if="servicoSelecionado.palavras_chave?.length">
                        <h5 class="font-medium text-[var(--text-color)] mb-2">Palavras-chave</h5>
                        <div class="flex gap-1 flex-wrap">
                            <Badge 
                                v-for="palavra in servicoSelecionado.palavras_chave" 
                                :key="palavra"
                                :value="palavra" 
                                severity="info" 
                            />
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-3 text-sm">
                        <div v-if="servicoSelecionado.prazo_dias">
                            <strong>Prazo:</strong> {{ servicoSelecionado.prazo_dias }} dias úteis
                        </div>
                        <div v-if="servicoSelecionado.tipo_processo">
                            <strong>Tipo:</strong> {{ servicoSelecionado.tipo_processo }}
                        </div>
                        <div v-if="servicoSelecionado.unidade_administrativa_resumo">
                            <strong>Setor vinculado:</strong>
                            {{
                                servicoSelecionado.unidade_administrativa_resumo.sigla
                                    || servicoSelecionado.unidade_administrativa_resumo.nome
                            }}
                        </div>
                    </div>

                    <div v-if="servicoSelecionado.preview_texto_rag">
                        <h5 class="font-medium text-[var(--text-color)] mb-2">Texto RAG Otimizado</h5>
                        <Textarea 
                            :value="servicoSelecionado.preview_texto_rag" 
                            readonly 
                            rows="4" 
                            class="w-full text-xs" 
                        />
                    </div>

                    <div v-if="servicoSelecionado.melhorias_aplicadas?.length">
                        <h5 class="font-medium text-[var(--text-color)] mb-2">Melhorias Aplicadas</h5>
                        <ul class="text-sm text-green-600 list-disc list-inside space-y-1">
                            <li v-for="melhoria in servicoSelecionado.melhorias_aplicadas" :key="melhoria">
                                {{ melhoria }}
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </Panel>
        </template>
    </div>
</template>