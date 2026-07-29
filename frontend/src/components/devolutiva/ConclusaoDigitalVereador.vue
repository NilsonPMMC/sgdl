<script setup>
import Divider from 'primevue/divider';
import Message from 'primevue/message';
import Tag from 'primevue/tag';
import PesquisaSatisfacaoVisual from '@/components/devolutiva/PesquisaSatisfacaoVisual.vue';
import { computed } from 'vue';
import { descricaoParaHtml, htmlParaTexto } from '@/utils/oficioTexto';
import { exibirProtocoloDemanda } from '@/utils/protocoloLegislativo';

const props = defineProps({
    pacote: { type: Object, required: true },
    /** Ocultar quando a timeline operacional já exibe os encerramentos por setor. */
    mostrarHistoricoTecnico: { type: Boolean, default: true }
});

const historicoEventos = computed(() =>
    (props.pacote?.historico_tecnico?.eventos_tecnicos || []).filter((ev) =>
        htmlParaTexto(ev?.parecer || '')
    )
);

const laudoHtml = computed(() => {
    const raw = props.pacote?.laudo_final || '';
    if (!raw) return '';
    if (/<[a-z][\s\S]*>/i.test(raw)) return raw;
    return descricaoParaHtml(raw);
});

const dataConclusao = computed(() => {
    const raw =
        props.pacote?.conclusao_em ||
        props.pacote?.devolutiva_em ||
        null;
    if (!raw) return null;
    const dt = new Date(raw);
    return Number.isNaN(dt.getTime()) ? null : raw;
});

const ETAPAS_ASSINATURA_DESPACHO_FINAL = ['DESPACHO_DEVOLUTIVA', 'CONCLUSAO_FINAL'];

const assinantesDespachoFinal = computed(() => {
    const lista = (props.pacote?.assinaturas || []).filter((a) =>
        ETAPAS_ASSINATURA_DESPACHO_FINAL.includes(String(a.etapa || '').toUpperCase())
    );
    const operador = lista.find((a) => a.papel === 'OPERADOR');
    const gestor = lista.find((a) => a.papel === 'GESTOR_PROTOCOLO');
    const linhas = [];
    if (operador?.signatario) {
        linhas.push({
            nome: operador.signatario,
            cargo: operador.cargo || operador.papel_display || 'Operador do Protocolo'
        });
    }
    if (gestor?.signatario) {
        linhas.push({
            nome: gestor.signatario,
            cargo: gestor.cargo || gestor.papel_display || 'Gestor do Protocolo'
        });
    }
    if (linhas.length) return linhas;
    const fallback =
        props.pacote?.conclusao_gestor_protocolo ||
        props.pacote?.conclusao_operador ||
        props.pacote?.conclusao_responsavel ||
        props.pacote?.devolutiva_responsavel;
    return fallback ? [{ nome: fallback, cargo: null }] : [];
});

const exibirAssinantesDespachoFinal = computed(() => assinantesDespachoFinal.value.length > 0);

