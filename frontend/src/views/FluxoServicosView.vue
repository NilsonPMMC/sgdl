<script setup>
import { onMounted, ref } from 'vue';
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
import Select from 'primevue/select';
import Tag from 'primevue/tag';
import ToggleSwitch from 'primevue/toggleswitch';

const toast = useToast();

const MODO_OPCOES = [
    { label: 'Triagem manual (Protocolo)', value: 'MANUAL' },
    { label: 'Despacho automático', value: 'AUTOMATICO' }
];

const MODO_UTILIZACAO_OPCOES = [
    { label: '— Herdar do assunto —', value: '' },
    { label: 'Protocolável', value: 'PROTOCOLAVEL' },
    { label: 'Somente orientação', value: 'INFORMATIVO' },
    { label: 'Protocolável com condição', value: 'PROTOCOLAVEL_CONDICIONAL' }
];

const loading = ref(false);
const salvandoId = ref(null);
const salvandoSetorId = ref(null);
const salvandoAssuntoId = ref(null);
const servicos = ref([]);
const assuntosCarta = ref([]);
const busca = ref('');
const unidadesPorOrgao = ref({});

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    return 'Operação não concluída.';
};

const garantirUnidadesOrgao = async (orgaoId) => {
    if (!orgaoId || unidadesPorOrgao.value[orgaoId]) return;
    try {
        const { data } = await ApiService.listarUnidadesAdministrativas({
            sinapse_orgao_id: orgaoId
        });
        unidadesPorOrgao.value[orgaoId] = data?.results || data || [];
    } catch {
        unidadesPorOrgao.value[orgaoId] = [];
    }
};

const opcoesSetor = (row) => {
    const base = [{ label: '— Sem vínculo explícito —', value: null }];
    const lista = unidadesPorOrgao.value[row.orgao_id] || [];
    return base.concat(
        lista.map((u) => ({
            label: u.sigla ? `${u.sigla} — ${u.nome}` : u.nome,
            value: u.id
        }))
    );
};

const rotuloSetorSugerido = (row) => {
    const s = row.setor_sugerido;
    if (!s) return null;
    return s.sigla || s.nome;
};

