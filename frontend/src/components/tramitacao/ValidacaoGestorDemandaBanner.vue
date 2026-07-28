<script setup>
import Button from 'primevue/button';
import Message from 'primevue/message';
import Tag from 'primevue/tag';
import { computed, onMounted, ref, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService';
import DialogAssinaturaEletronica from '@/components/tramitacao/DialogAssinaturaEletronica.vue';
import {
    DECLARACAO_GESTOR_PROTOCOLO,
    DECLARACAO_GESTOR_SETOR,
    MODO_PAINEL_ASSINATURA,
    demandaComValidacaoGestorPendente,
    pendenciaGestorSecretaria,
    rotuloEtapaAssinatura,
    rotuloValidacaoGestorPendente,
    usuarioDeveVerBannerValidacaoGestor,
    usuarioEhGestorProtocoloSgac,
    usuarioEhGestorSetorialOperacional,
    usuarioEhSecretaria,
    usuarioPodeValidarGestorNaDemanda
} from '@/constants/assinaturaEletronica';

const props = defineProps({
    demandaId: { type: [Number, String], required: true },
    assinaturasResumo: { type: Object, default: () => ({}) },
    autoAbrirValidacaoId: { type: [Number, String], default: null }
});

const emit = defineEmits(['validated']);

const userStore = useUserStore();
const toast = useToast();

const rotulo = computed(() => rotuloValidacaoGestorPendente(props.assinaturasResumo));
const ehGestorSgac = computed(() => usuarioEhGestorProtocoloSgac(userStore.currentUser, userStore));
const ehGestorSetorial = computed(() =>
    usuarioEhGestorSetorialOperacional(userStore.currentUser, userStore)
);
const ehSecretaria = computed(() => usuarioEhSecretaria(userStore.currentUser));
const ehProtocolo = computed(() => userStore.currentUser?.perfil === 'PROTOCOLO');
const ehGestorValidador = computed(() =>
    usuarioPodeValidarGestorNaDemanda(userStore.currentUser, userStore)
);
const pendenciaSecretaria = computed(() => pendenciaGestorSecretaria(props.assinaturasResumo));
const exibir = computed(() =>
    usuarioDeveVerBannerValidacaoGestor(
        props.assinaturasResumo,
        userStore.currentUser,
        userStore
    )
);

const validacao = ref(null);
const dialogVisible = ref(false);
const preview = ref(null);
const assinando = ref(false);
const carregandoPreview = ref(false);

async function carregarValidacao() {
    if (!ehGestorValidador.value) {
        validacao.value = null;
        return;
    }
    try {
        const { data } = await ApiService.listarAssinaturasValidacaoPendentes();
        validacao.value =
            (data?.results || []).find(
                (v) => Number(v.demanda_id) === Number(props.demandaId)
            ) || null;
    } catch {
        validacao.value = null;
    }
}

async function gerarPreview() {
    if (!validacao.value?.id) return;
    carregandoPreview.value = true;
    try {
        const { data } = await ApiService.previewValidacaoAssinaturaGestor(validacao.value.id);
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

async function abrirValidacao() {
    if (!validacao.value) {
        await carregarValidacao();
    }
    if (!validacao.value) {
        toast.add({
            severity: 'warn',
            summary: 'Validação',
            detail: 'Nenhuma pendência de assinatura encontrada para esta demanda.',
            life: 4000
        });
        return;
    }
    dialogVisible.value = true;
    preview.value = null;
    await gerarPreview();
}

async function confirmarValidacao(payload) {
    if (!validacao.value?.id) return;
    assinando.value = true;
    try {
        await ApiService.validarAssinaturaGestor(validacao.value.id, payload);
        toast.add({
            severity: 'success',
            summary: 'Assinatura validada',
            detail: 'A operação será concluída após o registro da sua assinatura.',
            life: 5000
        });
        dialogVisible.value = false;
        validacao.value = null;
        preview.value = null;
        emit('validated');
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

function declaracaoGestorAtual() {
    if (validacao.value?.tipo_gestor === 'SETOR') return DECLARACAO_GESTOR_SETOR;
    return validacao.value?.declaracao_gestor || DECLARACAO_GESTOR_PROTOCOLO;
}

watch(
    () => props.demandaId,
    () => {
        carregarValidacao();
    }
);

watch(
    () => props.assinaturasResumo,
    (resumo) => {
        if (demandaComValidacaoGestorPendente(resumo) && ehGestorValidador.value) {
            carregarValidacao();
        }
    },
    { deep: true }
);

watch(
    () => props.autoAbrirValidacaoId,
    async (id) => {
        if (!id || !ehGestorValidador.value) return;
        await carregarValidacao();
        const item = validacao.value;
        if (item && String(item.id) === String(id)) {
            await abrirValidacao();
        }
    }
);

onMounted(async () => {
    if (ehGestorValidador.value) {
        await carregarValidacao();
    }
    if (props.autoAbrirValidacaoId) {
        const item = validacao.value;
        if (item && String(item.id) === String(props.autoAbrirValidacaoId)) {
            await abrirValidacao();
        }
    }
});

defineExpose({ recarregar: carregarValidacao, abrirValidacao });
</script>

<template>
    <Message v-if="exibir" severity="warn" :closable="false" class="mb-4">
        <div class="flex flex-col gap-3">
            <p class="m-0">
                <strong>Validação do gestor pendente.</strong>
                {{ rotulo }}.
            </p>
            <p v-if="ehProtocolo" class="m-0 text-sm">
                Você já assinou como operador. O despacho ou a conclusão
                <strong>só será executado</strong> após o gestor validar em Assinaturas pendentes.
                Formulários de tramitação e despacho ficam bloqueados até lá.
            </p>
            <p v-else-if="ehSecretaria && pendenciaSecretaria" class="m-0 text-sm">
                A secretaria já assinou a operação. Ela
                <strong>só será concluída</strong> após o gestor do setor validar.
                Formulários de tramitação e scatter-gather ficam bloqueados até lá.
            </p>
            <p v-else-if="ehGestorSgac" class="m-0 text-sm">
                O operador já assinou. Revise o conteúdo e registre sua assinatura como gestor
                para concluir a operação.
            </p>
            <p v-else-if="ehGestorSetorial && pendenciaSecretaria" class="m-0 text-sm">
                A secretaria já assinou a operação. Revise o conteúdo e registre
                sua assinatura como gestor do setor para concluir o encerramento/despacho.
            </p>
            <div v-if="ehGestorValidador && validacao" class="flex flex-wrap items-center gap-2">
                <Tag
                    :value="rotuloEtapaAssinatura(validacao.etapa)"
                    severity="warn"
                />
                <Button
                    label="Validar assinatura (gestor)"
                    icon="pi pi-verified"
                    size="small"
                    @click="abrirValidacao"
                />
            </div>
            <p v-else-if="ehGestorValidador && !validacao" class="m-0 text-sm text-muted-color">
                Carregando pendências… ou acesse
                <router-link to="/assinaturas-pendentes" class="text-primary">Assinaturas pendentes</router-link>.
            </p>
        </div>
    </Message>

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
        @gerar-preview="gerarPreview"
    />
</template>
