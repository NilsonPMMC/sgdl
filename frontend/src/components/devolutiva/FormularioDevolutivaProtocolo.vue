<script setup>
import Chip from 'primevue/chip';
import Checkbox from 'primevue/checkbox';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Divider from 'primevue/divider';
import FileUpload from 'primevue/fileupload';
import Message from 'primevue/message';
import Tag from 'primevue/tag';
import DescricaoTramitacaoEditor from '@/components/tramitacao/DescricaoTramitacaoEditor.vue';
import DestinosTramitacaoEditor from '@/components/tramitacao/DestinosTramitacaoEditor.vue';
import { computed, onMounted, ref, watch } from 'vue';
import { MODO_DESPACHO } from '@/constants/tramitacaoFormulario';
import { filtrarArquivosDuplicados, mensagemAnexosRejeitados } from '@/utils/anexoValidacao';
import { descricaoTramitacaoParaExibicao } from '@/utils/tramitacaoTexto';
import ApiService from '@/service/ApiService';

const props = defineProps({
    modelValue: { type: Object, required: true },
    demandaId: { type: [Number, String], required: true },
    demandaContext: { type: Object, default: () => ({}) },
    orgaos: { type: Array, default: () => [] },
    usaFluxoOperacional: { type: Boolean, default: false },
    historicoTecnico: { type: Object, default: null },
    previewAtiva: { type: Boolean, default: false }
});

const emit = defineEmits(['update:modelValue', 'anexos-rejeitados', 'invalidar-preview']);

const anexosOperacionais = ref([]);
const carregandoAnexos = ref(false);
const historicoLocal = ref(null);
const carregandoHistorico = ref(false);

const historicoEfetivo = computed(() => historicoLocal.value ?? props.historicoTecnico);

const form = computed({
    get: () => props.modelValue,
    set: (v) => emit('update:modelValue', v)
});

function patch(partial, { invalidate = false } = {}) {
    emit('update:modelValue', { ...props.modelValue, ...partial });
    if (invalidate) emit('invalidar-preview');
}

const orgaosIntegraveisAlerta = computed(() => props.orgaos || []);

const contextoResposta = computed(() =>
    props.usaFluxoOperacional ? 'conclusao_final' : 'devolutiva'
);

const editorAlertaRef = ref(null);

function validarAlertaDestinos() {
    const linhas = (form.value.alerta_destinos || []).filter((d) => d.secretaria_id);
    if (!linhas.length) return { ok: true, erros: [], mensagem: null };
    return editorAlertaRef.value?.validarSetores?.() ?? { ok: true, erros: [], mensagem: null };
}

defineExpose({
    validarAlertaDestinos
});

async function carregarAnexosOperacionais() {
    if (!props.demandaId) return;
    carregandoAnexos.value = true;
    try {
        const { data } = await ApiService.getAnexosOperacionais(props.demandaId);
        anexosOperacionais.value = Array.isArray(data) ? data : [];
    } catch {
        anexosOperacionais.value = [];
    } finally {
        carregandoAnexos.value = false;
    }
}

async function carregarHistoricoTecnico() {
    if (!props.demandaId || !props.usaFluxoOperacional) {
        historicoLocal.value = null;
        return;
    }
    carregandoHistorico.value = true;
    try {
        const { data } = await ApiService.getHistoricoTecnicoOperacional(props.demandaId);
        historicoLocal.value = data;
    } catch {
        historicoLocal.value = props.historicoTecnico;
    } finally {
        carregandoHistorico.value = false;
    }
}

onMounted(() => {
    carregarAnexosOperacionais();
    carregarHistoricoTecnico();
});
watch(() => props.demandaId, () => {
    carregarAnexosOperacionais();
    carregarHistoricoTecnico();
});

function toggleAnexoOperacional(anexo) {
    const ids = [...(form.value.anexos_tramitacao_ids || [])];
    const idx = ids.indexOf(anexo.id);
    if (idx >= 0) ids.splice(idx, 1);
    else ids.push(anexo.id);
    patch({ anexos_tramitacao_ids: ids });
}

function anexoSelecionado(id) {
    return (form.value.anexos_tramitacao_ids || []).includes(id);
}

function onNovosAnexos(event) {
    const nomes = [
        ...(form.value.anexos_novos || []).map((f) => f.name),
        ...(form.value.anexos_tramitacao_ids || []).map((id) => {
            const a = anexosOperacionais.value.find((x) => x.id === id);
            return a?.nome;
        })
    ].filter(Boolean);
    const { aceitos, rejeitados } = filtrarArquivosDuplicados(event.files, nomes);
    patch({ anexos_novos: [...(form.value.anexos_novos || []), ...aceitos] });
    const msg = mensagemAnexosRejeitados(rejeitados);
    if (msg) emit('anexos-rejeitados', msg);
}

function removerNovoAnexo(nome) {
    patch({
        anexos_novos: (form.value.anexos_novos || []).filter((f) => f.name !== nome)
    });
}

