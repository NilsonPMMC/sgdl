<script setup>
import { computed } from 'vue';
import Tag from 'primevue/tag';
import Button from 'primevue/button';

const props = defineProps({
    estadoAtual: { type: String, default: 'COLETA_DADOS' },
    estadoLabel: { type: String, default: '' },
    severidadeEstado: { type: String, default: 'info' },
    demandas: { type: Array, default: () => [] },
    anexosPendentesCount: { type: Number, default: 0 },
    revisaoAtiva: { type: Object, default: null }
});

const emit = defineEmits(['revisar']);

const ETAPAS = [
    { codigo: 'COLETA_DADOS', rotulo: 'Pedido', icone: 'pi-comment' },
    { codigo: 'CONFIRMACAO_SINAPSE', rotulo: 'Serviço', icone: 'pi-book' },
    { codigo: 'COLETA_ENDERECO', rotulo: 'Local', icone: 'pi-map-marker' },
    { codigo: 'VALIDACAO_FINAL', rotulo: 'Revisão', icone: 'pi-check-circle' }
];

const indiceEtapaAtual = computed(() => {
    const idx = ETAPAS.findIndex((e) => e.codigo === props.estadoAtual);
    return idx >= 0 ? idx : 0;
});

function sinapseIdValido(valor) {
    if (valor == null || valor === '') return false;
    const n = Number(valor);
    return Number.isInteger(n) && n > 0;
}

function servicoConfirmado(demanda) {
    if (demanda?.servico?.confirmado === true) return true;
    const sid = demanda?.servico?.sinapse_servico_id ?? demanda?.sinapse_servico_id_sugerido;
    return sinapseIdValido(sid);
}

function tendenciaConfirmada(demanda) {
    return Boolean(
        demanda?.tendencia_id ?? demanda?.tendencia?.id ?? demanda?.origem_vinculo === 'TENDENCIA'
    );
}

function demandaForaCompetencia(demanda) {
    return Boolean(demanda?.fora_competencia);
}

function requerLocal(demanda) {
    return demanda?.requer_localizacao !== false;
}

function temLocal(demanda) {
    if (demanda?.endereco_opcional_dispensado) return true;
    if (demanda?.local_confirmado_usuario === true) return true;
    if (demanda?.latitude != null && demanda?.longitude != null) return false;
    return false;
}

function formatarEndereco(demanda) {
    const end = demanda?.endereco;
    if (end && typeof end === 'object') {
        const rua = [end.logradouro, end.numero].filter(Boolean).join(', ');
        const partes = [rua, end.complemento, end.bairro, end.cep].filter(Boolean);
        if (partes.length) return partes.join(' · ');
    }
    if (demanda?.latitude != null && demanda?.longitude != null) {
        return `Coordenadas: ${Number(demanda.latitude).toFixed(5)}, ${Number(demanda.longitude).toFixed(5)}`;
    }
    return null;
}

function rotuloServico(demanda) {
    if (demandaForaCompetencia(demanda)) {
        return demanda?.motivo_recusa || 'Fora da competência municipal';
    }
    if (demanda?.descartada) return 'Solicitação descartada';
    const trilha = demanda?.trilha_ouvidoria;
    if (trilha && typeof trilha === 'object') {
        const mapa = {
            sugestao: 'Sugestão',
            elogio: 'Elogio',
            denuncia: 'Denúncia',
            reclamacao: 'Reclamação'
        };
        const sub = trilha.subtipo || demanda?.subtipo_ouvidoria;
        return `Ouvidoria — ${mapa[sub] || 'manifestação'}`;
    }
    if (servicoConfirmado(demanda)) {
        return demanda?.servico?.nome || 'Serviço da carta confirmado';
    }
    if (tendenciaConfirmada(demanda)) {
        return demanda?.tendencia?.titulo || 'Tendência registrada';
    }
    if (demanda?.servico?.nome) return `${demanda.servico.nome} (aguardando confirmação)`;
    if (demanda?.candidatos_sinapse?.length) return 'Escolha o serviço na conversa';
    return 'Ainda não vinculado';
}

function orgaoServico(demanda) {
    return demanda?.servico?.orgao || null;
}

function rotuloFonteOuvidoria(demanda) {
    const trilha = demanda?.trilha_ouvidoria;
    if (!trilha || typeof trilha !== 'object') return null;
    if (trilha.detalhe_fonte) return trilha.detalhe_fonte;
    const mapa = {
        agente: 'Classificado pelo Agente',
        leitura_automatica: 'Confirmado pela leitura automática do pedido',
        combinada: 'Agente e leitura automática do pedido',
        // Sessões antigas
        groq: 'Classificado pelo Agente',
        regex: 'Confirmado pela leitura automática do pedido',
        hibrido: 'Agente e leitura automática do pedido'
    };
    return mapa[trilha.fonte_classificacao] || null;
}

