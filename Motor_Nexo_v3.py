import pandas as pd
import collections

def motor_fiscal_nexo_v5(file_path):
    # Carregamento e ordenação cronológica rigorosa
    df = pd.read_csv(file_path)
    df['Date / Time (UTC)'] = pd.to_datetime(df['Date / Time (UTC)'])
    df = df.sort_values('Date / Time (UTC)')

    inventory = collections.defaultdict(list)
    report_irs = []    
    report_swaps = []  
    report_transfers = [] 
    
    # Moedas que disparam o Anexo G (Saída do ecossistema cripto)
    fiat_real = ['EUR', 'USD', 'GBP']

    for _, row in df.iterrows():
        tipo = row['Type']
        dt_full = row['Date / Time (UTC)']
        m_in = str(row['Input Currency']) if pd.notna(row['Input Currency']) else ''
        m_out = str(row['Output Currency']) if pd.notna(row['Output Currency']) else ''
        q_in = abs(float(row['Input Amount'])) if pd.notna(row['Input Amount']) else 0
        q_out = abs(float(row['Output Amount'])) if pd.notna(row['Output Amount']) else 0
        usd_val = float(str(row['USD Equivalent']).replace('$', '').replace(',', '')) if pd.notna(row['USD Equivalent']) else 0

        # --- 1. ENTRADAS EXTERNAS (Matching) ---
        if tipo == 'Top up Crypto':
            inventory[m_out].append({
                'date': dt_full, 'qty': q_out, 'cost_basis': usd_val, 'source': 'EXTERNAL'
            })
            report_transfers.append({
                'Data': dt_full.strftime('%Y-%m-%d'),
                'Hora': dt_full.strftime('%H:%M:%S'),
                'Moeda': m_out, 'Quantidade': q_out, 'Tipo': 'Entrada_Externa'
            })
            continue

        # --- 2. RENDIMENTOS (Interest, Dividends, etc) ---
        if tipo in ['Interest', 'Fixed Term Interest', 'Dividend', 'Exchange Cashback', 'Exchange Deposited On']:
            inventory[m_out].append({
                'date': dt_full, 'qty': q_out, 'cost_basis': usd_val, 'source': 'INTERNAL'
            })
            continue

        # --- 3. OPERAÇÕES NEUTRAS ---
        if tipo in ['Locking Term Deposit', 'Unlocking Term Deposit', 'Deposit To Exchange', 'Withdraw Exchanged']:
            continue

        # --- 4. SAÍDAS E PERMUTAS (FIFO) ---
        if tipo in ['Exchange', 'Exchange To Withdraw', 'Withdrawal'] and m_in and q_in > 0:
            remaining = q_in
            total_cost = 0
            first_acq_date = None
            origem_externa = False
            
            while remaining > 0 and inventory[m_in]:
                lote = inventory[m_in][0]
                if first_acq_date is None: 
                    first_acq_date = lote['date']
                    origem_externa = (lote['source'] == 'EXTERNAL')
                
                if lote['qty'] <= remaining:
                    total_cost += lote['cost_basis']
                    remaining -= lote['qty']
                    inventory[m_in].pop(0)
                else:
                    ratio = remaining / lote['qty']
                    total_cost += lote['cost_basis'] * ratio
                    lote['cost_basis'] -= lote['cost_basis'] * ratio
                    lote['qty'] -= remaining
                    remaining = 0

            # --- DECISÃO FISCAL ---
            # Tributável se for Exchange To Withdraw ou Venda direta para Fiat
            is_taxable = (tipo == 'Exchange To Withdraw') or (tipo == 'Exchange' and m_out in fiat_real)

            if is_taxable:
                # Se for EUR/EURX usamos a quantidade real, senão o USD Equivalent
                valor_venda = q_out if m_out in ['EUR', 'EURX'] else usd_val
                
                if origem_externa:
                    status_365 = "TBD"
                else:
                    dias = (dt_full - first_acq_date).days
                    status_365 = f"{dias} dias"

                report_irs.append({
                    'Data_Venda': dt_full.strftime('%Y-%m-%d %H:%M:%S'),
                    'Ativo': m_in,
                    'Moeda_Venda': m_out if m_out else 'USD',
                    'Valor_Venda': valor_venda,
                    'Data_Aquisicao': first_acq_date.strftime('%Y-%m-%d %H:%M:%S') if first_acq_date else 'N/A',
                    'Custo_Aquisicao_USD': total_cost,
                    'Origem_Externa': "Sim" if origem_externa else "Não",
                    'Resultado': valor_venda - total_cost,
                    'Isento_365d': status_365
                })

            elif tipo == 'Exchange' and m_out not in fiat_real:
                # Permuta: Herança de custo e data
                inventory[m_out].append({
                    'date': first_acq_date if first_acq_date else dt_full,
                    'qty': q_out, 'cost_basis': total_cost, 
                    'source': 'EXTERNAL' if origem_externa else 'INTERNAL'
                })
                report_swaps.append({
                    'Data': dt_full.strftime('%Y-%m-%d %H:%M:%S'), 
                    'Saiu': m_in, 'Entrou': m_out, 'Custo_Herdado': total_cost
                })
            
            elif tipo == 'Withdrawal':
                # Registro para matching na exchange de destino
                report_transfers.append({
                    'Data': dt_full.strftime('%Y-%m-%d'),
                    'Hora': dt_full.strftime('%H:%M:%S'),
                    'Moeda': m_in, 'Quantidade': q_in, 'Tipo': 'Saida_Externa'
                })

    return pd.DataFrame(report_irs), pd.DataFrame(report_swaps), pd.DataFrame(report_transfers)

# Execução
vendas, swaps, transf = motor_fiscal_nexo_v5('nexo_transactions.csv')

# Salvar com as especificações solicitadas
vendas.to_csv('1_Anexo_G_Nexo_Final.csv', index=False, sep=';', decimal=',')
swaps.to_csv('2_Historico_Swaps_Final.csv', index=False, sep=';', decimal=',')
transf.to_csv('3_Log_Reconciliacao.csv', index=False, sep=';', decimal=',')
