<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import Message from 'primevue/message';
import { useToast } from 'primevue/usetoast';
import ApiService from '@/service/ApiService.js';
import DescricaoTramitacaoEditor from '@/components/tramitacao/DescricaoTramitacaoEditor.vue';

const props = defineProps({
    tramitacaoId: { type: [Number, String], required: true },
    descricaoAtual: { type: String, default: '' },
    podeEditar: { type: Boolean, default: false },
    segundosRestantes: { type: Number, default: 0 },
    aguardandoValidacaoGestor: { type: Boolean, default: false },
    contexto: { type: String, default: 'andamento' }
});

const emit = defineEmits(['atualizado']);

const toast = useToast();
const segundosLocal = ref(Math.max(0, Number(props.segundosRestantes) || 0));
const dialogVisible = ref(false);
const dialogExpandido = ref(false);
const descricaoEdicao = ref('');
const salvando = ref(false);
const excluindo = ref(false);
const confirmarExclusao = ref(false);

let timer = null;

const timerPausado = computed(
    () => dialogVisible.value || confirmarExclusao.value || salvando.value || excluindo.value
);

const aguardandoGestor = computed(() => Boolean(props.aguardandoValidacaoGestor));

const editorStyle = computed(() =>
    dialogExpandido.value ? 'min-height: 55vh' : 'min-height: 220px'
);

function iniciarTimer() {
    pararTimer();
    if (!props.podeEditar || segundosLocal.value <= 0 || timerPausado.value) {
        return;
    }
    timer = window.setInterval(() => {
        if (segundosLocal.value <= 1) {
            segundosLocal.value = 0;
            pararTimer();
            return;
        }
        segundosLocal.value -= 1;
    }, 1000);
}

function pararTimer() {
    if (timer) {
        window.clearInterval(timer);
        timer = null;
    }
}

watch(
    () => [props.podeEditar, props.segundosRestantes],
    ([pode, seg]) => {
        segundosLocal.value = Math.max(0, Number(seg) || 0);
        if (pode && segundosLocal.value > 0 && !timerPausado.value) {
            iniciarTimer();
        } else {
            pararTimer();
        }
    },
    { immediate: true }
);

watch(timerPausado, (pausado) => {
    if (pausado) pararTimer();
    else if (props.podeEditar && segundosLocal.value > 0) iniciarTimer();
});

onBeforeUnmount(pararTimer);

const mensagemAguardandoGestor = computed(() => {
    const ctx = String(props.contexto || '').toLowerCase();
    if (ctx.includes('conclusao') || ctx.includes('final')) {
        return 'Conclusão final aguardando validação do gestor.';
    }
    return 'Despacho aguardando validação do gestor.';
});

const visivel = computed(() => props.podeEditar && segundosLocal.value > 0);

function textoTemConteudo(html) {
    return (html || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/gi, ' ').trim().length > 0;
}

function abrirEdicao() {
    pararTimer();
    descricaoEdicao.value = props.descricaoAtual || '';
    dialogExpandido.value = false;
    dialogVisible.value = true;
}

function fecharEdicao() {
    dialogVisible.value = false;
    dialogExpandido.value = false;
    if (props.podeEditar && segundosLocal.value > 0) {
        iniciarTimer();
    }
}

async function salvarEdicao() {
    if (!textoTemConteudo(descricaoEdicao.value)) {
        toast.add({
            severity: 'warn',
            summary: 'Descrição obrigatória',
            detail: 'Informe o texto corrigido.',
            life: 4000
        });
        return;
    }
    salvando.value = true;
    try {
        const resp = await ApiService.atualizarTramitacao(props.tramitacaoId, {
            descricao: descricaoEdicao.value
        });
        fecharEdicao();
        const dados = resp?.data || {};
        if (dados.segundos_restantes_edicao != null) {
            segundosLocal.value = Math.max(0, Number(dados.segundos_restantes_edicao) || 0);
            if (props.podeEditar && segundosLocal.value > 0 && !timerPausado.value) {
                iniciarTimer();
            }
        }
        toast.add({
            severity: 'success',
            summary: 'Andamento corrigido',
            detail: 'O texto foi atualizado na timeline.',
            life: 3500
        });
        emit('atualizado', dados);
    } catch (err) {
        const detail =
            err?.response?.data?.detail || 'Não foi possível corrigir o andamento.';
        toast.add({ severity: 'error', summary: 'Erro', detail, life: 5000 });
    } finally {
        salvando.value = false;
    }
}

