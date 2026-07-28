<script setup>
import { computed, inject, onMounted, onUnmounted, provide, ref, watch } from 'vue';
import Tag from 'primevue/tag';
import {
    STATUS_NO_ABERTO,
    calcularTemposNo,
    formatarDuracaoSegundos,
    rotuloStatusNo,
    severidadeTempoNo,
    severityStatusNo
} from '@/constants/scatterGather';

const props = defineProps({
    nos: { type: Array, default: () => [] },
    nivel: { type: Number, default: 0 },
    /** Persiste scroll horizontal (sessionStorage) — informe o id da demanda na raiz. */
    scrollKey: { type: [Number, String], default: null }
});

const scrollViewport = ref(null);
const chaveScroll = computed(() =>
    props.nivel === 0 && props.scrollKey != null && props.scrollKey !== ''
        ? `sgdl:scatter-flow-scroll:${props.scrollKey}`
        : null
);

function restaurarScroll() {
    if (!scrollViewport.value || !chaveScroll.value) return;
    try {
        const raw = sessionStorage.getItem(chaveScroll.value);
        if (raw == null) return;
        const left = Number(raw);
        if (!Number.isNaN(left)) scrollViewport.value.scrollLeft = left;
    } catch {
        /* ignore */
    }
}

function salvarScroll() {
    if (!scrollViewport.value || !chaveScroll.value) return;
    try {
        sessionStorage.setItem(chaveScroll.value, String(scrollViewport.value.scrollLeft));
    } catch {
        /* ignore */
    }
}

let salvarScrollTimer = null;
function onScrollViewport() {
    if (salvarScrollTimer) clearTimeout(salvarScrollTimer);
    salvarScrollTimer = setTimeout(salvarScroll, 120);
}

const agoraLocal = ref(Date.now());
const agoraInjected = inject('scatterFlowClock', null);

if (props.nivel === 0) {
    provide('scatterFlowClock', agoraLocal);
}

let timer = null;
onMounted(() => {
    if (props.nivel !== 0) return;
    timer = setInterval(() => {
        agoraLocal.value = Date.now();
    }, 30000);
    restaurarScroll();
});
onUnmounted(() => {
    if (timer) clearInterval(timer);
    if (salvarScrollTimer) clearTimeout(salvarScrollTimer);
    salvarScroll();
});

watch(
    () => props.scrollKey,
    () => {
        if (props.nivel === 0) restaurarScroll();
    }
);

const agoraMs = computed(() => (agoraInjected ?? agoraLocal).value);

