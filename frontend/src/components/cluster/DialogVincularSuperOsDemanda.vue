<script setup>
import { ref, watch } from 'vue';
import ApiService from '@/service/ApiService';
import { formatarProtocoloLegislativo } from '@/utils/protocoloLegislativo';

import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import IconField from 'primevue/iconfield';
import InputIcon from 'primevue/inputicon';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import Tag from 'primevue/tag';

const props = defineProps({
    visible: { type: Boolean, default: false },
    demanda: { type: Object, default: null },
    vinculando: { type: Boolean, default: false }
});

const emit = defineEmits(['update:visible', 'vinculado', 'cancelar']);

const busca = ref('');
const carregando = ref(false);
const grupos = ref([]);
const selecionado = ref(null);
let debounceTimer = null;

const rotuloDemanda = () =>
    formatarProtocoloLegislativo(props.demanda?.protocolo_legislativo) ||
    props.demanda?.protocolo_executivo ||
    (props.demanda?.id ? `#${props.demanda.id}` : '');

const carregarGrupos = async (termo = '') => {
    if (!props.demanda?.id) return;
    carregando.value = true;
    try {
        const params = { limit: 20 };
        if (termo.trim()) params.q = termo.trim();
        const { data } = await ApiService.listarClustersVinculoDemanda(props.demanda.id, params);
        grupos.value = data?.results || [];
    } catch {
        grupos.value = [];
    } finally {
        carregando.value = false;
    }
};

const fechar = () => {
    emit('update:visible', false);
    emit('cancelar');
};

const confirmar = () => {
    if (!selecionado.value?.id) return;
    emit('vinculado', selecionado.value.id);
};

watch(
    () => props.visible,
    (aberto) => {
        if (aberto) {
            busca.value = '';
            selecionado.value = null;
            carregarGrupos('');
        }
    }
);

watch(busca, (valor) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => carregarGrupos(valor), 350);
});
</script>

<template>
    <Dialog
        :visible="visible"
        header="Vincular a Super OS existente"
        :modal="true"
        :closable="!vinculando"
        style="width: min(720px, 96vw)"
        @update:visible="(v) => !v && fechar()"
    >
        <div v-if="demanda" class="flex flex-col gap-4">
            <Message severity="info" :closable="false" class="m-0 text-sm">
                Este ofício não entrou automaticamente em um grupo. Selecione a Super OS ativa do
                <strong>mesmo serviço e mesma área</strong> para integrá-lo.
            </Message>

            <div class="text-sm">
                Ofício atual:
                <strong>{{ rotuloDemanda() }}</strong>
                <span class="text-muted-color"> — {{ demanda.titulo }}</span>
            </div>

            <IconField>
                <InputIcon class="pi pi-search" />
                <InputText
                    v-model="busca"
                    placeholder="Buscar grupo por tema, bairro ou número..."
                    fluid
                />
            </IconField>

            <DataTable
                v-model:selection="selecionado"
                :value="grupos"
                :loading="carregando"
                selectionMode="single"
                dataKey="id"
                size="small"
                stripedRows
                scrollable
                scrollHeight="280px"
                :metaKeySelection="false"
                emptyMessage="Nenhum grupo compatível encontrado. Abra Super Ordens para revisar outros grupos."
            >
                <Column selectionMode="single" headerStyle="width: 3rem" />
                <Column header="Grupo" style="min-width: 10rem">
                    <template #body="{ data }">
                        <div class="font-medium">{{ data.titulo }}</div>
                        <div v-if="data.servico_nome" class="text-xs text-primary">{{ data.servico_nome }}</div>
                    </template>
                </Column>
                <Column header="Local" style="min-width: 6rem">
                    <template #body="{ data }">
                        <span class="text-xs">{{ data.bairro_referencia || '—' }}</span>
                    </template>
                </Column>
                <Column header="Processos" style="width: 5rem">
                    <template #body="{ data }">{{ data.demandas_count ?? '—' }}</template>
                </Column>
                <Column header="Super OS" style="min-width: 7rem">
                    <template #body="{ data }">
                        <Tag
                            v-if="data.protocolo_super_os"
                            :value="data.protocolo_super_os"
                            severity="secondary"
                            class="text-xs"
                        />
                        <span v-else class="text-xs text-muted-color">Aguardando despacho</span>
                    </template>
                </Column>
            </DataTable>
        </div>

        <template #footer>
            <Button label="Cancelar" icon="pi pi-times" text :disabled="vinculando" @click="fechar" />
            <Button
                label="Vincular ao grupo"
                icon="pi pi-link"
                :loading="vinculando"
                :disabled="!selecionado?.id"
                @click="confirmar"
            />
        </template>
    </Dialog>
</template>