function formatarDataEvento(iso) {
    if (!iso) return '';
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return '';
    return dt.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function rotuloEventoHistorico(ev) {
    const org = ev?.orgao_nome || 'Secretaria';
    return ev?.setor_nome ? `${org} › ${ev.setor_nome}` : org;
}

function rotuloOrigemAnexo(anexo) {
    return anexo?.origem_label || anexo?.tipo_display || '—';
}

function parecerEventoExibicao(ev) {
    return descricaoTramitacaoParaExibicao(ev?.parecer || '');
}

const eventosHistoricoExibicao = computed(() =>
    (historicoEfetivo.value?.eventos_tecnicos || []).map((ev) => ({
        ev,
        rotulo: rotuloEventoHistorico(ev),
        parecer: parecerEventoExibicao(ev),
        data: formatarDataEvento(ev.timestamp)
    }))
);
</script>

<template>
    <div class="flex flex-col gap-5">
        <Message
            v-if="previewAtiva"
            severity="success"
            :closable="false"
            class="text-sm m-0"
        >
            Prévia de assinatura gerada. Revise o conteúdo abaixo, preencha as declarações na seção
            <strong>Assinatura eletrônica</strong> e confirme o envio.
        </Message>

        <div
            v-if="usaFluxoOperacional && (carregandoHistorico || eventosHistoricoExibicao.length)"
            class="p-3 surface-ground border-round"
        >
            <span class="font-semibold text-sm block mb-2">Histórico técnico consolidado</span>
            <p v-if="carregandoHistorico" class="text-sm text-muted-color m-0">Carregando encerramentos…</p>
            <template v-else>
            <div
                v-for="item in eventosHistoricoExibicao"
                :key="item.ev.tramitacao_id || item.ev.no_id || item.rotulo"
                class="mb-3 pb-3 border-bottom-1 surface-border last:border-none last:mb-0 last:pb-0"
            >
                <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <Tag :value="item.rotulo" severity="secondary" />
                    <span v-if="item.data" class="text-xs text-muted-color">
                        {{ item.data }}
                    </span>
                </div>
                <p v-if="item.ev.responsavel" class="m-0 mb-2 text-xs text-muted-color">
                    Registrado por <strong class="text-color">{{ item.ev.responsavel }}</strong>
                </p>
                <div
                    v-if="item.parecer.modo === 'html'"
                    class="tramitacao-descricao-html m-0 text-sm text-surface-800 dark:text-surface-100"
                    v-html="item.parecer.html"
                />
                <p
                    v-else-if="item.parecer.modo === 'texto'"
                    class="m-0 text-sm whitespace-pre-wrap text-surface-800 dark:text-surface-100"
                >
                    {{ item.parecer.texto }}
                </p>
            </div>
            </template>
        </div>

        <div>
            <DescricaoTramitacaoEditor
                :model-value="form.parecer_resposta"
                label="Resposta Final"
                :contexto="contextoResposta"
                :demanda-id="demandaId"
                :demanda-context="demandaContext"
                editor-style="min-height: 220px"
                @update:model-value="patch({ parecer_resposta: $event }, { invalidate: true })"
            />
            <p v-if="previewAtiva" class="text-xs text-muted-color mt-2 mb-0">
                Alterar o texto invalida a prévia — será necessário gerar assinatura novamente.
            </p>
        </div>

        <Divider />

        <div>
            <span class="font-semibold block mb-2">Anexos do processo</span>
            <p class="text-sm text-muted-color mt-0 mb-3">
                Selecione documentos já enviados nas tramitações operacionais para compor o despacho final.
            </p>
            <DataTable
                v-if="anexosOperacionais.length"
                :value="anexosOperacionais"
                :loading="carregandoAnexos"
                size="small"
                striped-rows
                data-key="id"
            >
                <Column header="" style="width: 3rem">
                    <template #body="{ data }">
                        <Checkbox
                            :model-value="anexoSelecionado(data.id)"
                            binary
                            @update:model-value="toggleAnexoOperacional(data)"
                        />
                    </template>
                </Column>
                <Column field="nome" header="Arquivo" />
                <Column header="Setor">
                    <template #body="{ data }">
                        {{ rotuloOrigemAnexo(data) }}
                    </template>
                </Column>
                <Column header="">
                    <template #body="{ data }">
                        <a
                            v-if="data.arquivo"
                            :href="data.arquivo"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="text-sm text-primary"
                        >
                            Abrir
                        </a>
                    </template>
                </Column>
            </DataTable>
            <p v-else-if="!carregandoAnexos" class="text-sm text-muted-color m-0">
                Nenhum anexo operacional disponível neste processo.
            </p>
        </div>

        <div>
            <label class="block mb-2 font-semibold">Novos anexos (opcional)</label>
            <FileUpload
                mode="basic"
                multiple
                accept="image/*,application/pdf"
                :max-file-size="5000000"
                choose-label="Selecionar PDF/fotos"
                @select="onNovosAnexos"
            />
            <div v-if="form.anexos_novos?.length" class="flex flex-wrap gap-2 mt-2">
                <Chip
                    v-for="file in form.anexos_novos"
                    :key="file.name"
                    :label="file.name"
                    removable
                    @remove="removerNovoAnexo(file.name)"
                />
            </div>
        </div>

        <Divider />

        <div>
            <span class="font-semibold block mb-2">Encaminhar alerta (opcional)</span>
            <p class="text-sm text-muted-color mt-0 mb-3">
                Informe órgãos e setores que receberão notificação e acesso somente leitura à devolutiva final.
            </p>
            <DestinosTramitacaoEditor
                ref="editorAlertaRef"
                :model-value="form.alerta_destinos"
                :modo="MODO_DESPACHO"
                :orgaos="orgaos"
                :orgaos-integraveis="orgaosIntegraveisAlerta"
                :permitir-integrados="true"
                :orgaos-editaveis="true"
                @update:model-value="patch({ alerta_destinos: $event })"
            />
        </div>
    </div>
</template>