const formatarDataHora = (iso) => {
    if (!iso) return '';
    return new Date(iso).toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

const temposNo = (no) => calcularTemposNo(no, agoraMs.value);

const rotuloOrgSetor = (no) => {
    const org = no.orgao_nome || (no.orgao_id ? `Órgão #${no.orgao_id}` : 'Órgão');
    return no.setor_nome ? `${org} › ${no.setor_nome}` : org;
};

const classeCard = (no) => ({
    'scatter-flow-card--aberto': no.status === STATUS_NO_ABERTO,
    'scatter-flow-card--concluido': no.status === 'CONCLUIDO'
});
</script>

<template>
    <div
        ref="scrollViewport"
        class="scatter-flowchart"
        :class="nivel === 0 ? 'scatter-flowchart--root' : ''"
        @scroll.passive="nivel === 0 ? onScrollViewport() : undefined"
    >
        <div :class="nivel === 0 ? 'scatter-flow-roots' : 'scatter-flow-siblings'">
            <div
                v-for="no in nos"
                :key="no.id"
                class="scatter-flow-node"
            >
                <div
                    class="scatter-flow-card"
                    :class="classeCard(no)"
                >
                    <div class="scatter-flow-card__header">
                        <Tag
                            :value="rotuloStatusNo(no.status)"
                            :severity="severityStatusNo(no.status)"
                            class="text-xs"
                        />
                        <span v-if="no.origem_label" class="scatter-flow-card__origem">
                            {{ no.origem_label }}
                        </span>
                    </div>

                    <div class="scatter-flow-card__titulo">
                        {{ rotuloOrgSetor(no) }}
                    </div>

                    <div v-if="no.abridor_nome" class="scatter-flow-card__meta">
                        <i class="pi pi-user text-xs" />
                        {{ no.abridor_nome }}
                    </div>

                    <div class="scatter-flow-card__datas">
                        <span v-if="no.aberto_em" title="Aberto em">
                            <i class="pi pi-sign-in text-xs" />
                            {{ formatarDataHora(no.aberto_em) }}
                        </span>
                        <span v-if="no.concluido_em" title="Concluído em">
                            <i class="pi pi-check text-xs" />
                            {{ formatarDataHora(no.concluido_em) }}
                        </span>
                    </div>

                    <div class="scatter-flow-card__tempos">
                        <Tag
                            v-if="no.status === STATUS_NO_ABERTO"
                            :value="`Parado há ${formatarDuracaoSegundos(temposNo(no).paradoSegundos)}`"
                            :severity="severidadeTempoNo(temposNo(no).paradoSegundos, true)"
                            icon="pi pi-clock"
                            class="text-xs"
                        />
                        <Tag
                            :value="`Total ${formatarDuracaoSegundos(temposNo(no).totalSegundos)}`"
                            severity="secondary"
                            icon="pi pi-history"
                            class="text-xs"
                        />
                    </div>
                </div>

                <div v-if="no.filhos?.length" class="scatter-flow-children">
                    <div class="scatter-flow-children__rail" />
                    <div class="scatter-flow-children__row">
                        <div
                            v-for="filho in no.filhos"
                            :key="filho.id"
                            class="scatter-flow-child"
                        >
                            <div class="scatter-flow-child__stem" />
                            <ArvoreNosOperacionais
                                :nos="[filho]"
                                :nivel="nivel + 1"
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.scatter-flowchart--root {
    width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 0.25rem 0.5rem 0.75rem;
    scroll-behavior: smooth;
}

.scatter-flow-roots {
    display: flex;
    flex-wrap: nowrap;
    justify-content: flex-start;
    align-items: flex-start;
    gap: 2rem;
    min-width: min-content;
    width: max-content;
}

.scatter-flow-siblings {
    display: contents;
}

.scatter-flow-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
}

.scatter-flow-card {
    position: relative;
    min-width: 15rem;
    max-width: 19rem;
    padding: 0.75rem 0.85rem;
    border: 2px solid var(--surface-border);
    border-radius: var(--border-radius);
    background: var(--surface-card);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    z-index: 1;
}

.scatter-flow-card--aberto {
    border-color: var(--orange-300);
    background: linear-gradient(
        180deg,
        var(--surface-card) 0%,
        color-mix(in srgb, var(--orange-50) 40%, var(--surface-card)) 100%
    );
}

.scatter-flow-card--concluido {
    border-color: var(--green-300);
    background: linear-gradient(
        180deg,
        var(--surface-card) 0%,
        color-mix(in srgb, var(--green-50) 35%, var(--surface-card)) 100%
    );
}

.scatter-flow-card__header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem 0.5rem;
    margin-bottom: 0.45rem;
}

.scatter-flow-card__origem {
    font-size: 0.7rem;
    color: var(--text-color-secondary);
    line-height: 1.2;
}

.scatter-flow-card__titulo {
    font-size: 0.875rem;
    font-weight: 600;
    line-height: 1.35;
    margin-bottom: 0.35rem;
}

.scatter-flow-card__meta {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.75rem;
    color: var(--text-color-secondary);
    margin-bottom: 0.35rem;
}

.scatter-flow-card__datas {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.72rem;
    color: var(--text-color-secondary);
    margin-bottom: 0.5rem;
}

.scatter-flow-card__datas span {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
}

.scatter-flow-card__tempos {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}

.scatter-flow-children {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    position: relative;
}

.scatter-flow-children__rail {
    width: 2px;
    height: 1.25rem;
    background: var(--surface-400, #adb5bd);
    flex-shrink: 0;
}

.scatter-flow-children__row {
    display: flex;
    flex-wrap: nowrap;
    justify-content: flex-start;
    align-items: flex-start;
    gap: 1.5rem 2rem;
    position: relative;
    width: max-content;
    min-width: 100%;
}

.scatter-flow-children__row::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--surface-400, #adb5bd);
}

.scatter-flow-child {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
}

.scatter-flow-child__stem {
    width: 2px;
    height: 1.5rem;
    background: var(--surface-400, #adb5bd);
    flex-shrink: 0;
}

@media (max-width: 768px) {
    .scatter-flow-card {
        min-width: 14rem;
    }
}
</style>
