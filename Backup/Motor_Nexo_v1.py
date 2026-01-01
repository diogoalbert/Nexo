import pandas as pd
import collections

def motor_fiscal_nexo(input_path):
    # 1. Carregamento e Limpeza (Lógica de Sinais)
    df = pd.read_csv(input_path)
    df['Date / Time (UTC)'] = pd.to_datetime(df['Date / Time (UTC)'])
    df = df.sort_values('Date / Time (UTC)')

    # Inventário segregado (Art. 43º)
    inventory = collections.defaultdict(list) 
    
    report_irs = []   # Vendas para Fiat (Anexo G)
    report_swaps = [] # Permutas (Herança de Custo)

    # Definição de Moedas Fiduciárias (e equivalentes para apuramento)
    fiat_list = ['EUR', 'USD', 'GBP', 'EURX', 'USDX']

    for _, row in df.iterrows():
        data = row['Date / Time (UTC)']
        tipo = row['Type']
        
        # Identificar Moedas e Quantidades (Sinais Reais)
        m_in, q_in = row['Input Currency'], abs(float(row['Input Amount']))
        m_out, q_out = row['Output Currency'], abs(float(row['Output Amount']))
        valor_usd = float(str(row['USD Equivalent']).replace('$', '').replace(',', ''))

        # A. ENTRADAS (Deposit, Interest, Bonus)
        # Juros e Bonus entram com Custo Zero conforme instrução
        if tipo in ['Interest', 'Deposit', 'Exchange Cashback', 'Top up Crypto', 'Dividend']:
            custo_unitario = 0.0 if tipo in ['Interest', 'Exchange Cashback', 'Dividend'] else valor_usd
            inventory[m_out].append({'date': data, 'qty': q_out, 'cost_total': custo_unitario})
            continue

        # B. SAÍDAS E PERMUTAS (Exchange, Card, Withdrawal)
        if tipo in ['Exchange', 'Card Reflection', 'Withdrawal']:
            # Se for levantamento direto de cripto, apenas removemos do inventário
            if tipo == 'Withdrawal' and m_in not in fiat_list:
                # (Lógica de reconciliação externa pode ser aplicada aqui)
                pass 

            # Processamento FIFO para saídas
            remaining = q_in
            total_cost_basis = 0
            datas_aquisicao = []

            while remaining > 0 and inventory[m_in]:
                lote = inventory[m_in][0]
                if lote['qty'] <= remaining:
                    total_cost_basis += lote['cost_total']
                    remaining -= lote['qty']
                    datas_aquisicao.append(lote['date'])
                    inventory[m_in].pop(0)
                else:
                    ratio = remaining / lote['qty']
                    custo_parcial = lote['cost_total'] * ratio
                    total_cost_basis += custo_parcial
                    lote['cost_total'] -= custo_parcial
                    lote['qty'] -= remaining
                    datas_aquisicao.append(lote['date'])
                    remaining = 0

            # C. CLASSIFICAÇÃO FISCAL
            # Se a saída for para FIAT ou pagamento (Card) = EVENTO TRIBUTÁVEL
            if m_out in fiat_list or tipo == 'Card Reflection':
                report_irs.append({
                    'Data_Venda': data,
                    'Ativo': m_in,
                    'Quantidade': q_in,
                    'Data_Aquisicao': datas_aquisicao[0] if datas_aquisicao else data,
                    'Valor_Venda_USD': valor_usd,
                    'Custo_Aquisicao_USD': total_cost_basis,
                    'Resultado': valor_usd - total_cost_basis,
                    'Hold_Superior_365d': (data - datas_aquisicao[0]).days > 365 if datas_aquisicao else False
                })
            
            # Se for Cripto-Cripto = PERMUTA ISENTA (Herança de Custo)
            elif m_in not in fiat_list and m_out not in fiat_list:
                inventory[m_out].append({
                    'date': datas_aquisicao[0] if datas_aquisicao else data,
                    'qty': q_out,
                    'cost_total': total_cost_basis
                })
                report_swaps.append({
                    'Data': data, 'Saiu': m_in, 'Entrou': m_out, 'Custo_Herdado': total_cost_basis
                })

    return pd.DataFrame(report_irs), pd.DataFrame(report_swaps)

# Gerar Relatórios
vendas_df, swaps_df = motor_fiscal_nexo('nexo_transactions.csv')
vendas_df.to_csv('G_Plus_Valias_Nexo_Final.csv', index=False, decimal=',')