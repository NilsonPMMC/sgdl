<script setup>
import { computed, onMounted, ref } from 'vue';
import ApiService from '@/service/ApiService';
import { useToast } from 'primevue/usetoast';

import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Dialog from 'primevue/dialog';
import InputNumber from 'primevue/inputnumber';
import InputSwitch from 'primevue/inputswitch';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import TabPanel from 'primevue/tabpanel';
import TabView from 'primevue/tabview';
import Tag from 'primevue/tag';
import Textarea from 'primevue/textarea';

const toast = useToast();

const abaAtiva = ref(0);

// —— Base cadastrada ——
const carregandoBase = ref(false);
const salvandoBase = ref(false);
const faqs = ref([]);
const buscaBase = ref('');
const dialogEdicao = ref(false);
const editando = ref(false);
const form = ref(formularioVazio());

function formularioVazio() {
    return {
        id: null,
        categoria_orientacao: '',
        slug: '',
        titulo: '',
        mensagem: '',
        orgao_hint: '',
        municipio_referencia: 'Mogi das Cruzes',
        ordem: 100,
        ativo: true,
        notas_internas: '',
        padroes_texto: ''
    };
}

function slugify(texto) {
    return String(texto || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 80);
}

const faqsFiltradas = computed(() => {
    const q = buscaBase.value.trim().toLowerCase();
    if (!q) return faqs.value;
    return faqs.value.filter(
        (f) =>
            (f.titulo || '').toLowerCase().includes(q) ||
            (f.categoria_orientacao || '').toLowerCase().includes(q) ||
            (f.orgao_hint || '').toLowerCase().includes(q)
    );
});

const extrairLista = (response) => {
    const data = response?.data;
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.results)) return data.results;
    return [];
};

const padroesParaTexto = (padroes) => {
    if (!Array.isArray(padroes)) return '';
    return padroes
        .filter((p) => p.ativo !== false)
        .sort((a, b) => (a.ordem || 0) - (b.ordem || 0))
        .map((p) => p.expressao)
        .join('\n');
};

const textoParaPadroes = (texto) =>
    String(texto || '')
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean);

const carregarBase = async () => {
    carregandoBase.value = true;
    try {
        const response = await ApiService.listarCopilotoFaq({ ordering: 'ordem,titulo' });
        faqs.value = extrairLista(response);
    } catch (_error) {
        faqs.value = [];
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: 'Não foi possível carregar a base FAQ.',
            life: 4000
        });
    } finally {
        carregandoBase.value = false;
    }
};

const abrirNova = () => {
    editando.value = false;
    form.value = formularioVazio();
    dialogEdicao.value = true;
};

const abrirEditar = async (row) => {
    editando.value = true;
    try {
        const response = await ApiService.obterCopilotoFaq(row.id);
        const item = response.data;
        form.value = {
            id: item.id,
            categoria_orientacao: item.categoria_orientacao,
            slug: item.slug,
            titulo: item.titulo,
            mensagem: item.mensagem,
            orgao_hint: item.orgao_hint,
            municipio_referencia: item.municipio_referencia || 'Mogi das Cruzes',
            ordem: item.ordem ?? 100,
            ativo: item.ativo !== false,
            notas_internas: item.notas_internas || '',
            padroes_texto: padroesParaTexto(item.padroes)
        };
        dialogEdicao.value = true;
    } catch (_error) {
        toast.add({
            severity: 'error',
            summary: 'Erro',
            detail: 'Falha ao abrir a entrada para edição.',
            life: 3500
        });
    }
};

const sincronizarPadroes = async (faqId, expressoes) => {
    const resp = await ApiService.listarCopilotoFaqPadroes({ faq: faqId });
    const existentes = extrairLista(resp);
    for (const p of existentes) {
        await ApiService.excluirCopilotoFaqPadrao(p.id);
    }
    let ordem = 10;
    for (const expressao of expressoes) {
        await ApiService.criarCopilotoFaqPadrao({
            faq: faqId,
            expressao,
            ativo: true,
            ordem,
            fonte: 'MANUAL'
        });
        ordem += 10;
    }
};

