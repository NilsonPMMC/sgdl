# Relatório de conferência — IDs duplicados na RM271698

> Gerado por `manage.py gerar_relatorio_rm_duplicados`. Validação com fonte RM/SEI; não altera o banco.

## Resumo

| Métrica | Valor |
|---------|-------|
| Linhas na planilha | 1191 |
| IDs únicos (`ID_UNIDADE`) | 1120 |
| Linhas extras (duplicatas) | 71 |
| IDs com mais de uma linha | 45 |
| Registros no banco SGDL (esperado) | 1120 |

A importação SGDL usa `ID_UNIDADE` como chave (`UnidadeAdministrativa.sinapse_unidade_id`): **1 registro por ID**. Linhas repetidas atualizam o mesmo registro; a **última linha processada** prevalece no e-mail.

Ver também: [importacao-unidades-rm271698.md](importacao-unidades-rm271698.md).

---

## Detalhamento por ID

### ID `110004661` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 81 | MCRUZ-SME-SNR | Seção de Normas e Regulação | legislacao@se-pmmc.com.br |
| 82 | MCRUZ-SME-SNR | Seção de Normas e Regulação | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 82** (`sei_naoresponder@sp.gov.br`).

### ID `110005012` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 690 | MCRUZ-IPREM-SUPERINTENDENCIA | Gabinete da Superintendencia | luizmiranda@mogidascruzes.sp.gov.br |
| 691 | MCRUZ-IPREM-SUPERINTENDENCIA | Gabinete da Superintendencia | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 691** (`sei_naoresponder@sp.gov.br`).

### ID `110005013` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 692 | MCRUZ-IPREM-EXPEDIENTE | Seção de Expediente | felipeamaral@mogidascruzes.sp.gov.br |
| 693 | MCRUZ-IPREM-EXPEDIENTE | Seção de Expediente | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 693** (`sei_naoresponder@sp.gov.br`).

### ID `110005014` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 694 | MCRUZ-IPREM-PREVIDENCIA | Departamento de Previdência | joseorlando@mogidascruzes.sp.gov.br |
| 695 | MCRUZ-IPREM-PREVIDENCIA | Departamento de Previdência | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 695** (`sei_naoresponder@sp.gov.br`).

### ID `110005015` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 696 | MCRUZ-IPREM-RH | Seção de Recursos Humanos e Folha de Pagamento | pessoal.iprem@mogidascruzes.sp.gov.br |
| 697 | MCRUZ-IPREM-RH | Seção de Recursos Humanos e Folha de Pagamento | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 697** (`sei_naoresponder@sp.gov.br`).

### ID `110005016` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 698 | MCRUZ-IPREM-TESOURARIA | Seção de Tesouraria | richard.iprem@mogidascruzes.sp.gov.br |
| 699 | MCRUZ-IPREM-TESOURARIA | Seção de Tesouraria | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 699** (`sei_naoresponder@sp.gov.br`).

### ID `110005017` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 700 | MCRUZ-IPREM-CONTABILIDADE | Seção de Contabilidade | eimarmachado@mogidascruzes.sp.gov.br |
| 701 | MCRUZ-IPREM-CONTABILIDADE | Seção de Contabilidade | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 701** (`sei_naoresponder@sp.gov.br`).

### ID `110005018` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 702 | MCRUZ-IPREM-COMPRAS | Seção de Compras e Licitação | anadomingues@mogidascruzes.sp.gov.br |
| 703 | MCRUZ-IPREM-COMPRAS | Seção de Compras e Licitação | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 703** (`sei_naoresponder@sp.gov.br`).

### ID `110005019` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 704 | MCRUZ-IPREM-CAIPREM | Conselho de Administração | caiprem@mogidascruzes.sp.gov.br |
| 705 | MCRUZ-IPREM-CAIPREM | Conselho de Administração | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 705** (`sei_naoresponder@sp.gov.br`).

