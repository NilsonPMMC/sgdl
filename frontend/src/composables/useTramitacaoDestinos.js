import { ref, watch } from 'vue';
import ApiService from '@/service/ApiService';

function rotuloUnidade(u, orgaoNome = '') {
    const base = u.sigla ? `${u.sigla} — ${u.nome}` : u.nome;
    return orgaoNome ? `${orgaoNome} › ${base}` : base;
}

/**
 * Carrega órgãos (Sinapse) e unidades administrativas filtradas por órgão(s).
 * H3-17: órgão → UA com busca.
 */
export function useTramitacaoDestinos() {
    const orgaos = ref([]);
    const unidades = ref([]);
    const carregandoOrgaos = ref(false);
    const carregandoUnidades = ref(false);

    const carregarOrgaos = async () => {
        if (orgaos.value.length) return orgaos.value;
        carregandoOrgaos.value = true;
        try {
            const { data } = await ApiService.getSecretarias();
            orgaos.value = Array.isArray(data) ? data : [];
            return orgaos.value;
        } catch {
            orgaos.value = [];
            return [];
        } finally {
            carregandoOrgaos.value = false;
        }
    };

    const carregarUnidadesPorOrgaos = async (orgaoIds = []) => {
        const ids = [...new Set((orgaoIds || []).filter(Boolean).map(Number))];
        if (!ids.length) {
            unidades.value = [];
            return [];
        }
        carregandoUnidades.value = true;
        try {
            const orgaoMap = Object.fromEntries(orgaos.value.map((o) => [o.id, o.nome]));
            const respostas = await Promise.all(
                ids.map((id) =>
                    ApiService.listarUnidadesAdministrativas({
                        sinapse_orgao_id: id,
                        ativo: true
                    }).then((r) => ({
                        orgaoId: id,
                        lista: Array.isArray(r.data) ? r.data : r.data?.results || []
                    }))
                )
            );
            const merged = [];
            const vistos = new Set();
            for (const { orgaoId, lista } of respostas) {
                const orgaoNome = orgaoMap[orgaoId] || `Órgão #${orgaoId}`;
                for (const u of lista) {
                    if (vistos.has(u.id)) continue;
                    vistos.add(u.id);
                    merged.push({
                        id: u.id,
                        sinapse_orgao_id: u.sinapse_orgao_id ?? orgaoId,
                        sigla: u.sigla,
                        nome: u.nome,
                        label: rotuloUnidade(u, ids.length > 1 ? orgaoNome : ''),
                        orgao_nome: orgaoNome
                    });
                }
            }
            merged.sort((a, b) => a.label.localeCompare(b.label, 'pt-BR'));
            unidades.value = merged;
            return merged;
        } catch {
            unidades.value = [];
            return [];
        } finally {
            carregandoUnidades.value = false;
        }
    };

    /** Observa orgao_ids e recarrega UAs automaticamente. */
    function useWatchOrgaos(orgaoIdsRef) {
        watch(
            orgaoIdsRef,
            (ids) => {
                carregarUnidadesPorOrgaos(ids);
            },
            { immediate: true, deep: true }
        );
    }

    return {
        orgaos,
        unidades,
        carregandoOrgaos,
        carregandoUnidades,
        carregarOrgaos,
        carregarUnidadesPorOrgaos,
        useWatchOrgaos
    };
}
