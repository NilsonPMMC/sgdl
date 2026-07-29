<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import ApiService from '@/service/ApiService';
import MultiSelect from 'primevue/multiselect';
import Select from 'primevue/select';
import InputNumber from 'primevue/inputnumber';
import Tag from 'primevue/tag';
import Message from 'primevue/message';

const props = defineProps({
    sessionId: { type: String, default: null },
    indiceDemanda: { type: Number, required: true },
    demanda: { type: Object, default: () => ({}) }
});

const emit = defineEmits(['atualizado']);

const vereadores = ref([]);
const numeracao = ref(null);
const salvando = ref(false);

const vereadoresIds = ref([]);
const autorVereadorId = ref(null);
const numeroIndicacao = ref(null);
/** Evita persistir ao hidratar do rascunho (só salva quando o usuário altera). */
const ignorarPersistencia = ref(false);
let debouncePersistir = null;

const vereadoresOpcoes = computed(() =>
    vereadores.value.map((v) => ({
        label: v.first_name || v.username,
        value: v.id
    }))
);

const autorVereadorOpcoes = computed(() =>
    vereadoresIds.value.map((id) => {
        const v = vereadores.value.find((x) => x.id === id);
        return { label: v?.first_name || v?.username || `#${id}`, value: id };
    })
);

function sincronizarDoRascunho() {
    ignorarPersistencia.value = true;
    const d = props.demanda || {};
    vereadoresIds.value = Array.isArray(d.vereadores_vinculados_ids)
        ? [...d.vereadores_vinculados_ids]
        : [];
    autorVereadorId.value = d.autor_vereador_id ?? vereadoresIds.value[0] ?? null;
    numeroIndicacao.value = d.numero_indicacao ?? numeracao.value?.proximo_numero ?? null;
    nextTick(() => {
        ignorarPersistencia.value = false;
    });
}

async function carregarBase() {
    try {
        const [respVer, respNum] = await Promise.all([
            ApiService.getUsuarios({ perfil: 'VEREADOR' }),
            ApiService.getNumeracaoIndicacao()
        ]);
        vereadores.value = respVer.data?.results || respVer.data || [];
        numeracao.value = respNum.data;
    } catch {
        vereadores.value = [];
        numeracao.value = null;
    }
    sincronizarDoRascunho();
}

const camposDesabilitados = computed(() => salvando.value || !props.sessionId);

async function persistir() {
    if (!props.sessionId || salvando.value || ignorarPersistencia.value) return;
    salvando.value = true;
    try {
        const { data } = await ApiService.atualizarIndicacaoCopiloto({
            session_id: props.sessionId,
            indice_demanda: props.indiceDemanda,
            vereadores_vinculados_ids: vereadoresIds.value,
            autor_vereador_id: autorVereadorId.value,
            numero_indicacao: numeroIndicacao.value
        });
        emit('atualizado', data);
    } catch {
        // falha silenciosa — usuário pode tentar de novo ao alterar o campo
    } finally {
        salvando.value = false;
    }
}

function agendarPersistir() {
    if (ignorarPersistencia.value) return;
    if (debouncePersistir) clearTimeout(debouncePersistir);
    debouncePersistir = setTimeout(() => {
        debouncePersistir = null;
        persistir();
    }, 350);
}

watch(
    () => props.demanda,
    () => sincronizarDoRascunho(),
    { deep: true }
);

watch([vereadoresIds, autorVereadorId, numeroIndicacao], () => {
    if (ignorarPersistencia.value) return;
    if (vereadoresIds.value.length && !vereadoresIds.value.includes(autorVereadorId.value)) {
        ignorarPersistencia.value = true;
        autorVereadorId.value = vereadoresIds.value[0];
        nextTick(() => {
            ignorarPersistencia.value = false;
        });
    }
    agendarPersistir();
});

watch(
    () => props.sessionId,
    (id) => {
        if (id && numeroIndicacao.value != null) {
            agendarPersistir();
        }
    }
);

onMounted(carregarBase);
</script>

<template>
    <div
        class="flex flex-col gap-3 rounded-xl border border-[var(--primary-color)]/25 bg-[var(--surface-ground)] p-3"
    >
        <p class="m-0 text-xs font-semibold uppercase tracking-wide text-[var(--primary-color)]">
            Indicação — Câmara Municipal
        </p>
        <Message v-if="!sessionId" severity="info" :closable="false" class="text-xs">
            Aguarde o copiloto concluir a análise para editar vereadores e número.
        </Message>
        <div v-if="numeracao" class="flex flex-wrap items-center gap-2 text-xs text-[var(--text-color-secondary)]">
            <span>Sugestão:</span>
            <Tag severity="info" :value="numeracao.protocolo_sugerido" />
            <span>Último: {{ numeracao.ultimo_numero }}/{{ numeracao.ano }}</span>
        </div>
        <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Vereadores vinculados</label>
            <MultiSelect
                v-model="vereadoresIds"
                :options="vereadoresOpcoes"
                option-label="label"
                option-value="value"
                placeholder="Selecione"
                display="chip"
                class="w-full"
                :disabled="camposDesabilitados"
            />
        </div>
        <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Autor (vereador)</label>
            <Select
                v-model="autorVereadorId"
                :options="autorVereadorOpcoes"
                option-label="label"
                option-value="value"
                placeholder="Autor da indicação"
                class="w-full"
                :disabled="camposDesabilitados || !vereadoresIds.length"
            />
        </div>
        <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Número (parte numérica)</label>
            <InputNumber v-model="numeroIndicacao" :min="1" fluid :disabled="camposDesabilitados" />
        </div>
        <p v-if="salvando" class="m-0 text-xs text-[var(--text-color-secondary)]">
            Salvando…
        </p>
    </div>
</template>