function statusDemanda(demanda) {
    if (demanda?.descartada) return { rotulo: 'Descartada', severity: 'secondary' };
    if (demandaForaCompetencia(demanda)) return { rotulo: 'Fora da competência', severity: 'danger' };
    if (demanda?.trilha_ouvidoria) return { rotulo: 'Ouvidoria', severity: 'success' };
    const localPendente =
        (requerLocal(demanda) || demanda?.corpus_aguarda_complemento) && !temLocal(demanda);
    if (localPendente) return { rotulo: 'Falta o local', severity: 'warn' };
    if (servicoConfirmado(demanda)) return { rotulo: 'Serviço OK', severity: 'success' };
    if (tendenciaConfirmada(demanda)) return { rotulo: 'Tendência', severity: 'info' };
    if (props.estadoAtual === 'CONFIRMACAO_SINAPSE') return { rotulo: 'Aguardando serviço', severity: 'warn' };
    return { rotulo: 'Em coleta', severity: 'info' };
}

function camposDemanda(demanda) {
    const tituloOk = Boolean((demanda?.titulo || '').trim());
    const descOk = Boolean((demanda?.descricao || '').trim());
    const assuntoOk = tituloOk || descOk;

    let servicoOk = false;
    let servicoPendente = true;
    if (demanda?.descartada || demandaForaCompetencia(demanda)) {
        servicoOk = true;
        servicoPendente = false;
    } else if (servicoConfirmado(demanda) || tendenciaConfirmada(demanda)) {
        servicoOk = true;
        servicoPendente = false;
    }

    const localNecessario =
        (requerLocal(demanda) || demanda?.corpus_aguarda_complemento) &&
        !demanda?.descartada &&
        !demandaForaCompetencia(demanda);
    const localOk = !localNecessario || temLocal(demanda);

    const anexos = Array.isArray(demanda?.anexos) ? demanda.anexos.length : 0;
    const enderecoFmt = formatarEndereco(demanda);

    return [
        {
            chave: 'assunto',
            rotulo: 'Assunto',
            ok: assuntoOk,
            valor: (demanda?.titulo || demanda?.descricao || '').trim(),
            pendente: !assuntoOk
        },
        {
            chave: 'servico',
            rotulo: 'Serviço / trilha',
            ok: servicoOk,
            valor: rotuloServico(demanda),
            pendente: servicoPendente && !demanda?.descartada && !demandaForaCompetencia(demanda)
        },
        {
            chave: 'local',
            rotulo: 'Local',
            ok: localOk,
            valor:
                enderecoFmt ||
                (demanda?.endereco_resumo && !localOk ? demanda.endereco_resumo : null) ||
                (demanda?.geocode_alerta && !localOk ? demanda.geocode_alerta : null) ||
                (localNecessario && !localOk ? 'Pendente — confirme o local ou informe CEP' : null),
            pendente: localNecessario && !localOk,
            opcional: !localNecessario
        },
        {
            chave: 'anexos',
            rotulo: 'Anexos',
            ok: anexos > 0,
            valor: anexos > 0 ? `${anexos} arquivo(s) vinculado(s)` : 'Nenhum (opcional)',
            pendente: false,
            opcional: true
        }
    ];
}

function podeRevisarCampo(campo, demanda) {
    if (demanda?.descartada || demandaForaCompetencia(demanda)) return false;
    switch (campo.chave) {
        case 'assunto':
            return campo.ok;
        case 'servico':
            return campo.ok && !campo.pendente;
        case 'local':
            return servicoConfirmado(demanda) || tendenciaConfirmada(demanda);
        case 'anexos':
            return props.estadoAtual === 'VALIDACAO_FINAL' || campo.ok;
        default:
            return false;
    }
}

const mapaEtapaRevisao = {
    assunto: 'pedido',
    servico: 'servico',
    local: 'local',
    anexos: 'anexos'
};

function solicitarRevisao(indice, chave) {
    const etapa = mapaEtapaRevisao[chave];
    if (!etapa) return;
    emit('revisar', { indice, etapa });
}

function campoEmRevisao(indice, chave) {
    const etapa = mapaEtapaRevisao[chave];
    if (!etapa || !props.revisaoAtiva) return false;
    return props.revisaoAtiva.etapa === etapa && props.revisaoAtiva.indiceDemanda === indice;
}

