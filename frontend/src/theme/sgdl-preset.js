/**
 * Tema institucional SGDL — cor primária #213a8f (PrimeVue Aura + Sakai).
 */
import { definePreset } from '@primeuix/themes';
import Aura from '@primeuix/themes/aura';

/**
 * Superfícies dark — âncoras #0a1628 (fundo) e #1e293b (painéis).
 * Tons 400–50 em escala slate para texto/bordas legíveis (evita azuis apagados).
 */
export const SGDL_DARK_SURFACE = {
    0: '#ffffff',
    50: '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#253045',
    900: '#1e293b',
    950: '#0a1628'
};

const darkTextScheme = {
    color: '{surface.100}',
    hoverColor: '{surface.0}',
    mutedColor: '{surface.400}',
    hoverMutedColor: '{surface.300}'
};

const darkContentScheme = {
    background: '{surface.900}',
    hoverBackground: '{surface.800}',
    borderColor: '{surface.700}',
    color: '{text.color}',
    hoverColor: '{text.hover.color}'
};

/** Paleta harmonizada a partir de #213a8f (500). */
export const SGDL_PRIMARY_PALETTE = {
    50: '#eef1f9',
    100: '#d5dcf0',
    200: '#aab9e1',
    300: '#8096d2',
    400: '#4d6db8',
    500: '#213a8f',
    600: '#1b3178',
    700: '#152861',
    800: '#101e4a',
    900: '#0c1638',
    950: '#080f28'
};

const primaryColorScheme = {
    light: {
        primary: {
            color: '{primary.500}',
            contrastColor: '#ffffff',
            hoverColor: '{primary.600}',
            activeColor: '{primary.700}'
        },
        highlight: {
            background: '{primary.50}',
            focusBackground: '{primary.100}',
            color: '{primary.700}',
            focusColor: '{primary.800}'
        }
    },
    dark: {
        primary: {
            color: '{primary.400}',
            contrastColor: '{surface.900}',
            hoverColor: '{primary.300}',
            activeColor: '{primary.200}'
        },
        highlight: {
            background: 'color-mix(in srgb, {primary.400}, transparent 84%)',
            focusBackground: 'color-mix(in srgb, {primary.400}, transparent 76%)',
            color: 'rgba(255,255,255,.87)',
            focusColor: 'rgba(255,255,255,.87)'
        }
    }
};

export const SgdlAuraPreset = definePreset(Aura, {
    semantic: {
        primary: SGDL_PRIMARY_PALETTE,
        colorScheme: {
            light: primaryColorScheme.light,
            dark: {
                ...primaryColorScheme.dark,
                surface: SGDL_DARK_SURFACE,
                text: darkTextScheme,
                content: darkContentScheme
            }
        }
    }
});

/** Tokens CSS adicionais (login, gráficos, mapas). */
export const SGDL_BRAND = {
    primary: SGDL_PRIMARY_PALETTE[500],
    primaryLight: SGDL_PRIMARY_PALETTE[400],
    primaryDark: SGDL_PRIMARY_PALETTE[700],
    primaryMuted: SGDL_PRIMARY_PALETTE[100],
    darkGround: SGDL_DARK_SURFACE[950],
    darkElevated: SGDL_DARK_SURFACE[900]
};
