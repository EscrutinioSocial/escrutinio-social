files_dir = '../../../scraper_data/doc/'
test_dir = files_dir + 'test/'
regiones_file = 'regions.json'
request_url = 'https://resultados.gob.ar/'
escuelas_url = "https://resultados.gob.ar/assets/data/precincts/"
authorization_header = 'Bearer 31d15a'
escuela_file = files_dir + 'escuelas/' + 'escuela.json' 
mesa_file = files_dir + 'mesas/' + '8741.json' 
mesa_out_test = test_dir + 'test_mesa_prueba.txt'

import json 
#FIXME TODO: Voy por aca
arch = f"{files_dir}{regiones_file}"

###############################
# Json escuelas 
###############################
def cargar_escuela_prueba():
    with open(escuela_file) as escuela_prueba:
        return json.load(escuela_prueba)

def probar_carga_escuelas():
    escuelas_bajadas = cargar_escuela_prueba()
    resultado_escuelas = '[{"c": 8741, "cc": "0101406691X", "n": "0101406691X", "tp": "P", "ll": true, "rf": "precincts/8/8741", "cs": []}]' 
    assert(json.dumps(escuelas_bajadas) == resultado_escuelas)

###############################
# Circuitos
###############################

def probar_circuitos():
    circuitos = []
    with open(arch) as json_file:
        print(json_file)
        valores = json.load(json_file)
        for value in valores:
            print(f"Valor: {value}")
            circuito = {}
            if(value['tp'] == 'R' and value['l'] == 4):
                circuito['distrito'] = value['cc'][:2]
                circuito['seccion'] = value['cc'][2:3]
                circuito['circuito'] = value['cc'][5:6]
                circuito['nombreCircuito'] = value['n']
                circuito['escuelas'] = value['chd']
                print(f"Circuito a agregar: {circuito}")
                circuitos.append(circuito)
#######################################
# URL Escuelas
#######################################
        # https://resultados.gob.ar/assets/data/precincts/14/s14002.json
        #https://resultados.gob.ar/assets/data/precincts/14/s14010.json
        #https://resultados.gob.ar/assets/data/precincts/7/s7455.json
        #url = f"https://resultados.gob.ar/assets/data/precincts/{id}/s{idEscuela}.json";
def probar_url_escuelas():
    id_escuela = 14010 
    id = id_escuela if (id_escuela < 1000) else id_escuela // 1000
    assert(id==14)
    # print(f"id:{id}")


#######################################
# Json mesas 
#######################################
def cargar_mesa_prueba():
    with open(mesa_file) as mesa_prueba:
        return json.load(mesa_prueba)

def cargar_mesas():
    escuelas_bajadas = {}
    escuelas_bajadas[8741] = cargar_escuela_prueba()
    mesas = []
    for id_escuela, valor1 in escuelas_bajadas.items():
        for valor_mesa in valor1:
            distrito = str(valor_mesa['cc'][:2])
            seccion = str(valor_mesa['cc'][2:5])
            nro_mesa = str(valor_mesa['cc'][5:10])
            if(True):
                mesa = {}
                mesa['id'] = valor_mesa['c']
                mesa['distrito'] = distrito
                mesa['seccion'] = seccion
                mesa['nro_mesa'] = nro_mesa
                mesa['url'] = valor_mesa['rf']
                #datos = self.descargar_json_mesa(mesa['url'])
                datos = cargar_mesa_prueba()
                mesa['votos'] = datos['rp']
                '''
                - cc son los cargos.
                - pc es el partido
                - v votos
                - tot: totales
                '''
                mesas.append(mesa)
    f = open(mesa_out_test, 'r+')
    mesas_str = f.read().rstrip('\n')
    #print(mesas_str)
    #print(json.dumps(mesas))
    assert(json.dumps(mesas) == mesas_str)



#probar_carga_escuelas()
#probar_url_escuelas()
cargar_mesas()
