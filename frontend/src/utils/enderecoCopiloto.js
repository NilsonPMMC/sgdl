/** Formulário de endereço na revisão local do Copiloto (H-JUL-13/14). */

export function snapshotEnderecoDemanda(demanda) {
    const end = demanda?.endereco && typeof demanda.endereco === 'object' ? demanda.endereco : {};
    return {
        cep: end.cep || '',
        logradouro: end.logradouro || '',
        bairro: end.bairro || '',
        numero: end.numero || ''
    };
}

/** Mínimo de caracteres úteis para autocomplete (espaços internos contam). */
export function termoBuscaLogradouroValido(termo, minimo = 3) {
    return (termo || '').trim().length >= minimo;
}