const salvarEntrada = async () => {
    const f = form.value;
    const cat = (f.categoria_orientacao || '').trim().toUpperCase().replace(/\s+/g, '_');
    if (!cat || !f.titulo?.trim() || !f.mensagem?.trim() || !f.orgao_hint?.trim()) {
        toast.add({
            severity: 'warn',
            summary: 'Campos obrigatórios',
            detail: 'Preencha categoria, título, mensagem e órgão competente.',
            life: 3500
        });
        return;
    }
    const padroes = textoParaPadroes(f.padroes_texto);
    if (!padroes.length) {
        toast.add({
            severity: 'warn',
            summary: 'Padrões',
            detail: 'Informe ao menos um padrão regex (um por linha).',
            life: 3500
        });
        return;
    }

    const payload = {
        categoria_orientacao: cat,
        slug: (f.slug || '').trim() || slugify(f.titulo) || slugify(cat),
        titulo: f.titulo.trim(),
        mensagem: f.mensagem.trim(),
        orgao_hint: f.orgao_hint.trim(),
        municipio_referencia: (f.municipio_referencia || 'Mogi das Cruzes').trim(),
        ordem: f.ordem ?? 100,
        ativo: f.ativo,
        notas_internas: (f.notas_internas || '').trim(),
        fonte: 'MANUAL'
    };

    salvandoBase.value = true;
    try {
        let faqId = f.id;
        if (editando.value && faqId) {
            await ApiService.atualizarCopilotoFaq(faqId, payload);
        } else {
            const criada = await ApiService.criarCopilotoFaq(payload);
            faqId = criada.data.id;
        }
        await sincronizarPadroes(faqId, padroes);
        dialogEdicao.value = false;
        await carregarBase();
        toast.add({
            severity: 'success',
            summary: 'Salvo',
            detail: editando.value ? 'FAQ atualizada.' : 'Nova FAQ cadastrada.',
            life: 3000
        });
    } catch (error) {
        const detail =
            error?.response?.data?.detail ||
            (typeof error?.response?.data === 'object'
                ? Object.entries(error.response.data)
                      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
                      .join('; ')
                : 'Falha ao salvar.');
        toast.add({
            severity: 'error',
            summary: 'Erro ao salvar',
            detail,
            life: 5500
        });
    } finally {
        salvandoBase.value = false;
    }
};

const severidadeFonte = (fonte) => {
    if (fonte === 'LLM') return 'info';
    if (fonte === 'MIGRACAO') return 'secondary';
    return 'success';
};

// —— Curadoria IA ——
const foco = ref('');
const gerando = ref(false);
const observacoes = ref('');
const municipio = ref('');
const sugestoes = ref([]);
const descartadas = ref(new Set());
const aprovandoId = ref(null);

const sugestoesVisiveis = computed(() =>
    sugestoes.value.filter((s) => !descartadas.value.has(s.id))
);

const palavrasChave = (item) => {
    const padroes = item.padroes_regex || [];
    return padroes.length ? padroes : ['—'];
};

const montarPayloadAprovar = (item) => {
    const padroes = (item.padroes_regex || []).filter(Boolean);
    if (!padroes.length) return null;
    const base = {
        categoria_orientacao: item.categoria_orientacao,
        titulo: item.titulo,
        mensagem: item.mensagem,
        orgao_hint: item.orgao_hint,
        padroes_regex: padroes,
        municipio_referencia: item.municipio_referencia || municipio.value || 'Mogi das Cruzes',
        notas_internas: item.notas_internas || 'Aprovado na curadoria web (IA)',
        substituir_padroes: false
    };
    if (item.ordem != null) base.ordem = item.ordem;
    return base;
};

const gerarSugestoes = async () => {
    gerando.value = true;
    descartadas.value = new Set();
    sugestoes.value = [];
    observacoes.value = '';
    try {
        const response = await ApiService.buscarSugestoesFaqLLM(foco.value);
        const data = response.data || {};
        municipio.value = data.municipio || '';
        observacoes.value = data.observacoes || '';
        sugestoes.value = Array.isArray(data.sugestoes) ? data.sugestoes : [];
        if (!sugestoes.value.length) {
            toast.add({
                severity: 'info',
                summary: 'Sem sugestões',
                detail: 'A IA não retornou novas entradas ou atualizações para este foco.',
                life: 4000
            });
        }
    } catch (error) {
        const detail =
            error?.response?.data?.detail ||
            'Não foi possível consultar a IA. Verifique a chave Groq e tente novamente.';
        toast.add({
            severity: 'error',
            summary: 'Erro na geração',
            detail,
            life: 5000
        });
    } finally {
        gerando.value = false;
    }
};

