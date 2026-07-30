/** Utilitários compartilhados para ajuste manual de pin no mapa (Leaflet). */

export function roundCoordMapa(valor) {
    return Math.round(Number(valor) * 1e6) / 1e6;
}

/**
 * @param {import('vue').Ref} marker
 * @param {(evento: import('leaflet').LeafletEvent) => void | Promise<void>} handler
 */
export function vincularMarcadorArrastavel(marker, handler) {
    if (!marker.value) {
        return;
    }
    marker.value.dragging?.enable();
    marker.value.off('dragend', handler);
    marker.value.on('dragend', handler);
}

/**
 * @param {import('vue').Ref<{ latitude?: number|null, longitude?: number|null, logradouro?: string, bairro?: string, cep?: string }>} demanda
 * @param {import('vue').Ref<string|null>} fonteGeocodificacao
 * @param {typeof import('@/service/ApiService.js').default} ApiService
 * @param {ReturnType<typeof import('primevue/usetoast').useToast>} toast
 */
export async function aplicarAjusteManualMapa(evento, demanda, fonteGeocodificacao, ApiService, toast) {
    const { lat, lng } = evento.target.getLatLng();
    const latitude = roundCoordMapa(lat);
    const longitude = roundCoordMapa(lng);
    demanda.value.latitude = latitude;
    demanda.value.longitude = longitude;
    fonteGeocodificacao.value = 'ajuste_mapa';

    try {
        const { data } = await ApiService.reverseGeocodingEndereco({ latitude, longitude });
        if (data.logradouro) {
            demanda.value.logradouro = data.logradouro;
        }
        if (data.bairro) {
            demanda.value.bairro = data.bairro;
        }
        if (data.cep) {
            demanda.value.cep = data.cep;
        }
        toast.add({
            severity: 'info',
            summary: 'Mapa',
            detail: `Ponto ajustado (${latitude.toFixed(6)}, ${longitude.toFixed(6)}).`,
            life: 3500
        });
    } catch {
        toast.add({
            severity: 'info',
            summary: 'Mapa',
            detail: `Coordenadas atualizadas (${latitude.toFixed(6)}, ${longitude.toFixed(6)}).`,
            life: 3500
        });
    }
}