### ID `110005020` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 706 | MCRUZ-IPREM-CFISCAL | Conselho Fiscal | conselhofiscal.iprem@mogidascruzes.sp.gov.br |
| 707 | MCRUZ-IPREM-CFISCAL | Conselho Fiscal | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 707** (`sei_naoresponder@sp.gov.br`).

### ID `110005021` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 708 | MCRUZ-IPREM-COMITE | Comitê de Investimentos | comite.iprem@mogidascruzes.sp.gov.br |
| 709 | MCRUZ-IPREM-COMITE | Comitê de Investimentos | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 709** (`sei_naoresponder@sp.gov.br`).

### ID `110005307` — 3 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 764 | MCRUZ-SEMAS-DGSUAS | Diretoria de Gestão do SUAS | livia.semas@mogidascruzes.sp.gov.br |
| 765 | MCRUZ-SEMAS-DGSUAS | Diretoria de Gestão do SUAS | simonelima@mogidascruzes.sp.gov.br |
| 766 | MCRUZ-SEMAS-DGSUAS | Diretoria de Gestão do SUAS | sei_naoresponder@sp.gov.br |

E-mails distintos: 3 — na importação prevalece a **linha 766** (`sei_naoresponder@sp.gov.br`).

### ID `110005308` — 3 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 767 | MCRUZ-SMAS-DGSUAS-SGSUAS | Seção de Gestão do SUAS e Regulação | livia.semas@mogidascruzes.sp.gov.br |
| 768 | MCRUZ-SMAS-DGSUAS-SGSUAS | Seção de Gestão do SUAS e Regulação | simonelima@mogidascruzes.sp.gov.br |
| 769 | MCRUZ-SMAS-DGSUAS-SGSUAS | Seção de Gestão do SUAS e Regulação | sei_naoresponder@sp.gov.br |

E-mails distintos: 3 — na importação prevalece a **linha 769** (`sei_naoresponder@sp.gov.br`).

### ID `110005309` — 4 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 770 | MCRUZ-SMAS-DGSUAS-GTRAB | Setor de Gestão do Trabalho | livia.semas@mogidascruzes.sp.gov.br |
| 771 | MCRUZ-SMAS-DGSUAS-GTRAB | Setor de Gestão do Trabalho | simonelima@mogidascruzes.sp.gov.br |
| 772 | MCRUZ-SMAS-DGSUAS-GTRAB | Setor de Gestão do Trabalho | carolina.semas@mogidascruzes.sp.gov.br |
| 773 | MCRUZ-SMAS-DGSUAS-GTRAB | Setor de Gestão do Trabalho | sei_naoresponder@sp.gov.br |

E-mails distintos: 4 — na importação prevalece a **linha 773** (`sei_naoresponder@sp.gov.br`).

### ID `110005310` — 4 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 774 | MCRUZ-SMAS-DGSUAS-VIG | Gestão Técnica de Vigilância Socioassistencial | livia.semas@mogidascruzes.sp.gov.br |
| 775 | MCRUZ-SMAS-DGSUAS-VIG | Gestão Técnica de Vigilância Socioassistencial | simonelima@mogidascruzes.sp.gov.br |
| 776 | MCRUZ-SMAS-DGSUAS-VIG | Gestão Técnica de Vigilância Socioassistencial | nayra.semas@mogidascruzes.sp.gov.br |
| 777 | MCRUZ-SMAS-DGSUAS-VIG | Gestão Técnica de Vigilância Socioassistencial | sei_naoresponder@sp.gov.br |

E-mails distintos: 4 — na importação prevalece a **linha 777** (`sei_naoresponder@sp.gov.br`).

### ID `110005311` — 5 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 778 | MCRUZ-SMAS-DGSUAS-VIGADM | Administrativo Vigilância Socioassistencial | livia.semas@mogidascruzes.sp.gov.br |
| 779 | MCRUZ-SMAS-DGSUAS-VIGADM | Administrativo Vigilância Socioassistencial | simonelima@mogidascruzes.sp.gov.br |
| 780 | MCRUZ-SMAS-DGSUAS-VIGADM | Administrativo Vigilância Socioassistencial | nayra.semas@mogidascruzes.sp.gov.br |
| 781 | MCRUZ-SMAS-DGSUAS-VIGADM | Administrativo Vigilância Socioassistencial | rodrigohonda.semas@mogidascruzes.sp.gov.br |
| 782 | MCRUZ-SMAS-DGSUAS-VIGADM | Administrativo Vigilância Socioassistencial | sei_naoresponder@sp.gov.br |

