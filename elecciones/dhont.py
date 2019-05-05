# calcular dhont

def calcular_dhont(bancas=10, valores=[]):
    ''' Calcula vía D'Hont las "n" bancas segun una lista de calores
    Parameters:
        bancas (int): Cantidad de bancas a elegir
        valores (list of dicts): Lista de diccionarios con el nombre del partido y sus votos. Ej {'nombre': 'Partido 1', 'valor': 1500}
    
    Returns:
        tupla (resultado_detalles, resultado_final)
            resultado_detalles: una lista de diccionarios con cada una de las bancas
            resultado_final: diccionario con el partido como key y la cantidad de bancas como valor
    '''

    total_votos = 0
    coeficientes = []
    for elemento in valores:
        valor = elemento['valor']
        total_votos += valor
        for coef in range(bancas):
            coef_valor = valor / (coef + 1)
            dict_coef = {'nombre': elemento['nombre'], 'coeficiente': coef_valor}
            coeficientes.append(dict_coef)
    
    # ordernar los coeficientezs y devolver las bancas en la cantidad elegida
    coeficientes_ordenados = sorted(coeficientes, key=lambda k: k['coeficiente'], reverse=True) 

    # calcular totales
    resultado_detalles = coeficientes_ordenados[:bancas]
    resultado_final = {}
    for coef in resultado_detalles:
        partido = coef['nombre']
        if partido not in resultado_final.keys():
            resultado_final[partido] = 0
        resultado_final[partido] += 1

    return resultado_detalles, resultado_final


""" PRUEBA
valores_de_prueba = [
        {'nombre': 'Partido 1', 'valor': 1500},
        {'nombre': 'Partido 2', 'valor': 2500},
        {'nombre': 'Partido 3', 'valor': 3500},
        {'nombre': 'Partido 4', 'valor': 500},
        {'nombre': 'Partido 5', 'valor': 800},
        {'nombre': 'Partido 6', 'valor': 400},
        {'nombre': 'Partido 7', 'valor': 100},
        {'nombre': 'Partido 8', 'valor': 50},
        ]

res, final = calcular_dhont(bancas=10, valores=valores_de_prueba)
c = 1
for r in res:
    nombre = r['nombre']
    coef = round(r['coeficiente'], 2)
    print(f'Banca {c}: Partido: {nombre} Coeficiente: {coef}')
    c += 1

print('################')
print(final)
"""

""" RESPUESTA:
Banca 1: Partido: Partido 3 Coeficiente: 3500.0
Banca 2: Partido: Partido 2 Coeficiente: 2500.0
Banca 3: Partido: Partido 3 Coeficiente: 1750.0
Banca 4: Partido: Partido 1 Coeficiente: 1500.0
Banca 5: Partido: Partido 2 Coeficiente: 1250.0
Banca 6: Partido: Partido 3 Coeficiente: 1166.67
Banca 7: Partido: Partido 3 Coeficiente: 875.0
Banca 8: Partido: Partido 2 Coeficiente: 833.33
Banca 9: Partido: Partido 5 Coeficiente: 800.0
Banca 10: Partido: Partido 1 Coeficiente: 750.0
################
{'Partido 3': 4, 'Partido 2': 3, 'Partido 1': 2, 'Partido 5': 1}
"""