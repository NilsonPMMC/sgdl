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
    cluster: { type: Object, default: null },
    vinculando: { type: Boolean, default: false }
});

const emit = defineEmits(['update:visible', 'vincular', 'cancelar']);

const busca = ref('');
const carregando = ref(false);
const candidatas = ref([]);
const selecionada = ref(null);
const servicoNome = ref('');
let debounceTimer = null;

const rotuloDemanda = (item) =>
    formatarProtocoloLegislativo(item?.protocolo_legislativo) ||
    item?.protocolo_executivo ||
    `#${item?.id}`;

const carregarCandidatas = async (termo = '') => {
    if (!props.cluster?.id) return;
    carregando.value = true;
    try {
        const params = { limit: 20 };
        if (termo.trim()) params.q = termo.trim();
        const { data } = await ApiService.listarDemandasCandidatasCluster(props.cluster.id, params);
        candidatas.value = data?.results || [];
        servicoNome.value = data?.servico_nome || props.cluster?.servico_nome || '';
    } catch {
        candidatas.value = [];
    } finally {
        carregando.value = false;
    }
};

const fechar = () => {
    emit('update:visible', false);
    emit('cancelar');
};

const confirmar = () => {
    if (!selecionada.value?.id || !selecionada.value?.compativel) return;
    emit('vincular', selecionada.value.id);
};

watch(
    () => props.visible,
    (aberto) => {
        if (aberto) {
            busca.value = '';
            selecionada.value = null;
            carregarCandidatas('');
        }
    }
);

watch(busca, (valor) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => carregarCandidatas(valor), 350);
});
</script>

<template>
    <Dialog
        :visible="visible"
        header="Vincular ofício ao grupo Super OS"
        :modal="true"
        :closable="!vinculando"
        style="width: min(720px, 96vw)"
        @update:visible="(v) => !v && fechar()"
    >
        <div v-if="cluster" class="flex flex-col gap-4">
            <Message severity="info" :closable="false" class="m-0 text-sm">
                Use esta ferramenta quando o sistema <strong>não agrupou automaticamente</strong> um ofício que
                pertence ao mesmo problema. O ofício deve ser do serviço
                <strong>{{ servicoNome || 'deste grupo' }}</strong> e na mesma área (bairro ou ~300 m).
            </Message>

            <div class="text-sm">
                Grupo selecionado: <strong>{{ cluster.titulo }}</strong>
                <span v-if="cluster.bairro_referencia" class="text-muted-color">
                    — {{ cluster.bairro_referencia }}
                </span>
            </div>

            <IconField>
                <InputIcon class="pi pi-search" />
                <InputText
                    v-model="busca"
                    placeholder="Buscar por ofício, título, vereador, bairro ou logradouro..."
                    fluid
                />
            </IconField>

            <DataTable
                v-model:selection="selecionada"
                :value="candidatas"
                :loading="carregando"
                selectionMode="single"
                dataKey="id"
                size="small"
                stripedRows
                scrollable
                scrollHeight="280px"
                :metaKeySelection="false"
                emptyMessage="Nenhum ofício encontrado. Tente outro termo ou verifique se aguarda protocolo."
            >
                <Column selectionMode="single" headerStyle="width: 3rem" />
                <Column header="Ofício" style="min-width: 8rem">
                    <template #body="{ data }">
                        <div class="font-medium">{{ rotuloDemanda(data) }}</div>
                        <div class="text-xs text-muted-color line-clamp-2">{{ data.titulo }}</div>
                    </template>
                </Column>
                <Column header="Vereador" style="min-width: 7rem">
                    <template #body="{ data }">
                        <span class="text-xs">{{ data.autor_nome || '—' }}</span>
                    </template>
                </Column>
                <Column header="Local" style="min-width: 7rem">
                    <template #body="{ data }">
                        <span class="text-xs">{{ data.bairro || data.logradouro || '—' }}</span>
                    </template>
                </Column>
                <Column header="Situação" style="min-width: 9rem">
                    <template #body="{ data }">
                        <Tag
                            v-if="data.compativel"
                            value="Pode vincular"
                            severity="success"
                            class="text-xs"
                        />
                        <span v-else class="text-xs text-orange-600" v-tooltip.top="data.motivo">
                            {{ data.motivo }}
                        </span>
                    </template>
                </Column>
            </DataTable>

            <p v-if="selecionada && !selecionada.compativel" class="m-0 text-xs text-orange-600">
                Este ofício não atende aos critérios do grupo. Escolha um item marcado como «Pode vincular».
            </p>
        </div>

        <template #footer>
            <Button label="Cancelar" icon="pi pi-times" text :disabled="vinculando" @click="fechar" />
            <Button
                label="Vincular ao grupo"
                icon="pi pi-link"
                :loading="vinculando"
                :disabled="!selecionada?.compativel"
                @click="confirmar"
            />
        </template>
    </Dialog>
</template>
