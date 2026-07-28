# Roteiro guiado — B5 + B8 (homologação pós-deploy)

> **Escopo:** despacho multi-secretaria (B5) e anexos em despacho/devolutiva (B8).  
> **Pré-requisito:** deploy com commits B5/B8; gate A1–A5 já validado.  
> **Documento mestre:** [ROTEIRO-HOMOLOGACAO-COMPLETO.md](ROTEIRO-HOMOLOGACAO-COMPLETO.md) (Fases 2–4) — **comece por lá** se estiver perdido.  
> **Referências:** [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md) · [homologacao-e2e-registro.md](homologacao-e2e-registro.md)

**Data sugerida:** após deploy em homologação operacional  
**Duração estimada:** 90–120 min (3 perfis + regressão)

---

## Perfis e contas necessárias

| Perfil | Uso no roteiro | Observação |
|--------|----------------|------------|
| **PROTOCOLO** | Cenários 1–4, 6 | Operador + gestor (dupla assinatura A4) |
| **SECRETARIA A** | Cenário 2 | Órgão distinto da Secretaria B |
| **SECRETARIA B** | Cenário 2 | Segundo destino do despacho multi |
| **VEREADOR** | Cenários 3, 5 | Autor do ofício de teste |

**Dados de teste sugeridos**

- 1 demanda em `AGUARDANDO_PROTOCOLO` (ofício enviado pelo vereador).
- 2 secretarias distintas no catálogo Sinapse (ex.: Zeladoria + Obras).
- Arquivos: `parecer-teste.pdf` (≤ 5 MB) e `foto-local.jpg` (≤ 5 MB), nomes **diferentes**.

---

## Checklist rápido (antes de começar)

- [ ] `python manage.py check --deploy` sem erros críticos no servidor
- [ ] Frontend buildado e publicado (`npm run build`)
- [ ] Backup restaurável registrado (checksum anotado)
- [ ] Usuários de teste com vínculo de secretaria correto (`sinapse_orgao_id`)

---

## Cenário 1 — Despacho single-secretaria + anexo (B8 + regressão A4)

**Objetivo:** garantir que o fluxo legado (1 secretaria) continua funcionando com upload.

| Passo | Ação | Resultado esperado |
|-------|------|-------------------|
| 1.1 | Login **PROTOCOLO** → fila **Protocolados** / aguardando despacho | Demanda de teste visível |
| 1.2 | Abrir **Despachar** → selecionar **1 secretaria** | MultiSelect aceita seleção única |
| 1.3 | Anexar `parecer-teste.pdf` | Chip com nome do arquivo aparece |
| 1.4 | Gerar prévia → marcar declarações → selecionar gestor → **Confirmar despacho** | Toast de sucesso; demanda sai da fila de aguardando |
| 1.5 | Abrir detalhe da demanda (Protocolo) → timeline | Tramitação **Despacho** com texto do protocolo executivo |
| 1.6 | Na mesma tramitação, verificar anexos | Link para `parecer-teste.pdf` visível ao Protocolo |
| 1.7 | Painel **Assinaturas eletrônicas** (B7) | Badge «Despacho assinado» — operador + gestor |

**Pass:** todos os passos OK.  
**Fail:** erro 400/500, anexo ausente na timeline, assinatura não registrada.

---

## Cenário 2 — Despacho multi-secretaria (B5)

**Objetivo:** ≥2 destinos criam processos separados; cada secretaria vê só sua fila.

| Passo | Ação | Resultado esperado |
|-------|------|-------------------|
| 2.1 | Nova demanda aguardando protocolo (ou segunda de teste) | Status `AGUARDANDO_PROTOCOLO` |
| 2.2 | **Despachar** → selecionar **Secretaria A + Secretaria B** | Mensagem info: «Despacho para 2 secretarias…» |
| 2.3 | (Opcional) Anexar 1 PDF | Anexo replicado em cada tramitação de despacho |
| 2.4 | Concluir assinatura dupla | Toast menciona **desdobramentos** com protocolos executivos extras |
| 2.5 | Anotar protocolos: principal + desdobramento `-D2` | 2 protocolos executivos distintos |
| 2.6 | Login **SECRETARIA A** → fila operacional | Vê **apenas** processo destinado à A |
| 2.7 | Login **SECRETARIA B** → fila operacional | Vê **apenas** processo destinado à B |
| 2.8 | Protocolo → verificar cluster (se aplicável) | Demandas vinculadas no mesmo cluster multi-destino |

