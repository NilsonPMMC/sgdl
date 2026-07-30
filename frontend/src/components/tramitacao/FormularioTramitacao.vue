<script setup>
import Checkbox from 'primevue/checkbox';
import FileUpload from 'primevue/fileupload';
import Select from 'primevue/select';
import Tag from 'primevue/tag';
import DestinosTramitacaoEditor from '@/components/tramitacao/DestinosTramitacaoEditor.vue';
import DescricaoTramitacaoEditor from '@/components/tramitacao/DescricaoTramitacaoEditor.vue';
import PanelNosEquivalentes from '@/components/demanda/PanelNosEquivalentes.vue';
import { computed, ref } from 'vue';
import { filtrarArquivosDuplicados, mensagemAnexosRejeitados } from '@/utils/anexoValidacao';
import {
    extrairDestinosPlaceholder
} from '@/constants/textoPadraoDespacho';
import {
    MODO_ANDAMENTO,
    MODO_DESPACHO,
    REGRAS_ASSINATURA,
    contarPernasDestinos
} from '@/constants/tramitacaoFormulario';

const props = defineProps({
    modo: {
        type: String,
        required: true,
        validator: (v) => [MODO_DESPACHO, MODO_ANDAMENTO].includes(v)
    },
    modelValue: { type: Object, required: true },
    orgaos: { type: Array, default: () => [] },
    orgaoCompetenteId: { type: Number, default: null },
    orgaoCompetenteNome: { type: String, default: '' },
    orgaosIntegraveis: { type: Array, default: () => [] },
    orgaoFixoId: { type: Number, default: null },
    orgaosEditaveis: { type: Boolean, default: false },
    permitirIntegrados: { type: Boolean, default: false },
    exibirDestinos: { type: Boolean, default: true },
    exibirTipoAndamento: { type: Boolean, default: true },
    labelDescricao: { type: String, default: '' },
    tiposAndamento: { type: Array, default: () => [] },
    layout: {
        type: String,
        default: 'dialog',
        validator: (v) => ['dialog', 'card'].includes(v)
    },
    /** Sobrescreve REGRAS_ASSINATURA[modo] — ex.: scatter encerrar obrigatório. */
    regrasAssinatura: { type: Object, default: null },
    /** Oculta checkbox de assinatura no formulário (ex.: despacho protocolo usa AssinaturaDespachoPanel). */
    exibirAssinaturaFormulario: { type: Boolean, default: true },
    /** Scatter-gather — painel de nós do operador (1+ na secretaria). */
    demandaId: { type: [Number, String], default: null },
    /** Contexto para placeholders em textos padrão (protocolo, autor, etc.). */
    demandaContext: { type: Object, default: () => ({}) },
    gruposNosPainel: { type: Array, default: () => [] },
    /** @deprecated use gruposNosPainel */
    gruposNosEquivalentes: { type: Array, default: () => [] },
    acoesNosEquivalentes: { type: Array, default: () => [] },
    noAtivoId: { type: [Number, String], default: null },
    responderTodos: { type: Boolean, default: false },
    nosSelecionadosIds: { type: Array, default: () => [] }
});

const emit = defineEmits([
    'update:modelValue',
    'invalidar-preview',
    'anexos-rejeitados',
    'anexo-invalido',
    'destinos-change',
    'nos-equivalentes-success',
    'nos-equivalentes-error',
    'usar-no-canonico',
    'encerrar-lote',
    'encerrar-selecionados',
    'update:responderTodos',
    'update:nosSelecionadosIds'
]);

const gruposPainelOperador = computed(() => {
    if (props.gruposNosPainel?.length) return props.gruposNosPainel;
    return Array.isArray(props.gruposNosEquivalentes) ? props.gruposNosEquivalentes : [];
});

const exibirPainelNosEquivalentes = computed(
    () => Boolean(props.demandaId) && gruposPainelOperador.value.length > 0
);

const regrasAssinatura = computed(() => props.regrasAssinatura || REGRAS_ASSINATURA[props.modo] || {});

function patchForm(partial) {
    emit('update:modelValue', { ...props.modelValue, ...partial });
}

function onDestinosChange(destinos) {
    emit('destinos-change', destinos);
    emit('invalidar-preview');
}

function onAnexosSelected(event) {
    const nomes = (props.modelValue.anexos || []).map((f) => f.name);
    const { aceitos, rejeitados } = filtrarArquivosDuplicados(event.files, nomes);
    patchForm({ anexos: [...(props.modelValue.anexos || []), ...aceitos] });
    const msg = mensagemAnexosRejeitados(rejeitados);
    if (msg) emit('anexos-rejeitados', msg);
}

function removerAnexo(nome) {
    patchForm({
        anexos: (props.modelValue.anexos || []).filter((f) => f.name !== nome)
    });
}

const maxFileSize = 5000000;

function onAnexoInvalido(event) {
    const tipo = event?.type || 'invalido';
    const nome = event?.file?.name || 'arquivo';
    const limiteMb = Math.round(maxFileSize / 1000000);
    const msg =
        tipo === 'fileSize'
            ? `"${nome}" excede ${limiteMb} MB. Reduza a imagem ou envie PDF.`
            : `"${nome}" não é um tipo permitido (PDF ou imagem).`;
    emit('anexo-invalido', msg);
}

const contextoDescricao = computed(() =>
    props.modo === MODO_DESPACHO ? 'despacho' : props.modelValue.tipo || 'andamento'
);

const contextoPlaceholdersDemanda = computed(() => ({
    ...props.demandaContext,
    ...extrairDestinosPlaceholder(props.modelValue?.destinos, props.orgaos)
}));

const editorDestinosRef = ref(null);

