<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { useUserStore } from '@/stores/userStore';
import ApiService from '@/service/ApiService.js';

import Button from 'primevue/button';
import Textarea from 'primevue/textarea';
import ProgressSpinner from 'primevue/progressspinner';
import Tag from 'primevue/tag';
import Select from 'primevue/select';
import InputText from 'primevue/inputtext';
import AutoComplete from 'primevue/autocomplete';
import InputMask from 'primevue/inputmask';
import CopilotoContextoPainel from '@/components/copiloto/CopilotoContextoPainel.vue';
import CopilotoIndicacaoCampos from '@/components/copiloto/CopilotoIndicacaoCampos.vue';
import MapaLocalAjustavel from '@/components/mapa/MapaLocalAjustavel.vue';
import {
    filtrarArquivosDuplicados,
    mensagemAnexosRejeitados,
    normalizarNomeArquivo
} from '@/utils/anexoValidacao';
import {
    resumoDuplicidadeFrontend,
    temDuplicidadeEmTramite
} from '@/utils/duplicidadeAlerta';
import Message from 'primevue/message';

const router = useRouter();
const toast = useToast();
const userStore = useUserStore();

const isModoIndicacao = computed(() => userStore.currentUser?.perfil === 'CAMARA');

/** @type {import('vue').Ref<string|null>} */
const sessionId = ref(null);
const mensagens = ref([]);
const inputTexto = ref('');
/** @typedef {{ id: string, file: File, indiceDemanda: number | null }} AnexoPendente */
/** @type {import('vue').Ref<AnexoPendente[]>} */
const anexosPendentes = ref([]);
const inputAnexosRef = ref(null);
const carregando = ref(false);
const painelContextoAberto = ref(false);

/** @type {import('vue').Ref<{ indiceDemanda: number, etapa: string }|null>} */
const revisaoAtiva = ref(null);
const sucessoCriacao = ref(null);
/** @type {import('vue').Ref<Array<Record<string, unknown>>|null>} */
const alertasDuplicidadeCriacao = ref(null);

/** @type {import('vue').Ref<Array<{id?:string, rotulo?:string, ranking?:number, texto_sugerido?:string, tem_detalhamento?:boolean, opcoes_carta?:Array, servico_padrao_id?:number}>>} */
const atalhosTopTrends = ref([]);
const atalhosTopTrendsExpandido = ref(false);
const atalhoEmDetalhamento = ref(null);
const opcoesCartaAtalho = ref([]);
const carregandoDetalheAtalho = ref(false);
const LIMITE_ATALHOS_VISIVEIS = 8;

function demandaPodeConfirmarLocal(demanda) {
    if (demanda?.descartada || demandaForaCompetencia(demanda)) return false;
    if (demanda?.requer_localizacao === false) return false;
    if (demanda?.endereco_opcional_dispensado) return false;
    if (demanda?.local_pendente_confirmacao === true) return true;
    if (demanda?.local_pendente_confirmacao === false) return false;
    if (demanda?.latitude != null && demanda?.longitude != null) return true;
    const end = demanda?.endereco;
    if (!end || typeof end !== 'object') return false;
    const logr = (end.logradouro || '').trim();
    const bairro = (end.bairro || '').trim();
    const cep = (end.cep || '').trim();
    return Boolean(logr && (bairro || cep));
}

const placeholderCompositor = computed(() => {
    if (isModoIndicacao.value && !demandasExtraidas.value.length) {
        return 'Descreva a indicação legislativa (objeto, fundamentação, pedido à Prefeitura)…';
    }
    const rev = revisaoAtiva.value;
    if (!rev) {
        return 'Descreva o pedido…';
    }
    if (rev.etapa === 'pedido') {
        return `Descreva as alterações na solicitação ${rev.indiceDemanda + 1}…`;
    }
    if (rev.etapa === 'local') {
        return `Informe o local da solicitação ${rev.indiceDemanda + 1} (rua, bairro, CEP)…`;
    }
    if (rev.etapa === 'anexos') {
        return 'Descreva o que deseja alterar nos documentos…';
    }
    return 'Descreva o pedido do cidadão…';
});

const estadoAtual = ref('COLETA_DADOS');
const demandasExtraidas = ref([]);

const estadoLabel = computed(() => {
    const map = {
        COLETA_DADOS: 'Coleta de dados',
        CONFIRMACAO_SINAPSE: 'Confirmação Sinapse',
        COLETA_ENDERECO: 'Endereço',
        VALIDACAO_FINAL: 'Validação final'
    };
    return map[estadoAtual.value] || estadoAtual.value;
});

const severidadeEstado = computed(() => {
    const m = {
        COLETA_DADOS: 'info',
        CONFIRMACAO_SINAPSE: 'warn',
        COLETA_ENDERECO: 'secondary',
        VALIDACAO_FINAL: 'success'
    };
    return m[estadoAtual.value] || 'secondary';
});

const listaChatRef = ref(null);

async function rolarParaOFim() {
    await nextTick();
    const el = listaChatRef.value;
    if (el) {
        el.scrollTop = el.scrollHeight;
    }
}

watch(mensagens, () => rolarParaOFim(), { deep: true });

const opcoesDemandaAnexo = computed(() =>
    demandasExtraidas.value
        .map((d, i) => ({ d, i }))
        .filter(({ d }) => !d?.descartada && !demandaForaCompetencia(d))
        .map(({ d, i }) => {
            const titulo = (d?.titulo || '').trim() || `Solicitação ${i + 1}`;
            const curto = titulo.length > 48 ? `${titulo.slice(0, 48)}…` : titulo;
            return { label: curto, value: i };
        })
);

/** Escolha manual de serviço na carta (índice da demanda → servico_id). */
const escolhaServicoCarta = ref({});
/** Detecta mudança nos candidatos da carta para atualizar o Select automaticamente. */
const candidatosFingerprint = ref({});

/** Valor sintético no Select da carta → trilha tendência. */
const NENHUMA_OPCAO_CARTA = '__NENHUMA_CARTA__';

function tendenciaConfirmada(demanda) {
    return Boolean(
        demanda?.tendencia_id ??
            demanda?.tendencia?.id ??
            demanda?.origem_vinculo === 'TENDENCIA'
    );
}

function sinapseIdValido(valor) {
    if (valor == null || valor === '') return false;
    const n = Number(valor);
    return Number.isInteger(n) && n > 0;
}

function servicoConfirmado(demanda) {
    if (tendenciaConfirmada(demanda)) return true;
    return demanda?.servico?.confirmado === true;
}

const LIMIAR_SCORE_CARTA = 2 / 3;
const LIMIAR_SCORE_DOMINIO = 0.4;
const MAX_OPCOES_CARTA = 5;
const MAX_OPCOES_DOMINIO = 8;

/** Aprovação individual na etapa final (índice → gerar rascunho). */
const aprovacaoFinal = ref({});

function ehModoCartaDominio(demanda) {
    return demanda?.modo_vinculo_servico === 'carta_dominio';
}

function limiarScoreDemanda(demanda) {
    return ehModoCartaDominio(demanda) ? LIMIAR_SCORE_DOMINIO : LIMIAR_SCORE_CARTA;
}

function maxOpcoesCartaDemanda(demanda) {
    return ehModoCartaDominio(demanda) ? MAX_OPCOES_DOMINIO : MAX_OPCOES_CARTA;
}

/** Candidatos da carta conforme modo (forte ≥ 66,66% ou domínio ≥ 40%). */
function pontuacaoCandidatoLocal(c, demanda) {
    const texto = `${demanda?.titulo || ''} ${demanda?.descricao || ''} ${demanda?.texto_para_embedding || ''}`.toLowerCase();
    const st = (c?.titulo || '').toLowerCase();
    let pts = Number(c?.score ?? 0);
    if (/linha\s+\d/.test(texto) || texto.includes('transporte coletivo') || texto.includes('coletivo municipal')) {
        if (st.includes('coletivo') && (st.includes('linha') || st.includes('ônibus') || st.includes('onibus'))) {
            pts += 0.58;
        } else if (st.includes('escolar') || st.includes('vaga') || st.includes('creche')) {
            pts -= 0.55;
        }
    }
    if (/poda|árvore|arvore|galho/.test(texto)) {
        if (/poda|árvore|arvore|galho|corte|arbor/.test(st)) {
            pts += 0.55;
        } else if (/tapa|burac|paviment/.test(st)) {
            pts -= 0.55;
        }
    }
    if (/tapa|buraco/.test(texto) && /tapa|burac|paviment/.test(st)) {
        pts += 0.35;
    }
    return pts;
}

function fingerprintCandidatos(demanda) {
    const rev = demanda?.candidatos_revisao ?? 0;
    const sug = demanda?.servico_sugerido_ui_id ?? '';
    const cands = demanda?.candidatos_sinapse;
    if (!Array.isArray(cands) || !cands.length) return `r${rev}|s${sug}|`;
    return `r${rev}|s${sug}|${cands.map((c) => `${c.servico_id}:${Math.round(Number(c.score ?? 0) * 1000)}`).join('|')}`;
}

function candidatosCartaExibicao(demanda) {
    const cands = demanda?.candidatos_sinapse;
    if (!Array.isArray(cands) || !cands.length) return [];
    const limiar = limiarScoreDemanda(demanda);
    const maxN = maxOpcoesCartaDemanda(demanda);
    return [...cands]
        .filter((c) => pontuacaoCandidatoLocal(c, demanda) >= limiar)
        .sort((a, b) => pontuacaoCandidatoLocal(b, demanda) - pontuacaoCandidatoLocal(a, demanda))
        .slice(0, maxN);
}

function escolheuNenhumaCarta(indice) {
    return escolhaServicoCarta.value[indice] === NENHUMA_OPCAO_CARTA;
}

function demandaForaCompetencia(demanda) {
    return Boolean(demanda?.fora_competencia);
}

/** Cada item do rascunho tem carta confirmada, tendência confirmada, descartado, ou não exige vínculo. */
function demandaVinculada(demanda, indice = null) {
    if (demandaForaCompetencia(demanda)) return false;
    if (demanda?.descartada) return true;
    if (servicoConfirmado(demanda)) return true;
    if (tendenciaConfirmada(demanda)) return true;
    if (demandaForaCarta(demanda)) {
        if (demanda?.vinculo_servico_ignorado) return true;
        if (indice != null && escolheuNenhumaCarta(indice)) return true;
    }
    return false;
}

function demandaForaCarta(demanda) {
    return Boolean(demanda?.fora_carta);
}

function corpusHintsDemanda(demanda) {
    const hints = demanda?.corpus_hints_historico;
    return Array.isArray(hints) ? hints : [];
}

function rotuloHintHistorico(hint) {
    if (hint?.titulo_sinapse_historico) {
        const rank = hint?.ranking ? `${hint.ranking}º — ` : '';
        return `${rank}${hint.titulo_sinapse_historico}`;
    }
    const rotulo = (hint?.atalho_sugerido || hint?.servico_legado || 'Pedido').trim();
    const rank = hint?.ranking ? `${hint.ranking}º — ` : '';
    return `${rank}${rotulo}`;
}

const temDemandaForaCompetencia = computed(() =>
    demandasExtraidas.value.some((d) => demandaForaCompetencia(d))
);

const todosServicosConfirmados = computed(() => {
    const lista = demandasExtraidas.value;
    if (!lista.length) return false;
    if (temDemandaForaCompetencia.value) return false;
    return lista.every((d, i) => demandaVinculada(d, i));
});

/** Aguardando escolha na carta (ou tendência via última opção do mesmo card). */
const demandasPendentesVinculo = computed(() =>
    demandasExtraidas.value
        .map((d, i) => ({ d, i }))
        .filter(
            ({ d }) =>
                !d?.descartada &&
                !demandaForaCompetencia(d) &&
                !servicoConfirmado(d) &&
                !tendenciaConfirmada(d)
        )
);

/** Itens no painel da carta (inclui descartados, para restaurar). */
const demandasNoPainelServico = computed(() =>
    demandasExtraidas.value
        .map((d, i) => ({ d, i }))
        .filter(({ d }) => !demandaForaCompetencia(d))
);

const demandasAtivasNoFluxo = computed(() =>
    demandasExtraidas.value.filter((d) => !d?.descartada && !demandaForaCompetencia(d))
);

const demandasParaAprovacaoFinal = computed(() =>
    demandasExtraidas.value
        .map((d, i) => ({ d, i }))
        .filter(({ d }) => !d?.descartada && !demandaForaCompetencia(d))
);

const demandasForaCompetenciaNoChat = computed(() =>
    demandasExtraidas.value
        .map((d, i) => ({ d, i }))
        .filter(({ d }) => demandaForaCompetencia(d))
);

const mostrarBlocoForaCompetenciaNoChat = computed(
    () => demandasForaCompetenciaNoChat.value.length > 0 && !sucessoCriacao.value
);

const demandasComCartaNoChat = demandasNoPainelServico;

const mostrarBlocoServicoNoChat = computed(() => {
    if (sucessoCriacao.value) return false;
    if (revisaoAtiva.value?.etapa === 'servico') return true;
    return demandasPendentesVinculo.value.length > 0;
});

/** Card de tendência separado desativado — tendência só dentro do card da carta. */
const mostrarBlocoTendenciaNoChat = computed(() => false);

const demandasAguardandoComplemento = computed(() =>
    demandasExtraidas.value
        .map((d, i) => ({ d, i }))
        .filter(
            ({ d }) =>
                !d?.descartada &&
                !demandaForaCompetencia(d) &&
                servicoConfirmado(d) &&
                (d?.corpus_aguarda_complemento || estadoAtual.value === 'COLETA_ENDERECO')
        )
);

const mostrarBlocoComplementoNoChat = computed(
    () => demandasAguardandoComplemento.value.length > 0 && !sucessoCriacao.value && !mostrarBlocoServicoNoChat.value
);

/** Busca semântica + formulário por índice de demanda fora da carta. */
const tendenciasSimilares = ref({});
const tituloTendenciaForm = ref({});
const escolhaTendenciaForm = ref({});

function textoParaBuscaTendencia(demanda) {
    return (
        (demanda?.texto_para_embedding || demanda?.titulo || demanda?.descricao || '')
            .trim()
            .slice(0, 2000) || 'solicitação'
    );
}

