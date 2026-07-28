<script setup>
import { computed, ref, watch } from 'vue';
import Avatar from 'primevue/avatar';
import Tag from 'primevue/tag';
import Divider from 'primevue/divider';
import Dialog from 'primevue/dialog';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import {
    FLUXO_TRANSVERSAL,
    rotuloFluxo,
    iconeEvento,
    severityEvento,
    timelineOperacionalOrdenada,
    timelineOperacionalVereadorOrdenada,
    tagRotuloInstitucionalEvento,
    rotuloTipoEventoOperacional,
    rotuloSetorEventoOperacional,
    responsavelEventoOperacional,
    assinaturasParaEventoOperacional,
    anexosEventoOperacional
} from '@/constants/operacionalEstado';
import { formatarDataAssinatura } from '@/constants/assinaturaEletronica';
import {
    descricaoEncerramentoNoSetorVereador,
    descricaoEventoOperacionalVereador,
    ehEncerramentoNoSetorVereador,
    montarTimelineVereador
} from '@/constants/tramitacaoVisibilidade';
import { descricaoTramitacaoParaExibicao } from '@/utils/tramitacaoTexto';
import { rotuloDestinoOcupado, contarNosArvore } from '@/constants/scatterGather';
import ArvoreNosOperacionais from '@/components/demanda/ArvoreNosOperacionais.vue';
import ApiService from '@/service/ApiService.js';
import Panel from 'primevue/panel';

const props = defineProps({
    timeline: { type: Array, default: () => [] },
    fluxoRoteamento: { type: String, default: '' },
    participantes: { type: Array, default: () => [] },
    pendencias: { type: Array, default: () => [] },
    demandaLiderId: { type: [Number, String], default: null },
    modoVereador: { type: Boolean, default: false },
    statusDemanda: { type: String, default: '' },
    assinaturas: { type: Array, default: () => [] },
    arvoreNos: { type: Array, default: () => [] },
    nosAtivos: { type: Number, default: 0 },
    historicoTecnico: { type: Object, default: null },
    demandaAtualId: { type: [Number, String], default: null },
    /** Quando false, exibe só marcos institucionais (ex.: laudo digital já traz histórico técnico). */
    incluirHistoricoTecnico: { type: Boolean, default: true }
});

const historicoEventos = computed(() => {
    if (!props.modoVereador) return [];
    return (props.historicoTecnico?.eventos_tecnicos || []).filter((ev) =>
        (ev?.parecer || '').trim()
    );
});

const historicoPorTramitacao = computed(() => {
    const map = new Map();
    for (const ev of historicoEventos.value) {
        if (ev.tramitacao_id != null) map.set(String(ev.tramitacao_id), ev);
    }
    return map;
});

function parecerHistoricoExibicao(ev) {
    return descricaoTramitacaoParaExibicao(ev?.parecer || '');
}

const items = computed(() => {
    if (props.modoVereador) {
        return montarTimelineVereador(
            props.timeline,
            props.historicoTecnico,
            props.statusDemanda,
            props.demandaAtualId,
            props.demandaLiderId,
            timelineOperacionalVereadorOrdenada,
            props.incluirHistoricoTecnico
        );
    }
    return timelineOperacionalOrdenada(props.timeline, {
        completa: !props.modoVereador,
        demandaAtualId: props.demandaAtualId,
        demandaLiderId: props.demandaLiderId
    });
});

const itemsComConteudo = computed(() =>
    items.value.map((item) => ({
        item,
        conteudo: conteudoItem(item),
        anexos: anexosEventoOperacional(item, props.modoVereador, historicoPorTramitacao.value),
        assinaturas: assinaturasParaEventoOperacional(item, props.assinaturas)
    }))
);

const ehTransversal = computed(() => props.fluxoRoteamento === FLUXO_TRANSVERSAL);

const STATUS_DEMANDA_ENCERRADA = ['FINALIZADO', 'DEVOLVIDO_VEREADOR'];

const demandaEncerrada = computed(() =>
    STATUS_DEMANDA_ENCERRADA.includes(String(props.statusDemanda || '').toUpperCase())
);

function participanteConcluido(p) {
    if (demandaEncerrada.value) return true;
    return Boolean(p?.conclusao_parcial || p?.concluida);
}

