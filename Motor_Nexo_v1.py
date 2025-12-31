import pandas as pd
import collections

def processar_irs_nexo(input_file):
    # Carregar dados
    df = pd.read_csv(input_file)
    df['Date / Time (UTC)'] = pd.to_datetime(df['Date / Time (UTC)'])
    df = df.sort_values('Date / Time (UTC)')

    # Inventário por moeda (FIFO)
    inventory = collections.defaultdict(list)
    
    # Relatórios de saída
    vendas_fiat = []
    permutas = []

    for _, row in df.iterrows():
        tipo = row['Type']
        moeda_in = row['Input Currency']
        qtd_in = abs(float(row['Input Amount']))
        moeda_out = row['Output Currency']
        qtd_out = float(row['Output Amount'])
        data = row['Date / Time (UTC)']
        valor_usd = float(str(row['USD Equivalent']).replace('$', '').replace(',', ''))

        # 1. ENTRADAS (Aquisições / Juros / Cashback)
        # Juros e Cashback entram com custo zero 
        if tipo in ['Interest', 'Exchange Cashback', 'Top up Crypto', 'Deposit']:
            custo = 0.0 if tipo in ['Interest', 'Exchange Cashback'] else valor_usd
            inventory[moeda_out].append({'date': data, 'qty': qtd_out, 'cost': custo})
            continue

        # 2. TROCAS (Exchange)
        if tipo == 'Exchange':
            # É uma Permuta se for Cripto-para-Cripto 
            is_fiat = moeda_out in ['EUR', 'USD', 'EURX'] # EURX tratado como fiduciária para apuramento
            
            # Retirar do inventário (FIFO)
            total_cost_basis = 0
            remaining_to_sell = qtd_in
            
            while remaining_to_sell > 0 and inventory[moeda_in]:
                lote = inventory[moeda_in][0]
                if lote['qty'] <= remaining_to_sell:
                    total_cost_basis += lote['cost']
                    remaining_to_sell -= lote['qty']
                    inventory[moeda_in].pop(0)
                else:
                    # Venda parcial do lote
                    proporcao = remaining_to_sell / lote['qty']
                    total_cost_basis += lote['cost'] * proporcao
                    lote['cost'] -= lote['cost'] * proporcao
                    lote['qty'] -= remaining_to_sell
                    remaining_to_sell = 0

            if is_fiat:
                # Evento Tributável: Venda para Fiat 
                vendas_fiat.append({
                    'Data_Venda': data,
                    'Moeda': moeda_in,
                    'Valor_Venda_USD': valor_usd,
                    'Custo_Aquisicao_USD': total_cost_basis,
                    'Plus_Valia': valor_usd - total_cost_basis
                })
            else:
                # Permuta Isenta: Herança de custo 
                inventory[moeda_out].append({
                    'date': data, 
                    'qty': qtd_out, 
                    'cost': total_cost_basis
                })
                permutas.append({
                    'Data': data, 'Saiu': moeda_in, 'Entrou': moeda_out, 'Custo_Transferido': total_cost_basis
                })

    return pd.DataFrame(vendas_fiat), pd.DataFrame(permutas)

# Execução
vendas, trocas = processar_irs_nexo('nexo_transactions.csv')
vendas.to_csv('G_Plus_Valias_Nexo.csv', index=False)