const resumoDemandas = computed(() =>
    props.demandas.map((d, i) => ({
        indice: i,
        demanda: d,
        status: statusDemanda(d),
        campos: camposDemanda(d),
        orgao: orgaoServico(d)
    }))
);

const totalPendencias = computed(() =>
    resumoDemandas.value.reduce(
        (acc, item) => acc + item.campos.filter((c) => c.pendente).length,
        0
    )
);

const mensagemEtapa = computed(() => {
    switch (props.estadoAtual) {
        case 'COLETA_DADOS':
            return 'Descreva o pedido na conversa. Cada solicitação identificada aparece abaixo.';
        case 'CONFIRMACAO_SINAPSE':
            return 'Confirme o serviço da carta ou registre como tendência no chat.';
        case 'COLETA_ENDERECO':
            return 'Informe onde o serviço deve ser executado (endereço, bairro ou localização).';
        case 'VALIDACAO_FINAL':
            return 'Revise o resumo e confirme a geração dos rascunhos de ofício.';
        default:
            return 'Acompanhe o que já foi entendido pela IA.';
    }
});
</script>

<template>
    <div class="copiloto-contexto flex flex-col gap-4">
        <!-- Etapas do fluxo -->
        <div>
            <div class="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-color-secondary)]">
                Etapa atual
            </div>
            <Tag :value="estadoLabel" :severity="severidadeEstado" />
            <p class="m-0 mt-2 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                {{ mensagemEtapa }}
            </p>
            <ol class="copiloto-etapas m-0 mt-3 flex list-none gap-1 p-0">
                <li
                    v-for="(etapa, idx) in ETAPAS"
                    :key="etapa.codigo"
                    class="copiloto-etapa flex flex-1 flex-col items-center gap-1 text-center"
                    :class="{
                        'copiloto-etapa--atual': idx === indiceEtapaAtual,
                        'copiloto-etapa--feita': idx < indiceEtapaAtual
                    }"
                >
                    <span class="copiloto-etapa-icone" :title="etapa.rotulo">
                        <i :class="['pi', etapa.icone]" aria-hidden="true" />
                    </span>
                    <span class="copiloto-etapa-rotulo">{{ etapa.rotulo }}</span>
                </li>
            </ol>
        </div>

        <!-- Resumo geral -->
        <div
            v-if="demandas.length"
            class="rounded-lg border border-[var(--surface-border)] bg-[var(--surface-ground)] px-3 py-2"
        >
            <div class="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span class="font-medium text-[var(--text-color)]">
                    {{ demandas.length }} solicitação{{ demandas.length > 1 ? 'ões' : '' }}
                </span>
                <span v-if="totalPendencias" class="text-xs text-amber-600 dark:text-amber-400">
                    {{ totalPendencias }} pendência{{ totalPendencias > 1 ? 's' : '' }}
                </span>
                <span v-else class="text-xs text-green-600 dark:text-green-400">Pronto para avançar</span>
            </div>
            <p v-if="anexosPendentesCount" class="m-0 mt-1 text-xs text-[var(--text-color-secondary)]">
                <i class="pi pi-paperclip mr-1" aria-hidden="true" />
                {{ anexosPendentesCount }} anexo(s) aguardando envio
            </p>
        </div>

        <!-- Cards por solicitação -->
        <div v-if="resumoDemandas.length" class="flex flex-col gap-3">
            <div
                v-for="item in resumoDemandas"
                :key="item.indice"
                class="overflow-hidden rounded-lg border border-[var(--surface-border)] bg-[var(--surface-card)] shadow-sm"
                :class="{
                    'opacity-60': item.demanda?.descartada,
                    'ring-2 ring-[var(--primary-color)]/40': props.revisaoAtiva?.indiceDemanda === item.indice
                }"
            >
                <div class="border-b border-[var(--surface-border)] px-3 py-2">
                    <div class="flex flex-wrap items-start justify-between gap-2">
                        <div class="min-w-0 flex-1">
                            <span class="text-xs font-medium text-[var(--text-color-secondary)]">
                                Solicitação {{ item.indice + 1 }}
                            </span>
                            <p class="m-0 mt-0.5 text-sm font-semibold leading-snug text-[var(--text-color)]">
                                {{ item.demanda?.titulo || 'Sem título ainda' }}
                            </p>
                        </div>
                        <Tag :value="item.status.rotulo" :severity="item.status.severity" class="!text-xs shrink-0" />
                    </div>
                    <p
                        v-if="item.demanda?.descricao && item.demanda.descricao !== item.demanda?.titulo"
                        class="m-0 mt-1 line-clamp-2 text-xs leading-relaxed text-[var(--text-color-secondary)]"
                    >
                        {{ item.demanda.descricao }}
                    </p>
                </div>

                <ul class="m-0 list-none p-0">
                    <li
                        v-for="campo in item.campos"
                        :key="campo.chave"
                        class="flex gap-2 border-b border-[var(--surface-border)] px-3 py-2 last:border-b-0"
                        :class="{ 'bg-[var(--primary-color)]/5': campoEmRevisao(item.indice, campo.chave) }"
                    >
                        <span class="mt-0.5 shrink-0" aria-hidden="true">
                            <i
                                v-if="campo.pendente"
                                class="pi pi-exclamation-circle text-amber-500"
                            />
                            <i
                                v-else-if="campo.ok"
                                class="pi pi-check-circle text-green-500"
                            />
                            <i
                                v-else-if="campo.opcional"
                                class="pi pi-minus-circle text-[var(--text-color-secondary)]"
                            />
                            <i v-else class="pi pi-circle text-[var(--text-color-secondary)]" />
                        </span>
                        <div class="min-w-0 flex-1">
                            <div class="text-xs font-medium text-[var(--text-color)]">
                                {{ campo.rotulo }}
                                <span v-if="campo.opcional && !campo.ok" class="font-normal text-[var(--text-color-secondary)]">
                                    (opcional)
                                </span>
                            </div>
                            <p
                                class="m-0 mt-0.5 text-xs leading-relaxed"
                                :class="
                                    campo.pendente
                                        ? 'text-amber-700 dark:text-amber-300'
                                        : campo.valor
                                          ? 'text-[var(--text-color-secondary)]'
                                          : 'text-[var(--text-color-secondary)] italic'
                                "
                            >
                                {{
                                    campo.pendente
                                        ? 'Aguardando na conversa'
                                        : campo.valor || '—'
                                }}
                            </p>
                            <p
                                v-if="campo.chave === 'servico' && rotuloFonteOuvidoria(item.demanda)"
                                class="m-0 mt-0.5 text-xs text-sky-700 dark:text-sky-300"
                            >
                                {{ rotuloFonteOuvidoria(item.demanda) }}
                            </p>
                            <p
                                v-if="campo.chave === 'servico' && item.orgao"
                                class="m-0 mt-0.5 text-xs text-[var(--text-color-secondary)]"
                            >
                                Órgão: {{ item.orgao }}
                            </p>
                            <Button
                                v-if="podeRevisarCampo(campo, item.demanda)"
                                label="Revisar"
                                icon="pi pi-pencil"
                                size="small"
                                text
                                class="!mt-1 !h-auto !px-0 !py-0"
                                @click="solicitarRevisao(item.indice, campo.chave)"
                            />
                        </div>
                    </li>
                </ul>
            </div>
        </div>

        <!-- Vazio -->
        <div
            v-else
            class="rounded-lg border border-dashed border-[var(--surface-border)] bg-[var(--surface-ground)] px-4 py-6 text-center"
        >
            <i class="pi pi-inbox text-2xl text-[var(--text-color-secondary)]" aria-hidden="true" />
            <p class="m-0 mt-2 text-sm font-medium text-[var(--text-color)]">Nada identificado ainda</p>
            <p class="m-0 mt-1 text-xs leading-relaxed text-[var(--text-color-secondary)]">
                Descreva o pedido do cidadão na conversa. Assunto, serviço e local aparecerão aqui conforme forem
                entendidos.
            </p>
        </div>
    </div>
</template>

<style scoped>
.copiloto-etapas {
    counter-reset: etapa;
}

.copiloto-etapa-icone {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 50%;
    background: var(--surface-ground);
    border: 1px solid var(--surface-border);
    color: var(--text-color-secondary);
    font-size: 0.75rem;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
}

.copiloto-etapa--atual .copiloto-etapa-icone {
    background: color-mix(in srgb, var(--primary-color) 15%, transparent);
    border-color: var(--primary-color);
    color: var(--primary-color);
}

.copiloto-etapa--feita .copiloto-etapa-icone {
    background: color-mix(in srgb, var(--p-green-500) 12%, transparent);
    border-color: var(--p-green-500);
    color: var(--p-green-600);
}

.copiloto-etapa-rotulo {
    font-size: 0.625rem;
    line-height: 1.2;
    color: var(--text-color-secondary);
}

.copiloto-etapa--atual .copiloto-etapa-rotulo {
    color: var(--text-color);
    font-weight: 600;
}

.line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
</style>
