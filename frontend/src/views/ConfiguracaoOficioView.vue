<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { blobParecePdf, mensagemErroRespostaBlob } from '@/utils/httpBlob';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import Dialog from 'primevue/dialog';
import FileUpload from 'primevue/fileupload';
import InputNumber from 'primevue/inputnumber';
import InputText from 'primevue/inputtext';
import ProgressSpinner from 'primevue/progressspinner';
import Select from 'primevue/select';

const toast = useToast();

const carregando = ref(true);
const salvando = ref(false);
const previewando = ref(false);
const previewPdfUrl = ref(null);
const previewDialogVisivel = ref(false);
const novaImagemCabecalho = ref(null);

const opcoesFormato = [
    { label: 'A4', value: 'A4' },
    { label: 'Carta (Letter)', value: 'LETTER' }
];

const opcoesOrientacao = [
    { label: 'Retrato', value: 'portrait' },
    { label: 'Paisagem', value: 'landscape' }
];

const opcoesLayout = [
    { label: 'Brasão | Descrição', value: 'BRASAO_ESQUERDA_TEXTO' },
    { label: 'Descrição | Brasão', value: 'TEXTO_ESQUERDA_BRASAO' },
    { label: 'Somente brasão (centro)', value: 'BRASAO_CENTRO' },
    { label: 'Brasão acima da descrição', value: 'BRASAO_ACIMA_TEXTO' },
    { label: 'Somente descrição (centro)', value: 'TEXTO_CENTRO' }
];

const form = ref({
    municipio: '',
    uf: '',
    orgao_destinatario: '',
    destinatario_tratamento: '',
    destinatario_nome: '',
    destinatario_cargo: '',
    titulo_instituicao: '',
    cabecalho_layout: 'BRASAO_ESQUERDA_TEXTO',
    imagem_cabecalho_url: null,
    instituicao_nome: '',
    brasao_largura_cm: 2.8,
    pagina_formato: 'A4',
    pagina_orientacao: 'portrait',
    margem_superior_cm: 2.5,
    margem_inferior_cm: 2.5,
    margem_esquerda_cm: 3.0,
    margem_direita_cm: 2.0,
    rodape_protocolo_altura_cm: 2.5,
    atualizado_em: null,
    remover_imagem_cabecalho: false
});

const previewCabecalho = ref(null);

const previewBrasaoLarguraPx = computed(() => {
    const cm = Number(form.value.brasao_largura_cm) || 2.8;
    return Math.round(cm * 37.8);
});

const temTextoCabecalho = computed(() => {
    if (form.value.cabecalho_layout === 'BRASAO_CENTRO') return false;
    return Boolean(
        (form.value.titulo_instituicao || '').trim() ||
            (form.value.municipio || '').trim() ||
            (form.value.uf || '').trim()
    );
});

const mostrarBrasaoMock = computed(() => Boolean(previewCabecalho.value));

const previewLayoutClasses = computed(() => {
    const layout = form.value.cabecalho_layout || 'BRASAO_ESQUERDA_TEXTO';
    const base = 'flex gap-3 w-full';
    switch (layout) {
        case 'TEXTO_ESQUERDA_BRASAO':
            return `${base} flex-row-reverse items-center`;
        case 'BRASAO_CENTRO':
            return `${base} justify-center items-center`;
        case 'TEXTO_CENTRO':
            return `${base} justify-center items-center`;
        case 'BRASAO_ACIMA_TEXTO':
            return `${base} flex-col items-center text-center`;
        default:
            return `${base} flex-row items-center`;
    }
});

const valorCampoFormulario = (campo) => {
    const valor = form.value[campo];
    if (valor && typeof valor === 'object' && 'value' in valor) {
        return valor.value;
    }
    return valor;
};

