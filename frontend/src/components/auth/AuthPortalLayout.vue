<script setup>
import FloatingConfigurator from '@/components/FloatingConfigurator.vue';
import { RouterLink } from 'vue-router';

defineProps({
    variant: {
        type: String,
        required: true,
        validator: (v) => ['vereador', 'prefeitura'].includes(v)
    },
    eyebrow: { type: String, required: true },
    title: { type: String, required: true },
    subtitle: { type: String, required: true },
    features: {
        type: Array,
        default: () => []
    },
    alternatePortal: {
        type: Object,
        required: true
    }
});
</script>

<template>
    <div class="auth-portal" :class="`auth-portal--${variant}`">
        <FloatingConfigurator />

        <section class="auth-portal__hero" aria-hidden="false">
            <div class="auth-portal__hero-bg" aria-hidden="true" />
            <div class="auth-portal__hero-overlay" aria-hidden="true" />

            <div class="auth-portal__hero-inner">
                <img
                    src="/layout/images/brasao_nome_pmmc.png"
                    alt="Prefeitura Municipal de Mauá"
                    class="auth-portal__brasao"
                />

                <span class="auth-portal__eyebrow">{{ eyebrow }}</span>
                <h1 class="auth-portal__title">{{ title }}</h1>
                <p class="auth-portal__subtitle">{{ subtitle }}</p>

                <ul v-if="features.length" class="auth-portal__features">
                    <li v-for="feature in features" :key="feature.label" class="auth-portal__feature">
                        <span class="auth-portal__feature-icon">
                            <i :class="feature.icon" />
                        </span>
                        <div>
                            <strong>{{ feature.label }}</strong>
                            <p>{{ feature.detail }}</p>
                        </div>
                    </li>
                </ul>
            </div>

            <div class="auth-portal__hero-glow" aria-hidden="true" />
            <div class="auth-portal__hero-grid" aria-hidden="true" />
        </section>

        <section class="auth-portal__main">
            <div class="auth-portal__main-inner">
                <slot />

                <RouterLink :to="alternatePortal.route" class="auth-portal__switch">
                    <span class="auth-portal__switch-label">{{ alternatePortal.label }}</span>
                    <span class="auth-portal__switch-hint">{{ alternatePortal.hint }}</span>
                    <i class="pi pi-arrow-right auth-portal__switch-icon" />
                </RouterLink>
            </div>
        </section>
    </div>
</template>

<style scoped>
.auth-portal {
    --auth-accent: var(--p-primary-400, #4d6db8);
    --auth-accent-soft: color-mix(in srgb, var(--auth-accent), transparent 82%);
    --auth-hero-text: #f8fafc;
    --auth-hero-muted: #cbd5e1;
    min-height: 100vh;
    min-height: 100dvh;
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.75fr);
    background: var(--surface-ground, #0a1628);
}

.auth-portal--vereador {
    --auth-accent: #d4af37;
    --auth-hero-overlay-opacity: 0.86;
    --auth-hero-bg: linear-gradient(
        145deg,
        #0a1628 0%,
        color-mix(in srgb, #12244a 92%, #d4af37 8%) 38%,
        #1a3262 68%,
        #213a8f 100%
    );
}

.auth-portal--prefeitura {
    --auth-accent: #38bdf8;
    --auth-hero-overlay-opacity: 0.82;
    --auth-hero-bg: linear-gradient(
        155deg,
        #0a1628 0%,
        color-mix(in srgb, #0f2744 90%, #38bdf8 10%) 35%,
        #1e293b 62%,
        #152861 100%
    );
}

.auth-portal__hero {
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: clamp(2rem, 5vw, 4rem);
    background-color: #0a1628;
    color: var(--auth-hero-text);
}

.auth-portal__hero-bg {
    position: absolute;
    inset: 0;
    z-index: 0;
    background: url('/layout/images/bg_mogi.png') center / cover no-repeat;
    filter: saturate(0.9) brightness(0.72);
    transform: scale(1.02);
}

.auth-portal__hero-overlay {
    position: absolute;
    inset: 0;
    z-index: 1;
    background: var(--auth-hero-bg);
    opacity: var(--auth-hero-overlay-opacity, 0.84);
}

.auth-portal__hero-inner {
    position: relative;
    z-index: 3;
    max-width: 34rem;
}

.auth-portal__brasao {
    width: min(100%, 17rem);
    margin-bottom: 1.75rem;
    filter: drop-shadow(0 12px 24px rgba(0, 0, 0, 0.25));
}

.auth-portal__eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--auth-accent);
    background: var(--auth-accent-soft);
    border: 1px solid color-mix(in srgb, var(--auth-accent), transparent 55%);
}

.auth-portal__title {
    margin: 1rem 0 0.75rem;
    font-size: clamp(2rem, 5vw, 3.25rem);
    font-weight: 800;
    line-height: 1.05;
    letter-spacing: -0.02em;
}

.auth-portal__subtitle {
    margin: 0;
    font-size: clamp(1rem, 2.2vw, 1.15rem);
    line-height: 1.65;
    color: var(--auth-hero-muted);
    max-width: 32rem;
}

.auth-portal__features {
    list-style: none;
    margin: 2rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
}

.auth-portal__feature {
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
    padding: 0.85rem 1rem;
    border-radius: 0.9rem;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
}

.auth-portal__feature strong {
    display: block;
    font-size: 0.95rem;
    margin-bottom: 0.15rem;
}

.auth-portal__feature p {
    margin: 0;
    font-size: 0.85rem;
    color: var(--auth-hero-muted);
    line-height: 1.45;
}

.auth-portal__feature-icon {
    flex-shrink: 0;
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 0.65rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--auth-accent-soft);
    color: var(--auth-accent);
}

