/** Validação de nomes de arquivo em anexos (B3). */

export function normalizarNomeArquivo(nome) {
    const base = String(nome || '')
        .split(/[/\\]/)
        .pop()
        ?.trim();
    return (base || '').toLowerCase();
}

export function nomeAnexoSalvo(anexo) {
    const url = anexo?.arquivo || '';
    const doUrl = url.split('/').pop() || '';
    return normalizarNomeArquivo(doUrl || anexo?.descricao || '');
}

/**
 * Separa arquivos novos em aceitos vs. rejeitados por nome duplicado.
 * @param {File[]} novos
 * @param {Iterable<string>} existentesNormalizados
 */
export function filtrarArquivosDuplicados(novos, existentesNormalizados = []) {
    const vistos = new Set([...existentesNormalizados].map((n) => normalizarNomeArquivo(n)));
    const aceitos = [];
    const rejeitados = [];

    for (const file of novos || []) {
        const norm = normalizarNomeArquivo(file?.name);
        if (!norm || vistos.has(norm)) {
            rejeitados.push(file);
        } else {
            aceitos.push(file);
            vistos.add(norm);
        }
    }

    return { aceitos, rejeitados };
}

export function mensagemAnexosRejeitados(rejeitados) {
    if (!rejeitados?.length) return '';
    const nomes = rejeitados.map((f) => f.name).join(', ');
    return `Anexo(s) ignorado(s) — já existe(m) com o mesmo nome: ${nomes}. Renomeie o arquivo ou remova o anterior.`;
}
