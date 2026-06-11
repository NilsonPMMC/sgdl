/** Extrai mensagem legível quando a API retorna erro JSON com responseType blob. */
export async function mensagemErroRespostaBlob(error, fallback = 'Não foi possível concluir a operação.') {
    const data = error?.response?.data;
    if (data instanceof Blob) {
        try {
            const json = JSON.parse(await data.text());
            if (json.detail) return String(json.detail);
            const partes = Object.values(json || {})
                .flat()
                .filter(Boolean);
            if (partes.length) return partes.join(' ');
        } catch {
            /* resposta não JSON */
        }
    }
    const payload = error?.response?.data;
    if (payload?.detail) return String(payload.detail);
    if (payload && typeof payload === 'object') {
        const partes = Object.values(payload)
            .flat()
            .filter(Boolean);
        if (partes.length) return partes.join(' ');
    }
    return fallback;
}

/** Confirma se o blob parece ser PDF (evita exibir JSON de erro no iframe). */
export function blobParecePdf(blob) {
    return blob instanceof Blob && blob.type.includes('pdf');
}
