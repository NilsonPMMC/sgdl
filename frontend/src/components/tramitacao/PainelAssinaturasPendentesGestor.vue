<script setup>
import Button from 'primevue/button';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Tag from 'primevue/tag';
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import DialogAssinaturaEletronica from '@/components/tramitacao/DialogAssinaturaEletronica.vue';
import ApiService from '@/service/ApiService';
import {
    DECLARACAO_GESTOR_PROTOCOLO,
    DECLARACAO_GESTOR_SETOR,
    MODO_PAINEL_ASSINATURA,
    rotuloEtapaAssinatura
} from '@/constants/assinaturaEletronica';
import { useToast } from 'primevue/usetoast';

const props = defineProps({
    autoAbrirValidacaoId: { type: [Number, String], default: null }
});

const router = useRouter();
const toast = useToast();

const carregando = ref(false);
const pendentes = ref([]);
const dialogVisible = ref(false);
const preview = ref(null);
const validacaoAtual = ref(null);
const assinando = ref(false);
const carregandoPreview = ref(false);

async function carregarPendentes() {
    carregando.value = true;
    try {
        const { data } = await ApiService.listarAssinaturasValidacaoPendentes();
        pendentes.value = data?.results || [];
    } catch (e) {
        console.error(e);
        pendentes.value = [];
    } finally {
        carregando.value = false;
    }
}

async function abrirValidacao(item) {
    validacaoAtual.value = item;
    dialogVisible.value = true;
    preview.value = null;
    await gerarPreviewValidacao();
}

async function gerarPreviewValidacao() {
    if (!validacaoAtual.value?.id) return;
    carregandoPreview.value = true;
    try {
        const { data } = await ApiService.previewValidacaoAssinaturaGestor(validacaoAtual.value.id);
        preview.value = data;
    } catch (e) {
        toast.add({
            severity: 'error',
            summary: 'Prévia indisponível',
            detail: e.response?.data?.detail || 'Não foi possível carregar a prévia.',
            life: 5000
        });
        dialogVisible.value = false;
    } finally {
        carregandoPreview.value = false;
    }
}

async function confirmarValidacao(payload) {
    if (!validacaoAtual.value?.id) return;
    assinando.value = true;
    try {
        await ApiService.validarAssinaturaGestor(validacaoAtual.value.id, payload);
        toast.add({
            severity: 'success',
            summary: 'Assinatura validada',
            detail: 'A assinatura foi registrada com sucesso.',
            life: 4000
        });
        dialogVisible.value = false;
        validacaoAtual.value = null;
        preview.value = null;
        await carregarPendentes();
    } catch (e) {
        toast.add({
            severity: 'error',
            summary: 'Falha na validação',
            detail: e.response?.data?.detail || 'Não foi possível registrar a assinatura.',
            life: 6000
        });
    } finally {
        assinando.value = false;
    }
}

function irParaDemanda(item) {
    router.push(`/demandas/detalhes/${item.demanda_id}?validacao_assinatura=${item.id}`);
}

function declaracaoGestorAtual() {
    if (validacaoAtual.value?.tipo_gestor === 'SETOR') return DECLARACAO_GESTOR_SETOR;
    return validacaoAtual.value?.declaracao_gestor || DECLARACAO_GESTOR_PROTOCOLO;
}

onMounted(async () => {
    await carregarPendentes();
    if (props.autoAbrirValidacaoId) {
        const item = pendentes.value.find(
            (p) => String(p.id) === String(props.autoAbrirValidacaoId)
        );
        if (item) {
            await abrirValidacao(item);
        }
    }
});

defineExpose({ carregarPendentes, abrirValidacao });
</script>

<template>
    <div class="flex flex-col gap-3">
        <div class="flex items-center justify-between gap-2 flex-wrap">
            <p class="m-0 text-sm text-muted-color">
                Despachos e conclusões aguardando sua assinatura como gestor.
            </p>
            <Button
                icon="pi pi-refresh"
                label="Atualizar"
                severity="secondary"
                text
                :loading="carregando"
                @click="carregarPendentes"
            />
        </div>

        <DataTable
            :value="pendentes"
            :loading="carregando"
            size="small"
            striped-rows
            :rows="10"
            paginator
            empty-message="Nenhuma assinatura pendente de validação."
        >
            <Column field="protocolo_executivo" header="Protocolo" style="min-width: 8rem">
                <template #body="{ data }">
                    {{ data.protocolo_executivo || data.protocolo_legislativo || `#${data.demanda_id}` }}
                </template>
            </Column>
            <Column header="Etapa" style="min-width: 12rem">
                <template #body="{ data }">
                    <Tag severity="warn" :value="rotuloEtapaAssinatura(data.etapa)" />
                </template>
            </Column>
            <Column header="Solicitante" style="min-width: 10rem">
                <template #body="{ data }">
                    {{ data.operador?.nome || '—' }}
                </template>
            </Column>
            <Column header="Ações" style="width: 10rem">
                <template #body="{ data }">
                    <div class="flex gap-1">
                        <Button
                            icon="pi pi-check"
                            label="Validar"
                            size="small"
                            @click="abrirValidacao(data)"
                        />
                        <Button
                            icon="pi pi-external-link"
                            size="small"
                            severity="secondary"
                            text
                            @click="irParaDemanda(data)"
                        />
                    </div>
                </template>
            </Column>
        </DataTable>

        <DialogAssinaturaEletronica
            v-model:visible="dialogVisible"
            titulo="Validar assinatura (gestor)"
            :preview="preview"
            :modo="MODO_PAINEL_ASSINATURA.GESTOR_APENAS"
            :declaracao-gestor-texto="declaracaoGestorAtual()"
            label-confirmar="Assinar e validar"
            :loading="assinando"
            :loading-preview="carregandoPreview"
            mensagem-intro="Revise o conteúdo assinado pelo operador e confirme sua assinatura como gestor."
            @confirmar="confirmarValidacao"
            @gerar-preview="gerarPreviewValidacao"
        />
    </div>
</template>
