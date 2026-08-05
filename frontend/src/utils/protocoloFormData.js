/** Payload multipart para despacho e devolutiva (B5/B8). */

import { destinosParaPayload } from '@/constants/tramitacaoFormulario';

export function payloadDespachoDestinos(formOuLegacy, orgaoCompetenteId = null) {
    let payload = {};
    if (formOuLegacy?.destinos?.length) {
        payload = destinosParaPayload(formOuLegacy, orgaoCompetenteId);
    } else {
        const integrados = (formOuLegacy?.secretaria_ids || []).filter(Boolean);
        const unidadeId = formOuLegacy?.unidade_destino_id || null;
        if (integrados.length) {
            payload = {
                destinos: integrados.map((secretaria_id) => {
                    const item = { secretaria_id: Number(secretaria_id) };
                    if (unidadeId && Number(secretaria_id) === Number(orgaoCompetenteId)) {
                        item.unidade_administrativa_id = Number(unidadeId);
                    }
                    return item;
                })
            };
        } else if (orgaoCompetenteId) {
            const item = { secretaria_id: Number(orgaoCompetenteId) };
            if (unidadeId) item.unidade_administrativa_id = Number(unidadeId);
            payload = { destinos: [item] };
        } else if (formOuLegacy?.secretaria_id) {
            const item = { secretaria_id: Number(formOuLegacy.secretaria_id) };
            if (unidadeId) item.unidade_administrativa_id = Number(unidadeId);
            payload = { destinos: [item] };
        }
    }
    const descricao = (formOuLegacy?.descricao || '').trim();
    if (descricao) payload.descricao = descricao;
    return payload;
}

export function buildMultipartPayload(payload, files, fileField = 'arquivos_anexos') {
    const body = { ...payload };
    if (Array.isArray(body.anexos_tramitacao_ids)) {
        body.anexos_tramitacao_ids = JSON.stringify(body.anexos_tramitacao_ids);
    }
    if (Array.isArray(body.alerta_destinos)) {
        body.alerta_destinos = JSON.stringify(body.alerta_destinos);
    }
    if (Array.isArray(body.no_ids)) {
        body.no_ids = JSON.stringify(body.no_ids);
    }
    if (!files?.length) {
        return { body, multipart: false };
    }
    const fd = new FormData();
    if (body.destinos) {
        fd.append('destinos', JSON.stringify(body.destinos));
    }
    Object.entries(body).forEach(([key, val]) => {
        if (key === 'destinos' || val == null || val === '') return;
        fd.append(key, val);
    });
    files.forEach((file) => fd.append(fileField, file));
    return { body: fd, multipart: true };
}

export function buildDevolutivaPayload(form, hashDocumento, declaracoes, modo = 'dual_protocolo') {
    const payload = {
        parecer_resposta: form.parecer_resposta || '',
        hash_documento: hashDocumento
    };
    if (form.modo_conclusao) {
        payload.modo_conclusao = form.modo_conclusao;
    }

    if (modo === 'gestor_apenas') {
        payload.declaracao_gestor = declaracoes.declaracaoGestorText;
        payload.assinatura_apenas_gestor = true;
        return payload;
    }

    if (modo === 'operador_apenas') {
        payload.declaracao_operador = declaracoes.declaracaoOperadorText;
        payload.declaracao = declaracoes.declaracaoOperadorText;
        if (form.anexos_tramitacao_ids?.length) {
            payload.anexos_tramitacao_ids = form.anexos_tramitacao_ids;
        }
        if (form.alerta_destinos?.length) {
            payload.alerta_destinos = form.alerta_destinos
                .filter((d) => d.secretaria_id)
                .map((d) => {
                    const item = { secretaria_id: Number(d.secretaria_id) };
                    const ids = d.unidade_administrativa_ids?.length
                        ? d.unidade_administrativa_ids
                        : d.unidade_administrativa_id
                          ? [d.unidade_administrativa_id]
                          : [];
                    if (ids.length === 1) item.unidade_administrativa_id = Number(ids[0]);
                    else if (ids.length > 1) item.unidade_administrativa_ids = ids.map(Number);
                    return item;
                });
        }
        return payload;
    }

    payload.declaracao_operador = declaracoes.declaracaoOperadorText;
    payload.declaracao = declaracoes.declaracaoOperadorText;
    payload.declaracao_gestor = declaracoes.declaracaoGestorText;
    payload.gestor_protocolo_id = form.gestor_protocolo_id;
    if (form.anexos_tramitacao_ids?.length) {
        payload.anexos_tramitacao_ids = form.anexos_tramitacao_ids;
    }
    if (form.alerta_destinos?.length) {
        payload.alerta_destinos = form.alerta_destinos
            .filter((d) => d.secretaria_id)
            .map((d) => {
                const item = { secretaria_id: Number(d.secretaria_id) };
                const ids = d.unidade_administrativa_ids?.length
                    ? d.unidade_administrativa_ids
                    : d.unidade_administrativa_id
                      ? [d.unidade_administrativa_id]
                      : [];
                if (ids.length === 1) item.unidade_administrativa_id = Number(ids[0]);
                else if (ids.length > 1) item.unidade_administrativa_ids = ids.map(Number);
                return item;
            });
    }
    return payload;
}

export function estadoFormularioDevolutiva(overrides = {}) {
    return {
        parecer_resposta: '',
        anexos_novos: [],
        anexos_tramitacao_ids: [],
        alerta_destinos: [],
        ...overrides
    };
}