function validarDestinos() {
    return editorDestinosRef.value?.validarSetores?.() ?? { ok: true, erros: [], mensagem: null };
}

function contarPernasValidas() {
    const mapRef = editorDestinosRef.value?.unidadesPorOrgao;
    const map = mapRef?.value ?? mapRef ?? {};
    return contarPernasDestinos(props.modelValue.destinos, map);
}

defineExpose({
    validarDestinos,
    contarPernasValidas
});
</script>

<template>
    <div class="flex flex-col gap-4">
        <PanelNosEquivalentes
            v-if="exibirPainelNosEquivalentes"
            :demanda-id="demandaId"
            :grupos="gruposPainelOperador"
            :acoes-disponiveis="acoesNosEquivalentes"
            :no-ativo-id="noAtivoId"
            :responder-todos="responderTodos"
            :nos-selecionados-ids="nosSelecionadosIds"
            @success="(data) => emit('nos-equivalentes-success', data)"
            @error="(msg) => emit('nos-equivalentes-error', msg)"
            @usar-canonico="(payload) => emit('usar-no-canonico', payload)"
            @encerrar-lote="(grupo) => emit('encerrar-lote', grupo)"
            @encerrar-selecionados="(grupo) => emit('encerrar-selecionados', grupo)"
            @update:responder-todos="(v) => emit('update:responderTodos', v)"
            @update:nos-selecionados-ids="(v) => emit('update:nosSelecionadosIds', v)"
        />

        <slot name="prepend" />

        <!-- 1. Destinos: órgão → setor (primeiro passo) -->
        <DestinosTramitacaoEditor
            v-if="exibirDestinos"
            ref="editorDestinosRef"
            :model-value="modelValue.destinos"
            :modo="modo"
            :orgaos="orgaos"
            :orgao-competente-id="orgaoCompetenteId"
            :orgao-competente-nome="orgaoCompetenteNome"
            :orgaos-integraveis="orgaosIntegraveis"
            :orgao-fixo-id="orgaoFixoId"
            :orgaos-editaveis="orgaosEditaveis"
            :permitir-integrados="permitirIntegrados"
            @update:model-value="patchForm({ destinos: $event })"
            @change="onDestinosChange"
        />

        <!-- 2. Tipo (andamento) -->
        <div v-if="modo === MODO_ANDAMENTO && exibirTipoAndamento">
            <label for="tipoTramitacao" class="block mb-2 font-medium">
                Tipo de andamento
                <span v-if="permitirIntegrados" class="font-normal text-muted-color text-sm">
                    (opcional se abrir apenas tramitação transversal)
                </span>
            </label>
            <Select
                id="tipoTramitacao"
                :model-value="modelValue.tipo"
                :options="tiposAndamento"
                option-label="label"
                option-value="value"
                placeholder="Selecione o tipo"
                fluid
                @update:model-value="patchForm({ tipo: $event })"
            />
        </div>

        <!-- 3. Descrição + IA -->
        <DescricaoTramitacaoEditor
            :model-value="modelValue.descricao"
            :contexto="contextoDescricao"
            :demanda-id="demandaId"
            :demanda-context="contextoPlaceholdersDemanda"
            :label="
                labelDescricao ||
                (modo === MODO_DESPACHO
                    ? 'Texto do despacho do protocolo'
                    : permitirIntegrados
                      ? 'Descrição / observações do andamento ou encaminhamento transversal'
                      : 'Descrição do andamento')
            "
            @update:model-value="patchForm({ descricao: $event })"
        />

        <!-- 4. Anexos -->
        <div>
            <label class="block mb-2 font-medium"><i class="pi pi-paperclip mr-1" /> Anexos</label>
            <FileUpload
                name="anexos"
                :multiple="true"
                accept="image/*,application/pdf"
                :max-file-size="maxFileSize"
                :choose-label="modo === MODO_DESPACHO ? 'Selecionar PDF/fotos' : 'Selecionar anexos'"
                :auto="false"
                :show-upload-button="false"
                @select="onAnexosSelected"
                @invalid-file-size="onAnexoInvalido"
                @invalid-file-type="onAnexoInvalido"
            />
            <p class="text-xs text-muted-color mt-1 mb-0">
                PDF ou imagens — até {{ Math.round(maxFileSize / 1000000) }} MB por arquivo.
            </p>
            <div v-if="modelValue.anexos?.length" class="mt-2 flex flex-wrap gap-2">
                <Tag
                    v-for="file in modelValue.anexos"
                    :key="file.name"
                    :value="file.name"
                    icon="pi pi-paperclip"
                    removable
                    @remove="removerAnexo(file.name)"
                />
            </div>
        </div>

        <!-- 5. Assinatura opcional no formulário -->
        <div
            v-if="exibirAssinaturaFormulario && (regrasAssinatura.opcionalCheckbox || regrasAssinatura.obrigatoria)"
            class="flex items-start gap-2 p-3 surface-50 border-round"
        >
            <Checkbox
                :model-value="modelValue.assinar_eletronicamente"
                binary
                input-id="assinar_form"
                @update:model-value="patchForm({ assinar_eletronicamente: $event })"
            />
            <label for="assinar_form" class="text-sm cursor-pointer">
                {{
                    regrasAssinatura.obrigatoria
                        ? 'Assinatura eletrônica obrigatória'
                        : 'Assinar eletronicamente'
                }}
                <span class="text-muted-color block text-xs">
                    {{
                        regrasAssinatura.obrigatoria
                            ? 'Marque a declaração para atestar esta operação antes de enviar.'
                            : 'Opcional — você também poderá confirmar na etapa final antes de enviar.'
                    }}
                </span>
            </label>
        </div>

        <slot name="extra" />
    </div>
</template>
