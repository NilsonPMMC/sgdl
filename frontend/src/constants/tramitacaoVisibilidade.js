/** Tipos de tramitação visíveis na timeline do perfil VEREADOR (P8). */
export const TIPOS_TRAMITACAO_VISIVEIS_VEREADOR = new Set([
    'ENVIO_OFICIAL',
    'DESPACHO',
    'CONCLUSAO',
    'SOLICITACAO_DEVOLUTIVA',
    'DEVOLUTIVA_PROTOCOLO',
    'CIENCIA_VEREADOR',
    'ENCERRAMENTO_DEVOLUTIVA'
]);

export function tramitacaoVisivelParaVereador(tipo) {
    return TIPOS_TRAMITACAO_VISIVEIS_VEREADOR.has((tipo || '').toUpperCase());
}

/** Rótulo amigável para marcos legislativos no perfil vereador. */
export function labelTramitacaoVereador(item) {
    if (!item) return '';
    if (item.tipo === 'CONCLUSAO') {
        return 'Serviço concluído pela Secretaria';
    }
    return item.tipo_display || item.tipo || '';
}