const loadServicos = async () => {
    loading.value = true;
    try {
        const [{ data }, assuntosResp] = await Promise.all([
            ApiService.listarFluxoServicosCarta({
                q: busca.value || undefined,
                limit: 300
            }),
            assuntosCarta.value.length
                ? Promise.resolve({ data: assuntosCarta.value })
                : ApiService.listarAssuntosCarta()
        ]);
        if (!assuntosCarta.value.length) {
            assuntosCarta.value = assuntosResp.data?.results || assuntosResp.data || [];
        }
        servicos.value = (data?.results || []).map((s) => ({
            ...s,
            assunto_id: s.utilizacao_sgdl?.assunto_id ?? s.assunto_id ?? null,
            modo_utilizacao_sgdl: s.utilizacao_sgdl?.modo_servico ?? ''
        }));
        const orgaos = [...new Set(servicos.value.map((s) => s.orgao_id).filter(Boolean))];
        await Promise.all(orgaos.map((id) => garantirUnidadesOrgao(id)));
    } catch (error) {
        servicos.value = [];
        toast.add({ severity: 'error', summary: 'Fluxo', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const opcoesAssunto = () => {
    const base = [{ label: '— Sem assunto —', value: null }];
    return base.concat(
        assuntosCarta.value.map((a) => ({
            label: a.nome,
            value: a.id
        }))
    );
};

const salvarAssuntoModo = async (row) => {
    if (!row?.sinapse_servico_id) return;
    salvandoAssuntoId.value = row.sinapse_servico_id;
    try {
        const { data } = await ApiService.upsertCartaAssunto({
            sinapse_servico_id: row.sinapse_servico_id,
            assunto_id: row.assunto_id,
            modo_utilizacao_sgdl: row.modo_utilizacao_sgdl ?? ''
        });
        Object.assign(row, data);
        row.assunto_id = data.utilizacao_sgdl?.assunto_id ?? row.assunto_id;
        row.modo_utilizacao_sgdl = data.utilizacao_sgdl?.modo_servico ?? '';
        toast.add({
            severity: 'success',
            summary: 'Classificação salva',
            detail: row.titulo,
            life: 2500
        });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Assunto', detail: extrairErro(error), life: 4000 });
    } finally {
        salvandoAssuntoId.value = null;
    }
};

const salvarLinha = async (row) => {
    if (!row?.sinapse_servico_id) return;
    salvandoId.value = row.sinapse_servico_id;
    try {
        const { data } = await ApiService.upsertFluxoServico({
            sinapse_servico_id: row.sinapse_servico_id,
            modo: row.modo,
            ativo: row.ativo
        });
        row.config_id = data.id;
        row.despacho_automatico = data.despacho_automatico;
        toast.add({
            severity: 'success',
            summary: 'Salvo',
            detail: `${row.titulo} — ${data.modo === 'AUTOMATICO' ? 'automático' : 'manual'}.`,
            life: 2500
        });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvandoId.value = null;
    }
};

const salvarSetor = async (row) => {
    if (!row?.sinapse_servico_id) return;
    salvandoSetorId.value = row.sinapse_servico_id;
    try {
        const { data } = await ApiService.upsertCartaSetor({
            sinapse_servico_id: row.sinapse_servico_id,
            unidade_administrativa_id: row.unidade_administrativa_id
        });
        Object.assign(row, data);
        toast.add({
            severity: 'success',
            summary: 'Setor vinculado',
            detail: row.titulo,
            life: 2500
        });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Setor', detail: extrairErro(error), life: 4000 });
    } finally {
        salvandoSetorId.value = null;
    }
};

onMounted(loadServicos);
</script>

<template>
    <div class="flex flex-col gap-6">
        <div>
            <h2 class="text-2xl font-semibold m-0">Gestão de fluxo por serviço</h2>
            <p class="text-surface-600 mt-1 mb-0 text-sm">
                Defina despacho automático e o <strong>setor operacional</strong> sugerido na carta
                otimizada. Ao protocolar, a demanda entra na fila <code>minha_unidade</code> do setor
                vinculado (ou na primeira unidade ativa do órgão, se não houver vínculo).
            </p>
        </div>

        <Message severity="info" :closable="false" class="text-sm m-0">
            Serviços em <strong>Despacho automático</strong> são protocolados ao receber o ofício do vereador, sem
            ação manual. Tendências e serviços sem órgão na carta permanecem na triagem manual.
        </Message>

        <Card>
            <template #title>Carta de serviços</template>
            <template #content>
                <div class="flex flex-wrap gap-3 mb-4">
                    <IconField class="flex-1 min-w-[16rem]">
                        <InputIcon class="pi pi-search" />
                        <InputText
                            v-model="busca"
                            placeholder="Buscar serviço..."
                            fluid
                            @keyup.enter="loadServicos"
                        />
                    </IconField>
                    <Button label="Buscar" icon="pi pi-search" @click="loadServicos" />
                </div>

                <DataTable
                    :value="servicos"
                    :loading="loading"
                    stripedRows
                    size="small"
                    paginator
                    :rows="15"
                    :rowsPerPageOptions="[15, 30, 50]"
                    responsiveLayout="scroll"
                    class="sgdl-table-scroll"
                >
                    <Column field="titulo" header="Serviço">
                        <template #body="{ data }">
                            <span class="font-medium">{{ data.titulo }}</span>
                            <p class="text-xs text-surface-500 m-0">ID Sinapse {{ data.sinapse_servico_id }}</p>
                        </template>
                    </Column>
                    <Column header="Órgão">
                        <template #body="{ data }">
                            <span class="text-sm">{{ data.orgao_nome || '—' }}</span>
                        </template>
                    </Column>
                    <Column header="Setor (carta)" style="min-width: 14rem">
                        <template #body="{ data }">
                            <Select
                                v-model="data.unidade_administrativa_id"
                                :options="opcoesSetor(data)"
                                optionLabel="label"
                                optionValue="value"
                                class="w-full"
                                :disabled="!data.orgao_id"
                                :loading="salvandoSetorId === data.sinapse_servico_id"
                                @change="salvarSetor(data)"
                            />
                            <p
                                v-if="rotuloSetorSugerido(data) && data.setor_origem === 'ORGAO'"
                                class="text-xs text-surface-500 m-0 mt-1"
                            >
                                Despacho usará: {{ rotuloSetorSugerido(data) }} (fallback órgão)
                            </p>
                        </template>
                    </Column>
                    <Column header="Assunto" style="min-width: 12rem">
                        <template #body="{ data }">
                            <Select
                                v-model="data.assunto_id"
                                :options="opcoesAssunto()"
                                optionLabel="label"
                                optionValue="value"
                                class="w-full"
                                :loading="salvandoAssuntoId === data.sinapse_servico_id"
                                @change="salvarAssuntoModo(data)"
                            />
                        </template>
                    </Column>
                    <Column header="Utilização SGDL" style="min-width: 12rem">
                        <template #body="{ data }">
                            <Select
                                v-model="data.modo_utilizacao_sgdl"
                                :options="MODO_UTILIZACAO_OPCOES"
                                optionLabel="label"
                                optionValue="value"
                                class="w-full"
                                @change="salvarAssuntoModo(data)"
                            />
                            <Tag
                                v-if="data.utilizacao_sgdl?.somente_orientacao"
                                value="Só orientação"
                                severity="warn"
                                class="mt-1"
                            />
                        </template>
                    </Column>
                    <Column header="Modo fluxo" style="min-width: 14rem">
                        <template #body="{ data }">
                            <Select
                                v-model="data.modo"
                                :options="MODO_OPCOES"
                                optionLabel="label"
                                optionValue="value"
                                class="w-full"
                                @change="salvarLinha(data)"
                            />
                        </template>
                    </Column>
                    <Column header="Ativo" style="width: 6rem">
                        <template #body="{ data }">
                            <ToggleSwitch v-model="data.ativo" @change="salvarLinha(data)" />
                        </template>
                    </Column>
                    <Column header="Efeito" style="width: 8rem">
                        <template #body="{ data }">
                            <Tag
                                v-if="data.modo === 'AUTOMATICO' && data.ativo"
                                value="Auto"
                                severity="success"
                            />
                            <Tag v-else value="Manual" severity="secondary" />
                        </template>
                    </Column>
                    <Column header="" style="width: 5rem">
                        <template #body="{ data }">
                            <Button
                                icon="pi pi-check"
                                text
                                rounded
                                :loading="salvandoId === data.sinapse_servico_id"
                                v-tooltip.top="'Salvar fluxo'"
                                @click="salvarLinha(data)"
                            />
                        </template>
                    </Column>
                </DataTable>
            </template>
        </Card>
    </div>
</template>