const exibirPainelParticipantes = computed(
    () =>
        ehTransversal.value &&
        props.participantes.length &&
        !exibirArvoreNos.value &&
        !(props.modoVereador && demandaEncerrada.value)
);

const exibirArvoreNos = computed(
    () => !props.modoVereador && Array.isArray(props.arvoreNos) && props.arvoreNos.length > 0
);

const resumoArvoreNos = computed(() => contarNosArvore(props.arvoreNos));

const chavePainelArvore = computed(() =>
    props.demandaAtualId != null && props.demandaAtualId !== ''
        ? `sgdl:scatter-arvore-panel:${props.demandaAtualId}`
        : null
);

function lerColapsadaSalva() {
    if (!chavePainelArvore.value) return null;
    try {
        const raw = sessionStorage.getItem(chavePainelArvore.value);
        if (raw === '1') return true;
        if (raw === '0') return false;
    } catch {
        /* ignore */
    }
    return null;
}

const colapsadaSalvaInicial = lerColapsadaSalva();
const arvoreNosColapsada = ref(
    colapsadaSalvaInicial ?? (props.nosAtivos ?? 0) === 0
);

watch(
    () => props.nosAtivos,
    (ativos) => {
        if (lerColapsadaSalva() !== null) return;
        arvoreNosColapsada.value = (ativos ?? 0) === 0;
    }
);

watch(arvoreNosColapsada, (colapsada) => {
    if (!chavePainelArvore.value) return;
    try {
        sessionStorage.setItem(chavePainelArvore.value, colapsada ? '1' : '0');
    } catch {
        /* ignore */
    }
});

