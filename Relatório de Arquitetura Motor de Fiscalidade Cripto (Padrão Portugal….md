# Relatório de Arquitetura: Motor de Fiscalidade Cripto (Padrão Portugal)  
# 1. Contexto Legal (CIRS Portugal)  
O motor deve respeitar as regras do IRS português para criptoativos (em vigor desde 2023, com retroatividade de conceitos de custo):  
* **Artigo 43º, nº 7 do CIRS (Segregação por Entidade):** O método FIFO não é global. Deve ser aplicado de forma isolada por cada exchange/instituição. O que acontece na Nexo é um silo independente da Binance.  
* **Isenção de Mais-Valias (Hold > 365 dias):** O motor deve rastrear a data de aquisição original. Vendas de ativos detidos por mais de um ano são isentas, mas devem ser reportadas.  
* **Permutas Isentas (Crypto-to-Crypto):** Trocas entre criptoativos (incluindo Stablecoins como USDT, USDC, TUSD) não geram apuramento de imposto. O custo e a data de aquisição do ativo vendido são transferidos para o ativo comprado (**Roll-over de base de custo**).  
* **Eventos Tributáveis:** Apenas a conversão de criptoativos para moeda fiduciária (EUR, BRL, USD) ou a utilização de cripto para pagamento de bens/serviços gera a obrigação de calcular a mais-valia.  
# 2. Conceitos Lógicos do Motor (Backend)  
## A. Lógica de Sinais (Agnóstica a Nomes de Operação)  
Para evitar falhas por mudanças de nomenclatura das exchanges (ex: "Buy" vs "Transaction Spend"), o motor deve basear-se no campo Change:  
* **Change Negativo (-):** Saída de inventário (Venda ou Swap).  
* **Change Positivo (+):** Entrada de inventário (Compra, Depósito ou Recebimento de Swap).  
* **Agrupamento por Timestamp:** Operações que ocorrem no mesmo segundo (ou janela de 2-5 segundos) devem ser tratadas como uma única transação composta.  
## B. Gestão de Inventário FIFO Desmembrado  
* **Estrutura de Lote:** Cada entrada no inventário deve ser um objeto: {quantidade, custo_total, data_aquisicao, exchange_origem}.  
* **Desmembramento de Venda:** Se uma venda consome múltiplos lotes de aquisição, o motor **deve gerar uma linha de relatório para cada lote**.  
    * *Exemplo:* Venda de 1 BTC que consome 0.5 BTC de Jan/2020 e 0.5 BTC de Mar/2021 = 2 linhas no CSV final.  
* **Rateio Proporcional:** O valor recebido na venda (ex: Euros) deve ser distribuído proporcionalmente ao tamanho de cada lote consumido.  
## C. Herança de Custo (Reconciliação de Carteiras)  
* **Transferências Externas (Match):** O motor deve identificar Withdrawals de uma carteira e Deposits noutra. Se o valor e a moeda coincidirem, o motor não assume "custo zero", mas sim herda o histórico da carteira de origem.  
# 3. Estrutura de Dados Requerida (Input Nexo)  
Para a Nexo, o motor precisará de processar:  
1. **Interest/Bonus:** Entradas com custo zero (rendimentos).  
2. **Exchange/Swap:** Trocas internas.  
3. **Transferências:** Depósitos e levantamentos.  
4. **Nexo Card:** Se aplicável, tratar cada compra com cartão como uma "Venda para Fiat" (Evento tributável).  
# 4. Outputs Esperados (Relatórios)  
O motor deve gerar três ficheiros distintos para total transparência:  
1. **Relatório IRS:** Apenas eventos tributáveis (Vendas para EUR), desmembrados linha a linha por lote, prontos para o Anexo G/J.  
2. **Relatório de Swaps:** Histórico de todas as permutas cripto-cripto, provando a origem do custo atual.  
3. **Relatório de Reconciliação:** Log de depósitos e levantamentos para validar a posse dos ativos entre exchanges.  
  
## 📑 Guia de Transposição de Contexto (Motor Nexo)  
**1. O Core da Lógica (Sinais e Timestamps)**  
* **Regra de Ouro:** Não confiar em nomes de operações (ex: "Exchange", "Interest"). Confiar no campo Amount (ou Change).  
* **Agrupamento:** Operações com o mesmo timestamp exato ou diferença de até 2 segundos fazem parte da mesma transação (Swap ou Venda).  
* **Identificação de Venda:** Se houver uma saída de Cripto e uma entrada de **EUR, GBP ou USD**, é um evento tributável. Tudo o resto é **Permuta**.  
**2. Tratamento de Ativos Específicos da Nexo**  
* **Nexo Interest/Bonus:** Deve ser tratado como entrada com **Custo Zero**. A data de aquisição é a data em que o juro caiu na conta.  
* **Nexo Card:** Cada transação com o cartão é uma "Venda para Fiat". O motor deve procurar o ativo que foi gasto (ex: BTC ou USDT) e calcular a mais-valia face ao preço do Euro no momento da compra.  
* **Nexo Token:** Se receberes dividendos ou cashback em NEXO, o custo de aquisição é zero.  
**3. Requisitos de Saída (Ficheiros)**  
Deves pedir à IA que gere a mesma estrutura tripartida:  
1. **G_Plus_Valias:** Formato Anexo G (Data Aquisição, Valor Aquisição, Data Venda, Valor Venda).  
2. **Swaps_History:** Prova de continuidade de custo para auditoria.  
3. **Transfers_Log:** Depósitos e Levantamentos para reconciliação entre Nexo, Binance e carteiras frias.  
**4. O "Pulo do Gato" (A Herança de Custo)**  
Explica à IA que o inventário da Nexo deve ser capaz de receber um ficheiro externo (como o de reconciliação que criámos para a Binance) para que, quando depositares algo na Nexo vindo da Binance, o motor não assuma custo zero, mas sim o **custo histórico vindo da exchange anterior**.  
Explica à IA que o inventário da Nexo deve ser capaz de receber um ficheiro externo (como o de reconciliação que criámos para a Binance) para que, quando depositares algo na Nexo vindo da Binance, o motor não assuma custo zero, mas sim o **custo histórico vindo da exchange anterior**.  
