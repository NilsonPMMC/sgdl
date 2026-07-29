/** Remove prefixo legado «OFICIO-» — o tipo vem da tag (Ofício / Indicação). */
export function formatarProtocoloLegislativo(valor) {
    if (valor == null || valor === '') return valor ?? '';
    return String(valor).trim().replace(/^OFICIO-/i, '');
}

/** Protocolo executivo (global) ou número legislativo formatado. */
export function exibirProtocoloDemanda(demanda, fallback = '—') {
    if (!demanda) return fallback;
    if (demanda.protocolo_executivo) return demanda.protocolo_executivo;
    const leg = formatarProtocoloLegislativo(demanda.protocolo_legislativo);
    return leg || fallback;
}