const formatarData = (iso) => {
    if (!iso) return '';
    return new Date(iso).toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

const MARKER_OBS = '\nObservação:';

function parseResumoObservacao(descricao) {
    const raw = String(descricao || '').trim();
    const idx = raw.indexOf(MARKER_OBS);
    if (idx >= 0) {
        return {
            resumo: raw.slice(0, idx).trim(),
            observacao: raw.slice(idx + MARKER_OBS.length).trim()
        };
    }
    return { resumo: raw, observacao: '' };
}

function rotuloPerna(perna) {
    const org = perna.orgao_nome || (perna.secretaria_id ? `Órgão #${perna.secretaria_id}` : 'Órgão');
    const setor =
        perna.setor_nome ||
        (perna.unidade_administrativa_id ? `Setor #${perna.unidade_administrativa_id}` : 'sem setor');
    return `${org} › ${setor}`;
}

/** Destinos do despacho scatter — lista completa ou fallback legado (1º destino). */
function destinosScatterEvento(meta) {
    if (Array.isArray(meta?.destinos) && meta.destinos.length) {
        return meta.destinos;
    }
    if (meta?.destino_orgao_id || meta?.destino_orgao_nome) {
        return [
            {
                secretaria_id: meta.destino_orgao_id,
                orgao_nome: meta.destino_orgao_nome,
                unidade_administrativa_id: meta.destino_setor_id,
                setor_nome: meta.setor_nome
            }
        ];
    }
    return [];
}

function conteudoItem(item) {
    if (props.modoVereador) {
        if (ehEncerramentoNoSetorVereador(item)) {
            return {
                tipo: 'descricao',
                descricao: descricaoTramitacaoParaExibicao(descricaoEncerramentoNoSetorVereador())
            };
        }

        const evHistorico =
            item._historicoEvento ||
            historicoPorTramitacao.value.get(String(item.id)) ||
            null;
        if (evHistorico) {
            return {
                tipo: 'historico_tecnico',
                evento: evHistorico,
                descricao: parecerHistoricoExibicao(evHistorico)
            };
        }
        const parecerMeta = (item?.metadata?.parecer || '').trim();
        if (parecerMeta) {
            return {
                tipo: 'descricao',
                descricao: descricaoTramitacaoParaExibicao(parecerMeta)
            };
        }
        return {
            tipo: 'descricao',
            descricao: descricaoTramitacaoParaExibicao(descricaoEventoOperacionalVereador(item))
        };
    }

    const meta = item?.metadata || {};

    if (meta.parecer) {
        return {
            tipo: 'descricao',
            descricao: descricaoTramitacaoParaExibicao(meta.parecer)
        };
    }
    if (meta.justificativa) {
        return {
            tipo: 'descricao',
            descricao: descricaoTramitacaoParaExibicao(meta.justificativa)
        };
    }

    if (meta.acao === 'ABERTURA_PERNAS_TRANSVERSAL') {
        const { resumo, observacao } = parseResumoObservacao(item?.descricao);
        return {
            tipo: 'transversal',
            resumo,
            descricao: descricaoTramitacaoParaExibicao(observacao),
            pernas: Array.isArray(meta.pernas) ? meta.pernas : []
        };
    }

    if (meta.scatter_gather) {
        const destinos = destinosScatterEvento(meta);
        return {
            tipo: 'scatter',
            descricao: descricaoTramitacaoParaExibicao(item?.descricao || ''),
            destinos,
            nosAtivos: meta.nos_ativos,
            noFilhosIds: Array.isArray(meta.no_filhos_ids) ? meta.no_filhos_ids : []
        };
    }

    return {
        tipo: 'descricao',
        descricao: descricaoTramitacaoParaExibicao(item?.descricao)
    };
}

function nomeAnexo(anexo) {
    if (anexo?.nome) return anexo.nome;
    const url = anexo?.arquivo || '';
    return url.split('/').pop() || 'Anexo';
}

function funcaoAssinatura(ass) {
    return ass.cargo || ass.papel_display || ass.papel || '—';
}

const assinaturaModalVisible = ref(false);
const assinaturaCarregando = ref(false);
const assinaturaDetalhe = ref(null);
const assinaturaErro = ref('');

async function abrirDetalheAssinatura(ass) {
    if (!ass?.codigo_validacao) return;
    assinaturaModalVisible.value = true;
    assinaturaCarregando.value = true;
    assinaturaDetalhe.value = null;
    assinaturaErro.value = '';
    try {
        const { data } = await ApiService.validarAssinatura(ass.codigo_validacao);
        assinaturaDetalhe.value = data;
    } catch (err) {
        assinaturaErro.value = err?.response?.data?.detail || 'Não foi possível carregar a assinatura.';
    } finally {
        assinaturaCarregando.value = false;
    }
}

function fecharDetalheAssinatura() {
    assinaturaModalVisible.value = false;
    assinaturaDetalhe.value = null;
    assinaturaErro.value = '';
}
</script>

<template>
    <div class="operacional-timeline">
        <div v-if="fluxoRoteamento && !modoVereador" class="flex flex-wrap items-center gap-2 mb-4">
            <Tag
                :value="rotuloFluxo(fluxoRoteamento)"
                :severity="ehTransversal ? 'help' : 'info'"
                icon="pi pi-directions"
            />
            <Tag
                v-if="nosAtivos > 0"
                :value="`${nosAtivos} nó(s) operacional(is) aberto(s)`"
                severity="warn"
                icon="pi pi-sitemap"
            />
            <span v-if="ehTransversal && !exibirArvoreNos" class="text-sm text-muted-color">
                Cada secretaria conclui parcialmente; o processo avança quando todas concluírem.
            </span>
        </div>

        <Panel
            v-if="exibirArvoreNos"
            v-model:collapsed="arvoreNosColapsada"
            toggleable
            class="mb-4 scatter-arvore-panel"
        >
            <template #header>
                <div class="flex flex-wrap align-items-center gap-2">
                    <i class="pi pi-sitemap text-primary" />
                    <span class="font-semibold text-sm">Fluxo operacional</span>
                    <Tag
                        :value="`${resumoArvoreNos.total} nó(s)`"
                        severity="secondary"
                        class="text-xs"
                    />
                    <Tag
                        v-if="resumoArvoreNos.abertos > 0"
                        :value="`${resumoArvoreNos.abertos} aberto(s)`"
                        severity="warn"
                        class="text-xs"
                    />
                    <Tag
                        v-else
                        value="Concluído"
                        severity="success"
                        class="text-xs"
                    />
                </div>
            </template>
            <ArvoreNosOperacionais :nos="arvoreNos" :scroll-key="demandaAtualId" />
        </Panel>

        <div
            v-if="exibirPainelParticipantes"
            class="card mb-4 p-3 surface-ground"
        >
            <span class="font-semibold text-sm block mb-2">Participantes do fluxo transversal</span>
            <div class="flex flex-wrap gap-2">
                <Tag
                    v-for="p in participantes"
                    :key="p.perna_id || p.demanda_id"
                    :value="`${p.orgao_nome || 'Órgão'}${p.setor_nome ? ' › ' + p.setor_nome : ''} · ${participanteConcluido(p) ? 'Concluído' : 'Pendente'}`"
                    :severity="participanteConcluido(p) ? 'success' : 'warn'"
                    :icon="participanteConcluido(p) ? 'pi pi-check' : 'pi pi-clock'"
                />
            </div>
            <p v-if="!modoVereador && pendencias.length" class="text-xs text-muted-color m-0 mt-2">
                Aguardando conclusão parcial:
                {{
                    pendencias
                        .map((p) =>
                            p.setor_nome ? `${p.orgao_nome} › ${p.setor_nome}` : p.orgao_nome
                        )
                        .filter(Boolean)
                        .join(', ')
                }}
            </p>
        </div>

        <div v-if="itemsComConteudo.length" class="timeline-container pt-6 pb-3">
            <div class="flex flex-col gap-6">
                <div
                    v-for="{ item, conteudo, anexos, assinaturas: assinaturasItem } in itemsComConteudo"
                    :key="`${item.id}-${item.timestamp}`"
                    class="flex gap-3"
                >
                    <div class="flex flex-col items-center timeline-icon-container">
                        <Avatar
                            :icon="iconeEvento(item.tipo, item).icon"
                            shape="circle"
                            size="large"
                            :class="iconeEvento(item.tipo, item).color"
                            :title="rotuloTipoEventoOperacional(item, modoVereador)"
                        />
                    </div>
                    <div class="card flex-1 operacional-evento-card">
                        <!-- Header -->
                        <header class="operacional-evento-header flex flex-row items-center justify-between gap-3 mb-3">
                            <div class="operacional-evento-meta text-sm text-muted-color min-w-0">
                                <strong class="text-color">{{ rotuloSetorEventoOperacional(item) }}</strong>
                                <template v-if="!modoVereador && responsavelEventoOperacional(item, false)">
                                    <span class="operacional-meta-sep" aria-hidden="true">|</span>
                                    <span class="inline-flex align-items-center gap-1">
                                        <i class="pi pi-user text-xs" aria-hidden="true" />
                                        {{ responsavelEventoOperacional(item, false) }}
                                    </span>
                                </template>
                                <span class="operacional-meta-sep" aria-hidden="true">|</span>
                                <span class="inline-flex align-items-center gap-1">
                                    <i class="pi pi-calendar text-xs" aria-hidden="true" />
                                    {{ formatarData(item.timestamp) }}
                                </span>
                            </div>
                            <Tag
                                :value="tagRotuloInstitucionalEvento(item, modoVereador)"
                                :severity="severityEvento(item.tipo, item)"
                                class="shrink-0"
                            />
                        </header>

                        <Divider class="mt-0 mb-3" />

                        <!-- Content -->
                        <section class="operacional-evento-conteudo">
                            <template v-if="conteudo.tipo === 'transversal'">
                                <p v-if="conteudo.resumo" class="m-0 text-sm font-medium mb-2">
                                    {{ conteudo.resumo }}
                                </p>
                                <template v-if="conteudo.descricao.modo === 'html'">
                                    <p
                                        v-if="conteudo.descricao.html"
                                        class="m-0 mb-1 text-sm text-muted-color"
                                    >
                                        Observação:
                                    </p>
                                    <div
                                        class="tramitacao-descricao-html text-sm"
                                        v-html="conteudo.descricao.html"
                                    />
                                </template>
                                <p
                                    v-else-if="conteudo.descricao.texto"
                                    class="m-0 text-sm whitespace-pre-wrap"
                                >
                                    <span class="text-muted-color">Observação: </span>
                                    {{ conteudo.descricao.texto }}
                                </p>
                                <div
                                    v-if="conteudo.pernas.length"
                                    class="mt-3 p-3 surface-50 border-round"
                                >
                                    <span class="font-medium text-sm block mb-2">Pernas abertas</span>
                                    <ul class="m-0 pl-4 text-sm">
                                        <li v-for="(perna, idx) in conteudo.pernas" :key="idx">
                                            {{ rotuloPerna(perna) }}
                                        </li>
                                    </ul>
                                </div>
                            </template>

                            <template v-else-if="conteudo.tipo === 'scatter'">
                                <div
                                    v-if="conteudo.descricao.modo === 'html'"
                                    class="tramitacao-descricao-html m-0"
                                    v-html="conteudo.descricao.html"
                                />
                                <p
                                    v-else-if="conteudo.descricao.texto"
                                    class="m-0 whitespace-pre-wrap tramitacao-descricao-texto"
                                >
                                    {{ conteudo.descricao.texto }}
                                </p>
                                <div v-if="conteudo.destinos?.length" class="mt-2 text-sm">
                                    <span class="text-muted-color">
                                        {{ conteudo.destinos.length > 1 ? 'Destinos:' : 'Destino:' }}
                                    </span>
                                    <ul
                                        v-if="conteudo.destinos.length > 1"
                                        class="m-0 mt-1 pl-4"
                                    >
                                        <li
                                            v-for="(dest, idx) in conteudo.destinos"
                                            :key="`${dest.secretaria_id}-${dest.unidade_administrativa_id}-${idx}`"
                                        >
                                            {{ rotuloDestinoOcupado(dest) }}
                                        </li>
                                    </ul>
                                    <strong v-else class="ml-1">
                                        {{ rotuloDestinoOcupado(conteudo.destinos[0]) }}
                                    </strong>
                                </div>
                                <p
                                    v-if="conteudo.noFilhosIds?.length > 1"
                                    class="m-0 mt-1 text-xs text-muted-color"
                                >
                                    {{ conteudo.noFilhosIds.length }} nó(s) operacional(is) aberto(s).
                                </p>
                                <p
                                    v-if="!modoVereador && conteudo.nosAtivos != null"
                                    class="m-0 mt-2 text-xs text-muted-color"
                                >
                                    Nós ativos após operação: {{ conteudo.nosAtivos }}
                                </p>
                            </template>

                            <template v-else-if="conteudo.tipo === 'historico_tecnico'">
                                <p
                                    v-if="conteudo.evento.responsavel"
                                    class="m-0 mb-2 text-xs text-muted-color"
                                >
                                    Registrado por
                                    <strong class="text-color">{{ conteudo.evento.responsavel }}</strong>
                                </p>
                                <div
                                    v-if="conteudo.descricao?.modo === 'html'"
                                    class="tramitacao-descricao-html m-0 text-sm"
                                    v-html="conteudo.descricao.html"
                                />
                                <p
                                    v-else-if="conteudo.descricao?.texto"
                                    class="m-0 text-sm whitespace-pre-wrap tramitacao-descricao-texto"
                                >
                                    {{ conteudo.descricao.texto }}
                                </p>
                            </template>

                            <template v-else-if="conteudo.descricao?.modo === 'html'">
                                <div
                                    class="tramitacao-descricao-html m-0"
                                    v-html="conteudo.descricao.html"
                                />
                            </template>
                            <p
                                v-else-if="conteudo.descricao?.texto"
                                class="m-0 whitespace-pre-wrap tramitacao-descricao-texto"
                            >
                                {{ conteudo.descricao.texto }}
                            </p>
                            <p
                                v-else-if="conteudo.descricao?.modo === 'vazio'"
                                class="m-0 text-sm text-muted-color italic"
                            >
                                Sem descrição registrada.
                            </p>
                        </section>

                        <!-- Footer -->
                        <footer
                            v-if="anexos.length || assinaturasItem.length"
                            class="operacional-evento-rodape mt-3"
                        >
                            <Divider class="my-3" />

                            <div v-if="anexos.length" class="mb-3">
                                <span class="font-medium text-sm block mb-2">
                                    <i class="pi pi-paperclip mr-1" aria-hidden="true" />
                                    Anexos
                                </span>
                                <div class="flex flex-col gap-2">
                                    <a
                                        v-for="anexo in anexos"
                                        :key="anexo.id"
                                        :href="anexo.arquivo"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        class="no-underline text-color hover:text-primary flex align-items-center text-sm"
                                    >
                                        <i class="pi pi-file mr-2" aria-hidden="true" />
                                        {{ nomeAnexo(anexo) }}
                                    </a>
                                </div>
                            </div>

                            <div v-if="assinaturasItem.length">
                                <span class="font-medium text-sm block mb-2">
                                    <i class="pi pi-verified mr-1" aria-hidden="true" />
                                    Assinaturas
                                </span>
                                <div class="flex flex-col gap-2">
                                    <div
                                        v-for="(ass, idx) in assinaturasItem"
                                        :key="`${ass.etapa}-${ass.papel}-${idx}`"
                                        class="assinatura-linha text-sm text-muted-color"
                                    >
                                        <span class="text-color">{{ ass.signatario }}</span>
                                        <span class="operacional-meta-sep" aria-hidden="true">|</span>
                                        <span>{{ funcaoAssinatura(ass) }}</span>
                                        <span class="operacional-meta-sep" aria-hidden="true">|</span>
                                        <span>{{ formatarDataAssinatura(ass.assinado_em) }}</span>
                                        <span class="operacional-meta-sep" aria-hidden="true">|</span>
                                        <button
                                            v-if="ass.codigo_validacao"
                                            type="button"
                                            class="p-0 border-none bg-transparent text-primary cursor-pointer hover:underline text-sm"
                                            @click="abrirDetalheAssinatura(ass)"
                                        >
                                            Assinatura
                                        </button>
                                        <span v-else class="text-muted-color">Assinatura</span>
                                    </div>
                                </div>
                            </div>
                        </footer>
                    </div>
                </div>
            </div>
        </div>

        <Dialog
            v-model:visible="assinaturaModalVisible"
            header="Detalhe da assinatura eletrônica"
            modal
            :style="{ width: 'min(520px, 95vw)' }"
            @hide="fecharDetalheAssinatura"
        >
            <div v-if="assinaturaCarregando" class="flex justify-center py-6">
                <ProgressSpinner style="width: 40px; height: 40px" />
            </div>
            <Message v-else-if="assinaturaErro" severity="error" :closable="false">
                {{ assinaturaErro }}
            </Message>
            <div v-else-if="assinaturaDetalhe?.valido" class="flex flex-col gap-2 text-sm">
                <Tag value="Assinatura válida" severity="success" class="w-fit" />
                <p class="m-0">
                    <strong>Etapa:</strong>
                    {{ assinaturaDetalhe.etapa_display || assinaturaDetalhe.etapa }}
                </p>
                <p class="m-0">
                    <strong>Signatário:</strong> {{ assinaturaDetalhe.signatario }}
                </p>
                <p v-if="assinaturaDetalhe.cargo" class="m-0">
                    <strong>Cargo:</strong> {{ assinaturaDetalhe.cargo }}
                </p>
                <p v-if="assinaturaDetalhe.papel_display" class="m-0">
                    <strong>Papel:</strong> {{ assinaturaDetalhe.papel_display }}
                </p>
                <p class="m-0">
                    <strong>Demanda:</strong> {{ assinaturaDetalhe.demanda_titulo }}
                </p>
                <p class="m-0">
                    <strong>Assinado em:</strong>
                    {{ formatarDataAssinatura(assinaturaDetalhe.assinado_em) }}
                </p>
                <p class="m-0 text-xs text-muted-color break-all">
                    Código: {{ assinaturaDetalhe.codigo_validacao }}
                </p>
            </div>
        </Dialog>
    </div>
</template>

<style scoped>
.timeline-container {
    position: relative;
}
.timeline-container::before {
    content: '';
    position: absolute;
    left: 1.25rem;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--surface-border);
}
.timeline-icon-container {
    position: relative;
    z-index: 1;
}
.operacional-evento-header {
    flex-wrap: wrap;
}
.operacional-evento-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem 0.5rem;
    line-height: 1.4;
}
.operacional-meta-sep {
    color: var(--text-color-secondary);
    user-select: none;
}
.assinatura-linha {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem 0.5rem;
    line-height: 1.4;
}
.tramitacao-descricao-texto {
    white-space: pre-wrap;
    line-height: 1.5;
}
.tramitacao-descricao-html :deep(p) {
    margin: 0 0 0.5rem;
    line-height: 1.5;
}
.tramitacao-descricao-html :deep(p:last-child) {
    margin-bottom: 0;
}
</style>