E-mails distintos: 5 — na importação prevalece a **linha 782** (`sei_naoresponder@sp.gov.br`).

### ID `110005312` — 5 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 783 | MCRUZ-SMAS-DGSUAS-MONIT1 | Monitoramento - Acolhimento Pessoas em Situação de Rua | livia.semas@mogidascruzes.sp.gov.br |
| 784 | MCRUZ-SMAS-DGSUAS-MONIT1 | Monitoramento - Acolhimento Pessoas em Situação de Rua | simonelima@mogidascruzes.sp.gov.br |
| 785 | MCRUZ-SMAS-DGSUAS-MONIT1 | Monitoramento - Acolhimento Pessoas em Situação de Rua | nayra.semas@mogidascruzes.sp.gov.br |
| 786 | MCRUZ-SMAS-DGSUAS-MONIT1 | Monitoramento - Acolhimento Pessoas em Situação de Rua | carla.semas@mogidascruzes.sp.gov.br |
| 787 | MCRUZ-SMAS-DGSUAS-MONIT1 | Monitoramento - Acolhimento Pessoas em Situação de Rua | sei_naoresponder@sp.gov.br |

E-mails distintos: 5 — na importação prevalece a **linha 787** (`sei_naoresponder@sp.gov.br`).

### ID `110005313` — 5 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 788 | MCRUZ-SMAS-DGSUAS-MONIT2 | Monitoramento - Acolhimento Crianças e Adolescentes | livia.semas@mogidascruzes.sp.gov.br |
| 789 | MCRUZ-SMAS-DGSUAS-MONIT2 | Monitoramento - Acolhimento Crianças e Adolescentes | simonelima@mogidascruzes.sp.gov.br |
| 790 | MCRUZ-SMAS-DGSUAS-MONIT2 | Monitoramento - Acolhimento Crianças e Adolescentes | nayra.semas@mogidascruzes.sp.gov.br |
| 791 | MCRUZ-SMAS-DGSUAS-MONIT2 | Monitoramento - Acolhimento Crianças e Adolescentes | ingridrufino@mogidascruzes.sp.gov.br |
| 792 | MCRUZ-SMAS-DGSUAS-MONIT2 | Monitoramento - Acolhimento Crianças e Adolescentes | sei_naoresponder@sp.gov.br |

E-mails distintos: 5 — na importação prevalece a **linha 792** (`sei_naoresponder@sp.gov.br`).

### ID `110005314` — 5 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 793 | MCRUZ-SMAS-DGSUAS-MONIT3 | Monitoramento - Acolhimento Pessoas Idosas | livia.semas@mogidascruzes.sp.gov.br |
| 794 | MCRUZ-SMAS-DGSUAS-MONIT3 | Monitoramento - Acolhimento Pessoas Idosas | simonelima@mogidascruzes.sp.gov.br |
| 795 | MCRUZ-SMAS-DGSUAS-MONIT3 | Monitoramento - Acolhimento Pessoas Idosas | nayra.semas@mogidascruzes.sp.gov.br |
| 796 | MCRUZ-SMAS-DGSUAS-MONIT3 | Monitoramento - Acolhimento Pessoas Idosas | marcoscarvalho.semas@mogidascruzes.sp.gov.br |
| 797 | MCRUZ-SMAS-DGSUAS-MONIT3 | Monitoramento - Acolhimento Pessoas Idosas | sei_naoresponder@sp.gov.br |

E-mails distintos: 5 — na importação prevalece a **linha 797** (`sei_naoresponder@sp.gov.br`).