const montarFormData = () => {
    const formData = new FormData();
    const campos = [
        'municipio',
        'uf',
        'orgao_destinatario',
        'destinatario_tratamento',
        'destinatario_nome',
        'destinatario_cargo',
        'titulo_instituicao',
        'cabecalho_layout',
        'pagina_formato',
        'pagina_orientacao',
        'brasao_largura_cm',
        'margem_superior_cm',
        'margem_inferior_cm',
        'margem_esquerda_cm',
        'margem_direita_cm',
        'rodape_protocolo_altura_cm'
    ];
    campos.forEach((campo) => {
        const valor = valorCampoFormulario(campo);
        if (valor === null || valor === undefined || valor === '') {
            formData.append(campo, '');
            return;
        }
        if (typeof valor === 'number') {
            formData.append(campo, Number.isInteger(valor) ? String(valor) : valor.toFixed(2));
            return;
        }
        formData.append(campo, String(valor).replace(',', '.'));
    });
    if (novaImagemCabecalho.value) {
        formData.append('imagem_cabecalho', novaImagemCabecalho.value);
    } else if (form.value.remover_imagem_cabecalho) {
        formData.append('remover_imagem_cabecalho', 'true');
    }
    return formData;
};

const revogarPreviewPdfUrl = () => {
    if (previewPdfUrl.value) {
        URL.revokeObjectURL(previewPdfUrl.value);
        previewPdfUrl.value = null;
    }
};

const gerarPreviewPdf = async ({ abrirDialogo = false } = {}) => {
    previewando.value = true;
    try {
        const { data } = await ApiService.previewConfiguracaoOficioPdf(montarFormData());
        const blob = new Blob([data], { type: 'application/pdf' });

        if (!blobParecePdf(blob)) {
            throw new Error('Resposta inválida do servidor.');
        }

        revogarPreviewPdfUrl();
        previewPdfUrl.value = URL.createObjectURL(blob);

        if (abrirDialogo) {
            previewDialogVisivel.value = true;
        }
    } catch (error) {
        const detalhe = await mensagemErroRespostaBlob(
            error,
            'Não foi possível gerar o PDF de amostra.'
        );
        toast.add({
            severity: 'error',
            summary: 'Pré-visualização',
            detail: detalhe,
            life: 5000
        });
    } finally {
        previewando.value = false;
    }
};

const abrirPreviewPdf = () => gerarPreviewPdf({ abrirDialogo: true });

const fecharPreviewDialog = () => {
    previewDialogVisivel.value = false;
};

const carregar = async () => {
    carregando.value = true;
    try {
        const { data } = await ApiService.getConfiguracaoOficio();
        form.value = { ...form.value, ...data, remover_imagem_cabecalho: false };
        previewCabecalho.value = data.imagem_cabecalho_url || null;
        novaImagemCabecalho.value = null;
    } catch {
        toast.add({
            severity: 'error',
            summary: 'Configuração',
            detail: 'Não foi possível carregar o modelo de ofício.',
            life: 5000
        });
    } finally {
        carregando.value = false;
    }
};

const onImagemCabecalhoSelect = (event) => {
    const file = event.files?.[0];
    if (!file) return;
    novaImagemCabecalho.value = file;
    previewCabecalho.value = URL.createObjectURL(file);
    form.value.remover_imagem_cabecalho = false;
};

const removerImagemCabecalho = () => {
    novaImagemCabecalho.value = null;
    previewCabecalho.value = null;
    form.value.imagem_cabecalho_url = null;
    form.value.remover_imagem_cabecalho = true;
};

const salvar = async () => {
    salvando.value = true;
    try {
        const { data } = await ApiService.updateConfiguracaoOficio(montarFormData());
        form.value = { ...form.value, ...data, remover_imagem_cabecalho: false };
        previewCabecalho.value = data.imagem_cabecalho_url || null;
        novaImagemCabecalho.value = null;
        toast.add({
            severity: 'success',
            summary: 'Configuração',
            detail: 'Modelo de ofício salvo com sucesso.',
            life: 3000
        });
    } catch (error) {
        const detalhe =
            error?.response?.data?.detail ||
            Object.values(error?.response?.data || {})
                .flat()
                .join(' ') ||
            'Não foi possível salvar a configuração.';
        toast.add({ severity: 'error', summary: 'Configuração', detail: String(detalhe), life: 5000 });
    } finally {
        salvando.value = false;
    }
};

