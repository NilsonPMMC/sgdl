<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import markerIconUrl from '/images/marker-icon.png';
import markerIconRetinaUrl from '/images/marker-icon-2x.png';
import markerShadowUrl from '/images/marker-shadow.png';

const props = defineProps({
    latitude: { type: Number, required: true },
    longitude: { type: Number, required: true },
    mapId: { type: String, default: 'mapa-local-ajustavel' },
    height: { type: String, default: '12rem' },
    zoom: { type: Number, default: 17 },
    draggable: { type: Boolean, default: true },
    scrollWheelZoom: { type: Boolean, default: true },
    mostrarDica: { type: Boolean, default: true }
});

const emit = defineEmits(['ajustado']);

const mapEl = ref(null);
const latAtual = ref(Number(props.latitude));
const lngAtual = ref(Number(props.longitude));
let map = null;
let marker = null;
let arrastando = false;

const defaultIcon = L.icon({
    iconUrl: markerIconUrl,
    iconRetinaUrl: markerIconRetinaUrl,
    shadowUrl: markerShadowUrl,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

function roundCoord(valor) {
    return Math.round(Number(valor) * 1e6) / 1e6;
}

function coordsValidas(lat, lng) {
    return !Number.isNaN(Number(lat)) && !Number.isNaN(Number(lng));
}

function posicaoAtual() {
    return [Number(latAtual.value), Number(lngAtual.value)];
}

function initMap() {
    if (!mapEl.value || map || !coordsValidas(latAtual.value, lngAtual.value)) {
        return;
    }
    const coords = posicaoAtual();
    map = L.map(mapEl.value, { scrollWheelZoom: props.scrollWheelZoom }).setView(coords, props.zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    marker = L.marker(coords, { icon: defaultIcon, draggable: props.draggable }).addTo(map);
    marker.on('dragstart', () => {
        arrastando = true;
    });
    if (props.draggable) {
        marker.on('dragend', (evento) => {
            arrastando = false;
            const { lat, lng } = evento.target.getLatLng();
            latAtual.value = roundCoord(lat);
            lngAtual.value = roundCoord(lng);
            emit('ajustado', { latitude: latAtual.value, longitude: lngAtual.value });
        });
    }
}

function atualizarMarcador() {
    if (!map || !marker || !coordsValidas(latAtual.value, lngAtual.value)) {
        return;
    }
    const coords = posicaoAtual();
    marker.setLatLng(coords);
    map.setView(coords, map.getZoom());
}

watch(
    () => [props.latitude, props.longitude],
    ([lat, lng]) => {
        if (arrastando) {
            return;
        }
        const latN = roundCoord(lat);
        const lngN = roundCoord(lng);
        if (
            roundCoord(latAtual.value) === latN &&
            roundCoord(lngAtual.value) === lngN
        ) {
            return;
        }
        latAtual.value = latN;
        lngAtual.value = lngN;
        if (map && marker) {
            atualizarMarcador();
        }
    }
);

watch(
    () => props.draggable,
    (podeArrastar) => {
        if (!marker) {
            return;
        }
        if (podeArrastar) {
            marker.dragging?.enable();
        } else {
            marker.dragging?.disable();
        }
    }
);

onMounted(() => {
    nextTick(() => {
        initMap();
        map?.invalidateSize();
    });
});

onBeforeUnmount(() => {
    if (map) {
        map.remove();
        map = null;
        marker = null;
    }
});

function invalidateSize() {
    map?.invalidateSize();
}

defineExpose({ invalidateSize });
</script>

<template>
    <div>
        <div
            :id="mapId"
            ref="mapEl"
            class="w-full overflow-hidden rounded-lg border border-[var(--surface-border)]"
            :style="{ height }"
            role="application"
            :aria-label="draggable ? 'Mapa com pin arrastável' : 'Mapa de localização'"
        />
        <p
            v-if="draggable && mostrarDica"
            class="m-0 mt-1 text-xs text-[var(--text-color-secondary)]"
        >
            Arraste o pin para o local exato no mapa.
        </p>
    </div>
</template>
