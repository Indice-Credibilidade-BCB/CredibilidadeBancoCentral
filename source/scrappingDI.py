# %% Importando dados

import pandas as pd
import requests
from typing import Iterable

# %% Funções Principais
VERTICES = {
    30:   7806,
    60:   7807,
    90:   7808,
    120:  7809,
    180:  7811,
    360:  7817,
    720:  7810,
    1080: 7818,
    1800: 7819,
    }

urlBase = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados'

def baixarVertice(code: int, d0: str, d1: str) -> pd.Series:
    url = urlBase.format(code=code)
    r = requests.get(
        url,
        params = {'formato': 'json', 'dataInicial': d0, 'dataFinal': d1},
        timeout = 60,
        )
    r.raise_for_status()
    dataframe = pd.DataFrame(r.json())
    if dataframe.empty:
        return pd.Series(dtype=float)
    dataframe['data'] = pd.to_datetime(dataframe['data'], dayfirst=True)
    dataframe['valor'] = dataframe['valor'].astype(float)
    return dataframe.set_index('data')['valor']

def verticesJuncao(dataInicial: str,
             dataFinal: str,
             vertices: Iterable[int] = VERTICES.keys()) -> pd.DataFrame:
    out = {}
    
    for du in vertices:
        code = VERTICES[du]
        try:
            s = baixarVertice(code, dataInicial, dataFinal)
            
            if s.empty:
                print('Sem dados para esse DU ou vértice')
                
            else:
                out[f'DU_{du}'] = s
        except Exception as e:
            print(f"Erro vértice {du} - código: {e}")
    if not out:
        return pd.DataFrame()
    dataframe = pd.concat(out, axis=1).sort_index()
    dataframe.index_name = 'data'
    
    return dataframe

# %% Função e exportação

swapDI = verticesJuncao("01/01/2017", "01/01/2026")
print(f'Tamanho do dataframe: {swapDI.shape}')
print('Exemplo do dataframe')
display(swapDI.head())
print('Exportando Dataframe...')
swapDI.to_csv('SwapDI.csv')
print('Dataframe exportado')