const abrirPreviewPdfEmNovaAba = () => {
    if (previewPdfUrl.value) {
        window.open(previewPdfUrl.value, '_blank');
        return;
    }
    gerarPreviewPdf({ abrirDialogo: true });
};

onMounted(carregar);
onUnmounted(revogarPreviewPdfUrl);
</script>

<template>
    <div class="flex flex-col gap-6">
        <div
            class="flex flex-col gap-4 rounded-xl border border-surface-200 bg-surface-0 p-5 shadow-sm dark:border-surface-700 dark:bg-surface-900 md:flex-row md:items-center md:justify-between"
        >
            <div class="flex flex-col gap-1">
                <h2 class="m-0 text-2xl font-semibold text-surface-900 dark:text-surface-0">
                    Modelo de ofício — Câmara Municipal
                </h2>
                <p class="m-0 text-sm text-surface-600 dark:text-surface-300">
                    Ajuste margens, brasão e layout e clique em «Atualizar pré-visualização» — não é necessário salvar antes.
                </p>
            </div>
            <div class="flex flex-wrap gap-2">
                <Button
                    label="Atualizar pré-visualização"
                    icon="pi pi-refresh"
                    severity="secondary"
                    outlined
                    :loading="previewando"
                    :disabled="carregando"
                    @click="gerarPreviewPdf()"
                />
                <Button
                    label="Abrir PDF"
                    icon="pi pi-external-link"
                    severity="secondary"
                    text
                    :disabled="carregando || previewando || !previewPdfUrl"
                    @click="abrirPreviewPdfEmNovaAba"
                />
                <Button
                    label="Tela cheia"
                    icon="pi pi-window-maximize"
                    severity="secondary"
                    text
                    :disabled="carregando || previewando"
                    @click="abrirPreviewPdf"
                />
                <Button
                    label="Ver PDF"
                    icon="pi pi-file-pdf"
                    severity="secondary"
                    outlined
                    class="xl:hidden"
                    :loading="previewando"
                    :disabled="carregando"
                    @click="abrirPreviewPdf"
                />
                <Button label="Salvar" icon="pi pi-save" :loading="salvando" :disabled="carregando" @click="salvar" />
            </div>
        </div>

        <div
            v-if="carregando"
            class="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-surface-300 dark:border-surface-600"
        >
            <ProgressSpinner />
        </div>

        <div v-else class="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_minmax(320px,42%)]">
            <div class="flex flex-col gap-6">
            <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <section
                class="flex flex-col gap-5 rounded-xl border border-surface-200 bg-surface-0 p-5 shadow-sm dark:border-surface-700 dark:bg-surface-900"
            >
                <div>
                    <h3 class="m-0 text-lg font-semibold text-surface-900 dark:text-surface-0">Cabeçalho</h3>
                    <p class="mt-1 mb-0 text-sm text-surface-600 dark:text-surface-400">
                        Posicionamento dos elementos e largura do brasão (reflete no PDF e na miniatura abaixo).
                    </p>
                </div>

                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium text-surface-700 dark:text-surface-200">
                        Disposição do cabeçalho
                    </label>
                    <Select
                        v-model="form.cabecalho_layout"
                        :options="opcoesLayout"
                        optionLabel="label"
                        optionValue="value"
                        class="w-full"
                    />
                </div>

                <div class="flex flex-col gap-2">
                    <label for="titulo_instituicao" class="text-sm font-medium text-surface-700 dark:text-surface-200">
                        Título institucional <span class="font-normal text-surface-400">(opcional)</span>
                    </label>
                    <InputText
                        id="titulo_instituicao"
                        v-model="form.titulo_instituicao"
                        class="w-full"
                        placeholder="Ex.: CÂMARA MUNICIPAL DE MOGI DAS CRUZES"
                    />
                    <p class="m-0 text-xs text-surface-500">
                        Deixe em branco para exibir somente o brasão (com layout «Somente brasão» ou sem texto).
                    </p>
                </div>

                <div
                    class="rounded-lg border border-dashed border-surface-300 bg-surface-50 p-4 dark:border-surface-600 dark:bg-surface-950"
                >
                    <p class="m-0 mb-2 text-xs font-medium uppercase tracking-wide text-surface-500">Miniatura</p>
                    <div :class="previewLayoutClasses">
                        <template v-if="mostrarBrasaoMock && form.cabecalho_layout !== 'TEXTO_CENTRO'">
                            <img
                                :src="previewCabecalho"
                                alt="Brasão"
                                class="h-auto shrink-0 object-contain"
                                :style="{ width: `${previewBrasaoLarguraPx}px` }"
                            />
                        </template>
                        <div
                            v-else-if="!mostrarBrasaoMock && form.cabecalho_layout !== 'TEXTO_CENTRO'"
                            class="flex h-14 shrink-0 items-center justify-center rounded bg-surface-200 px-3 text-xs text-surface-500"
                            :style="{ width: `${previewBrasaoLarguraPx}px` }"
                        >
                            Brasão
                        </div>
                        <div v-if="temTextoCabecalho" class="min-w-0 flex-1">
                            <p
                                v-if="form.titulo_instituicao"
                                class="m-0 text-xs font-semibold uppercase leading-snug text-surface-800 dark:text-surface-100"
                            >
                                {{ form.titulo_instituicao }}
                            </p>
                            <p v-if="form.municipio || form.uf" class="m-0 mt-1 text-xs text-surface-500">
                                {{ [form.municipio, form.uf].filter(Boolean).join(' — ') }}
                            </p>
                        </div>
                        <p
                            v-else-if="form.cabecalho_layout === 'TEXTO_CENTRO'"
                            class="m-0 text-xs text-surface-400"
                        >
                            Preencha título, município ou UF
                        </p>
                    </div>
                    <hr class="mt-3 border-surface-300 dark:border-surface-600" />
                </div>

                <div class="flex flex-wrap gap-2">
                    <FileUpload
                        mode="basic"
                        name="imagem_cabecalho"
                        accept="image/png,image/jpeg,image/webp"
                        :maxFileSize="2000000"
                        :auto="true"
                        :customUpload="true"
                        chooseLabel="Enviar brasão"
                        class="p-button-outlined"
                        @uploader="onImagemCabecalhoSelect"
                    />
                    <Button
                        v-if="previewCabecalho"
                        label="Remover imagem"
                        icon="pi pi-trash"
                        severity="danger"
                        outlined
                        @click="removerImagemCabecalho"
                    />
                </div>

                <div class="sgdl-field-number">
                    <label class="text-sm font-medium text-surface-700 dark:text-surface-200">
                        Largura do brasão (cm)
                    </label>
                    <InputNumber
                        v-model="form.brasao_largura_cm"
                        :min="1"
                        :max="12"
                        :minFractionDigits="1"
                        :maxFractionDigits="2"
                        :step="0.1"
                        class="w-full"
                        inputClass="w-full"
                    />
                </div>

                <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div class="flex flex-col gap-2">
                        <label for="municipio" class="text-sm font-medium text-surface-700 dark:text-surface-200">
                            Município <span class="font-normal text-surface-400">(opcional)</span>
                        </label>
                        <InputText id="municipio" v-model="form.municipio" class="w-full" placeholder="Ex.: Mogi das Cruzes" />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label for="uf" class="text-sm font-medium text-surface-700 dark:text-surface-200">
                            UF <span class="font-normal text-surface-400">(opcional)</span>
                        </label>
                        <InputText id="uf" v-model="form.uf" class="w-full" maxlength="2" placeholder="SP" />
                    </div>
                </div>
            </section>

            <section
                class="flex flex-col gap-5 rounded-xl border border-surface-200 bg-surface-0 p-5 shadow-sm dark:border-surface-700 dark:bg-surface-900"
            >
                <div>
                    <h3 class="m-0 text-lg font-semibold text-surface-900 dark:text-surface-0">Página, margens e rodapé</h3>
                    <p class="mt-1 mb-0 text-sm text-surface-600 dark:text-surface-400">
                        Refletem na pré-visualização em PDF ao clicar no botão acima.
                    </p>
                </div>

                <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div class="flex flex-col gap-2">
                        <label class="text-sm font-medium text-surface-700 dark:text-surface-200">Formato</label>
                        <Select
                            v-model="form.pagina_formato"
                            :options="opcoesFormato"
                            optionLabel="label"
                            optionValue="value"
                            class="w-full"
                        />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label class="text-sm font-medium text-surface-700 dark:text-surface-200">Orientação</label>
                        <Select
                            v-model="form.pagina_orientacao"
                            :options="opcoesOrientacao"
                            optionLabel="label"
                            optionValue="value"
                            class="w-full"
                        />
                    </div>
                </div>

                <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div class="sgdl-field-number min-w-0">
                        <label class="text-sm font-medium text-surface-700 dark:text-surface-200">Margem superior (cm)</label>
                        <InputNumber
                            v-model="form.margem_superior_cm"
                            :min="0.5"
                            :max="10"
                            :minFractionDigits="1"
                            :maxFractionDigits="2"
                            :step="0.1"
                            class="w-full"
                            inputClass="w-full"
                        />
                    </div>
                    <div class="sgdl-field-number min-w-0">
                        <label class="text-sm font-medium text-surface-700 dark:text-surface-200">Margem inferior (cm)</label>
                        <InputNumber
                            v-model="form.margem_inferior_cm"
                            :min="0.5"
                            :max="10"
                            :minFractionDigits="1"
                            :maxFractionDigits="2"
                            :step="0.1"
                            class="w-full"
                            inputClass="w-full"
                        />
                    </div>
                    <div class="sgdl-field-number min-w-0">
                        <label class="text-sm font-medium text-surface-700 dark:text-surface-200">Margem esquerda (cm)</label>
                        <InputNumber
                            v-model="form.margem_esquerda_cm"
                            :min="0.5"
                            :max="10"
                            :minFractionDigits="1"
                            :maxFractionDigits="2"
                            :step="0.1"
                            class="w-full"
                            inputClass="w-full"
                        />
                    </div>
                    <div class="sgdl-field-number min-w-0">
                        <label class="text-sm font-medium text-surface-700 dark:text-surface-200">Margem direita (cm)</label>
                        <InputNumber
                            v-model="form.margem_direita_cm"
                            :min="0.5"
                            :max="10"
                            :minFractionDigits="1"
                            :maxFractionDigits="2"
                            :step="0.1"
                            class="w-full"
                            inputClass="w-full"
                        />
                    </div>
                </div>

                <div class="sgdl-field-number">
                    <label class="text-sm font-medium text-surface-700 dark:text-surface-200">
                        Altura reservada — protocolo digital (cm)
                    </label>
                    <InputNumber
                        v-model="form.rodape_protocolo_altura_cm"
                        :min="1"
                        :max="8"
                        :minFractionDigits="1"
                        :maxFractionDigits="2"
                        :step="0.1"
                        class="w-full"
                        inputClass="w-full"
                    />
                </div>

                <p v-if="form.atualizado_em" class="m-0 text-xs text-surface-500">
                    Última atualização: {{ new Date(form.atualizado_em).toLocaleString('pt-BR') }}
                </p>
            </section>

            <section
                class="flex flex-col gap-5 rounded-xl border border-surface-200 bg-surface-0 p-5 shadow-sm dark:border-surface-700 dark:bg-surface-900 xl:col-span-2"
            >
                <div>
                    <h3 class="m-0 text-lg font-semibold text-surface-900 dark:text-surface-0">
                        Destinatário padrão (Prefeitura)
                    </h3>
                    <p class="mt-1 mb-0 text-sm text-surface-600 dark:text-surface-400">
                        Usado na montagem automática do texto quando a demanda ainda não possui corpo formatado.
                    </p>
                </div>

                <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div class="flex flex-col gap-2 md:col-span-2">
                        <label for="orgao_destinatario" class="text-sm font-medium text-surface-700 dark:text-surface-200">
                            Órgão destinatário
                        </label>
                        <InputText id="orgao_destinatario" v-model="form.orgao_destinatario" class="w-full" />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label for="destinatario_tratamento" class="text-sm font-medium text-surface-700 dark:text-surface-200">
                            Tratamento
                        </label>
                        <InputText id="destinatario_tratamento" v-model="form.destinatario_tratamento" class="w-full" />
                    </div>
                    <div class="flex flex-col gap-2">
                        <label for="destinatario_nome" class="text-sm font-medium text-surface-700 dark:text-surface-200">
                            Nome
                        </label>
                        <InputText id="destinatario_nome" v-model="form.destinatario_nome" class="w-full" />
                    </div>
                    <div class="flex flex-col gap-2 md:col-span-2">
                        <label for="destinatario_cargo" class="text-sm font-medium text-surface-700 dark:text-surface-200">
                            Cargo
                        </label>
                        <InputText id="destinatario_cargo" v-model="form.destinatario_cargo" class="w-full" />
                    </div>
                </div>
            </section>
            </div>
            </div>

            <aside
                class="hidden xl:flex xl:flex-col xl:gap-3 xl:rounded-xl xl:border xl:border-surface-200 xl:bg-surface-0 xl:p-4 xl:shadow-sm dark:xl:border-surface-700 dark:xl:bg-surface-900 xl:sticky xl:top-4 xl:self-start xl:max-h-[calc(100vh-6rem)]"
            >
                <div class="flex items-center justify-between gap-2">
                    <div>
                        <h3 class="m-0 text-base font-semibold text-surface-900 dark:text-surface-0">Pré-visualização PDF</h3>
                        <p class="m-0 mt-1 text-xs text-surface-500">Valores atuais do formulário</p>
                    </div>
                    <Button
                        icon="pi pi-refresh"
                        severity="secondary"
                        text
                        rounded
                        :loading="previewando"
                        v-tooltip.left="'Atualizar'"
                        @click="gerarPreviewPdf()"
                    />
                </div>

                <div
                    v-if="previewPdfUrl"
                    class="min-h-[480px] flex-1 overflow-hidden rounded-lg border border-surface-200 bg-surface-100 dark:border-surface-600 dark:bg-surface-950"
                >
                    <iframe
                        :src="previewPdfUrl"
                        title="Pré-visualização do ofício"
                        class="h-full min-h-[480px] w-full border-0 bg-white"
                    />
                </div>
                <div
                    v-else
                    class="flex min-h-[480px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-surface-300 px-4 text-center dark:border-surface-600"
                >
                    <i class="pi pi-file-pdf text-3xl text-surface-400" />
                    <p class="m-0 text-sm text-surface-500">
                        Clique em «Atualizar pré-visualização» para gerar o PDF com as medidas do formulário.
                    </p>
                    <Button
                        label="Gerar agora"
                        icon="pi pi-refresh"
                        size="small"
                        outlined
                        :loading="previewando"
                        @click="gerarPreviewPdf()"
                    />
                </div>
            </aside>
        </div>

        <Dialog
            v-model:visible="previewDialogVisivel"
            modal
            maximizable
            header="Pré-visualização do ofício"
            class="sgdl-preview-dialog"
            :style="{ width: 'min(960px, 96vw)' }"
            @hide="fecharPreviewDialog"
        >
            <div v-if="previewPdfUrl" class="overflow-hidden rounded-lg border border-surface-200 dark:border-surface-600">
                <iframe
                    :src="previewPdfUrl"
                    title="Pré-visualização do ofício"
                    class="h-[75vh] w-full border-0 bg-white"
                />
            </div>
            <div v-else class="flex min-h-[240px] items-center justify-center">
                <ProgressSpinner />
            </div>
            <template #footer>
                <Button label="Fechar" icon="pi pi-times" text @click="fecharPreviewDialog" />
                <Button
                    label="Abrir em nova aba"
                    icon="pi pi-external-link"
                    :disabled="!previewPdfUrl"
                    @click="abrirPreviewPdfEmNovaAba"
                />
            </template>
        </Dialog>
    </div>
</template>

<style scoped>
.sgdl-field-number {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    width: 100%;
    min-width: 0;
}
.sgdl-field-number :deep(.p-inputnumber) {
    width: 100%;
    display: block;
}
.sgdl-field-number :deep(.p-inputnumber-input) {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
}
</style>
