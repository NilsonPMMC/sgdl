import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';

import PrimeVue from 'primevue/config';
import ConfirmationService from 'primevue/confirmationservice';
import ToastService from 'primevue/toastservice';
import Tooltip from 'primevue/tooltip';
import StyleClass from 'primevue/styleclass';

import '@/assets/styles.scss';

import { SgdlAuraPreset } from '@/theme/sgdl-preset';

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(PrimeVue, {
    theme: {
        preset: SgdlAuraPreset,
        options: {
            darkModeSelector: '.app-dark',
            cssLayer: false
        }
    }
});
app.use(ToastService);
app.use(ConfirmationService);
app.directive('tooltip', Tooltip);
app.directive('styleclass', StyleClass);

app.mount('#app');