async function confirmarDesfazer() {
    excluindo.value = true;
    try {
        await ApiService.excluirTramitacao(props.tramitacaoId);
        confirmarExclusao.value = false;
        toast.add({
            severity: 'success',
            summary: 'Andamento desfeito',
            detail: 'O registro foi removido da timeline e do fluxo operacional.',
            life: 3500
        });
        emit('atualizado');
    } catch (err) {
        const detail =
            err?.response?.data?.detail || 'Não foi possível desfazer o andamento.';
        toast.add({ severity: 'error', summary: 'Erro', detail, life: 5000 });
    } finally {
        excluindo.value = false;
    }
}
</script>

<template>
    <div v-if="visivel" class="tramitacao-janela-correcao mt-3 pt-3 border-top-1 surface-border">
        <Message severity="info" :closable="false" class="m-0 mb-2 text-sm">
            <template v-if="timerPausado">
                Contador pausado — conclua a correção ou cancele para retomar a contagem.
            </template>
            <template v-else-if="aguardandoGestor">
                {{ mensagemAguardandoGestor }}
                Você tem <strong>{{ segundosLocal }}s</strong> para corrigir ou desfazer antes da
                aprovação.
            </template>
            <template v-else>
                Você tem <strong>{{ segundosLocal }}s</strong> para corrigir ou desfazer este andamento.
            </template>
        </Message>
        <div class="flex flex-wrap gap-2">
            <Button
                label="Corrigir texto"
                icon="pi pi-pencil"
                size="small"
                outlined
                @click="abrirEdicao"
            />
            <Button
                label="Desfazer"
                icon="pi pi-undo"
                size="small"
                severity="danger"
                outlined
                @click="confirmarExclusao = true"
            />
        </div>

        <Dialog
            v-model:visible="dialogVisible"
            header="Corrigir andamento"
            modal
            maximizable
            :style="dialogExpandido ? { width: '96vw' } : { width: 'min(720px, 96vw)' }"
            @maximize="dialogExpandido = true"
            @unmaximize="dialogExpandido = false"
            @hide="dialogExpandido = false"
        >
            <DescricaoTramitacaoEditor
                v-model="descricaoEdicao"
                label="Descrição corrigida"
                :contexto="contexto"
                :editor-style="editorStyle"
            />
            <template #footer>
                <Button label="Cancelar" text @click="fecharEdicao" />
                <Button
                    label="Salvar correção"
                    icon="pi pi-check"
                    :loading="salvando"
                    @click="salvarEdicao"
                />
            </template>
        </Dialog>

        <Dialog
            v-model:visible="confirmarExclusao"
            header="Desfazer andamento"
            modal
            :style="{ width: 'min(480px, 95vw)' }"
        >
            <p class="m-0 text-sm">
                O registro será removido da timeline e do painel operacional (nós scatter, se
                aplicável). Encaminhamentos de setor já aplicados em outras demandas não serão
                revertidos automaticamente.
            </p>
            <template #footer>
                <Button label="Cancelar" text @click="confirmarExclusao = false" />
                <Button
                    label="Confirmar desfazer"
                    icon="pi pi-trash"
                    severity="danger"
                    :loading="excluindo"
                    @click="confirmarDesfazer"
                />
            </template>
        </Dialog>
    </div>
</template>
