import pandas as pd
import collections

def motor_fiscal_nexo_v3(file_path):
    df = pd.read_csv(file_path)
    df['Date / Time (UTC)'] = pd.to_datetime(df['Date / Time (UTC)'])
    df = df.sort_values('Date / Time (UTC)')

    inventory = collections.defaultdict(list)
    report_irs = []    # Anexo G
    report_swaps = []  # Memória de cálculo de permutas
    report_transfers = [] # Log para Matching (Transferências Externas)
    
    fiat_equivalents = ['EUR', 'EURX', 'USD', 'GBP']

    for _, row in df.iterrows():
        tipo = row['Type']
        data = row['Date / Time (UTC)']
        m_in, q_in = row['Input Currency'], abs(float(row['Input Amount'])) if pd.notna(row['Input Amount']) else 0
        m_out, q_out = row['Output Currency'], abs(float(row['Output Amount'])) if pd.notna(row['Output Amount']) else 0
        usd_val = float(str(row['USD Equivalent']).replace('$', '').replace(',', '')) if pd.notna(row['USD Equivalent']) else 0

        # --- 1. ENTRADAS EXTERNAS (Necessitam de Matching Posterior) ---
        if tipo == 'Top up Crypto':
            inventory[m_out].append({
                'date': data, 
                'qty': q_out, 
                'cost_basis': usd_val,
                'source': 'EXTERNAL_TRANSFER' # Tag para rastreio
            })
            report_transfers.append({
                'Data': data, 'Moeda': m_out, 'Quantidade': q_out, 
                'Valor_USD_Nexo': usd_val, 'Tipo': 'Entrada_Externa',
                'Status_Matching': 'PENDENTE' # Para saberes que precisas validar o custo original
            })
            continue

        # --- 2. RENDIMENTOS (Categoria E - Custo USD da Nexo) ---
        if tipo in ['Interest', 'Fixed Term Interest', 'Dividend', 'Exchange Cashback', 'Exchange Deposited On']:
            inventory[m_out].append({
                'date': data, 'qty': q_out, 'cost_basis': usd_val, 'source': 'NEXO_EARN'
            })
            continue

        # --- 3. OPERAÇÕES NEUTRAS ---
        if tipo in ['Locking Term Deposit', 'Unlocking Term Deposit', 'Deposit To Exchange', 'Withdraw Exchanged']:
            continue

        # --- 4. SAÍDAS (FIFO) ---
        if tipo in ['Exchange', 'Exchange To Withdraw', 'Withdrawal']:
            remaining = q_in
            total_cost = 0
            first_acq_date = None
            is_external_source = False # Rastreia se estamos a vender algo que veio de fora
            
            while remaining > 0 and inventory[m_in]:
                lote = inventory[m_in][0]
                if first_acq_date is None: 
                    first_acq_date = lote['date']
                    if lote.get('source') == 'EXTERNAL_TRANSFER':
                        is_external_source = True
                
                if lote['qty'] <= remaining:
                    total_cost += lote['cost_basis']
                    remaining -= lote['qty']
                    inventory[m_in].pop(0)
                else:
                    ratio = remaining / lote['qty']
                    cost_part = lote['cost_basis'] * ratio
                    total_cost += cost_part
                    lote['cost_basis'] -= cost_part
                    lote['qty'] -= remaining
                    remaining = 0

            # A. Venda para Fiat (Tributável)
            if tipo == 'Exchange To Withdraw' or (tipo == 'Exchange' and m_out in fiat_equivalents):
                valor_venda = q_out if 'EUR' in m_out else usd_val
                report_irs.append({
                    'Ativo': m_in,
                    'Data_Venda': data,
                    'Data_Aquisicao': first_acq_date,
                    'Valor_Venda': valor_venda,
                    'Custo_Aquisicao': total_cost,
                    'Plus_Valia': valor_venda - total_cost,
                    'Origem_Externa': is_external_source, # Indica se o custo base pode precisar de ajuste
                    'Isento_365d': (data - first_acq_date).days > 365 if first_acq_date else False
                })

            # B. Permuta (Isenta)
            elif tipo == 'Exchange' and m_out not in fiat_equivalents:
                inventory[m_out].append({
                    'date': first_acq_date if first_acq_date else data,
                    'qty': q_out,
                    'cost_basis': total_cost,
                    'source': 'EXTERNAL_TRANSFER' if is_external_source else 'INTERNAL_SWAP'
                })
                report_swaps.append({
                    'Data': data, 'Saiu': m_in, 'Entrou': m_out, 
                    'Custo_Herdado': total_cost, 'Origem_Acquisição': first_acq_date
                })
            
            # C. Saída para outra carteira (Withdrawal)
            elif tipo == 'Withdrawal':
                report_transfers.append({
                    'Data': data, 'Moeda': m_in, 'Quantidade': q_in, 
                    'Custo_Acumulado': total_cost, 'Tipo': 'Saida_Externa'
                })

    return pd.DataFrame(report_irs), pd.DataFrame(report_swaps), pd.DataFrame(report_transfers)

# Gerar ficheiros
vendas_df, swaps_df, trans_df = motor_fiscal_nexo_v3('nexo_transactions.csv')
vendas_df.to_csv('1_Anexo_G_Nexo.csv', index=False, sep=';', decimal=',')
swaps_df.to_csv('2_Historico_Swaps.csv', index=False, sep=';', decimal=',')
trans_df.to_csv('3_Log_Transferencias_Matching.csv', index=False, sep=';', decimal=',')