function formatarData(iso) {
    if (!iso) return '—';
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return '—';
    return dt.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function parecerEvento(ev) {
    return htmlParaTexto(ev?.parecer || '');
}
</script>

<template>
    <div class="card conclusao-digital-vereador !p-0 overflow-hidden">
        <div
            class="p-4 md:p-5 border-bottom-1 surface-border bg-surface-50 dark:bg-surface-900"
        >
            <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <p class="m-0 text-xs uppercase tracking-wide text-muted-color">Ofício — processo</p>
                    <h4 class="m-0 mt-1 text-xl font-semibold text-surface-900 dark:text-surface-0">
                        Laudo final do processo
                    </h4>
                    <p class="m-0 mt-2 text-sm text-surface-700 dark:text-surface-200">
                        {{ exibirProtocoloDemanda(pacote, `#${pacote.demanda_id}`) }}
                        <span v-if="pacote.titulo"> · {{ pacote.titulo }}</span>
                    </p>
                </div>
                <Tag value="Processo concluído pelo Protocolo" severity="success" />
            </div>
        </div>

        <div class="p-4 md:p-5 flex flex-col gap-5 bg-surface-0 dark:bg-surface-950">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div class="p-3 surface-ground dark:bg-surface-800 border-round border-1 surface-border">
                    <span class="text-xs text-muted-color block mb-1">Conclusão emitida em</span>
                    <strong class="text-sm text-surface-900 dark:text-surface-0">
                        {{ formatarData(dataConclusao) }}
                    </strong>
                </div>
                <div
                    v-if="exibirAssinantesDespachoFinal"
                    class="p-3 surface-ground dark:bg-surface-800 border-round border-1 surface-border"
                >
                    <span class="text-xs text-muted-color block mb-2">Despacho final assinado por</span>
                    <div class="flex flex-col gap-2">
                        <div
                            v-for="(linha, idx) in assinantesDespachoFinal"
                            :key="`${linha.nome}-${idx}`"
                            class="flex flex-wrap items-baseline gap-x-2 gap-y-0"
                        >
                            <strong class="text-sm text-surface-900 dark:text-surface-0">
                                {{ linha.nome }}
                            </strong>
                            <span v-if="linha.cargo" class="text-xs text-muted-color">
                                {{ linha.cargo }}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <section v-if="laudoHtml">
                <h5 class="mt-0 mb-3 flex items-center gap-2 text-surface-900 dark:text-surface-0">
                    <i class="pi pi-verified text-primary" aria-hidden="true" />
                    Laudo do despacho final (Protocolo)
                </h5>
                <div
                    class="demanda-descricao-html p-4 surface-ground dark:bg-surface-800 border-round border-1 surface-border text-sm text-surface-800 dark:text-surface-100"
                    v-html="laudoHtml"
                />
            </section>
            <Message v-else severity="warn" :closable="false" class="m-0">
                Laudo do despacho final ainda não disponível neste processo.
            </Message>

            <section v-if="pacote.anexos_devolutiva?.length">
                <h5 class="mt-0 mb-3 flex items-center gap-2 text-surface-900 dark:text-surface-0">
                    <i class="pi pi-paperclip text-primary" aria-hidden="true" />
                    Anexos do despacho final
                </h5>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <a
                        v-for="anexo in pacote.anexos_devolutiva"
                        :key="anexo.id"
                        :href="anexo.arquivo"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="flex items-center gap-2 p-3 border-1 surface-border border-round no-underline text-surface-900 dark:text-surface-0 hover:surface-hover transition-colors"
                    >
                        <i class="pi pi-file-pdf text-primary text-xl shrink-0" aria-hidden="true" />
                        <span class="text-sm font-medium truncate">{{ anexo.nome || 'Anexo' }}</span>
                    </a>
                </div>
            </section>

            <section v-if="mostrarHistoricoTecnico && historicoEventos.length">
                <h5 class="mt-0 mb-3 flex items-center gap-2 text-surface-900 dark:text-surface-0">
                    <i class="pi pi-history text-primary" aria-hidden="true" />
                    Histórico técnico consolidado
                </h5>
                <div class="flex flex-col gap-3">
                    <div
                        v-for="(ev, idx) in historicoEventos"
                        :key="idx"
                        class="p-3 surface-ground dark:bg-surface-800 border-round border-left-3 border-primary"
                    >
                        <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
                            <Tag :value="ev.orgao_nome || 'Secretaria'" severity="secondary" />
                            <span v-if="ev.timestamp" class="text-xs text-muted-color">
                                {{ formatarData(ev.timestamp) }}
                            </span>
                        </div>
                        <p
                            v-if="ev.responsavel"
                            class="m-0 mb-2 text-xs text-muted-color"
                        >
                            Registrado por <strong class="text-color">{{ ev.responsavel }}</strong>
                        </p>
                        <p class="m-0 text-sm text-surface-800 dark:text-surface-100 whitespace-pre-wrap">
                            {{ parecerEvento(ev) }}
                        </p>
                    </div>
                </div>
            </section>

            <Divider />

            <section>
                <h5 class="mt-0 mb-3 flex items-center gap-2 text-surface-900 dark:text-surface-0">
                    <i class="pi pi-star text-primary" aria-hidden="true" />
                    Pesquisa de satisfação
                </h5>
                <PesquisaSatisfacaoVisual :readonly="false" :encerrado="false" />
            </section>
        </div>
    </div>
</template>
