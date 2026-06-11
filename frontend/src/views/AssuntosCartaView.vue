<script setup>
import { onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Message from 'primevue/message';
import Select from 'primevue/select';
import Tag from 'primevue/tag';
import Textarea from 'primevue/textarea';

const toast = useToast();

const MODO_OPCOES = [
    { label: 'Protocolável', value: 'PROTOCOLAVEL' },
    { label: 'Somente orientação', value: 'INFORMATIVO' },
    { label: 'Protocolável com condição', value: 'PROTOCOLAVEL_CONDICIONAL' }
];

const loading = ref(false);
const salvandoId = ref(null);
const assuntos = ref([]);

const extrairErro = (error) => error?.response?.data?.detail || 'Operação não concluída.';

const loadAssuntos = async () => {
    loading.value = true;
    try {
        const { data } = await ApiService.listarAssuntosCarta({ todos: 1 });
        assuntos.value = Array.isArray(data) ? data : data?.results || [];
    } catch (error) {
        assuntos.value = [];
        toast.add({ severity: 'error', summary: 'Assuntos', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const salvarAssunto = async (row) => {
    salvandoId.value = row.id;
    try {
        const { data } = await ApiService.atualizarAssuntoCarta(row.id, {
            modo_utilizacao_sgdl: row.modo_utilizacao_sgdl,
            mensagem_orientacao: row.mensagem_orientacao || ''
        });
        Object.assign(row, data);
        toast.add({ severity: 'success', summary: 'Assunto atualizado', detail: row.nome, life: 2500 });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvandoId.value = null;
    }
};

onMounted(loadAssuntos);
</script>

<template>
    <div class="flex flex-col gap-6">
        <div>
            <h2 class="text-2xl font-semibold m-0">Assuntos temáticos da carta</h2>
            <p class="text-surface-600 mt-1 mb-0 text-sm">
                Define o modo padrão de utilização no Copiloto por assunto. Serviços individuais
                podem ter exceção na tela «Fluxo por serviço».
            </p>
        </div>

        <Message severity="info" :closable="false" class="text-sm m-0">
            Serviços <strong>informativos</strong> continuam na triagem semântica, com badge
            «Só orientação»; o bloqueio ocorre ao confirmar ou enviar ofício.
        </Message>

        <Card>
            <template #content>
                <DataTable
                    :value="assuntos"
                    :loading="loading"
                    stripedRows
                    size="small"
                    paginator
                    :rows="20"
                    responsiveLayout="scroll"
                    class="sgdl-table-scroll"
                >
                    <Column field="ordem" header="#" style="width: 3rem" />
                    <Column field="nome" header="Assunto" />
                    <Column header="Modo padrão" style="min-width: 14rem">
                        <template #body="{ data }">
                            <Select
                                v-model="data.modo_utilizacao_sgdl"
                                :options="MODO_OPCOES"
                                optionLabel="label"
                                optionValue="value"
                                class="w-full"
                                @change="salvarAssunto(data)"
                            />
                        </template>
                    </Column>
                    <Column header="Orientação (Copiloto)" style="min-width: 18rem">
                        <template #body="{ data }">
                            <Textarea
                                v-model="data.mensagem_orientacao"
                                rows="2"
                                class="w-full text-sm"
                                autoResize
                                @blur="salvarAssunto(data)"
                            />
                        </template>
                    </Column>
                    <Column header="Badge" style="width: 8rem">
                        <template #body="{ data }">
                            <Tag
                                v-if="data.modo_utilizacao_sgdl === 'INFORMATIVO'"
                                value="Só orientação"
                                severity="warn"
                            />
                            <Tag v-else value="Protocolável" severity="success" />
                        </template>
                    </Column>
                    <Column header="" style="width: 4rem">
                        <template #body="{ data }">
                            <Button
                                icon="pi pi-check"
                                text
                                rounded
                                :loading="salvandoId === data.id"
                                @click="salvarAssunto(data)"
                            />
                        </template>
                    </Column>
                </DataTable>
            </template>
        </Card>
    </div>
</template>