### ID `110005315` — 5 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 798 | MCRUZ-SMAS-DGSUAS-MONIT4 | Monitoramento - Serviços de Convivência Crianças e Adolescentes | livia.semas@mogidascruzes.sp.gov.br |
| 799 | MCRUZ-SMAS-DGSUAS-MONIT4 | Monitoramento - Serviços de Convivência Crianças e Adolescentes | simonelima@mogidascruzes.sp.gov.br |
| 800 | MCRUZ-SMAS-DGSUAS-MONIT4 | Monitoramento - Serviços de Convivência Crianças e Adolescentes | nayra.semas@mogidascruzes.sp.gov.br |
| 801 | MCRUZ-SMAS-DGSUAS-MONIT4 | Monitoramento - Serviços de Convivência Crianças e Adolescentes | mayaragenari@mogidascruzes.sp.gov.br |
| 802 | MCRUZ-SMAS-DGSUAS-MONIT4 | Monitoramento - Serviços de Convivência Crianças e Adolescentes | sei_naoresponder@sp.gov.br |

E-mails distintos: 5 — na importação prevalece a **linha 802** (`sei_naoresponder@sp.gov.br`).

### ID `110005316` — 5 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 803 | MCRUZ-SMAS-DGSUAS-MONIT5 | Monitoramento - Serviços Pessoas com Deficiência | livia.semas@mogidascruzes.sp.gov.br |
| 804 | MCRUZ-SMAS-DGSUAS-MONIT5 | Monitoramento - Serviços Pessoas com Deficiência | simonelima@mogidascruzes.sp.gov.br |
| 805 | MCRUZ-SMAS-DGSUAS-MONIT5 | Monitoramento - Serviços Pessoas com Deficiência | nayra.semas@mogidascruzes.sp.gov.br |
| 806 | MCRUZ-SMAS-DGSUAS-MONIT5 | Monitoramento - Serviços Pessoas com Deficiência | patriciamaria.semas@mogidascruzes.sp.gov.br |
| 807 | MCRUZ-SMAS-DGSUAS-MONIT5 | Monitoramento - Serviços Pessoas com Deficiência | sei_naoresponder@sp.gov.br |

E-mails distintos: 5 — na importação prevalece a **linha 807** (`sei_naoresponder@sp.gov.br`).

### ID `110005329` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 820 | MCRUZ-SMAS-DIVDGG-EXP-MP | Expediente Ministério Público | lilian.semas@mogidascruzes.sp.gov.br |
| 821 | MCRUZ-SMAS-DIVDGG-EXP-MP | Expediente Ministério Público | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 821** (`sei_naoresponder@sp.gov.br`).

### ID `110005330` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 822 | MCRUZ-SMAS-DIVDGG-EXP-TJ | Expediente Tribunal de Justiça | lilian.semas@mogidascruzes.sp.gov.br |
| 823 | MCRUZ-SMAS-DIVDGG-EXP-TJ | Expediente Tribunal de Justiça | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 823** (`sei_naoresponder@sp.gov.br`).

### ID `110005331` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 824 | MCRUZ-SMAS-DIVDGG-EXP-EPL | Expediente Poder Legislativo | lilian.semas@mogidascruzes.sp.gov.br |
| 825 | MCRUZ-SMAS-DIVDGG-EXP-EPL | Expediente Poder Legislativo | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 825** (`sei_naoresponder@sp.gov.br`).

### ID `110005332` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 826 | MCRUZ-SMAS-CRASJL | CRAS Jardim Layr | craslayr.semas@mogidascruzes.sp.gov.br |
| 827 | MCRUZ-SMAS-CRASJL | CRAS Jardim Layr | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 827** (`sei_naoresponder@sp.gov.br`).

### ID `110005333` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 828 | MCRUZ-SMAS-CRACS | CRAS César de Souza | crascesar.semas@mogidascruzes.sp.gov.br |
| 829 | MCRUZ-SMAS-CRACS | CRAS César de Souza | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 829** (`sei_naoresponder@sp.gov.br`).