const descartar = (item) => {
    descartadas.value = new Set([...descartadas.value, item.id]);
};

const aprovar = async (item) => {
    const payload = montarPayloadAprovar(item);
    if (!payload) {
        toast.add({
            severity: 'warn',
            summary: 'Inválido',
            detail: 'A sugestão precisa de ao menos um padrão (palavra-chave) para salvar.',
            life: 3500
        });
        return;
    }
    if (!payload.titulo || !payload.mensagem || !payload.orgao_hint) {
        toast.add({
            severity: 'warn',
            summary: 'Dados incompletos',
            detail: 'Título, mensagem e órgão competente são obrigatórios para aprovar.',
            life: 3500
        });
        return;
    }

    aprovandoId.value = item.id;
    try {
        await ApiService.aprovarSugestaoFaq(payload);
        descartar(item);
        await carregarBase();
        toast.add({
            severity: 'success',
            summary: 'Salvo',
            detail: `"${item.titulo || item.categoria_orientacao}" foi aprovado e gravado na base FAQ.`,
            life: 3500
        });
    } catch (error) {
        const detail =
            error?.response?.data?.detail ||
            (typeof error?.response?.data === 'object'
                ? JSON.stringify(error.response.data)
                : 'Falha ao salvar a sugestão.');
        toast.add({
            severity: 'error',
            summary: 'Erro ao aprovar',
            detail,
            life: 5000
        });
    } finally {
        aprovandoId.value = null;
    }
};

onMounted(() => {
    carregarBase();
});
</script>