.auth-portal__hero-glow {
    position: absolute;
    z-index: 2;
    width: 48rem;
    height: 48rem;
    border-radius: 50%;
    background: radial-gradient(circle, color-mix(in srgb, var(--auth-accent), transparent 75%), transparent 55%);
    top: -12rem;
    right: -16rem;
    pointer-events: none;
}

.auth-portal__hero-grid {
    position: absolute;
    z-index: 2;
    inset: 0;
    opacity: 0.18;
    background-image:
        linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: linear-gradient(to bottom, black, transparent 85%);
    pointer-events: none;
}

.auth-portal__main {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: clamp(1.5rem, 4vw, 3rem);
    background:
        radial-gradient(circle at top right, color-mix(in srgb, var(--auth-accent), transparent 88%), transparent 45%),
        var(--surface-ground, #0a1628);
}

.auth-portal__main-inner {
    width: min(100%, 30rem);
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
}

.auth-portal__switch {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.95rem 1.1rem;
    border-radius: 0.95rem;
    text-decoration: none;
    color: var(--text-color);
    background: color-mix(in srgb, var(--surface-card, #1e293b), transparent 8%);
    border: 1px solid var(--surface-border, rgba(255, 255, 255, 0.08));
    transition: border-color 0.2s ease, transform 0.2s ease;
}

.auth-portal__switch:hover {
    border-color: color-mix(in srgb, var(--auth-accent), transparent 45%);
    transform: translateY(-1px);
}

.auth-portal__switch-label {
    font-weight: 700;
    font-size: 0.92rem;
}

.auth-portal__switch-hint {
    flex: 1;
    font-size: 0.8rem;
    color: var(--text-color-secondary);
}

.auth-portal__switch-icon {
    color: var(--auth-accent);
}

@media (max-width: 960px) {
    .auth-portal {
        grid-template-columns: 1fr;
        grid-template-rows: auto 1fr;
    }

    .auth-portal__hero {
        min-height: auto;
        padding: 2rem 1.25rem 1.5rem;
    }

    .auth-portal__hero-inner {
        max-width: none;
        text-align: center;
    }

    .auth-portal__brasao {
        margin-inline: auto;
        width: min(100%, 12rem);
    }

    .auth-portal__features {
        display: none;
    }

    .auth-portal__title {
        font-size: clamp(1.75rem, 7vw, 2.35rem);
    }

    .auth-portal__main {
        padding-top: 0.5rem;
        align-items: flex-start;
    }

    .auth-portal__main-inner {
        width: 100%;
    }
}

@media (max-width: 480px) {
    .auth-portal__switch {
        flex-wrap: wrap;
    }

    .auth-portal__switch-hint {
        flex-basis: 100%;
        padding-left: 0;
    }
}
</style>