async function carregarSimilaresTendencia(indice, demanda) {
    const atual = tendenciasSimilares.value[indice];
    if (atual?.loaded || atual?.loading) return;

    tendenciasSimilares.value = {
        ...tendenciasSimilares.value,
        [indice]: { loading: true, loaded: false, items: [] }
    };

    try {
        const { data } = await ApiService.buscarTendenciasSimilares({
            texto: textoParaBuscaTendencia(demanda),
            limite: 5
        });
        const items = Array.isArray(data?.resultados) ? data.resultados : [];
        tendenciasSimilares.value = {
            ...tendenciasSimilares.value,
            [indice]: { loading: false, loaded: true, items }
        };
        const escolha = { ...escolhaTendenciaForm.value };
        if (escolha[indice] == null) {
            escolha[indice] = items.length ? items[0].id : 'nova';
            escolhaTendenciaForm.value = escolha;
        }
    } catch (err) {
        tendenciasSimilares.value = {
            ...tendenciasSimilares.value,
            [indice]: { loading: false, loaded: true, items: [], erro: true }
        };
        const escolha = { ...escolhaTendenciaForm.value };
        if (escolha[indice] == null) escolha[indice] = 'nova';
        escolhaTendenciaForm.value = escolha;
    }
}

function opcoesTendenciaSelect(indice) {
    const pack = tendenciasSimilares.value[indice];
    const items = pack?.items || [];
    const opcoes = items.map((t) => {
        const pct =
            t.similaridade != null ? ` · ${Math.round(Number(t.similaridade) * 100)}%` : '';
        const vol = t.volume_total != null ? ` (${t.volume_total} ocorr.)` : '';
        return {
            label: `${t.titulo}${pct}${vol}`,
            value: t.id
        };
    });
    opcoes.push({ label: 'Registrar como nova tendência', value: 'nova' });
    return opcoes;
}

async function aplicarTendenciaDemanda(indiceDemanda) {
    if (!sessionId.value) return;
    const titulo = (tituloTendenciaForm.value[indiceDemanda] || '').trim();
    if (!titulo) {
        toast.add({
            severity: 'warn',
            summary: 'Tendência',
            detail: 'Informe um título para identificar esta solicitação.',
            life: 4000
        });
        return;
    }

    const escolha = escolhaTendenciaForm.value[indiceDemanda];
    const payload = {
        session_id: sessionId.value,
        indice_demanda: indiceDemanda,
        titulo
    };
    if (escolha !== 'nova' && escolha != null) {
        payload.tendencia_id = escolha;
    }

    carregando.value = true;
    try {
        const { data } = await ApiService.confirmarTendenciaCopiloto(payload);
        aplicarRespostaCopiloto(data, {
            limparRevisao:
                revisaoAtiva.value?.etapa === 'servico' &&
                revisaoAtiva.value?.indiceDemanda === indiceDemanda
        });
        const msgIa = (data.resposta_agente || '').trim();
        if (msgIa) adicionarMensagem('assistant', msgIa);
        toast.add({
            severity: 'success',
            summary: 'Tendência registrada',
            detail: 'Solicitação fora da carta vinculada. O ofício pode seguir em rascunho.',
            life: 4000
        });
    } catch (err) {
        const detalhe =
            err?.response?.data?.detail ||
            err?.response?.data?.mensagem ||
            err?.message ||
            'Não foi possível registrar.';
        const is503 = err?.response?.status === 503;
        toast.add({
            severity: 'error',
            summary: is503 ? 'Módulo desativado' : 'Tendência',
            detail: String(detalhe),
            life: 6000
        });
    } finally {
        carregando.value = false;
    }
}

watch(
    escolhaServicoCarta,
    (mapa) => {
        for (const [chave, valor] of Object.entries(mapa || {})) {
            if (valor !== NENHUMA_OPCAO_CARTA) continue;
            const i = Number(chave);
            const d = demandasExtraidas.value[i];
            if (!d) continue;
            const titulos = { ...tituloTendenciaForm.value };
            if (!titulos[i]?.trim()) {
                titulos[i] = (d.titulo || d.descricao || 'Solicitação fora da carta').trim();
            }
            tituloTendenciaForm.value = titulos;
            carregarSimilaresTendencia(i, d);
        }
    },
    { deep: true }
);

const jaPerguntouAnexosNoChat = ref(false);
/** Usuário enviou anexos ou optou por «continuar sem anexos» — oculta o bloco de anexos. */
const etapaAnexosConcluida = ref(false);

/** Etapa de local — após confirmar serviço na carta, antes de anexos. */
const mostrarBlocoEnderecoNoChat = computed(() => {
    if (sucessoCriacao.value || !demandasExtraidas.value.length) return false;
    if (mostrarBlocoForaCompetenciaNoChat.value) return false;
    if (revisaoAtiva.value?.etapa === 'local') return true;
    if (isModoIndicacao.value) {
        if (!todosServicosConfirmados.value || mostrarBlocoServicoNoChat.value) return false;
        return estadoAtual.value === 'COLETA_ENDERECO';
    }
    if (!todosServicosConfirmados.value || mostrarBlocoServicoNoChat.value) return false;
    return estadoAtual.value === 'COLETA_ENDERECO';
});

const mostrarBlocoAnexosNoChat = computed(() => {
    if (sucessoCriacao.value || !demandasExtraidas.value.length) return false;
    if (mostrarBlocoForaCompetenciaNoChat.value) return false;
    if (revisaoAtiva.value?.etapa === 'anexos') return true;
    if (etapaAnexosConcluida.value) return false;
    if (!todosServicosConfirmados.value || mostrarBlocoServicoNoChat.value) return false;
    if (estadoAtual.value === 'COLETA_DADOS' || estadoAtual.value === 'COLETA_ENDERECO') return false;
    return estadoAtual.value === 'VALIDACAO_FINAL';
});

const mostrarAnexarNoCompositor = computed(
    () => {
        if (etapaAnexosConcluida.value || sucessoCriacao.value) return false;
        if (estadoAtual.value === 'COLETA_ENDERECO') return false;
        if (demandasAtivasNoFluxo.value.length > 1 && !todosServicosConfirmados.value) {
            return false;
        }
        return true;
    }
);

watch(todosServicosConfirmados, (ok) => {
    if (!ok) {
        etapaAnexosConcluida.value = false;
        jaPerguntouAnexosNoChat.value = false;
    }
});

function melhorServicoIdPorScore(demanda) {
    const cands = candidatosCartaExibicao(demanda);
    const opcoes = new Set(cands.map((c) => c.servico_id));
    if (sinapseIdValido(demanda?.servico_sugerido_ui_id)) {
        const sugerido = Number(demanda.servico_sugerido_ui_id);
        if (opcoes.has(sugerido)) return sugerido;
    }
    return cands[0]?.servico_id ?? null;
}

function opcoesServicoCarta(demanda) {
    const daCarta = candidatosCartaExibicao(demanda).map((c) => {
        const pct = c.score != null ? ` · ${Math.round(Number(c.score) * 100)}%` : '';
        const badge = c.somente_orientacao ? ' · Só orientação' : '';
        return {
            label: `${c.titulo || 'Serviço'}${pct}${badge}${c.orgao ? ` — ${c.orgao}` : ''}`,
            value: c.servico_id,
            somente_orientacao: Boolean(c.somente_orientacao),
            mensagem_orientacao: c.mensagem_orientacao || ''
        };
    });
    daCarta.push({
        label: 'Nenhuma das opções — registrar como tendência',
        value: NENHUMA_OPCAO_CARTA
    });
    return daCarta;
}

function prepararTendenciaAPartirDaCarta(indiceDemanda) {
    const d = demandasExtraidas.value[indiceDemanda];
    if (!d) return;
    const titulos = { ...tituloTendenciaForm.value };
    if (!titulos[indiceDemanda]?.trim()) {
        titulos[indiceDemanda] = (d.titulo || d.descricao || 'Solicitação fora da carta').trim();
    }
    tituloTendenciaForm.value = titulos;
    escolhaTendenciaForm.value = { ...escolhaTendenciaForm.value, [indiceDemanda]: 'nova' };
    carregarSimilaresTendencia(indiceDemanda, d);
}

async function aplicarHintCorpus(indiceDemanda, hint) {
    const servicoId = hint?.sinapse_servico_id_sugerido_historico;
    if (servicoId == null || !sessionId.value || carregando.value) return;
    escolhaServicoCarta.value = { ...escolhaServicoCarta.value, [indiceDemanda]: servicoId };
    await aplicarServicoCarta(indiceDemanda);
}

async function aplicarServicoCarta(indiceDemanda) {
    const servicoId = escolhaServicoCarta.value[indiceDemanda];
    if (servicoId == null || !sessionId.value) return;
    if (servicoId === NENHUMA_OPCAO_CARTA) {
        prepararTendenciaAPartirDaCarta(indiceDemanda);
        return;
    }
    const opcoes = opcoesServicoCarta(demandasExtraidas.value[indiceDemanda] || {});
    const escolhido = opcoes.find((o) => o.value === servicoId);
    if (escolhido?.somente_orientacao) {
        toast.add({
            severity: 'warn',
            summary: 'Somente orientação',
            detail:
                escolhido.mensagem_orientacao ||
                'Este serviço não gera ofício pelo gabinete. Oriente o munícipe ao canal correto.',
            life: 7000
        });
        return;
    }
    carregando.value = true;
    try {
        const { data } = await ApiService.confirmarServicoCopiloto({
            session_id: sessionId.value,
            indice_demanda: indiceDemanda,
            sinapse_servico_id: servicoId
        });
        aplicarRespostaCopiloto(data, {
            limparRevisao:
                revisaoAtiva.value?.etapa === 'servico' &&
                revisaoAtiva.value?.indiceDemanda === indiceDemanda
        });
        if (data.estado_atual === 'COLETA_ENDERECO') {
            etapaAnexosConcluida.value = false;
        }
        const msgIa = (data.resposta_agente || '').trim();
        if (msgIa) adicionarMensagem('assistant', msgIa);
        toast.add({
            severity: 'success',
            summary: 'Serviço confirmado',
            detail: 'Carta de serviços atualizada para esta solicitação.',
            life: 3000
        });
    } catch (err) {
        const detalhe = err?.response?.data?.detail || err?.message || 'Não foi possível salvar.';
        toast.add({ severity: 'error', summary: 'Carta de serviços', detail: String(detalhe), life: 5000 });
    } finally {
        carregando.value = false;
    }
}

watch(
    demandasExtraidas,
    (lista) => {
        const next = { ...escolhaServicoCarta.value };
        const fps = { ...candidatosFingerprint.value };
        lista.forEach((d, i) => {
            if (servicoConfirmado(d)) {
                const sid = d?.servico?.sinapse_servico_id ?? d?.sinapse_servico_id_sugerido;
                if (sinapseIdValido(sid)) next[i] = Number(sid);
                return;
            }
            const fp = fingerprintCandidatos(d);
            const fpAnterior = fps[i];
            fps[i] = fp;
            const opcoesValidas = new Set(opcoesServicoCarta(d).map((o) => o.value));
            const sugerido = melhorServicoIdPorScore(d);
            if (fpAnterior !== fp) {
                next[i] = sugerido != null && opcoesValidas.has(sugerido) ? sugerido : null;
            } else if (next[i] != null && !opcoesValidas.has(next[i])) {
                next[i] = sugerido != null && opcoesValidas.has(sugerido) ? sugerido : null;
            } else if (next[i] == null && sugerido != null && opcoesValidas.has(sugerido)) {
                next[i] = sugerido;
            }
        });
        candidatosFingerprint.value = fps;
        escolhaServicoCarta.value = next;
    },
    { deep: true }
);