<template>
    <div class="flex flex-col gap-4 p-4 md:p-6 mx-auto">
        <div>
            <h1 class="text-2xl font-semibold text-surface-900 dark:text-surface-0 m-0">FAQ Copiloto</h1>
            <p class="text-surface-600 dark:text-surface-400 mt-2 mb-0">
                Gerencie orientações fora da competência municipal e revise sugestões da IA antes de publicar.
            </p>
        </div>

        <TabView v-model:activeIndex="abaAtiva">
            <TabPanel header="Base cadastrada">
                <div class="flex flex-col gap-4 pt-2">
                    <div class="flex flex-wrap gap-2 justify-between items-center">
                        <span class="text-sm text-surface-600 dark:text-surface-400">
                            {{ faqsFiltradas.length }} entrada(s)
                        </span>
                        <div class="flex flex-wrap gap-2">
                            <InputText
                                v-model="buscaBase"
                                placeholder="Buscar título, categoria ou órgão..."
                                class="w-64"
                            />
                            <Button
                                icon="pi pi-refresh"
                                severity="secondary"
                                outlined
                                :loading="carregandoBase"
                                @click="carregarBase"
                            />
                            <Button label="Nova entrada" icon="pi pi-plus" @click="abrirNova" />
                        </div>
                    </div>

                    <DataTable
                        :value="faqsFiltradas"
                        :loading="carregandoBase"
                        dataKey="id"
                        paginator
                        :rows="15"
                        responsiveLayout="scroll"
                        class="sgdl-table-scroll"
                        stripedRows
                    >
                        <Column field="ordem" header="Ordem" style="width: 5rem" />
                        <Column field="titulo" header="Título" />
                        <Column field="categoria_orientacao" header="Categoria">
                            <template #body="{ data }">
                                <span class="font-mono text-xs">{{ data.categoria_orientacao }}</span>
                            </template>
                        </Column>
                        <Column field="orgao_hint" header="Órgão" />
                        <Column header="Status">
                            <template #body="{ data }">
                                <Tag
                                    :value="data.ativo ? 'Ativo' : 'Inativo'"
                                    :severity="data.ativo ? 'success' : 'danger'"
                                />
                            </template>
                        </Column>
                        <Column header="Fonte">
                            <template #body="{ data }">
                                <Tag :value="data.fonte" :severity="severidadeFonte(data.fonte)" />
                            </template>
                        </Column>
                        <Column header="Padrões">
                            <template #body="{ data }">
                                {{ (data.padroes || []).length }}
                            </template>
                        </Column>
                        <Column header="Ações" style="width: 7rem">
                            <template #body="{ data }">
                                <Button
                                    icon="pi pi-pencil"
                                    text
                                    rounded
                                    severity="secondary"
                                    v-tooltip.top="'Editar'"
                                    @click="abrirEditar(data)"
                                />
                            </template>
                        </Column>
                        <template #empty>
                            <div class="text-center py-6 text-surface-500">Nenhuma FAQ cadastrada.</div>
                        </template>
                    </DataTable>
                </div>
            </TabPanel>

            <TabPanel header="Curadoria IA">
                <div class="flex flex-col gap-6 pt-2">
                    <Card class="shadow-sm">
                        <template #title>Gerar sugestões</template>
                        <template #content>
                            <div class="flex flex-col gap-4">
                                <div class="flex flex-col gap-2">
                                    <label
                                        for="foco-faq"
                                        class="text-sm font-medium text-surface-700 dark:text-surface-300"
                                    >
                                        Foco / tema (opcional)
                                    </label>
                                    <InputText
                                        id="foco-faq"
                                        v-model="foco"
                                        placeholder="Ex.: DETRAN, iluminação pública, Procon..."
                                        class="w-full"
                                        :disabled="gerando"
                                        @keyup.enter="gerarSugestoes"
                                    />
                                </div>
                                <Button
                                    label="Gerar Sugestões com IA"
                                    icon="pi pi-sparkles"
                                    :loading="gerando"
                                    @click="gerarSugestoes"
                                />
                            </div>
                        </template>
                    </Card>

                    <div
                        v-if="gerando"
                        class="flex flex-col items-center justify-center gap-4 py-16 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-900"
                    >
                        <ProgressSpinner style="width: 3rem; height: 3rem" strokeWidth="4" />
                        <p class="text-lg text-surface-700 dark:text-surface-200 m-0 font-medium">
                            A IA está analisando a cidade...
                        </p>
                        <p class="text-sm text-surface-500 m-0">Isso pode levar até um minuto.</p>
                    </div>

                    <Message v-if="observacoes && !gerando" severity="info" :closable="false" class="w-full">
                        <span class="font-medium">Observações da IA:</span>
                        {{ observacoes }}
                        <span v-if="municipio" class="block mt-1 text-sm opacity-80">Município: {{ municipio }}</span>
                    </Message>

                    <div v-if="!gerando && sugestoesVisiveis.length" class="flex flex-col gap-4">
                        <h2 class="text-lg font-semibold m-0 text-surface-800 dark:text-surface-100">
                            Sugestões para revisão ({{ sugestoesVisiveis.length }})
                        </h2>

                        <Card
                            v-for="item in sugestoesVisiveis"
                            :key="item.id"
                            class="shadow-sm border border-surface-200 dark:border-surface-700"
                        >
                            <template #title>
                                <div class="flex flex-wrap items-center gap-2">
                                    <span>{{ item.titulo || item.categoria_orientacao }}</span>
                                    <Tag
                                        :value="item.tipo === 'atualizacao' ? 'Atualização' : 'Nova entrada'"
                                        :severity="item.tipo === 'atualizacao' ? 'warn' : 'success'"
                                    />
                                </div>
                            </template>
                            <template #subtitle>
                                <span class="text-sm font-mono text-surface-500">{{ item.categoria_orientacao }}</span>
                            </template>
                            <template #content>
                                <dl class="grid gap-3 m-0 text-sm">
                                    <div>
                                        <dt class="font-medium text-surface-600 dark:text-surface-400">
                                            Órgão competente
                                        </dt>
                                        <dd class="m-0 mt-1">{{ item.orgao_hint || '—' }}</dd>
                                    </div>
                                    <div>
                                        <dt class="font-medium text-surface-600 dark:text-surface-400">
                                            Mensagem de orientação
                                        </dt>
                                        <dd class="m-0 mt-1 whitespace-pre-wrap">{{ item.mensagem || '—' }}</dd>
                                    </div>
                                    <div>
                                        <dt class="font-medium text-surface-600 dark:text-surface-400">
                                            Palavras-chave (regex)
                                        </dt>
                                        <dd class="m-0 mt-1 flex flex-wrap gap-2">
                                            <Tag
                                                v-for="(kw, idx) in palavrasChave(item)"
                                                :key="`${item.id}-kw-${idx}`"
                                                :value="kw"
                                                severity="secondary"
                                                class="font-mono text-xs"
                                            />
                                        </dd>
                                    </div>
                                </dl>
                            </template>
                            <template #footer>
                                <div class="flex flex-wrap gap-2 justify-end">
                                    <Button
                                        label="Descartar"
                                        severity="secondary"
                                        outlined
                                        icon="pi pi-times"
                                        :disabled="aprovandoId === item.id"
                                        @click="descartar(item)"
                                    />
                                    <Button
                                        label="Aprovar e Salvar"
                                        icon="pi pi-check"
                                        :loading="aprovandoId === item.id"
                                        @click="aprovar(item)"
                                    />
                                </div>
                            </template>
                        </Card>
                    </div>

                    <Message
                        v-else-if="!gerando && sugestoes.length && !sugestoesVisiveis.length"
                        severity="success"
                        :closable="false"
                    >
                        Todas as sugestões desta rodada foram tratadas (aprovadas ou descartadas).
                    </Message>
                </div>
            </TabPanel>
        </TabView>

        <Dialog
            v-model:visible="dialogEdicao"
            :header="editando ? 'Editar FAQ' : 'Nova FAQ'"
            modal
            class="w-full max-w-2xl"
            :style="{ width: '95vw', maxWidth: '42rem' }"
        >
            <div class="flex flex-col gap-4">
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Categoria (código LLM)</label>
                    <InputText
                        v-model="form.categoria_orientacao"
                        placeholder="ENERGIA_CONCESSIONARIA"
                        class="font-mono"
                        :disabled="editando"
                    />
                    <small v-if="editando" class="text-surface-500">A categoria não pode ser alterada após o cadastro.</small>
                </div>
                <div v-if="!editando" class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Slug (opcional)</label>
                    <InputText v-model="form.slug" placeholder="Gerado automaticamente a partir do título" />
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Título</label>
                    <InputText v-model="form.titulo" />
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Mensagem de orientação</label>
                    <Textarea v-model="form.mensagem" rows="4" class="w-full" autoResize />
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Órgão competente</label>
                    <InputText v-model="form.orgao_hint" />
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Município de referência</label>
                    <InputText v-model="form.municipio_referencia" />
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="flex flex-col gap-2">
                        <label class="text-sm font-medium">Ordem (prioridade)</label>
                        <InputNumber v-model="form.ordem" :min="0" :max="9999" class="w-full" />
                    </div>
                    <div class="flex flex-col gap-2 justify-end">
                        <label class="text-sm font-medium">Ativo no Copiloto</label>
                        <div class="flex items-center gap-2 h-full pt-1">
                            <InputSwitch v-model="form.ativo" />
                            <span class="text-sm">{{ form.ativo ? 'Sim' : 'Não' }}</span>
                        </div>
                    </div>
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Padrões regex (um por linha)</label>
                    <Textarea
                        v-model="form.padroes_texto"
                        rows="6"
                        class="w-full font-mono text-sm"
                        placeholder="\\bcpfl\\b&#10;\\bfalta\\s+de\\s+luz\\b"
                    />
                </div>
                <div class="flex flex-col gap-2">
                    <label class="text-sm font-medium">Notas internas (opcional)</label>
                    <Textarea v-model="form.notas_internas" rows="2" class="w-full" autoResize />
                </div>
            </div>
            <template #footer>
                <Button label="Cancelar" severity="secondary" text @click="dialogEdicao = false" />
                <Button label="Salvar" icon="pi pi-check" :loading="salvandoBase" @click="salvarEntrada" />
            </template>
        </Dialog>
    </div>
</template>
