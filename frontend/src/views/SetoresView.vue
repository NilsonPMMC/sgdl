<script setup>
import { computed, onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';
import { useUserStore } from '@/stores/userStore';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import Select from 'primevue/select';
import Tag from 'primevue/tag';
import ToggleSwitch from 'primevue/toggleswitch';

const toast = useToast();
const userStore = useUserStore();
const podeGerir = computed(() => ['GESTOR', 'PROTOCOLO'].includes(userStore.perfil));

const loading = ref(false);
const loadingDepara = ref(false);
const importando = ref(false);
const setores = ref([]);
const depara = ref([]);
const orgaos = ref([]);
const usuarios = ref([]);
const dialogNovo = ref(false);
const dialogResp = ref(false);
const salvando = ref(false);
const setorSelecionado = ref(null);

const formNovo = ref({
    sinapse_orgao_id: null,
    nome: '',
    sigla: ''
});

const formResp = ref({
    usuario_id: null
});

const extrairErro = (error) => {
    const data = error?.response?.data;
    if (data?.detail) return String(data.detail);
    return 'Operação não concluída.';
};

const loadOrgaos = async () => {
    try {
        const { data } = await ApiService.listarOrgaosSetores();
        orgaos.value = (data?.results || []).map((o) => ({
            label: o.nome || o.label || `Órgão ${o.id}`,
            value: o.id
        }));
    } catch {
        orgaos.value = [];
    }
};

const loadDepara = async () => {
    if (!podeGerir.value) return;
    loadingDepara.value = true;
    try {
        let { data } = await ApiService.listarDeParaRmSinapse();
        let lista = Array.isArray(data) ? data : data?.results || [];
        if (!lista.length) {
            await ApiService.carregarDeParaRmCsv();
            ({ data } = await ApiService.listarDeParaRmSinapse());
            lista = Array.isArray(data) ? data : data?.results || [];
        }
        depara.value = lista;
    } catch {
        depara.value = [];
    } finally {
        loadingDepara.value = false;
    }
};

const salvarDepara = async (row) => {
    try {
        await ApiService.atualizarDeParaRmSinapse(row.id, {
            sinapse_orgao_id: row.sinapse_orgao_id || null,
            ativo: row.ativo,
            observacao: row.observacao || ''
        });
        toast.add({ severity: 'success', summary: 'De-para salvo', detail: row.cod_rm, life: 2000 });
    } catch (error) {
        toast.add({ severity: 'error', summary: 'De-para', detail: extrairErro(error), life: 4000 });
    }
};

const importarRm = async (dryRun = false) => {
    importando.value = true;
    try {
        const { data } = await ApiService.importarUnidadesRm({ dry_run: dryRun, carregar_csv: true });
        toast.add({
            severity: dryRun ? 'info' : 'success',
            summary: dryRun ? 'Simulação RM271698' : 'Importação RM271698',
            detail: `${data.importadas} novas, ${data.atualizadas} atualizadas, ${data.ignoradas_orfaos} órfãs.`,
            life: 6000
        });
        if (!dryRun) await loadSetores();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Importação', detail: extrairErro(error), life: 5000 });
    } finally {
        importando.value = false;
    }
};

const loadSetores = async () => {
    loading.value = true;
    try {
        const { data } = await ApiService.listarUnidadesAdministrativas();
        setores.value = Array.isArray(data) ? data : data?.results || [];
    } catch (error) {
        setores.value = [];
        toast.add({ severity: 'error', summary: 'Setores', detail: extrairErro(error), life: 4000 });
    } finally {
        loading.value = false;
    }
};

const abrirNovo = () => {
    formNovo.value = { sinapse_orgao_id: null, nome: '', sigla: '' };
    dialogNovo.value = true;
};

const salvarNovo = async () => {
    salvando.value = true;
    try {
        await ApiService.criarUnidadeAdministrativa(formNovo.value);
        dialogNovo.value = false;
        toast.add({ severity: 'success', summary: 'Setor criado', life: 2500 });
        await loadSetores();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvando.value = false;
    }
};

const abrirResponsaveis = async (row) => {
    setorSelecionado.value = row;
    formResp.value = { usuario_id: null };
    try {
        const { data } = await ApiService.getUsuarios({ perfil: 'SECRETARIA' });
        const lista = data?.results || data || [];
        usuarios.value = lista
            .filter((u) => !row.sinapse_orgao_id || u.sinapse_orgao_id === row.sinapse_orgao_id)
            .map((u) => ({
                label: u.first_name ? `${u.first_name} ${u.last_name || ''}`.trim() : u.username,
                value: u.id
            }));
    } catch {
        usuarios.value = [];
    }
    dialogResp.value = true;
};

const vincularResponsavel = async () => {
    if (!setorSelecionado.value?.id || !formResp.value.usuario_id) return;
    salvando.value = true;
    try {
        await ApiService.vincularResponsavelSetor(setorSelecionado.value.id, {
            usuario_id: formResp.value.usuario_id
        });
        dialogResp.value = false;
        toast.add({ severity: 'success', summary: 'Responsável vinculado', life: 2500 });
        await loadSetores();
    } catch (error) {
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    } finally {
        salvando.value = false;
    }
};

const toggleAtivo = async (row) => {
    try {
        await ApiService.atualizarUnidadeAdministrativa(row.id, { ativo: row.ativo });
        toast.add({ severity: 'success', summary: 'Atualizado', life: 2000 });
    } catch (error) {
        row.ativo = !row.ativo;
        toast.add({ severity: 'error', summary: 'Erro', detail: extrairErro(error), life: 4000 });
    }
};

onMounted(async () => {
    if (podeGerir.value) {
        await loadOrgaos();
        await loadDepara();
    }
    await loadSetores();
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
                <h1 class="text-2xl font-semibold m-0">Setores (unidades administrativas)</h1>
                <p class="text-muted-color m-0 mt-1">
                    Cadastro de setores por órgão, responsáveis e base para tramitação operacional.
                </p>
            </div>
            <div class="flex flex-wrap gap-2">
                <Button
                    v-if="podeGerir"
                    label="Simular importação RM"
                    icon="pi pi-play"
                    severity="secondary"
                    outlined
                    :loading="importando"
                    @click="importarRm(true)"
                />
                <Button
                    v-if="podeGerir"
                    label="Importar RM271698"
                    icon="pi pi-upload"
                    :loading="importando"
                    @click="importarRm(false)"
                />
                <Button v-if="podeGerir" label="Novo setor" icon="pi pi-plus" @click="abrirNovo" />
            </div>
        </div>

        <Message v-if="!podeGerir" severity="info" :closable="false">
            Visualização dos setores do seu órgão. Encaminhamentos operacionais usam estes cadastros.
        </Message>

        <Card>
            <template #content>
                <DataTable
                    :value="setores"
                    :loading="loading"
                    stripedRows
                    paginator
                    :rows="15"
                    dataKey="id"
                    responsiveLayout="scroll"
                    class="sgdl-table-scroll"
                >
                    <Column field="sigla" header="Sigla" style="width: 6rem" />
                    <Column field="nome" header="Nome" />
                    <Column field="orgao_nome" header="Órgão" />
                    <Column header="Responsáveis">
                        <template #body="{ data }">
                            <Tag
                                v-for="r in (data.responsaveis || []).slice(0, 3)"
                                :key="r.id"
                                :value="r.usuario_nome"
                                class="mr-1 mb-1"
                                severity="secondary"
                            />
                            <span v-if="!(data.responsaveis || []).length" class="text-muted-color">—</span>
                        </template>
                    </Column>
                    <Column header="Ativo" style="width: 6rem">
                        <template #body="{ data }">
                            <ToggleSwitch v-if="podeGerir" v-model="data.ativo" @change="toggleAtivo(data)" />
                            <Tag v-else :value="data.ativo ? 'Sim' : 'Não'" :severity="data.ativo ? 'success' : 'danger'" />
                        </template>
                    </Column>
                    <Column v-if="podeGerir" header="Ações" style="width: 8rem">
                        <template #body="{ data }">
                            <Button
                                label="Resp."
                                size="small"
                                text
                                icon="pi pi-users"
                                @click="abrirResponsaveis(data)"
                            />
                        </template>
                    </Column>
                </DataTable>
            </template>
        </Card>

        <Card v-if="podeGerir">
            <template #title>De-para RM ↔ Sinapse</template>
            <template #content>
                <Message severity="info" :closable="false" class="text-sm mb-3">
                    Mapeie o código da secretaria na planilha RM (ex.: SMSBE) para o órgão Sinapse.
                    Unidades sem mapeamento ativo não entram na importação.
                </Message>
                <DataTable
                    :value="depara"
                    :loading="loadingDepara"
                    stripedRows
                    size="small"
                    paginator
                    :rows="15"
                    responsiveLayout="scroll"
                >
                    <Column field="cod_rm" header="COD_RM" />
                    <Column header="Órgão Sinapse">
                        <template #body="{ data }">
                            <Select
                                v-model="data.sinapse_orgao_id"
                                :options="orgaos"
                                optionLabel="label"
                                optionValue="value"
                                placeholder="Pendente"
                                showClear
                                filter
                                class="w-full"
                                @change="salvarDepara(data)"
                            />
                        </template>
                    </Column>
                    <Column field="orgao_nome" header="Nome Sinapse" />
                    <Column header="Ativo" style="width: 6rem">
                        <template #body="{ data }">
                            <ToggleSwitch v-model="data.ativo" @change="salvarDepara(data)" />
                        </template>
                    </Column>
                    <Column field="observacao" header="Obs." />
                </DataTable>
            </template>
        </Card>

        <Dialog v-model:visible="dialogNovo" header="Novo setor" modal style="width: 28rem">
            <div class="flex flex-col gap-3">
                <Select
                    v-model="formNovo.sinapse_orgao_id"
                    :options="orgaos"
                    optionLabel="label"
                    optionValue="value"
                    placeholder="Órgão"
                    filter
                />
                <InputText v-model="formNovo.nome" placeholder="Nome do setor" />
                <InputText v-model="formNovo.sigla" placeholder="Sigla (opcional)" maxlength="32" />
            </div>
            <template #footer>
                <Button label="Cancelar" text @click="dialogNovo = false" />
                <Button label="Salvar" :loading="salvando" @click="salvarNovo" />
            </template>
        </Dialog>

        <Dialog v-model:visible="dialogResp" header="Vincular responsável" modal style="width: 24rem">
            <p class="mt-0">{{ setorSelecionado?.nome }}</p>
            <Select
                v-model="formResp.usuario_id"
                :options="usuarios"
                optionLabel="label"
                optionValue="value"
                placeholder="Usuário (Secretaria)"
                filter
            />
            <template #footer>
                <Button label="Cancelar" text @click="dialogResp = false" />
                <Button label="Vincular" :loading="salvando" @click="vincularResponsavel" />
            </template>
        </Dialog>
    </div>
</template>