async function novaBuscaSemantica(indiceDemanda) {
    if (!sessionId.value) return;
    carregando.value = true;
    try {
        const { data } = await ApiService.retriagemCartaCopiloto({
            session_id: sessionId.value,
            indice_demanda: indiceDemanda
        });
        if (Array.isArray(data.demandas_extraidas)) demandasExtraidas.value = data.demandas_extraidas;
        if (data.estado_atual) estadoAtual.value = data.estado_atual;
        const msg = (data.resposta_agente || '').trim();
        if (msg) adicionarMensagem('assistant', msg);
    } catch (err) {
        toast.add({
            severity: 'error',
            summary: 'Busca na carta',
            detail: String(err?.response?.data?.detail || err?.message || 'Falha'),
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
}

async function ignorarSugestoesCarta(indiceDemanda) {
    if (!sessionId.value) return;
    carregando.value = true;
    try {
        const { data } = await ApiService.ignorarServicoCopiloto({
            session_id: sessionId.value,
            indice_demanda: indiceDemanda
        });
        if (Array.isArray(data.demandas_extraidas)) demandasExtraidas.value = data.demandas_extraidas;
        if (data.estado_atual) estadoAtual.value = data.estado_atual;
        escolhaServicoCarta.value = { ...escolhaServicoCarta.value, [indiceDemanda]: NENHUMA_OPCAO_CARTA };
        prepararTendenciaAPartirDaCarta(indiceDemanda);
        const msg = (data.resposta_agente || '').trim();
        if (msg) adicionarMensagem('assistant', msg);
    } catch (err) {
        toast.add({
            severity: 'error',
            summary: 'Carta',
            detail: String(err?.response?.data?.detail || err?.message || 'Falha'),
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
}

async function descartarSolicitacao(indiceDemanda) {
    if (!sessionId.value) return;
    carregando.value = true;
    try {
        const { data } = await ApiService.marcarDemandaCopiloto({
            session_id: sessionId.value,
            indice_demanda: indiceDemanda,
            descartada: true
        });
        if (data.session_id) sessionId.value = data.session_id;
        if (Array.isArray(data.demandas_extraidas)) demandasExtraidas.value = data.demandas_extraidas;
        if (data.estado_atual) estadoAtual.value = data.estado_atual;
        aprovacaoFinal.value = { ...aprovacaoFinal.value, [indiceDemanda]: false };
        const esc = { ...escolhaServicoCarta.value };
        delete esc[indiceDemanda];
        escolhaServicoCarta.value = esc;
        anexosPendentes.value = anexosPendentes.value.map((a) =>
            a.indiceDemanda === indiceDemanda ? { ...a, indiceDemanda: null } : a
        );
        toast.add({
            severity: 'info',
            summary: 'Solicitação descartada',
            detail: 'Este item não entrará no ofício. Você pode restaurá-lo a qualquer momento.',
            life: 3500
        });
    } catch (err) {
        toast.add({
            severity: 'error',
            summary: 'Descartar',
            detail: String(err?.response?.data?.detail || err?.message || 'Falha'),
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
}

async function restaurarSolicitacao(indiceDemanda) {
    if (!sessionId.value) return;
    carregando.value = true;
    try {
        const { data } = await ApiService.marcarDemandaCopiloto({
            session_id: sessionId.value,
            indice_demanda: indiceDemanda,
            descartada: false
        });
        if (data.session_id) sessionId.value = data.session_id;
        if (Array.isArray(data.demandas_extraidas)) demandasExtraidas.value = data.demandas_extraidas;
        if (data.estado_atual) estadoAtual.value = data.estado_atual;
    } catch (err) {
        toast.add({
            severity: 'error',
            summary: 'Restaurar',
            detail: String(err?.response?.data?.detail || err?.message || 'Falha'),
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
}

function usarLocalizacaoAtual(indiceDemanda) {
    if (!navigator.geolocation) {
        toast.add({
            severity: 'warn',
            summary: 'GPS',
            detail: 'Geolocalização não disponível neste navegador.',
            life: 4000
        });
        return;
    }
    carregando.value = true;
    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            try {
                const { data } = await ApiService.atualizarLocalizacaoCopiloto({
                    session_id: sessionId.value,
                    indice_demanda: indiceDemanda,
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude
                });
                aplicarRespostaCopiloto(data, {
                    limparRevisao:
                        revisaoAtiva.value?.etapa === 'local' &&
                        revisaoAtiva.value?.indiceDemanda === indiceDemanda
                });
                toast.add({ severity: 'success', summary: 'Localização', detail: 'GPS registrado.', life: 3000 });
            } catch (err) {
                toast.add({
                    severity: 'error',
                    summary: 'GPS',
                    detail: String(err?.response?.data?.detail || err?.message || 'Falha'),
                    life: 5000
                });
            } finally {
                carregando.value = false;
            }
        },
        () => {
            carregando.value = false;
            toast.add({
                severity: 'warn',
                summary: 'GPS',
                detail: 'Permissão negada ou indisponível.',
                life: 4000
            });
        },
        { enableHighAccuracy: true, timeout: 15000 }
    );
}

async function ajustarMapaCopiloto(indiceDemanda, { latitude, longitude }) {
    if (!sessionId.value) return;

    const lista = [...demandasExtraidas.value];
    const atual = lista[indiceDemanda];
    if (atual) {
        lista[indiceDemanda] = {
            ...atual,
            latitude,
            longitude,
            coordenadas_fonte: 'ajuste_mapa',
            coordenadas_observacao: 'Ponto ajustado manualmente no mapa.'
        };
        demandasExtraidas.value = lista;
    }

    carregando.value = true;
    try {
        const { data } = await ApiService.atualizarLocalizacaoCopiloto({
            session_id: sessionId.value,
            indice_demanda: indiceDemanda,
            latitude,
            longitude,
            fonte: 'ajuste_mapa',
            confirmar_local: false
        });
        aplicarRespostaCopiloto(data, {
            limparRevisao:
                revisaoAtiva.value?.etapa === 'local' &&
                revisaoAtiva.value?.indiceDemanda === indiceDemanda
        });
        const d = data.demandas_extraidas?.[indiceDemanda];
        if (d?.latitude != null && d?.longitude != null) {
            toast.add({
                severity: 'info',
                summary: 'Mapa',
                detail: `Ponto ajustado (${Number(d.latitude).toFixed(6)}, ${Number(d.longitude).toFixed(6)}). Confirme o local quando estiver correto.`,
                life: 4000
            });
        }
    } catch (err) {
        toast.add({
            severity: 'error',
            summary: 'Mapa',
            detail: String(err?.response?.data?.detail || err?.message || 'Falha ao ajustar o ponto'),
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
}

/** Formulário estruturado de endereço (Fase 2 — autocomplete alinhado ao DemandaForm). */
const enderecoFormCopiloto = ref({});
const sugLogradourosCopiloto = ref([]);
const buscandoLogradourosCopiloto = ref(false);
const indiceAutocompleteLogradouro = ref(0);
let debounceLogradouroCopiloto = null;

function obterFormEnderecoCopiloto(indice) {
    const atual = enderecoFormCopiloto.value[indice];
    const d = demandasExtraidas.value[indice];
    const end = d?.endereco && typeof d.endereco === 'object' ? d.endereco : {};
    const snapshot = {
        cep: end.cep || '',
        logradouro: end.logradouro || '',
        bairro: end.bairro || '',
        numero: end.numero || '',
    };
    if (!atual) {
        enderecoFormCopiloto.value = { ...enderecoFormCopiloto.value, [indice]: { ...snapshot } };
        return enderecoFormCopiloto.value[indice];
    }
    const mudou =
        (atual.logradouro || '') !== (snapshot.logradouro || '') ||
        (atual.bairro || '') !== (snapshot.bairro || '') ||
        (atual.cep || '') !== (snapshot.cep || '');
    if (mudou && !carregando.value) {
        enderecoFormCopiloto.value = {
            ...enderecoFormCopiloto.value,
            [indice]: { ...atual, ...snapshot },
        };
    }
    return enderecoFormCopiloto.value[indice];
}

function searchLogradouroCopiloto(event, indice) {
    indiceAutocompleteLogradouro.value = indice;
    const termo = (event.query || '').trim();
    if (debounceLogradouroCopiloto) {
        clearTimeout(debounceLogradouroCopiloto);
    }
    if (termo.length < 3) {
        sugLogradourosCopiloto.value = [];
        return;
    }
    const form = obterFormEnderecoCopiloto(indice);
    debounceLogradouroCopiloto = setTimeout(async () => {
        buscandoLogradourosCopiloto.value = true;
        try {
            const bairro = (form.bairro || '').trim() || null;
            const { data } = await ApiService.buscarLogradouros(termo, bairro);
            sugLogradourosCopiloto.value = data.resultados || [];
        } catch {
            sugLogradourosCopiloto.value = [];
        } finally {
            buscandoLogradourosCopiloto.value = false;
        }
    }, 350);
}

function onLogradouroSelecionadoCopiloto(event, indice) {
    const item = event.value;
    if (!item || typeof item === 'string') return;
    const form = obterFormEnderecoCopiloto(indice);
    form.logradouro = item.logradouro || item.label || form.logradouro;
    if (item.bairro) form.bairro = item.bairro;
    if (item.cep) form.cep = item.cep;
}

async function buscarCepCopiloto(indice) {
    const form = obterFormEnderecoCopiloto(indice);
    const cepLimpo = form.cep ? String(form.cep).replace(/\D/g, '') : '';
    if (cepLimpo.length !== 8) return;
    try {
        const { data } = await ApiService.buscarCepGeocoding(cepLimpo);
        form.logradouro = data.logradouro || form.logradouro;
        form.bairro = data.bairro || form.bairro;
        form.cep = data.cep || form.cep;
        toast.add({
            severity: 'success',
            summary: 'CEP',
            detail: 'Logradouro e bairro preenchidos via ViaCEP.',
            life: 3000,
        });
    } catch (err) {
        toast.add({
            severity: 'error',
            summary: 'CEP',
            detail: String(err?.response?.data?.detail || 'CEP não encontrado.'),
            life: 3500,
        });
    }
}

async function aplicarEnderecoCopiloto(indice) {
    if (!sessionId.value || carregando.value) return;
    const form = obterFormEnderecoCopiloto(indice);
    const logr = (form.logradouro || '').trim();
    const bairro = (form.bairro || '').trim();
    const cep = (form.cep || '').trim();
    if (!logr && !bairro && cep.replace(/\D/g, '').length < 8) {
        toast.add({
            severity: 'warn',
            summary: 'Endereço',
            detail: 'Informe CEP ou logradouro com bairro.',
            life: 4000,
        });
        return;
    }
    carregando.value = true;
    try {
        const { data } = await ApiService.editarLocalCopiloto({
            session_id: sessionId.value,
            indice_demanda: indice,
            endereco: {
                cep: cep || undefined,
                logradouro: logr || undefined,
                bairro: bairro || undefined,
                numero: (form.numero || '').trim() || undefined,
            },
        });
        aplicarRespostaCopiloto(data, {
            limparRevisao:
                revisaoAtiva.value?.etapa === 'local' &&
                revisaoAtiva.value?.indiceDemanda === indice,
        });
    } catch (err) {
        toast.add({
            severity: 'error',
            summary: 'Endereço',
            detail: String(err?.response?.data?.detail || err?.message || 'Falha ao aplicar endereço.'),
            life: 5000,
        });
    } finally {
        carregando.value = false;
    }
}

function indicesAprovadosParaFinalizar() {
    const lista = demandasExtraidas.value;
    if (lista.length <= 1) {
        return lista.some((d) => !d?.descartada && !demandaForaCompetencia(d)) ? [0] : [];
    }
    return lista
        .map((d, i) => ({ d, i }))
        .filter(
            ({ d, i }) =>
                !d?.descartada &&
                !demandaForaCompetencia(d) &&
                aprovacaoFinal.value[i] !== false
        )
        .map(({ i }) => i);
}

async function recusarGeracaoRascunhos() {
    if (carregando.value) return;
    await enviarMensagem('não');
}

async function finalizarComAprovacao() {
    const indices = indicesAprovadosParaFinalizar();
    if (!indices.length) {
        toast.add({
            severity: 'warn',
            summary: 'Finalizar',
            detail: 'Marque pelo menos uma solicitação para gerar rascunho.',
            life: 4000
        });
        return;
    }
    if (isModoIndicacao.value && !indicacaoProntaParaFinalizar.value) {
        toast.add({
            severity: 'warn',
            summary: 'Indicação',
            detail: 'Vincule vereadores, informe o número e anexe o PDF assinado.',
            life: 5000
        });
        return;
    }
    const payload = { mensagem: 'finalizar', indices_aprovados: indices };
    if (sessionId.value) payload.session_id = sessionId.value;
    carregando.value = true;
    try {
        const { data } = await ApiService.interagirCopiloto(payload);
        if (data.session_id) sessionId.value = data.session_id;
        if (data.estado_atual) estadoAtual.value = data.estado_atual;
        if (Array.isArray(data.demandas_extraidas)) demandasExtraidas.value = data.demandas_extraidas;
        const textoIa = (data.resposta_agente || '').trim();
        if (textoIa) adicionarMensagem('assistant', textoIa);
        if (Array.isArray(data.demandas_criadas) && data.demandas_criadas.length) {
            sucessoCriacao.value = data.demandas_criadas;
        }
    } catch (err) {
        toast.add({
            severity: 'error',
            summary: 'Copiloto',
            detail: String(err?.response?.data?.detail || err?.message || 'Falha'),
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
}

watch(
    demandasExtraidas,
    (lista) => {
        const next = { ...aprovacaoFinal.value };
        const descartados = new Set();
        lista.forEach((d, i) => {
            if (d?.descartada) {
                next[i] = false;
                descartados.add(i);
            } else if (next[i] === undefined && !demandaForaCompetencia(d)) {
                next[i] = d?.aprovado_final !== false;
            }
        });
        aprovacaoFinal.value = next;
        if (descartados.size) {
            anexosPendentes.value = anexosPendentes.value.map((a) =>
                descartados.has(a.indiceDemanda) ? { ...a, indiceDemanda: null } : a
            );
        }
    },
    { deep: true }
);

async function confirmarTodosServicosCarta() {
    const pendentes = demandasComCartaNoChat.value.filter(
        ({ d, i }) =>
            !d?.descartada &&
            !servicoConfirmado(d) &&
            escolhaServicoCarta.value[i] != null &&
            escolhaServicoCarta.value[i] !== NENHUMA_OPCAO_CARTA
    );
    for (const { i } of pendentes) {
        await aplicarServicoCarta(i);
    }
}

function pularAnexos() {
    if (etapaAnexosConcluida.value) return;
    return enviarMensagem('continuar sem anexos');
}

function marcarEtapaAnexosConcluida(textoUsuario, tinhaAnexos) {
    if (isModoIndicacao.value) {
        const t = (textoUsuario || '').trim();
        if (/^confirmar\s+(?:os\s+)?(?:documentos|anexos)/i.test(t) && temPdfIndicacao.value) {
            etapaAnexosConcluida.value = true;
        }
        return;
    }
    const t = (textoUsuario || '').trim().toLowerCase();
    if (
        tinhaAnexos ||
        /^continuar\s+sem\s+anexos?\.?$/.test(t) ||
        /^confirmar\s+(?:os\s+)?(?:documentos|anexos)/i.test(t)
    ) {
        etapaAnexosConcluida.value = true;
    }
}

function aplicarRespostaCopiloto(data, { limparRevisao = false } = {}) {
    if (data.session_id) sessionId.value = data.session_id;
    if (Array.isArray(data.demandas_extraidas)) {
        demandasExtraidas.value = data.demandas_extraidas;
    }
    if (data.estado_atual) estadoAtual.value = data.estado_atual;
    if (isModoIndicacao.value && Array.isArray(data.demandas_extraidas) && !temPdfIndicacao.value) {
        etapaAnexosConcluida.value = false;
    }
    if (Array.isArray(data.corpus_atalhos_top_trends) && data.corpus_atalhos_top_trends.length) {
        atalhosTopTrends.value = data.corpus_atalhos_top_trends;
    }
    if (data.reabrir_anexos) etapaAnexosConcluida.value = false;
    if (data.revisao_encerrada) {
        revisaoAtiva.value = null;
    }
    if (data.revisao_etapa != null && data.revisao_indice_demanda != null) {
        revisaoAtiva.value = {
            indiceDemanda: data.revisao_indice_demanda,
            etapa: data.revisao_etapa
        };
    } else if (limparRevisao) {
        revisaoAtiva.value = null;
    }
}

async function scrollParaBlocoEtapa(etapa) {
    await nextTick();
    const seletor =
        etapa === 'servico'
            ? '[data-copiloto-bloco="servico"]'
            : etapa === 'local'
              ? '[data-copiloto-bloco="local"]'
              : etapa === 'anexos'
                ? '[data-copiloto-bloco="anexos"]'
                : null;
    if (!seletor) return;
    listaChatRef.value?.querySelector(seletor)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function revisarEtapa({ indice, etapa }) {
    if (!sessionId.value) {
        toast.add({
            severity: 'warn',
            summary: 'Copiloto',
            detail: 'Inicie a conversa antes de revisar uma etapa.',
            life: 4000
        });
        return;
    }
    carregando.value = true;
    try {
        const { data } = await ApiService.revisarEtapaCopiloto({
            session_id: sessionId.value,
            indice_demanda: indice,
            etapa
        });
        aplicarRespostaCopiloto(data);
        const msgIa = (data.resposta_agente || '').trim();
        if (msgIa) adicionarMensagem('assistant', msgIa);
        painelContextoAberto.value = false;
        if (etapa === 'servico' || etapa === 'local' || etapa === 'anexos') {
            await scrollParaBlocoEtapa(etapa);
        }
        await nextTick();
        listaChatRef.value?.closest('.flex-col')?.querySelector('textarea')?.focus();
    } catch (err) {
        const detalhe = err?.response?.data?.detail || err?.message || 'Não foi possível reabrir a etapa.';
        toast.add({ severity: 'error', summary: 'Revisar', detail: String(detalhe), life: 5000 });
    } finally {
        carregando.value = false;
    }
}

function confirmarLocalDemanda(indiceDemanda) {
    const n = indiceDemanda + 1;
    return enviarMensagem(
        demandasExtraidas.value.length > 1
            ? `confirmar local solicitação ${n}`
            : 'confirmar local'
    );
}

function confirmarDocumentos() {
    if (isModoIndicacao.value && !temPdfIndicacao.value) {
        toast.add({
            severity: 'warn',
            summary: 'Indicação',
            detail: 'Anexe o PDF da indicação assinada antes de continuar.',
            life: 5000
        });
        return;
    }
    return enviarMensagem('confirmar documentos');
}

async function removerAnexoSalvo(indiceSessao) {
    if (!sessionId.value) return;
    carregando.value = true;
    try {
        const { data } = await ApiService.removerAnexoSessaoCopiloto({
            session_id: sessionId.value,
            indice_sessao: indiceSessao
        });
        aplicarRespostaCopiloto(data);
        toast.add({ severity: 'success', summary: 'Anexos', detail: 'Arquivo removido.', life: 3000 });
    } catch (err) {
        const detalhe = err?.response?.data?.detail || err?.message || 'Falha ao remover.';
        toast.add({ severity: 'error', summary: 'Anexos', detail: String(detalhe), life: 5000 });
    } finally {
        carregando.value = false;
    }
}

function anexosSalvosDemanda(indiceDemanda) {
    const d = demandasExtraidas.value[indiceDemanda];
    return Array.isArray(d?.anexos) ? d.anexos : [];
}

const temAnexosSalvosNaSessao = computed(() =>
    demandasExtraidas.value.some((_, i) => anexosSalvosDemanda(i).length > 0)
);

const demandasEscopoLocal = computed(() => {
    const idxRev =
        revisaoAtiva.value?.etapa === 'local' ? revisaoAtiva.value.indiceDemanda : null;
    const base = demandasExtraidas.value
        .map((d, i) => ({ d, i }))
        .filter(
            ({ d }) =>
                d?.requer_localizacao !== false &&
                !d?.descartada &&
                !demandaForaCompetencia(d) &&
                !d?.endereco_opcional_dispensado
        );
    if (idxRev != null) return base.filter(({ i }) => i === idxRev);
    if (estadoAtual.value === 'COLETA_ENDERECO') {
        if (isModoIndicacao.value) {
            const ind = base.filter(({ d }) => d?.modo_indicacao);
            if (ind.length) return ind;
        }
        return base.filter(
            ({ d }) => d.local_pendente_confirmacao === true || demandaPodeConfirmarLocal(d)
        );
    }
    return base;
});

const indiceDemandaGps = computed(() => {
    if (revisaoAtiva.value?.etapa === 'local') {
        return revisaoAtiva.value.indiceDemanda;
    }
    return demandasEscopoLocal.value[0]?.i ?? 0;
});

const labelGpsCopiloto = computed(() => {
    const idx = indiceDemandaGps.value;
    if (demandasExtraidas.value.length > 1) {
        return `Usar minha localização (solicitação ${idx + 1})`;
    }
    return 'Usar minha localização';
});

const indiceDemandaRevisaoAnexos = computed(() =>
    revisaoAtiva.value?.etapa === 'anexos' ? revisaoAtiva.value.indiceDemanda : null
);

function emRevisaoDemanda(indice, etapa) {
    return revisaoAtiva.value?.etapa === etapa && revisaoAtiva.value?.indiceDemanda === indice;
}

const mostrarVinculoAnexoDemanda = computed(
    () => demandasAtivasNoFluxo.value.length > 1 && anexosPendentes.value.length > 0
);

const anexosSemVinculo = computed(() =>
    mostrarVinculoAnexoDemanda.value
        ? anexosPendentes.value.filter((a) => a.indiceDemanda === null || a.indiceDemanda === undefined)
        : []
);

watch(
    () => demandasExtraidas.value.length,
    (n, prev) => {
        if (n === 1) {
            anexosPendentes.value = anexosPendentes.value.map((a) => ({
                ...a,
                indiceDemanda: 0
            }));
        } else if (n > 1 && prev === 1) {
            anexosPendentes.value = anexosPendentes.value.map((a) => ({
                ...a,
                indiceDemanda: null
            }));
        }
    }
);

const indiceUltimaMensagemAssistente = computed(() => {
    for (let i = mensagens.value.length - 1; i >= 0; i--) {
        if (mensagens.value[i].role === 'assistant') return i;
    }
    return -1;
});

const ultimaMensagemAssistente = computed(() => {
    const idx = indiceUltimaMensagemAssistente.value;
    if (idx < 0) return '';
    return mensagens.value[idx].texto || '';
});

const temCartaSinapseNoRascunho = computed(() =>
    demandasExtraidas.value.some((d) => (d?.candidatos_sinapse?.length || 0) > 0)
);

/** Texto de triagem da carta — redundante com o card «Serviço na carta». */
function mensagemRelacionadaFluxoCarta(texto) {
    const t = (texto || '').trim();
    if (!t) return false;
    const low = t.toLowerCase();
    if (/(consultei a carta|similaridade|op[cç][õo]es mais pr[oó]ximas)/i.test(low)) {
        return true;
    }
    if (/escolha no painel/i.test(low) && /(carta oficial|servi[cç]o na carta|tend[eê]ncia)/i.test(low)) {
        return true;
    }
    if (/^entendi:/i.test(t) && /painel/i.test(low)) {
        return true;
    }
    if (extrairOpcoesNumeradas(t).length >= 2 && /carta/i.test(low)) {
        return true;
    }
    return false;
}

function ocultarBolhaAssistenteNoChat(m) {
    if (m.role !== 'assistant') return false;
    if (!mensagemRelacionadaFluxoCarta(m.texto)) return false;
    if (todosServicosConfirmados.value) return true;
    if (mostrarBlocoServicoNoChat.value) return true;
    if (temCartaSinapseNoRascunho.value) return true;
    return false;
}

function extrairOpcoesNumeradas(texto) {
    const fonte = texto || '';
    const seen = new Set();
    const out = [];

    function tryAdd(num, label) {
        const n = String(num).replace(/^0+/, '') || String(num);
        const lb = (label || '')
            .trim()
            .replace(/\s+/g, ' ')
            .replace(/[,;]\s*$/, '');
        if (!n || !lb || lb.length < 3) return;
        if (seen.has(n)) return;
        seen.add(n);
        out.push({ numero: n, label: lb });
    }

    const p1 = /^\s*(\d+)\.\s+(.+)$/gm;
    let m;
    while ((m = p1.exec(fonte)) !== null) tryAdd(m[1], m[2]);

    const p2 = /^\s*(\d+)\)\s*(.+)$/gm;
    while ((m = p2.exec(fonte)) !== null) tryAdd(m[1], m[2]);

    const p3 = /(?:^|[\s,;])(\d+)\s*[-–]\s*([^,;\n]+?)(?=(?:\s*[,;]\s*)?\d+\s*[-–)\.]|\s*$)/g;
    while ((m = p3.exec(fonte)) !== null) tryAdd(m[1], m[2]);

    const p4 = /(\d+)\)\s*([^,;\n]+?)(?=\s*(?:,|\s+ou\s+|\s+e\s+)\d+\)|$)/gi;
    while ((m = p4.exec(fonte)) !== null) tryAdd(m[1], m[2]);

    out.sort((a, b) => parseInt(a.numero, 10) - parseInt(b.numero, 10));
    return out;
}

const opcoesNumeradasDetectadas = computed(() => extrairOpcoesNumeradas(ultimaMensagemAssistente.value));

function anexoEhPdf(nome) {
    return (nome || '').toLowerCase().endsWith('.pdf');
}

function temPdfNaDemanda(indice) {
    const salvos = anexosSalvosDemanda(indice);
    if (salvos.some((a) => anexoEhPdf(a.nome))) return true;
    return anexosPendentes.value.some(
        (a) =>
            (a.indiceDemanda === indice || (demandasExtraidas.value.length === 1 && indice === 0)) &&
            anexoEhPdf(a.file?.name)
    );
}

const temPdfIndicacao = computed(() => {
    if (!isModoIndicacao.value) return true;
    return demandasParaAprovacaoFinal.value.every(({ i }) => temPdfNaDemanda(i));
});

function indicacaoMetadadosOk(demanda) {
    const ids = demanda?.vereadores_vinculados_ids || [];
    return ids.length > 0 && Number(demanda?.numero_indicacao) >= 1;
}

const indicacaoProntaParaFinalizar = computed(() => {
    if (!isModoIndicacao.value) return true;
    if (!todosServicosConfirmados.value) return false;
    const ativas = demandasParaAprovacaoFinal.value;
    if (!ativas.length) return false;
    return ativas.every(({ d, i }) => indicacaoMetadadosOk(d) && temPdfNaDemanda(i));
});

const mostrarMetadadosIndicacao = computed(() => {
    if (!isModoIndicacao.value) return false;
    if (estadoAtual.value !== 'VALIDACAO_FINAL') return false;
    if (!demandasParaAprovacaoFinal.value.length) return false;
    return etapaAnexosConcluida.value;
});

const mostrarSimNaoValidacao = computed(() => {
    if (carregando.value || sucessoCriacao.value) return false;
    if (estadoAtual.value !== 'VALIDACAO_FINAL') return false;
    if (!todosServicosConfirmados.value) return false;
    if (mostrarBlocoServicoNoChat.value) return false;
    if (isModoIndicacao.value) {
        return indicacaoProntaParaFinalizar.value && etapaAnexosConcluida.value;
    }
    return etapaAnexosConcluida.value;
});

const mostrarOpcoesSinapse = computed(() => {
    if (mostrarBlocoServicoNoChat.value || mostrarBlocoTendenciaNoChat.value) return false;
    if (carregando.value || sucessoCriacao.value || mostrarSimNaoValidacao.value) return false;
    const op = opcoesNumeradasDetectadas.value;
    if (op.length < 1) return false;
    if (estadoAtual.value === 'CONFIRMACAO_SINAPSE') return true;
    const t = ultimaMensagemAssistente.value;
    if (!t) return false;
    const low = t.toLowerCase();
    return /(opç|opc|escolh|servi[cç]o|lista abaixo|carta)/i.test(low);
});

const mostrarSimNaoBinario = computed(() => {
    if (
        mostrarBlocoServicoNoChat.value ||
        mostrarBlocoTendenciaNoChat.value ||
        carregando.value ||
        sucessoCriacao.value ||
        mostrarSimNaoValidacao.value ||
        mostrarOpcoesSinapse.value
    ) {
        return false;
    }
    const t = ultimaMensagemAssistente.value;
    if (!t || !t.includes('?')) return false;
    const trecho = t.slice(-320).toLowerCase();
    return (
        (trecho.includes('sim') && (trecho.includes('não') || trecho.includes('nao'))) ||
        (trecho.includes('sim ou não') || trecho.includes('sim ou nao'))
    );
});

const temMensagemUsuario = computed(() => mensagens.value.some((m) => m.role === 'user'));

const mostrarAtalhosTopTrends = computed(() => {
    if (carregando.value || sucessoCriacao.value) return false;
    if (estadoAtual.value !== 'COLETA_DADOS') return false;
    if (temMensagemUsuario.value) return false;
    if (mostrarOpcoesSinapse.value || mostrarSimNaoBinario.value) return false;
    return atalhosTopTrends.value.length > 0 && !atalhoEmDetalhamento.value;
});

const mostrarDetalheAtalho = computed(() => Boolean(atalhoEmDetalhamento.value));

const atalhosTopTrendsVisiveis = computed(() => {
    const lista = atalhosTopTrends.value;
    if (atalhosTopTrendsExpandido.value) return lista;
    return lista.slice(0, LIMITE_ATALHOS_VISIVEIS);
});

async function carregarAtalhosTopTrends() {
    try {
        const { data } = await ApiService.corpusLegadoAtalhosCopiloto(12);
        const lista = Array.isArray(data?.atalhos) ? data.atalhos : [];
        const filtrada = lista.filter((a) => (a?.rotulo || '').trim().toLowerCase() !== 'outros');
        if (filtrada.length) {
            atalhosTopTrends.value = filtrada;
        }
    } catch {
        // chips opcionais — falha silenciosa
    }
}

function rotuloAtalho(atalho) {
    return (atalho?.rotulo || 'Pedido').trim();
}

function cancelarDetalheAtalho() {
    atalhoEmDetalhamento.value = null;
    opcoesCartaAtalho.value = [];
}

async function usarAtalhoTopTrend(atalho) {
    const opcoesInline = Array.isArray(atalho?.opcoes_carta) ? atalho.opcoes_carta : [];
    const precisaDetalhe =
        atalho?.tem_detalhamento && (opcoesInline.length > 1 || (atalho?.qtd_opcoes_carta ?? 0) > 1);

    if (precisaDetalhe) {
        atalhoEmDetalhamento.value = atalho;
        opcoesCartaAtalho.value = opcoesInline;
        if (!opcoesInline.length && atalho?.id) {
            carregandoDetalheAtalho.value = true;
            try {
                const { data } = await ApiService.corpusLegadoAtalhoDetalhe(atalho.id);
                opcoesCartaAtalho.value = Array.isArray(data?.opcoes_carta) ? data.opcoes_carta : [];
            } catch {
                toast.add({
                    severity: 'warn',
                    summary: 'Pedidos frequentes',
                    detail: 'Não foi possível carregar os serviços da carta. Tente digitar o pedido.',
                    life: 4000
                });
                cancelarDetalheAtalho();
            } finally {
                carregandoDetalheAtalho.value = false;
            }
        }
        return;
    }

    const padraoId = atalho?.servico_padrao_id ?? opcoesInline[0]?.servico_id;
    await enviarMensagemComAtalho(atalho, padraoId ? { servico_id: padraoId } : null);
}

async function enviarMensagemComAtalho(atalho, opcao) {
    const base = (inputTexto.value || '').trim();
    const textoPadrao = atalho?.texto_sugerido || `Solicito ${(atalho?.rotulo || 'serviço').toLowerCase()}.`;
    const texto = base || textoPadrao;
    const extras = {
        corpus_atalho_id: atalho?.id || atalho?.eixo_id || null
    };
    if (opcao?.servico_id != null) {
        extras.corpus_sinapse_servico_id = opcao.servico_id;
    }
    cancelarDetalheAtalho();
    await enviarMensagem(texto, extras);
}

function rotuloOpcaoCartaAtalho(opcao) {
    const titulo = (opcao?.titulo || 'Serviço').trim();
    if (opcao?.padrao) {
        return `${titulo} (mais comum)`;
    }
    return titulo;
}

watch(
    [
        mostrarBlocoServicoNoChat,
        mostrarBlocoComplementoNoChat,
        mostrarBlocoForaCompetenciaNoChat,
        mostrarBlocoTendenciaNoChat,
        mostrarBlocoAnexosNoChat,
        mostrarSimNaoValidacao
    ],
    () => rolarParaOFim()
);

function adicionarMensagem(role, texto) {
    mensagens.value.push({
        role,
        texto,
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    });
}

function indiceDemandaPadraoParaNovoAnexo() {
    const n = demandasExtraidas.value.length;
    if (n === 1) return 0;
    return null;
}

function onSelecionarAnexos(event) {
    const files = event?.target?.files;
    if (!files?.length) return;
    const padrao = indiceDemandaPadraoParaNovoAnexo();
    const existentes = anexosPendentes.value.map((a) => normalizarNomeArquivo(a.file?.name));
    const { aceitos, rejeitados } = filtrarArquivosDuplicados(Array.from(files), existentes);

    if (rejeitados.length) {
        toast.add({
            severity: 'warn',
            summary: 'Anexo duplicado',
            detail: mensagemAnexosRejeitados(rejeitados),
            life: 5000
        });
    }
    if (!aceitos.length) {
        if (inputAnexosRef.value) {
            inputAnexosRef.value.value = '';
        }
        return;
    }

    const novos = aceitos.map((file) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
        file,
        indiceDemanda: padrao
    }));
    anexosPendentes.value = [...anexosPendentes.value, ...novos];
    if (inputAnexosRef.value) {
        inputAnexosRef.value.value = '';
    }
}

function removerAnexoPendente(indice) {
    anexosPendentes.value = anexosPendentes.value.filter((_, i) => i !== indice);
}

function abrirSeletorAnexos() {
    inputAnexosRef.value?.click();
}

const podeEnviar = computed(() => {
    const temTexto = inputTexto.value.trim().length > 0;
    const temAnexos = anexosPendentes.value.length > 0;
    if (!temTexto && !temAnexos) return false;
    if (mostrarVinculoAnexoDemanda.value && anexosSemVinculo.value.length > 0) {
        return false;
    }
    return true;
});

/** @param {string} [textoOpcional] — se omitido, usa o conteúdo do campo de texto */
/** @param {{ corpus_atalho_id?: string, corpus_sinapse_servico_id?: number }} [extras] */
async function enviarMensagem(textoOpcional, extras = {}) {
    const texto =
        textoOpcional !== undefined && textoOpcional !== null
            ? String(textoOpcional).trim()
            : inputTexto.value.trim();
    const pendentes = [...anexosPendentes.value];
    if ((!texto && !pendentes.length) || carregando.value) return;

    if (mostrarVinculoAnexoDemanda.value && pendentes.some((p) => p.indiceDemanda === null)) {
        toast.add({
            severity: 'warn',
            summary: 'Anexos',
            detail: 'Selecione a solicitação de cada anexo antes de enviar.',
            life: 4000
        });
        return;
    }

    const rotuloUsuario =
        texto ||
        (pendentes.length === 1
            ? `📎 ${pendentes[0].file.name}`
            : `📎 ${pendentes.length} anexos enviados`);
    adicionarMensagem('user', rotuloUsuario);
    marcarEtapaAnexosConcluida(texto, pendentes.length > 0);
    inputTexto.value = '';
    anexosPendentes.value = [];
    carregando.value = true;

    try {
        const payload = { mensagem: texto };
        if (sessionId.value) {
            payload.session_id = sessionId.value;
        }
        if (pendentes.length) {
            payload.anexos = pendentes.map((p) => p.file);
            payload.anexo_demanda_indices = pendentes.map((p) => p.indiceDemanda);
        }
        if (extras.corpus_atalho_id) {
            payload.corpus_atalho_id = extras.corpus_atalho_id;
        }
        if (extras.corpus_sinapse_servico_id != null) {
            payload.corpus_sinapse_servico_id = extras.corpus_sinapse_servico_id;
        }

        const { data } = await ApiService.interagirCopiloto(payload);

        if (data.session_id) {
            sessionId.value = data.session_id;
        }
        aplicarRespostaCopiloto(data);
        if (data.reabrir_anexos) {
            etapaAnexosConcluida.value = false;
        }
        if (
            isModoIndicacao.value &&
            pendentes.some((p) => anexoEhPdf(p.file?.name)) &&
            demandasParaAprovacaoFinal.value.every(({ i }) => temPdfNaDemanda(i))
        ) {
            etapaAnexosConcluida.value = true;
        }

        const rev = revisaoAtiva.value;
        if (
            rev?.etapa === 'local' &&
            /^confirmar\s+(?:o\s+)?local/i.test(texto) &&
            (data.revisao_encerrada || data.estado_atual !== 'COLETA_ENDERECO')
        ) {
            revisaoAtiva.value = null;
        }
        if (rev?.etapa === 'anexos' && (data.revisao_encerrada || /^confirmar\s+(?:os\s+)?(?:documentos|anexos)/i.test(texto))) {
            revisaoAtiva.value = null;
            etapaAnexosConcluida.value = true;
        }

        if (pendentes.length && !data.anexos_adiados) {
            if (
                revisaoAtiva.value?.etapa === 'anexos' ||
                etapaAnexosConcluida.value
            ) {
                revisaoAtiva.value = null;
            }
        }

        if (data.recusou_geracao_rascunhos) {
            etapaAnexosConcluida.value = false;
        }

        const textoIa = (data.resposta_agente || '').trim() || '(Sem resposta textual.)';
        adicionarMensagem('assistant', textoIa);

        const criadas = data.demandas_criadas;
        if (Array.isArray(criadas) && criadas.length > 0) {
            sucessoCriacao.value = criadas;
            const alertas = data.alertas_duplicidade;
            alertasDuplicidadeCriacao.value = Array.isArray(alertas) && alertas.length ? alertas : null;
            if (Array.isArray(alertas) && alertas.length > 0) {
                const resumo =
                    resumoDuplicidadeFrontend(alertas) ||
                    (data.duplicidade_resumo?.mensagem_resumo
                        ? {
                              severity: data.duplicidade_resumo.sugerir_nao_enviar ? 'error' : 'warn',
                              summary: data.duplicidade_resumo.sugerir_nao_enviar
                                  ? 'Possível duplicidade em tramitação'
                                  : 'Possível duplicidade de rascunho',
                              detail: data.duplicidade_resumo.mensagem_resumo,
                              sugerirNaoEnviar: Boolean(data.duplicidade_resumo.sugerir_nao_enviar)
                          }
                        : null);
                if (resumo) {
                    toast.add({
                        severity: resumo.severity,
                        summary: resumo.summary,
                        detail: resumo.detail,
                        life: resumo.sugerirNaoEnviar ? 16000 : 12000
                    });
                }
            }
        }
        if (data.anexos_adiados) {
            anexosPendentes.value = pendentes;
            etapaAnexosConcluida.value = false;
            toast.add({
                severity: 'info',
                summary: 'Anexos',
                detail:
                    'Com mais de um serviço no pedido, confirme cada serviço na carta e envie os arquivos novamente na etapa Documentos. Os anexos selecionados foram mantidos.',
                life: 8000
            });
        }
    } catch (err) {
        if (pendentes.length) {
            anexosPendentes.value = pendentes;
            etapaAnexosConcluida.value = false;
        }
        const detalhe = err?.response?.data?.detail || err?.response?.data?.mensagem || err?.message || 'Falha na comunicação.';
        const respostaApi = (err?.response?.data?.resposta_agente || '').trim();
        toast.add({ severity: 'error', summary: 'Copiloto', detail: String(detalhe), life: 5000 });
        adicionarMensagem(
            'assistant',
            respostaApi ||
                'Não consegui concluir esta etapa. Tente novamente ou reformule a mensagem.'
        );
    } finally {
        carregando.value = false;
    }
}

function enviar() {
    return enviarMensagem();
}

function onTeclaInput(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        enviarMensagem();
    }
}

function rotuloOpcaoCurto(op) {
    const max = 48;
    if (op.label.length <= max) return `${op.numero}. ${op.label}`;
    return `${op.numero}. ${op.label.slice(0, max)}…`;
}

function aplicarMetadadosIndicacao(data) {
    aplicarRespostaCopiloto(data);
}

function irParaRascunhos() {
    if (isModoIndicacao.value) {
        router.push({ name: 'demandas', query: { status: 'RASCUNHO' } });
        return;
    }
    router.push({ name: 'demandas', query: { status: 'RASCUNHO' } });
}

function assinarEnviarRascunhosCopiloto() {
    if (isModoIndicacao.value && sucessoCriacao.value?.length === 1) {
        router.push({ name: 'indicacao-editar', params: { id: sucessoCriacao.value[0].id } });
        return;
    }
    if (!sucessoCriacao.value?.length || sucessoCriacao.value.length < 2) {
        irParaRascunhos();
        return;
    }
    router.push({
        name: 'demandas',
        query: {
            status: 'RASCUNHO',
            enviar_lote: sucessoCriacao.value.map((d) => d.id).join(',')
        }
    });
}

function novaConversa() {
    anexosPendentes.value = [];
    escolhaServicoCarta.value = {};
    candidatosFingerprint.value = {};
    jaPerguntouAnexosNoChat.value = false;
    etapaAnexosConcluida.value = false;
    tendenciasSimilares.value = {};
    tituloTendenciaForm.value = {};
    escolhaTendenciaForm.value = {};
    revisaoAtiva.value = null;
    sessionId.value = null;
    mensagens.value = [];
    inputTexto.value = '';
    estadoAtual.value = 'COLETA_DADOS';
    demandasExtraidas.value = [];
    sucessoCriacao.value = null;
    alertasDuplicidadeCriacao.value = null;
    atalhosTopTrendsExpandido.value = false;
    cancelarDetalheAtalho();
    aprovacaoFinal.value = {};
    adicionarMensagem(
        'assistant',
        isModoIndicacao.value
            ? 'Olá! Descreva a indicação legislativa com suas palavras. Anexe o PDF com as assinaturas ' +
                  'dos vereadores; na validação final, vincule os parlamentares e confirme o número da Câmara.'
            : 'Olá! Conte o pedido com suas palavras, pode anexar documentos a qualquer momento. ' +
                  'Se for zeladoria ou serviço em via/parque, informe também o local quando souber.'
    );
    if (!isModoIndicacao.value) {
        carregarAtalhosTopTrends();
    }
}

novaConversa();
</script>

<template>
    <!-- Altura explícita + min-h-0 para o flex filho poder encolher e o scroll funcionar -->
    <div
        class="copiloto-shell flex min-h-0 flex-col overflow-hidden rounded-xl border border-[var(--surface-border)] bg-[var(--surface-ground)] shadow-sm h-[calc(100dvh-6.75rem)] max-h-[calc(100dvh-6.75rem)] min-h-[20rem] sm:h-[calc(100dvh-8rem)] sm:max-h-[calc(100dvh-8rem)] sm:min-h-[22rem]"
    >
        <!-- Cabeçalho -->
        <header class="copiloto-header flex shrink-0 flex-col gap-3 border-b border-[var(--surface-border)] bg-[var(--surface-section)] px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-5">
            <div class="copiloto-header__intro min-w-0 w-full sm:flex-1">
                <h1 class="m-0 text-lg font-semibold leading-tight text-[var(--text-color)] sm:text-2xl">
                    {{ isModoIndicacao ? 'Copiloto — Indicações' : 'Copiloto de demandas' }}
                </h1>
                <p class="mt-1.5 text-xs leading-relaxed text-[var(--text-color-secondary)] sm:mt-1 sm:text-sm">
                    <template v-if="isModoIndicacao">
                        Descreva a indicação na conversa, anexe o PDF assinado e confirme vereadores e numeração
                        antes de gerar o rascunho.
                    </template>
                    <template v-else>
                        Descreva o pedido na conversa — o painel <strong class="font-medium">Contexto</strong> mostra o que
                        já foi entendido (assunto, serviço, local).
                    </template>
                </p>
            </div>
            <div class="copiloto-header__actions flex w-full shrink-0 items-stretch gap-2 sm:w-auto">
                <Button
                    type="button"
                    label="Contexto"
                    icon="pi pi-list"
                    severity="secondary"
                    outlined
                    class="copiloto-header__btn flex-1 lg:!hidden"
                    @click="painelContextoAberto = true"
                />
                <Button
                    type="button"
                    label="Nova conversa"
                    icon="pi pi-refresh"
                    severity="secondary"
                    outlined
                    class="copiloto-header__btn copiloto-header__btn--nova hidden shrink-0 sm:inline-flex"
                    @click="novaConversa"
                />
            </div>
        </header>

        <!-- Sucesso -->
        <div
            v-if="sucessoCriacao"
            class="flex min-h-0 flex-1 flex-col items-center justify-center gap-6 overflow-y-auto bg-[var(--surface-ground)] px-4 py-10"
        >
            <div class="max-w-md text-center">
                <i class="pi pi-check-circle text-6xl text-green-500" aria-hidden="true"></i>
                <h2 class="mt-4 text-2xl font-semibold text-[var(--text-color)]">
                    {{ isModoIndicacao ? 'Indicação registrada!' : 'Demandas criadas!' }}
                </h2>
                <p class="mt-2 leading-relaxed text-[var(--text-color-secondary)]">
                    Foram gerados <strong class="text-[var(--text-color)]">{{ sucessoCriacao.length }}</strong>
                    {{ isModoIndicacao ? 'rascunho(s) de indicação' : 'rascunho(s)' }} (IDs:
                    {{ sucessoCriacao.map((d) => d.id).join(', ') }}).
                </p>
                <Message
                    v-if="alertasDuplicidadeCriacao?.length"
                    :severity="temDuplicidadeEmTramite(alertasDuplicidadeCriacao) ? 'error' : 'warn'"
                    :closable="false"
                    class="mt-4 text-left text-sm"
                >
                    <template v-if="temDuplicidadeEmTramite(alertasDuplicidadeCriacao)">
                        <strong>Atenção — possível duplicidade em tramitação.</strong>
                        <ul class="m-0 mt-2 list-disc pl-5">
                            <li v-for="a in alertasDuplicidadeCriacao" :key="a.demanda_id">
                                {{ a.mensagem || `#${a.demanda_id} «${a.titulo}» (${a.status_label || a.status})` }}
                            </li>
                        </ul>
                        <p class="m-0 mt-2">
                            O rascunho foi registrado, mas recomendamos <strong>não enviar oficialmente</strong>
                            e acompanhar o processo existente.
                        </p>
                    </template>
                    <template v-else>
                        <strong>Possível duplicidade de rascunho.</strong>
                        <ul class="m-0 mt-2 list-disc pl-5">
                            <li v-for="a in alertasDuplicidadeCriacao" :key="a.demanda_id">
                                {{ a.mensagem || `#${a.demanda_id} «${a.titulo}»` }}
                            </li>
                        </ul>
                        <p class="m-0 mt-2">Revise se não é o mesmo pedido antes de protocolar.</p>
                    </template>
                </Message>
            </div>
            <div class="flex flex-col gap-2 sm:flex-row">
                <Button
                    v-if="isModoIndicacao && sucessoCriacao.length === 1"
                    label="Revisar indicação"
                    icon="pi pi-pencil"
                    @click="router.push({ name: 'indicacao-editar', params: { id: sucessoCriacao[0].id } })"
                />
                <Button
                    v-else-if="sucessoCriacao.length > 1"
                    label="Assinar e enviar todos"
                    icon="pi pi-send"
                    @click="assinarEnviarRascunhosCopiloto"
                />
                <Button
                    :label="isModoIndicacao ? 'Ver indicações' : 'Revisar rascunhos'"
                    icon="pi pi-table"
                    severity="secondary"
                    outlined
                    @click="irParaRascunhos"
                />
                <Button label="Continuar no copiloto" icon="pi pi-comments" severity="secondary" outlined @click="sucessoCriacao = null" />
            </div>
        </div>

        <!-- Corpo: coluna chat (flex-1 + min-h-0) | painel -->
        <div v-else class="flex min-h-0 flex-1 flex-row overflow-hidden">
            <!-- Coluna chat: mensagens ocupam o espaço; compositor shrink-0 na base -->
            <div class="flex min-h-0 min-w-0 flex-1 flex-col">
                <div
                    ref="listaChatRef"
                    class="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-[var(--surface-ground)] px-3 py-4 sm:px-5"
                >
                    <div class="mx-auto flex max-w-3xl flex-col gap-3">
                        <div
                            v-for="(m, idx) in mensagens"
                            :key="m.id"
                            class="flex w-full"
                            :class="m.role === 'user' ? 'justify-end' : 'justify-start'"
                        >
                            <div
                                v-if="!ocultarBolhaAssistenteNoChat(m)"
                                class="max-w-[min(100%,28rem)] break-words rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm sm:text-base"
                                :class="
                                    m.role === 'user'
                                        ? 'rounded-br-md bg-primary text-primary-contrast'
                                        : 'rounded-bl-md border border-[var(--surface-border)] bg-[var(--surface-card)] text-[var(--text-color)]'
                                "
                            >
                                <span class="whitespace-pre-wrap">{{ m.texto }}</span>
                            </div>
                        </div>

                        <div
                            v-if="mostrarBlocoForaCompetenciaNoChat"
                            class="mx-auto w-full max-w-3xl rounded-2xl border border-red-500/40 bg-[var(--surface-card)] p-4 shadow-sm"
                        >
                            <div class="mb-3 flex flex-wrap items-center gap-2">
                                <span class="text-sm font-semibold text-[var(--text-color)]">
                                    <i class="pi pi-ban mr-1" aria-hidden="true" />
                                    Pedido fora da competência municipal
                                </span>
                            </div>
                            <p class="m-0 mb-3 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                                O assunto não pode virar ofício pelo gabinete. Reformule descrevendo um problema de
                                serviço público da Prefeitura (zeladoria, obras, meio ambiente, etc.) ou use o cadastro
                                tradicional de demandas para outros assuntos.
                            </p>
                            <div
                                v-for="{ d, i } in demandasForaCompetenciaNoChat"
                                :key="`chat-fc-${i}`"
                                class="mb-3 flex flex-col gap-2 rounded-xl border border-red-400/30 bg-red-500/5 p-3 last:mb-0"
                            >
                                <span class="text-sm font-medium text-[var(--text-color)]">
                                    {{ i + 1 }}. {{ d.titulo || 'Solicitação' }}
                                </span>
                                <p class="m-0 text-xs text-[var(--text-color-secondary)]">
                                    {{ d.motivo_recusa || 'Não corresponde a um serviço público municipal.' }}
                                </p>
                                <div
                                    v-if="d.faq_orientacao?.titulo"
                                    class="mt-1 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] p-2"
                                >
                                    <p class="m-0 text-xs font-semibold text-[var(--text-color)]">
                                        {{ d.faq_orientacao.titulo }}
                                    </p>
                                    <p class="m-0 mt-1 text-xs text-[var(--text-color-secondary)]">
                                        {{ d.faq_orientacao.mensagem }}
                                    </p>
                                    <p
                                        v-if="d.faq_orientacao.orgao_hint"
                                        class="m-0 mt-1 text-xs text-[var(--text-color-secondary)]"
                                    >
                                        <i class="pi pi-info-circle mr-1" aria-hidden="true" />
                                        {{ d.faq_orientacao.orgao_hint }}
                                    </p>
                                </div>
                            </div>
                            <Button
                                label="Nova conversa"
                                icon="pi pi-refresh"
                                size="small"
                                severity="secondary"
                                outlined
                                class="self-start"
                                @click="novaConversa"
                            />
                        </div>

                        <div
                            v-if="mostrarBlocoServicoNoChat"
                            data-copiloto-bloco="servico"
                            class="mx-auto w-full max-w-3xl rounded-2xl border border-amber-500/35 bg-[var(--surface-card)] p-4 shadow-sm"
                        >
                            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
                                <span class="text-sm font-semibold text-[var(--text-color)]">
                                    <i class="pi pi-book mr-1" aria-hidden="true" />
                                    Serviço na carta de serviços
                                </span>
                                <Button
                                    v-if="demandasComCartaNoChat.length > 1"
                                    label="Confirmar sugestões"
                                    icon="pi pi-check-circle"
                                    size="small"
                                    severity="success"
                                    outlined
                                    :loading="carregando"
                                    @click="confirmarTodosServicosCarta"
                                />
                            </div>
                            <p class="m-0 mb-3 text-xs text-[var(--text-color-secondary)]">
                                <strong>Carta de serviços:</strong>
                                <template v-if="demandasComCartaNoChat.some(({ d }) => ehModoCartaDominio(d))">
                                    quando o pedido é do mesmo eixo (ex.: mobilidade), listamos até
                                    {{ MAX_OPCOES_DOMINIO }} serviços com similaridade ≥
                                    {{ Math.round(LIMIAR_SCORE_DOMINIO * 100) }}% — ou registre como tendência.
                                </template>
                                <template v-else>
                                    até {{ MAX_OPCOES_CARTA }} opções com similaridade ≥
                                    {{ Math.round(LIMIAR_SCORE_CARTA * 100) }}%. Abaixo disso, use tendência.
                                </template>
                                Pode ignorar, refazer a busca, escolher no menu ou descartar uma solicitação quando houver mais de um pedido.
                            </p>
                            <div
                                v-for="{ d, i } in demandasComCartaNoChat"
                                :key="`chat-srv-${i}`"
                                class="mb-3 flex flex-col gap-2 rounded-xl border border-[var(--surface-border)] bg-[var(--surface-ground)] p-3 last:mb-0"
                                :class="{
                                    'opacity-60': d.descartada,
                                    'ring-2 ring-[var(--primary-color)]/40': emRevisaoDemanda(i, 'servico')
                                }"
                            >
                                <div class="flex flex-wrap items-center gap-2">
                                    <span class="text-sm font-medium text-[var(--text-color)]">
                                        {{ i + 1 }}. {{ d.titulo || 'Solicitação' }}
                                    </span>
                                    <Tag v-if="d.descartada" value="Descartada" severity="secondary" class="!text-xs" />
                                    <Tag v-else-if="servicoConfirmado(d)" value="Confirmado" severity="success" class="!text-xs" />
                                    <Tag v-else-if="d.servico_alerta" value="Revise a opção" severity="warn" class="!text-xs" />
                                </div>
                                <template v-if="d.descartada">
                                    <p class="m-0 text-xs text-[var(--text-color-secondary)]">
                                        Esta solicitação foi ignorada e não será incluída no ofício.
                                    </p>
                                    <Button
                                        label="Restaurar solicitação"
                                        icon="pi pi-undo"
                                        size="small"
                                        severity="secondary"
                                        text
                                        :loading="carregando"
                                        @click="restaurarSolicitacao(i)"
                                    />
                                </template>
                                <template v-else>
                                <p
                                    v-if="d.dominio_operacional?.label && ehModoCartaDominio(d)"
                                    class="m-0 text-xs text-sky-800 dark:text-sky-300"
                                >
                                    Eixo reconhecido: <strong>{{ d.dominio_operacional.label }}</strong> — escolha um
                                    serviço da carta abaixo ou «Nenhuma das opções» para tendência.
                                </p>
                                <p
                                    v-else-if="demandaForaCarta(d) || !candidatosCartaExibicao(d).length"
                                    class="m-0 text-xs text-amber-700 dark:text-amber-400"
                                >
                                    Nenhuma opção atingiu {{ Math.round(limiarScoreDemanda(d) * 100) }}% — registre como
                                    tendência ou use «Nova busca».
                                </p>
                                <div
                                    v-if="corpusHintsDemanda(d).length && (demandaForaCarta(d) || !candidatosCartaExibicao(d).length)"
                                    class="flex flex-col gap-2 rounded-lg border border-sky-500/30 bg-sky-500/5 px-3 py-2"
                                >
                                    <span class="text-xs font-medium uppercase tracking-wide text-sky-800 dark:text-sky-300">
                                        Serviços da carta sugeridos
                                    </span>
                                    <p class="m-0 text-xs text-[var(--text-color-secondary)]">
                                        Escolha o serviço mais adequado — cada opção confirma na carta e segue para complementar o local.
                                    </p>
                                    <ul class="m-0 flex list-none flex-col gap-2 p-0">
                                        <li
                                            v-for="h in corpusHintsDemanda(d)"
                                            :key="h.id || h.servico_legado"
                                            class="flex flex-wrap items-center gap-2"
                                        >
                                            <Button
                                                v-if="h.sinapse_servico_id_sugerido_historico"
                                                :label="rotuloHintHistorico(h)"
                                                icon="pi pi-check"
                                                size="small"
                                                severity="info"
                                                outlined
                                                class="!text-left"
                                                :loading="carregando"
                                                @click="aplicarHintCorpus(i, h)"
                                            />
                                            <span v-else class="text-sm text-[var(--text-color)]">
                                                {{ rotuloHintHistorico(h) }}
                                            </span>
                                            <Tag
                                                v-if="h.padrao"
                                                value="Mais comum"
                                                severity="success"
                                                class="!text-xs"
                                            />
                                        </li>
                                    </ul>
                                </div>
                                <div v-if="!servicoConfirmado(d)" class="flex flex-wrap gap-2">
                                    <Button
                                        label="Nova busca"
                                        icon="pi pi-refresh"
                                        size="small"
                                        severity="secondary"
                                        outlined
                                        :loading="carregando"
                                        @click="novaBuscaSemantica(i)"
                                    />
                                    <Button
                                        label="Ignorar sugestões"
                                        icon="pi pi-ban"
                                        size="small"
                                        severity="secondary"
                                        text
                                        :loading="carregando"
                                        @click="ignorarSugestoesCarta(i)"
                                    />
                                    <Button
                                        v-if="demandasAtivasNoFluxo.length > 1"
                                        label="Descartar solicitação"
                                        icon="pi pi-trash"
                                        size="small"
                                        severity="danger"
                                        text
                                        :loading="carregando"
                                        @click="descartarSolicitacao(i)"
                                    />
                                </div>
                                <Select
                                    :key="fingerprintCandidatos(d)"
                                    v-model="escolhaServicoCarta[i]"
                                    :options="opcoesServicoCarta(d)"
                                    option-label="label"
                                    option-value="value"
                                    :placeholder="`Serviços da carta (≥ ${Math.round(limiarScoreDemanda(d) * 100)}%)`"
                                    class="w-full"
                                    :disabled="carregando || servicoConfirmado(d)"
                                />
                                <div
                                    v-if="escolheuNenhumaCarta(i)"
                                    class="flex flex-col gap-3 rounded-lg border border-violet-400/40 bg-violet-500/5 p-3"
                                >
                                    <span class="text-xs font-semibold text-[var(--text-color)]">
                                        2º passo — tendência (fora da carta)
                                    </span>
                                    <div
                                        v-if="tendenciasSimilares[i]?.loading"
                                        class="flex items-center gap-2 text-xs text-[var(--text-color-secondary)]"
                                    >
                                        <ProgressSpinner class="!h-5 !w-5" strokeWidth="6" />
                                        Buscando tendências semelhantes…
                                    </div>
                                    <template v-else>
                                        <label class="text-xs font-medium text-[var(--text-color-secondary)]">
                                            Título para registro
                                        </label>
                                        <InputText
                                            v-model="tituloTendenciaForm[i]"
                                            class="w-full"
                                            :disabled="carregando"
                                            placeholder="Ex.: Reserva em área não catalogada"
                                        />
                                        <label class="text-xs font-medium text-[var(--text-color-secondary)]">
                                            {{
                                                (tendenciasSimilares[i]?.items?.length || 0) > 0
                                                    ? 'Vincular a tendência existente ou criar nova'
                                                    : 'Nova tendência'
                                            }}
                                        </label>
                                        <Select
                                            v-model="escolhaTendenciaForm[i]"
                                            :options="opcoesTendenciaSelect(i)"
                                            option-label="label"
                                            option-value="value"
                                            placeholder="Tendência"
                                            class="w-full"
                                            :disabled="carregando"
                                        />
                                        <p
                                            v-if="tendenciasSimilares[i]?.erro"
                                            class="m-0 text-xs text-amber-600 dark:text-amber-400"
                                        >
                                            Busca indisponível; será criada uma nova tendência.
                                        </p>
                                        <Button
                                            label="Confirmar tendência"
                                            icon="pi pi-check"
                                            size="small"
                                            severity="secondary"
                                            class="self-start"
                                            :loading="carregando"
                                            :disabled="!tituloTendenciaForm[i]?.trim()"
                                            @click="aplicarTendenciaDemanda(i)"
                                        />
                                    </template>
                                </div>
                                <Button
                                    v-if="!servicoConfirmado(d) && !escolheuNenhumaCarta(i)"
                                    label="Confirmar serviço na carta"
                                    icon="pi pi-check"
                                    size="small"
                                    class="self-start"
                                    :disabled="escolhaServicoCarta[i] == null || carregando"
                                    @click="aplicarServicoCarta(i)"
                                />
                                </template>
                            </div>
                        </div>

                        <div
                            v-if="mostrarBlocoComplementoNoChat"
                            data-copiloto-bloco="complemento"
                            class="mx-auto w-full max-w-3xl rounded-2xl border border-emerald-500/35 bg-[var(--surface-card)] p-4 shadow-sm"
                        >
                            <div class="mb-2">
                                <span class="text-sm font-semibold text-[var(--text-color)]">
                                    <i class="pi pi-map-marker mr-1" aria-hidden="true" />
                                    Complementar informações
                                </span>
                                <p class="m-0 mt-1 text-xs text-[var(--text-color-secondary)]">
                                    O serviço já está na carta. Descreva no campo abaixo rua, número, bairro, referência ou
                                    detalhes adicionais do pedido.
                                </p>
                            </div>
                            <div
                                v-for="{ d, i } in demandasAguardandoComplemento"
                                :key="`chat-comp-${i}`"
                                class="mb-2 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] px-3 py-2 last:mb-0"
                            >
                                <p class="m-0 text-sm font-medium text-[var(--text-color)]">
                                    {{ i + 1 }}. {{ d.servico?.nome || d.titulo || 'Solicitação' }}
                                </p>
                                <p
                                    v-if="d.servico?.orgao"
                                    class="m-0 mt-0.5 text-xs text-[var(--text-color-secondary)]"
                                >
                                    {{ d.servico.orgao }}
                                </p>
                            </div>
                        </div>

                        <div
                            v-if="false"
                            class="mx-auto w-full max-w-3xl rounded-2xl border border-violet-500/35 bg-[var(--surface-card)] p-4 shadow-sm"
                        >
                            <div class="mb-3">
                                <span class="text-sm font-semibold text-[var(--text-color)]">
                                    <i class="pi pi-compass mr-1" aria-hidden="true" />
                                    Solicitação fora da carta
                                </span>
                                <p class="m-0 mt-1 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                                    Não encontramos serviço na carta com confiança suficiente (≥ 70%). Registre como
                                    tendência para gestão interna; depois informe o endereço para seguir com o ofício.
                                </p>
                            </div>
                            <div
                                v-for="{ d, i } in demandasForaCartaNoChat"
                                :key="`chat-tend-${i}`"
                                class="mb-3 flex flex-col gap-3 rounded-xl border border-[var(--surface-border)] bg-[var(--surface-ground)] p-3 last:mb-0"
                            >
                                <span class="text-sm font-medium text-[var(--text-color)]">
                                    {{ d.titulo || `Solicitação ${i + 1}` }}
                                </span>
                                <div
                                    v-if="tendenciasSimilares[i]?.loading"
                                    class="flex items-center gap-2 text-xs text-[var(--text-color-secondary)]"
                                >
                                    <ProgressSpinner class="!h-5 !w-5" strokeWidth="6" />
                                    Buscando tendências semelhantes…
                                </div>
                                <template v-else>
                                    <label class="text-xs font-medium text-[var(--text-color-secondary)]">
                                        Título para registro
                                    </label>
                                    <InputText
                                        v-model="tituloTendenciaForm[i]"
                                        class="w-full"
                                        :disabled="carregando"
                                        placeholder="Ex.: Buraco em via não catalogada"
                                    />
                                    <label class="text-xs font-medium text-[var(--text-color-secondary)]">
                                        {{
                                            (tendenciasSimilares[i]?.items?.length || 0) > 0
                                                ? 'Vincular a tendência existente ou criar nova'
                                                : 'Nova tendência'
                                        }}
                                    </label>
                                    <Select
                                        v-model="escolhaTendenciaForm[i]"
                                        :options="opcoesTendenciaSelect(i)"
                                        option-label="label"
                                        option-value="value"
                                        placeholder="Escolha"
                                        class="w-full"
                                        :disabled="carregando"
                                    />
                                    <p
                                        v-if="tendenciasSimilares[i]?.erro"
                                        class="m-0 text-xs text-amber-600 dark:text-amber-400"
                                    >
                                        Busca semântica indisponível; será criada uma nova tendência.
                                    </p>
                                    <Button
                                        label="Confirmar tendência"
                                        icon="pi pi-check"
                                        size="small"
                                        severity="secondary"
                                        class="self-start"
                                        :loading="carregando"
                                        :disabled="!tituloTendenciaForm[i]?.trim()"
                                        @click="aplicarTendenciaDemanda(i)"
                                    />
                                </template>
                            </div>
                        </div>

                        <div
                            v-if="mostrarBlocoEnderecoNoChat"
                            data-copiloto-bloco="local"
                            class="mx-auto w-full max-w-3xl rounded-2xl border border-[var(--primary-color)]/30 bg-[var(--surface-card)] p-4 shadow-sm"
                        >
                            <p class="m-0 mb-1 text-sm font-semibold text-[var(--text-color)]">
                                <i class="pi pi-map-marker mr-1" aria-hidden="true" />
                                {{ isModoIndicacao ? 'Local da indicação (opcional)' : 'Local da solicitação' }}
                                <span
                                    v-if="revisaoAtiva?.etapa === 'local'"
                                    class="ml-2 text-xs font-normal text-[var(--primary-color)]"
                                >
                                    (revisão — solicitação {{ revisaoAtiva.indiceDemanda + 1 }})
                                </span>
                            </p>
                            <p class="m-0 mb-3 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                                <template v-if="isModoIndicacao">
                                    Informe logradouro, bairro e CEP (recomendado), use a localização do aparelho
                                    ou continue sem local se a indicação não tiver endereço específico.
                                </template>
                                <template v-else>
                                    Use o formulário abaixo (CEP recomendado), a mensagem de chat,
                                    GPS ou «Continuar sem local». O fluxo não trava se o mapa não
                                    localizar o ponto com precisão.
                                </template>
                            </p>
                            <div class="mb-3 flex flex-wrap gap-2">
                                <Button
                                    :label="labelGpsCopiloto"
                                    icon="pi pi-map"
                                    severity="secondary"
                                    outlined
                                    :disabled="carregando"
                                    @click="usarLocalizacaoAtual(indiceDemandaGps)"
                                />
                                <Button
                                    label="Continuar sem local"
                                    severity="secondary"
                                    text
                                    :disabled="carregando"
                                    @click="enviarMensagem('continuar sem local')"
                                />
                            </div>
                            <div
                                v-for="{ d, i } in demandasEscopoLocal"
                                :key="`endereco-${i}`"
                                class="mb-3 flex flex-col gap-2"
                            >
                                <p
                                    v-if="demandasEscopoLocal.length > 1"
                                    class="m-0 text-xs font-medium text-[var(--text-color-secondary)]"
                                >
                                    Solicitação {{ i + 1 }}
                                </p>
                                <div
                                    class="grid grid-cols-1 gap-3 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] p-3 sm:grid-cols-12"
                                >
                                    <div class="sm:col-span-3">
                                        <label
                                            class="mb-1 block text-xs font-medium text-[var(--text-color-secondary)]"
                                            :for="`copiloto-cep-${i}`"
                                        >
                                            CEP
                                        </label>
                                        <InputMask
                                            :id="`copiloto-cep-${i}`"
                                            v-model="obterFormEnderecoCopiloto(i).cep"
                                            mask="99999-999"
                                            placeholder="99999-999"
                                            class="w-full"
                                            :disabled="carregando"
                                            @blur="buscarCepCopiloto(i)"
                                        />
                                    </div>
                                    <div class="sm:col-span-9">
                                        <label
                                            class="mb-1 block text-xs font-medium text-[var(--text-color-secondary)]"
                                            :for="`copiloto-logr-${i}`"
                                        >
                                            Logradouro
                                        </label>
                                        <AutoComplete
                                            :id="`copiloto-logr-${i}`"
                                            v-model="obterFormEnderecoCopiloto(i).logradouro"
                                            :suggestions="sugLogradourosCopiloto"
                                            optionLabel="label"
                                            :loading="buscandoLogradourosCopiloto && indiceAutocompleteLogradouro === i"
                                            placeholder="Mín. 3 letras (vias de Mogi das Cruzes)"
                                            class="w-full"
                                            inputClass="w-full"
                                            :disabled="carregando"
                                            @complete="searchLogradouroCopiloto($event, i)"
                                            @item-select="onLogradouroSelecionadoCopiloto($event, i)"
                                        />
                                    </div>
                                    <div class="sm:col-span-3">
                                        <label
                                            class="mb-1 block text-xs font-medium text-[var(--text-color-secondary)]"
                                            :for="`copiloto-num-${i}`"
                                        >
                                            Número
                                        </label>
                                        <InputText
                                            :id="`copiloto-num-${i}`"
                                            v-model="obterFormEnderecoCopiloto(i).numero"
                                            class="w-full"
                                            :disabled="carregando"
                                        />
                                    </div>
                                    <div class="sm:col-span-6">
                                        <label
                                            class="mb-1 block text-xs font-medium text-[var(--text-color-secondary)]"
                                            :for="`copiloto-bairro-${i}`"
                                        >
                                            Bairro
                                        </label>
                                        <InputText
                                            :id="`copiloto-bairro-${i}`"
                                            v-model="obterFormEnderecoCopiloto(i).bairro"
                                            class="w-full"
                                            :disabled="carregando"
                                        />
                                    </div>
                                    <div class="flex items-end sm:col-span-3">
                                        <Button
                                            label="Aplicar endereço"
                                            icon="pi pi-check"
                                            size="small"
                                            class="w-full"
                                            :loading="carregando"
                                            @click="aplicarEnderecoCopiloto(i)"
                                        />
                                    </div>
                                </div>
                                <div
                                    v-if="d.endereco_resumo"
                                    class="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] px-3 py-2 text-sm text-[var(--text-color)]"
                                >
                                    <span class="text-xs font-semibold text-[var(--text-color-secondary)]">
                                        Endereço identificado:
                                    </span>
                                    {{ d.endereco_resumo }}
                                </div>
                                <Message
                                    v-if="d.geocode_alerta"
                                    severity="warn"
                                    :closable="false"
                                    class="m-0 text-xs"
                                >
                                    {{ d.geocode_alerta }}
                                </Message>
                                <p
                                    v-else-if="d.coordenadas_observacao && d.latitude != null && d.longitude != null"
                                    class="m-0 text-xs text-[var(--text-color-secondary)]"
                                >
                                    {{ d.coordenadas_observacao }}
                                </p>
                                <p
                                    v-if="d.latitude != null && d.longitude != null"
                                    class="m-0 text-xs text-[var(--text-color-secondary)]"
                                >
                                    Coordenadas: {{ Number(d.latitude).toFixed(6) }},
                                    {{ Number(d.longitude).toFixed(6) }}
                                </p>
                                <MapaLocalAjustavel
                                    v-if="d.latitude != null && d.longitude != null"
                                    :key="`copiloto-mapa-${i}-${d.latitude}-${d.longitude}`"
                                    :map-id="`copiloto-mapa-${i}`"
                                    :latitude="Number(d.latitude)"
                                    :longitude="Number(d.longitude)"
                                    height="9rem"
                                    :zoom="17"
                                    :draggable="!carregando"
                                    @ajustado="(coords) => ajustarMapaCopiloto(i, coords)"
                                />
                                <Button
                                    v-if="demandaPodeConfirmarLocal(d)"
                                    :label="
                                        demandasExtraidas.length > 1
                                            ? `Confirmar local (solicitação ${i + 1})`
                                            : 'Confirmar local'
                                    "
                                    icon="pi pi-check"
                                    class="self-start"
                                    :disabled="carregando"
                                    @click="confirmarLocalDemanda(i)"
                                />
                            </div>
                        </div>

                        <div
                            v-if="mostrarBlocoAnexosNoChat"
                            data-copiloto-bloco="anexos"
                            class="mx-auto w-full max-w-3xl rounded-2xl border border-[var(--primary-color)]/30 bg-[var(--surface-card)] p-4 shadow-sm"
                        >
                            <p class="m-0 mb-1 text-sm font-semibold text-[var(--text-color)]">
                                <i class="pi pi-paperclip mr-1" aria-hidden="true" />
                                {{ isModoIndicacao ? 'PDF da indicação' : 'Documentos complementares' }}
                                <span
                                    v-if="revisaoAtiva?.etapa === 'anexos'"
                                    class="ml-2 text-xs font-normal text-[var(--primary-color)]"
                                >
                                    (revisão — solicitação {{ revisaoAtiva.indiceDemanda + 1 }})
                                </span>
                            </p>
                            <p class="m-0 mb-3 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                                <template v-if="isModoIndicacao">
                                    Anexe o PDF da indicação assinada pelos vereadores. O documento é obrigatório
                                    para gerar o rascunho.
                                </template>
                                <template v-else>
                                    Deseja anexar fotos ou PDFs?
                                    <template v-if="demandasAtivasNoFluxo.length > 1">
                                        Se forem vários arquivos, indique a qual solicitação cada um pertence.
                                    </template>
                                </template>
                            </p>
                            <div
                                v-if="demandasExtraidas.some((d, i) => anexosSalvosDemanda(i).length) && (indiceDemandaRevisaoAnexos == null || anexosSalvosDemanda(indiceDemandaRevisaoAnexos).length)"
                                class="mb-3 flex flex-col gap-2 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] p-2"
                            >
                                <span class="text-xs font-medium text-[var(--text-color-secondary)]">
                                    Arquivos já enviados
                                </span>
                                <template
                                    v-for="(d, i) in demandasExtraidas"
                                    :key="`anexos-salvos-${i}`"
                                >
                                    <template v-if="indiceDemandaRevisaoAnexos == null || i === indiceDemandaRevisaoAnexos">
                                    <div
                                        v-for="anexo in anexosSalvosDemanda(i)"
                                        :key="`salvo-${i}-${anexo.indice_sessao}`"
                                        class="flex items-center justify-between gap-2 rounded-md border border-[var(--surface-border)] bg-[var(--surface-card)] px-2 py-1.5 text-sm"
                                    >
                                        <span class="truncate">
                                            <span class="text-xs text-[var(--text-color-secondary)]">
                                                Sol. {{ i + 1 }}:
                                            </span>
                                            {{ anexo.nome }}
                                        </span>
                                        <Button
                                            icon="pi pi-trash"
                                            text
                                            rounded
                                            size="small"
                                            severity="danger"
                                            :disabled="carregando"
                                            @click="removerAnexoSalvo(anexo.indice_sessao)"
                                        />
                                    </div>
                                    </template>
                                </template>
                            </div>
                            <div v-if="anexosPendentes.length" class="mb-3 flex flex-col gap-2 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] p-2">
                                <div
                                    v-for="(item, idx) in anexosPendentes"
                                    :key="item.id"
                                    class="flex flex-col gap-2 rounded-md border border-[var(--surface-border)] bg-[var(--surface-card)] p-2 sm:flex-row sm:items-center"
                                >
                                    <div class="flex min-w-0 flex-1 items-center gap-2 text-sm">
                                        <i class="pi pi-file shrink-0 text-[var(--text-color-secondary)]" />
                                        <span class="truncate" :title="item.file.name">{{ item.file.name }}</span>
                                    </div>
                                    <Select
                                        v-if="mostrarVinculoAnexoDemanda"
                                        v-model="item.indiceDemanda"
                                        :options="opcoesDemandaAnexo"
                                        option-label="label"
                                        option-value="value"
                                        placeholder="Solicitação"
                                        class="w-full sm:w-48"
                                        :disabled="carregando"
                                    />
                                    <Button icon="pi pi-times" text rounded size="small" :disabled="carregando" @click="removerAnexoPendente(idx)" />
                                </div>
                            </div>
                            <div class="flex flex-wrap gap-2">
                                <Button type="button" label="Anexar arquivos" icon="pi pi-upload" :disabled="carregando" @click="abrirSeletorAnexos" />
                                <Button v-if="anexosPendentes.length" label="Enviar anexos" icon="pi pi-send" :loading="carregando" :disabled="!podeEnviar" @click="enviar" />
                                <Button
                                    v-if="temAnexosSalvosNaSessao"
                                    label="Confirmar documentos"
                                    icon="pi pi-check"
                                    :disabled="carregando"
                                    @click="confirmarDocumentos"
                                />
                                <Button
                                    v-if="!isModoIndicacao"
                                    label="Continuar sem anexos"
                                    severity="secondary"
                                    text
                                    :disabled="carregando || etapaAnexosConcluida"
                                    @click="pularAnexos"
                                />
                            </div>
                        </div>

                        <div
                            v-if="mostrarMetadadosIndicacao"
                            class="mx-auto w-full max-w-3xl flex flex-col gap-3"
                        >
                            <CopilotoIndicacaoCampos
                                v-for="{ d, i } in demandasParaAprovacaoFinal"
                                :key="`ind-campos-${i}`"
                                :session-id="sessionId"
                                :indice-demanda="i"
                                :demanda="d"
                                @atualizado="aplicarMetadadosIndicacao"
                            />
                        </div>

                        <div
                            v-if="mostrarSimNaoValidacao"
                            class="mx-auto w-full max-w-3xl rounded-2xl border border-primary/35 bg-[var(--surface-card)] p-4 shadow-sm"
                        >
                            <p class="m-0 mb-1 text-sm font-semibold text-[var(--text-color)]">
                                <i class="pi pi-file-edit mr-1" aria-hidden="true" />
                                {{ isModoIndicacao ? 'Gerar rascunho da indicação' : 'Gerar ofícios em rascunho' }}
                            </p>
                            <p class="m-0 mb-3 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                                <template v-if="isModoIndicacao">
                                    Revise o teor, vereadores, número e PDF. Confirme para registrar a indicação em rascunho.
                                </template>
                                <template v-else>
                                    Revise cada solicitação. Com mais de um pedido, marque quais viram rascunho de ofício.
                                </template>
                            </p>
                            <div
                                v-if="demandasParaAprovacaoFinal.length > 1"
                                class="mb-3 flex flex-col gap-2 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] p-3"
                            >
                                <div
                                    v-for="{ d, i } in demandasParaAprovacaoFinal"
                                    :key="`aprov-${i}`"
                                    class="flex flex-wrap items-center gap-2 text-sm"
                                >
                                    <label class="flex cursor-pointer items-center gap-2">
                                        <input
                                            v-model="aprovacaoFinal[i]"
                                            type="checkbox"
                                            class="rounded"
                                        />
                                        <span>
                                            {{ i + 1 }}. {{ (d.titulo || 'Solicitação').slice(0, 56) }}
                                        </span>
                                    </label>
                                    <Tag v-if="d.anexos?.length" :value="`${d.anexos.length} anexo(s)`" severity="info" class="!text-xs" />
                                </div>
                            </div>
                            <div class="flex flex-wrap gap-2">
                                <Button
                                    label="Sim, gerar rascunhos"
                                    icon="pi pi-check"
                                    severity="success"
                                    :disabled="carregando"
                                    @click="demandasParaAprovacaoFinal.length > 1 ? finalizarComAprovacao() : enviarMensagem('sim')"
                                />

                                <Button
                                    label="Não"
                                    icon="pi pi-times"
                                    severity="secondary"
                                    outlined
                                    :disabled="carregando"
                                    @click="recusarGeracaoRascunhos"
                                />
                            </div>
                        </div>

                        <div v-if="carregando" class="flex items-center gap-2 py-2 text-sm text-[var(--text-color-secondary)]">
                            <ProgressSpinner class="!h-6 !w-6" strokeWidth="6" />
                            <span>A IA está pensando…</span>
                        </div>
                    </div>
                </div>

                <!-- Compositor fixo no rodapé da coluna -->
                <div
                    class="shrink-0 border-t border-[var(--surface-border)] bg-[var(--surface-section)] px-3 py-3 sm:px-5 sm:py-4"
                >
                    <div class="mx-auto flex max-w-3xl flex-col gap-2">
                        <input
                            ref="inputAnexosRef"
                            type="file"
                            class="hidden"
                            multiple
                            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.webp,.txt"
                            @change="onSelecionarAnexos"
                        />
                        <div
                            v-if="mostrarAtalhosTopTrends"
                            class="flex flex-col gap-2 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] px-3 py-2"
                        >
                            <span class="text-xs font-medium uppercase tracking-wide text-[var(--text-color-secondary)]">
                                Pedidos frequentes
                            </span>
                            <p class="m-0 text-xs text-[var(--text-color-secondary)]">
                                Escolha o tipo de pedido, em seguida selecione o serviço na carta, se necessário.
                            </p>
                            <div class="flex flex-wrap gap-2">
                                <Button
                                    v-for="a in atalhosTopTrendsVisiveis"
                                    :key="a.id || a.rotulo"
                                    :label="rotuloAtalho(a)"
                                    size="small"
                                    outlined
                                    severity="secondary"
                                    class="text-left"
                                    :disabled="carregando"
                                    @click="usarAtalhoTopTrend(a)"
                                />
                            </div>
                            <Button
                                v-if="atalhosTopTrends.length > LIMITE_ATALHOS_VISIVEIS && !atalhosTopTrendsExpandido"
                                label="Ver mais"
                                size="small"
                                text
                                severity="secondary"
                                class="self-start"
                                @click="atalhosTopTrendsExpandido = true"
                            />
                        </div>
                        <div
                            v-if="mostrarDetalheAtalho"
                            class="flex flex-col gap-2 rounded-lg border border-[var(--primary-color)]/35 bg-[var(--surface-ground)] px-3 py-2"
                        >
                            <div class="flex flex-wrap items-center justify-between gap-2">
                                <span class="text-xs font-medium uppercase tracking-wide text-[var(--text-color)]">
                                    {{ atalhoEmDetalhamento?.rotulo || 'Detalhe do pedido' }}
                                </span>
                                <Button
                                    label="Voltar"
                                    icon="pi pi-arrow-left"
                                    size="small"
                                    text
                                    severity="secondary"
                                    @click="cancelarDetalheAtalho"
                                />
                            </div>
                            <p class="m-0 text-xs text-[var(--text-color-secondary)]">
                                Escolha o serviço na carta. O mais comum aparece primeiro.
                            </p>
                            <div v-if="carregandoDetalheAtalho" class="flex items-center gap-2 py-1 text-sm">
                                <ProgressSpinner class="!h-5 !w-5" strokeWidth="6" />
                                <span>Carregando serviços…</span>
                            </div>
                            <div v-else class="flex flex-col gap-2">
                                <Button
                                    v-for="op in opcoesCartaAtalho"
                                    :key="op.servico_id"
                                    :label="rotuloOpcaoCartaAtalho(op)"
                                    size="small"
                                    :outlined="!op.padrao"
                                    :severity="op.padrao ? 'primary' : 'secondary'"
                                    class="justify-start text-left"
                                    :disabled="carregando"
                                    @click="enviarMensagemComAtalho(atalhoEmDetalhamento, op)"
                                />
                            </div>
                        </div>
                        <Textarea
                            v-model="inputTexto"
                            class="copiloto-textarea w-full"
                            rows="3"
                            auto-resize
                            :placeholder="placeholderCompositor"
                            :disabled="carregando"
                            @keydown="onTeclaInput"
                        />
                        <div
                            v-if="anexosPendentes.length && !mostrarBlocoAnexosNoChat"
                            class="flex flex-col gap-2 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] px-3 py-2"
                        >
                            <span class="text-xs font-medium uppercase tracking-wide text-[var(--text-color-secondary)]">
                                Anexos para enviar
                            </span>
                            <p
                                v-if="mostrarVinculoAnexoDemanda"
                                class="m-0 text-xs text-[var(--text-color-secondary)]"
                            >
                                Há mais de uma solicitação no rascunho — indique a qual cada arquivo pertence.
                            </p>
                            <div
                                v-for="(item, idx) in anexosPendentes"
                                :key="item.id"
                                class="flex flex-col gap-2 rounded-md border border-[var(--surface-border)] bg-[var(--surface-card)] p-2 sm:flex-row sm:items-center"
                            >
                                <div class="flex min-w-0 flex-1 items-center gap-2 text-sm">
                                    <i class="pi pi-paperclip shrink-0 text-[var(--text-color-secondary)]" aria-hidden="true" />
                                    <span class="truncate" :title="item.file.name">{{ item.file.name }}</span>
                            </div>
                                <Select
                                    v-if="mostrarVinculoAnexoDemanda"
                                    v-model="item.indiceDemanda"
                                    :options="opcoesDemandaAnexo"
                                    option-label="label"
                                    option-value="value"
                                    placeholder="Solicitação"
                                    class="w-full sm:w-[min(100%,14rem)]"
                                    :disabled="carregando"
                                    :invalid="item.indiceDemanda === null"
                                />
                                <Button
                                    icon="pi pi-times"
                                    severity="secondary"
                                    text
                                    rounded
                                    size="small"
                                    class="shrink-0 self-end sm:self-center"
                                    :disabled="carregando"
                                    aria-label="Remover anexo"
                                    @click="removerAnexoPendente(idx)"
                                />
                            </div>
                        </div>
                        <!-- Respostas rápidas no rodapé (opções numeradas / sim-não genérico) -->
                        <div
                            v-if="mostrarOpcoesSinapse || mostrarSimNaoBinario"
                            class="flex flex-col gap-2 rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] px-3 py-2"
                        >
                            <span class="text-xs font-medium uppercase tracking-wide text-[var(--text-color-secondary)]">
                                Resposta rápida
                            </span>
                            <div v-if="mostrarOpcoesSinapse" class="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                                <Button
                                    v-for="op in opcoesNumeradasDetectadas"
                                    :key="op.numero"
                                    v-tooltip.top="op.label"
                                    :label="rotuloOpcaoCurto(op)"
                                    severity="secondary"
                                    outlined
                                    class="justify-start text-left"
                                    @click="enviarMensagem(op.numero)"
                                />
                            </div>
                            <div v-else-if="mostrarSimNaoBinario" class="flex flex-wrap gap-2">
                                <Button label="Sim" severity="success" outlined @click="enviarMensagem('sim')" />
                                <Button label="Não" severity="secondary" outlined @click="enviarMensagem('não')" />
                            </div>
                        </div>

                        <div class="copiloto-composer-actions flex gap-2">
                            <Button
                                v-if="mostrarAnexarNoCompositor"
                                type="button"
                                label="Anexar"
                                icon="pi pi-paperclip"
                                severity="secondary"
                                outlined
                                class="flex-1 sm:flex-none"
                                :disabled="carregando"
                                @click="abrirSeletorAnexos"
                            />
                            <Button
                                label="Enviar"
                                icon="pi pi-send"
                                class="flex-[1.4] sm:ml-auto sm:flex-none sm:min-w-[8.5rem]"
                                :loading="carregando"
                                :disabled="!podeEnviar"
                                @click="enviar"
                            />
                        </div>
                    </div>
                </div>
            </div>

            <!-- Painel desktop -->
            <aside
                class="hidden w-[min(100%,22rem)] shrink-0 flex-col overflow-y-auto border-l border-[var(--surface-border)] bg-[var(--surface-section)] lg:flex"
            >
                <div class="shrink-0 border-b border-[var(--surface-border)] px-4 py-3">
                    <span class="font-semibold text-[var(--text-color)]">Contexto</span>
                    <p class="m-0 mt-1 text-xs text-[var(--text-color-secondary)]">Resumo do que já foi coletado</p>
                </div>
                <div class="flex flex-col p-4">
                    <CopilotoContextoPainel
                        :estado-atual="estadoAtual"
                        :estado-label="estadoLabel"
                        :severidade-estado="severidadeEstado"
                        :demandas="demandasExtraidas"
                        :anexos-pendentes-count="anexosPendentes.length"
                        :revisao-ativa="revisaoAtiva"
                        @revisar="revisarEtapa"
                    />
                </div>
            </aside>
        </div>

        <!-- Mobile: backdrop + gaveta -->
        <div
            v-if="painelContextoAberto"
            class="fixed inset-0 z-[100] bg-black/40 lg:hidden"
            @click="painelContextoAberto = false"
        />
        <div
            v-if="painelContextoAberto"
            class="copiloto-drawer-mobile fixed bottom-0 right-0 top-0 z-[110] flex w-full max-w-sm flex-col overflow-hidden border-l border-[var(--surface-border)] bg-[var(--surface-card)] shadow-2xl lg:hidden"
            @click.stop
        >
            <div class="flex shrink-0 items-center justify-between border-b border-[var(--surface-border)] px-4 py-3">
                <div>
                    <span class="font-semibold text-[var(--text-color)]">Contexto</span>
                    <p class="m-0 text-xs text-[var(--text-color-secondary)]">Resumo do que já foi coletado</p>
                </div>
                <Button icon="pi pi-times" text rounded severity="secondary" @click="painelContextoAberto = false" />
            </div>
            <div class="flex flex-1 flex-col overflow-y-auto p-4">
                <CopilotoContextoPainel
                    :estado-atual="estadoAtual"
                    :estado-label="estadoLabel"
                    :severidade-estado="severidadeEstado"
                    :demandas="demandasExtraidas"
                    :anexos-pendentes-count="anexosPendentes.length"
                    :revisao-ativa="revisaoAtiva"
                    @revisar="revisarEtapa"
                />
            </div>
        </div>
    </div>
</template>

<style scoped>
/* PrimeVue Textarea: harmonizar com Tailwind / tema */
:deep(.copiloto-textarea) {
    width: 100%;
    min-height: 5.5rem;
    resize: vertical;
    border-radius: 0.75rem;
    border: 1px solid var(--surface-border);
    background: var(--surface-ground);
    color: var(--text-color);
    padding: 0.75rem 1rem;
    font-size: 0.9375rem;
    line-height: 1.5;
    transition:
        border-color 0.15s ease,
        box-shadow 0.15s ease;
}

:deep(.copiloto-textarea:hover:not(:disabled)) {
    border-color: var(--primary-color);
}

:deep(.copiloto-textarea:focus) {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary-color) 25%, transparent);
}

:deep(.copiloto-textarea:disabled) {
    opacity: 0.65;
    cursor: not-allowed;
}

.copiloto-header__actions :deep(.copiloto-header__btn) {
    justify-content: center;
}

.copiloto-header__actions :deep(.copiloto-header__btn--nova) {
    flex-shrink: 0;
}

.copiloto-header__actions :deep(.copiloto-header__btn--nova .p-button-label) {
    white-space: nowrap;
}

@media (min-width: 640px) {
    .copiloto-header__actions :deep(.copiloto-header__btn) {
        justify-content: flex-start;
    }
}

.copiloto-composer-actions :deep(.p-button) {
    min-height: 2.75rem;
}

.copiloto-drawer-mobile {
    animation: copiloto-slide-in 0.22s ease-out;
}

@keyframes copiloto-slide-in {
    from {
        transform: translateX(100%);
    }
    to {
        transform: translateX(0);
    }
}
</style>