### ID `110005334` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 830 | MCRUZ-SMAS-CRASVNU | CRAS Vila Nova União | crasnovauniao.semas@mogidascruzes.sp.gov.br |
| 831 | MCRUZ-SMAS-CRASVNU | CRAS Vila Nova União | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 831** (`sei_naoresponder@sp.gov.br`).

### ID `110005335` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 832 | MCRUZ-SMAS-CRASJ | CRAS Jundiapeba I | crasjundiapeba.semas@mogidascruzes.sp.gov.br |
| 833 | MCRUZ-SMAS-CRASJ | CRAS Jundiapeba I | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 833** (`sei_naoresponder@sp.gov.br`).

### ID `110005336` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 834 | MCRUZ-SMAS-CRASJII | CRAS Jundiapeba II | crasjundiapeba2@mogidascruzes.sp.gov.br |
| 835 | MCRUZ-SMAS-CRASJII | CRAS Jundiapeba II | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 835** (`sei_naoresponder@sp.gov.br`).

### ID `110005337` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 836 | MCRUZ-SMAS-CRASVB | CRAS Vila Brasileira | crasvilabrasileira@mogidascruzes.sp.gov.br |
| 837 | MCRUZ-SMAS-CRASVB | CRAS Vila Brasileira | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 837** (`sei_naoresponder@sp.gov.br`).

### ID `110005338` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 838 | MCRUZ-SMAS-CRASC | CRAS Centro | crascentro.semas@mogidascruzes.sp.gov.br |
| 839 | MCRUZ-SMAS-CRASC | CRAS Centro | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 839** (`sei_naoresponder@sp.gov.br`).

### ID `110005339` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 840 | MCRUZ-SMAS-PCF | Programa Criança Feliz | criancafeliz.semas@mogidascruzes.sp.gov.br |
| 841 | MCRUZ-SMAS-PCF | Programa Criança Feliz | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 841** (`sei_naoresponder@sp.gov.br`).

### ID `110005451` — 3 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 1075 | MCRUZ-SMAS-DGPPC-AJ | Apoio Jurídico | patriciacristina@mogidascruzes.sp.gov.br |
| 1076 | MCRUZ-SMAS-DGPPC-AJ | Apoio Jurídico | audrey.semas@mogidascruzes.sp.gov.br |
| 1077 | MCRUZ-SMAS-DGPPC-AJ | Apoio Jurídico | sei_naoresponder@sp.gov.br |

E-mails distintos: 3 — na importação prevalece a **linha 1077** (`sei_naoresponder@sp.gov.br`).

### ID `110005452` — 3 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 1078 | MCRUZ-SMAS-SGRH | Seção de Gestão de Recursos Humanos | lilian.semas@mogidascruzes.sp.gov.br |
| 1079 | MCRUZ-SMAS-SGRH | Seção de Gestão de Recursos Humanos | melissadao@mogidascruzes.sp.gov.br |
| 1080 | MCRUZ-SMAS-SGRH | Seção de Gestão de Recursos Humanos | sei_naoresponder@sp.gov.br |

E-mails distintos: 3 — na importação prevalece a **linha 1080** (`sei_naoresponder@sp.gov.br`).

### ID `110005475` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 1103 | MCRUZ-SMAS-ACESSUAS/CONDUZ | Programa Acessuas/Conduz | conduz.semas@mogidascruzes.sp.gov.br |
| 1104 | MCRUZ-SMAS-ACESSUAS/CONDUZ | Programa Acessuas/Conduz | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 1104** (`sei_naoresponder@sp.gov.br`).

### ID `110005596` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 962 | MCRUZ-SMAS-DGPCP-EXPEDIENTE | Departamento de Gestão de Prestação de Contas de Parcerias - EXPEDIENTE | prestacaodecontas.semas@mogidascruzes.sp.gov.br |
| 963 | MCRUZ-SMAS-DGPCP-EXPEDIENTE | Departamento de Gestão de Prestação de Contas de Parcerias - EXPEDIENTE | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 963** (`sei_naoresponder@sp.gov.br`).