**Pass:** filas isoladas por órgão; 2 protocolos executivos.  
**Fail:** uma secretaria vê processo da outra; só 1 protocolo criado.

---

## Cenário 3 — Devolutiva com anexo (B8)

**Objetivo:** anexo na devolutiva aparece no pacote do vereador (respeitando P8).

**Pré-condição:** demanda em `AGUARDANDO_DEVOLUTIVA_PROTOCOLO` (secretaria já solicitou devolutiva).

| Passo | Ação | Resultado esperado |
|-------|------|-------------------|
| 3.1 | Login **PROTOCOLO** → fila **Devolutivas** | Demanda listada |
| 3.2 | **Despachar devolutiva** → texto ≥ 10 caracteres | Campo obrigatório validado |
| 3.3 | Anexar `foto-local.jpg` | Chip visível |
| 3.4 | Prévia + assinatura dupla → enviar | Status `DEVOLVIDO_VEREADOR` |
| 3.5 | Login **VEREADOR** (autor) → abrir demanda | Pacote de devolutiva visível |
| 3.6 | Seção **Anexos do Protocolo** | Link para `foto-local.jpg` abre/baixa |
| 3.7 | Timeline vereador (P8) | **Não** expõe trânsito interno de despacho; marcos institucionais OK |

**Pass:** anexo no pacote; P8 preservado.  
**Fail:** vereador não vê anexo; timeline expõe despacho interno.

---

## Cenário 4 — Validação B3 em anexos de despacho

| Passo | Ação | Resultado esperado |
|-------|------|-------------------|
| 4.1 | No diálogo de despacho, selecionar **dois arquivos com o mesmo nome** | UI alerta e ignora duplicata (B3) |
| 4.2 | Tentar enviar só duplicatas | Nenhum anexo enviado; despacho pode prosseguir sem anexo |

**Pass:** alerta claro; API não aceita nomes repetidos no lote.

---

## Cenário 5 — Regressão encerramento (pós-devolutiva)

| Passo | Ação | Resultado esperado |
|-------|------|-------------------|
| 5.1 | Vereador redige resposta ao cidadão + confirma ciência | Fluxo encerramento legislativo intacto |
| 5.2 | PDF resposta ao cidadão | Gera sem regressão |

---

## Cenário 6 — API / evidências técnicas (opcional, operador técnico)

```bash
cd /var/www/sgdl/backend
source ../venv/bin/activate
python manage.py check --deploy
python manage.py test core.tests.test_despacho_destinos core.tests.test_tramitacao_texto core.tests.test_oficio_texto -v1
```

```bash
cd /var/www/sgdl/frontend
npm run build
```

Anotar no registro de homologação: data, commit SHA, resultado dos testes.

---

## Matriz pass/fail (critérios Onda B)

| ID | Critério | Cenário |
|----|----------|---------|
| **B5** | Despacho ≥2 destinos → tramitações separadas; secretarias veem só sua fila | 2 |
| **B8** | Upload despacho/devolutiva; anexo no pacote devolutiva | 1, 3 |
| **B3** | Nomes duplicados bloqueados | 4 |
| **B7** | Despacho assinado visível após A4 | 1 |
| **A4** | Dupla assinatura operador + gestor | 1, 2, 3 |

---

## Registro de execução

| Cenário | Executor | Data | Pass/Fail | Observações |
|---------|----------|------|-----------|-------------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |

**Homologação B5+B8:** ☐ Aprovado ☐ Reprovado — motivo: _______________

---

## Problemas conhecidos / limitações

- Desdobramento multi-secretaria usa sufixo `-D2`, `-D3` no `protocolo_legislativo` (constraint única por autor).
- Máximo **5** secretarias por despacho.
- Anexos multi-despacho são **copiados** para cada tramitação (mesmo arquivo em cada processo).
- Vereador **não** vê anexos do despacho inicial na timeline (P8); vê anexos apenas no **pacote devolutiva**.

---

**Última atualização:** 2026-06-10
