<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import ApiService from '@/service/ApiService.js';
import { useUserStore } from '@/stores/userStore'; // Importa o store
import { filtrarNotificacoesSemAtraso } from '@/utils/metricasSlaVereador';
import { useToast } from 'primevue/usetoast';
import DataView from 'primevue/dataview';
import Button from 'primevue/button';
import Tag from 'primevue/tag';

const notificacoes = ref([]);
const loading = ref(true);
const router = useRouter();
const userStore = useUserStore(); // Instancia o store
const toast = useToast();

const fetchNotificacoes = async () => {
    loading.value = true;

    try {
        const response = await ApiService.getNotificacoes();

        const bruto =
            response.data && Array.isArray(response.data.results)
                ? response.data.results
                : Array.isArray(response.data)
                  ? response.data
                  : [];
        notificacoes.value = filtrarNotificacoesSemAtraso(bruto, userStore.currentUser?.perfil);
    } catch (error) {
        console.error('Erro ao buscar notificações:', error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Falha ao carregar notificações.', life: 3000 });
        notificacoes.value = [];
    } finally {
        loading.value = false;
    }
};

const marcarTodasLidas = async () => {
    loading.value = true;
    try {
        await ApiService.marcarTodasNotificacoesComoLidas();
        await fetchNotificacoes();
    } catch (error) {
        console.error('Erro ao marcar todas como lidas:', error);
        toast.add({ severity: 'error', summary: 'Erro', detail: 'Não foi possível marcar notificações.', life: 3000 });
        loading.value = false;
    }
};

const onNotificationClick = async (notif) => {
    try {
        if (!notif.lida) {
            await ApiService.marcarNotificacaoComoLida(notif.id);
            const index = notificacoes.value.findIndex((n) => n.id === notif.id);
            if (index !== -1) {
                notificacoes.value[index].lida = true;
            }
        }
        router.push(notif.link || '/');
    } catch (error) {
        console.error('Erro ao marcar notificação como lida:', error);
        toast.add({ severity: 'warn', summary: 'Atenção', detail: 'Falha ao registrar leitura da notificação.', life: 3000 });
        router.push(notif.link || '/');
    }
};

const getIconInfo = (tipo) => {
    switch (tipo) {
        case 'ATRASO':
            return { icon: 'pi pi-exclamation-triangle', bgClass: 'bg-red-100 dark:bg-red-900 text-red-500' };
        case 'CONCLUSAO':
            return { icon: 'pi pi-check-circle', bgClass: 'bg-green-100 dark:bg-green-900 text-green-500' };
        case 'DESPACHO':
            return { icon: 'pi pi-send', bgClass: 'bg-blue-100 dark:bg-blue-900 text-blue-500' };
        case 'TRANSFERENCIA':
            return { icon: 'pi pi-arrow-right-arrow-left', bgClass: 'bg-purple-100 dark:bg-purple-900 text-purple-500' };
        case 'NOVO_OFICIO':
            return { icon: 'pi pi-file-plus', bgClass: 'bg-blue-100 dark:bg-blue-900 text-blue-500' };
        default:
            return { icon: 'pi pi-bell', bgClass: 'bg-gray-100 dark:bg-gray-900 text-gray-500' };
    }
};

const formatarData = (dataString) => {
    if (!dataString) return 'Sem data';
    const data = new Date(dataString);
    return data.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

onMounted(() => {
    if (userStore.isAuthenticated) {
        fetchNotificacoes();
    } else {
        loading.value = false;
    }
});
</script>

<template>
    <div class="card">
        <div class="flex justify-between items-center mb-4">
            <h5 class="m-0">Todas as Notificações</h5>
            <Button label="Marcar todas como lidas" icon="pi pi-check-double" severity="secondary" @click="marcarTodasLidas" :loading="loading" :disabled="notificacoes.length === 0" />
        </div>

        <DataView :value="notificacoes" :layout="'list'" :loading="loading" dataKey="id">
            <template #empty>
                <div class="p-4 text-center text-gray-500">Nenhuma notificação encontrada.</div>
            </template>

            <template #list="slotProps">
                <div v-for="item in slotProps.items" :key="item.id" class="col-12">
                    <div
                        class="flex flex-col xl:flex-row xl:items-start p-4 gap-4 w-full cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 border-b border-gray-200 dark:border-gray-700"
                        :class="{ 'opacity-60': item.lida }"
                        @click="onNotificationClick(item)"
                    >
                        <div class="flex items-center justify-center p-3 rounded-full w-12 h-12" :class="getIconInfo(item.tipo).bgClass">
                            <i class="pi text-2xl" :class="getIconInfo(item.tipo).icon"></i>
                        </div>
                        <div class="flex flex-col gap-2 flex-grow">
                            <div class="text-base font-medium text-gray-800 dark:text-white">
                                {{ item.mensagem }}
                            </div>
                            <div class="flex items-center gap-4">
                                <span class="text-sm text-gray-500">
                                    {{ formatarData(item.data_criacao) }}
                                </span>
                                <Tag v-if="!item.lida" value="Nova" severity="info"></Tag>
                            </div>
                        </div>
                        <i class="pi pi-chevron-right text-gray-400 self-center"></i>
                    </div>
                </div>
            </template>
        </DataView>
    </div>
</template>

<style scoped>
.p-dataview .p-dataview-content > .col-12 {
    padding: 0 !important;
}
</style>