### ID `110005597` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 964 | MCRUZ-SMAS-DGPCP-PCONT- AUDESP | Departamento de Gestão de Prestação de Contas de Parcerias - AUDESP | sei_naoresponder@sp.gov.br |
| 965 | MCRUZ-SMAS-DGPCP-PCONT- AUDESP | Departamento de Gestão de Prestação de Contas de Parcerias - AUDESP | prestacaodecontas.semas@mogidascruzes.sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 965** (`prestacaodecontas.semas@mogidascruzes.sp.gov.br`).

### ID `110005598` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 966 | MCRUZ-SMAS-DGPCP-PCONT-PAG | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT-PAGAMENTO | prestacaodecontas.semas@mogidascruzes.sp.gov.br |
| 967 | MCRUZ-SMAS-DGPCP-PCONT-PAG | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT-PAGAMENTO | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 967** (`sei_naoresponder@sp.gov.br`).

### ID `110005599` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 968 | MCRUZ-SMAS-DGPCP-PCONT.1 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT.1 | prestacaodecontas.semas@mogidascruzes.sp.gov.br |
| 969 | MCRUZ-SMAS-DGPCP-PCONT.1 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT.1 | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 969** (`sei_naoresponder@sp.gov.br`).

### ID `110005600` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 970 | MCRUZ-SMAS-DGPCP-PCONT.2 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT.2 | sei_naoresponder@sp.gov.br |
| 971 | MCRUZ-SMAS-DGPCP-PCONT.2 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT.2 | prestacaodecontas.semas@mogidascruzes.sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 971** (`prestacaodecontas.semas@mogidascruzes.sp.gov.br`).

### ID `110005601` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 972 | MCRUZ-SMAS-DGPCP-PCONT.3 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT.3 | prestacaodecontas.semas@mogidascruzes.sp.gov.br |
| 973 | MCRUZ-SMAS-DGPCP-PCONT.3 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT.3 | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 973** (`sei_naoresponder@sp.gov.br`).

### ID `110005602` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 974 | MCRUZ-SMAS-DGPCP-PCONT.4 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT.4 | prestacaodecontas.semas@mogidascruzes.sp.gov.br |
| 975 | MCRUZ-SMAS-DGPCP-PCONT.4 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT.4 | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 975** (`sei_naoresponder@sp.gov.br`).

### ID `110005603` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 976 | MCRUZ-SMAS-DGPCP-PCONT-ESTÁG.1 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT-ESTÁG.1 | prestacaodecontas.semas@mogidascruzes.sp.gov.br |
| 977 | MCRUZ-SMAS-DGPCP-PCONT-ESTÁG.1 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT-ESTÁG.1 | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 977** (`sei_naoresponder@sp.gov.br`).

### ID `110005604` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 978 | MCRUZ-SMAS-DGPCP-PCONT-ESTÁG.2 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT-ESTÁG.2 | prestacaodecontas.semas@mogidascruzes.sp.gov.br |
| 979 | MCRUZ-SMAS-DGPCP-PCONT-ESTÁG.2 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT-ESTÁG.2 | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 979** (`sei_naoresponder@sp.gov.br`).

### ID `110005605` — 2 ocorrências

**Atenção:** sigla, nome ou e-mail divergem entre linhas.

| Linha | Sigla | Unidade | E-mail |
|-------|-------|---------|--------|
| 980 | MCRUZ-SMAS-DGPCP-PCONT-ESTÁG.3 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT-ESTÁG.3 | prestacaodecontas.semas@mogidascruzes.sp.gov.br |
| 981 | MCRUZ-SMAS-DGPCP-PCONT-ESTÁG.3 | Departamento de Gestão de Prestação de Contas de Parcerias - PCONT-ESTÁG.3 | sei_naoresponder@sp.gov.br |

E-mails distintos: 2 — na importação prevalece a **linha 981** (`sei_naoresponder@sp.gov.br`).

