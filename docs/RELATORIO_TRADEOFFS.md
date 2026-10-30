# Relatório de trade-offs — ETL Distribuidora Vetor

## Problema
47 clientes com 25 grafias diferentes de bairro (mais 1 registro sem bairro), 4 formatos de telefone,
4 formatos de data, CNPJ com e sem máscara e 34% dos CEPs ausentes ou zerados. Sem tratamento, um
relatório por bairro mostra 25 linhas onde existem 4 bairros.

## O que foi automatizado — e por quê
| Decisão | Motivo |
|---|---|
| Normalização textual determinística (caixa, acento, `DF`, parênteses) | Resolve a maior parte das variantes sem custo nem risco; é reprodutível e testável |
| Dicionário variante → bairro canônico em arquivo CSV | Regra explícita e auditável; quem conhece o negócio amplia sem editar código |
| Padronização de CNPJ, telefone (E.164) e datas | Transformações sem ambiguidade; cada uma gera linha de auditoria |
| Consulta de CEP (ViaCEP → BrasilAPI) com cache | Única fonte externa de verdade geográfica; o cache evita repetir chamadas e torna reexecuções rápidas e estáveis |
| Divergência CEP × bairro: a API prevalece, com flag | Fonte estruturada vence texto livre, mas a decisão fica visível e reversível |

## O que ficou para tratamento manual — e por quê
| Item | Motivo |
|---|---|
| Bairros fora do dicionário e correspondências *fuzzy* | Aproximar texto automaticamente pode juntar bairros diferentes; um erro silencioso contamina o relatório |
| Bairro da API que não existe no dicionário | Pode ser variante nova legítima ou erro da API; só quem conhece a região decide |
| CEPs de outra UF | Indício de erro de cadastro, não de grafia |
| Datas ambíguas (`dd/mm` × `mm/dd`) | Sem segunda fonte não há como confirmar; fica a premissa `dd/mm` + flag `data_ambigua` |
| CNPJ com dígito verificador inválido | Descartar apagaria a base inteira; ficou como sinalização, e a decisão cabe ao negócio |

## Trade-offs principais
1. **Precisão × cobertura.** Preferimos deixar um bairro nulo com revisão a "chutar". O custo é
   trabalho manual residual; o ganho é que nenhum número do relatório depende de adivinhação.
2. **Dependência externa × autonomia.** A API melhora a qualidade, mas pode falhar ou devolver nomes
   fora do padrão. Mitigação: fallback entre dois provedores, cache, falhas nunca cacheadas, e o
   pipeline funciona sem API (`--sem-api`) usando só o dicionário.
3. **Bairro-pai × subdivisão.** Agrupar em "Águas Claras" perde o recorte Sul/Norte; guardá-lo em
   coluna própria permite as duas visões, ao custo de uma coluna a mais.
4. **Rigor × utilidade (CNPJ).** Validar e rejeitar seria o correto em produção, mas aqui geraria
   tabela vazia. Optamos por marcar e documentar o limite.
5. **Recarga completa × incremental.** Simples e idempotente para o volume do desafio, mas não escala
   como está.

## Resultado (execução offline sobre o CSV fornecido)
25 grafias de bairro → **4 bairros** canônicos (Águas Claras, Taguatinga, Vicente Pires, Guará);
1 cliente sem bairro (CLI0047, sem CEP também); 191 linhas de auditoria; 6 datas ambíguas; 10 e-mails
fora do padrão ASCII sinalizados. Os números com a API (divergências CEP × bairro, revisões manuais)
dependem das respostas reais de ViaCEP/BrasilAPI e saem no resumo da primeira execução com rede.

## Próximos passos
Rodar com a API no ambiente do desafio, revisar a fila `revisao_manual = true`, ampliar o dicionário
e reexecutar (o cache evita novas chamadas). Em produção: quarentena para CNPJ inválido e carga incremental.
