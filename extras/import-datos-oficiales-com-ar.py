import requests
import os
import json
import csv 

ubicaciones_file = 'ubicaciones.json'

if not os.path.exists(ubicaciones_file):
    ubicaciones = 'https://datosoficiales.com.ar/metadata/ubicaciones.json'
    req = requests.get(ubicaciones)
    raw_data = req.text
    json_data = json.loads(raw_data)
    nice_json_data = json.dumps(json_data, indent=4, sort_keys=True)
    f = open(ubicaciones_file, 'w')
    f.write(nice_json_data)
    f.close()

# Mesa 3918 (Mendiolaza por ejemplo tiene estas URLs)
# https://datosoficiales.com.ar/resultados/CO/3/5040A/1/3918/GOB.json
# en ubicaciones es:
"""
    {
        "ancestros": [
            "CO",
            "CO.3",
            "CO.3.5040A",
            "CO.3.5040A.1",
            "CO.3.5040A.1.3918"
        ],
        "clase_ubicacion": "Mesa",
        "descripcion_ubicacion": "3918",
        "id_ubicacion": "CO.3.5040A.1.3918"
    },
"""

f = open(ubicaciones_file, 'r')
json_data = json.load(f)
f.close()

c = 0

file_csv = open('gobernador-cordoba-2019-provisorio-por-mesas.csv', 'w')
fieldnames = None

for data in json_data:
    c += 1
    if data['clase_ubicacion'] == 'Mesa':
        mesa = {}
        mesa_nro = data['descripcion_ubicacion']
        mesa['mesa'] = mesa_nro
         
        ubicaciones = data["id_ubicacion"].split('.')
        url_gobernador = 'https://datosoficiales.com.ar/resultados/{}/{}/{}/{}/{}/GOB.json'.format(ubicaciones[0], ubicaciones[1], ubicaciones[2], ubicaciones[3], ubicaciones[4])
        print('MESA: {} => {}'.format(mesa_nro, url_gobernador))
        mesa['url_gob'] = url_gobernador

        """ Ejemplo de una mesa
            {"clase_ubicacion": "Mesa",
                "cant_votos_positivos": 249,
                "resultados": [
                    {"clase_candidatura": "Lista",  "id_candidatura": "102", "descripcion_candidatura": "Partido Uni\u00f3n Ciudadana", "cant_votos": 0},
                    {"clase_candidatura": "Lista", "id_candidatura": "104", "descripcion_candidatura": "Vecinalismo Independiente", "cant_votos": 0}, 
                    {"clase_candidatura": "Lista", "id_candidatura": "1539", "descripcion_candidatura": "Movimiento Avanzada Socialista", "cant_votos": 0},
                    {"clase_candidatura": "Lista", "id_candidatura": "1547", "descripcion_candidatura": "MST - Nueva Izquierda", "cant_votos": 0},
                    {"clase_candidatura": "Lista", "id_candidatura": "1548", "descripcion_candidatura": "C\u00f3rdoba Cambia", "cant_votos": 23},
                    {"clase_candidatura": "Lista", "id_candidatura": "1549", "descripcion_candidatura": "Frente de Izquierda y de los Trabajadores", "cant_votos": 1},
                    {"clase_candidatura": "Lista", "id_candidatura": "1550", "descripcion_candidatura": "Hacemos por C\u00f3rdoba", "cant_votos": 146},
                    {"clase_candidatura": "Lista", "id_candidatura": "20", "descripcion_candidatura": "Partido Humanista", "cant_votos": 1},
                    {"clase_candidatura": "Lista", "id_candidatura": "30", "descripcion_candidatura": "Uni\u00f3n C\u00edvica Radical", "cant_votos": 63},
                    {"clase_candidatura": "Lista", "id_candidatura": "31", "descripcion_candidatura": "Uni\u00f3n del Centro Democr\u00e1tico (U.CE.DE.)", "cant_votos": 0},
                    {"clase_candidatura": "Lista", "id_candidatura": "524", "descripcion_candidatura": "Encuentro Vecinal C\u00f3rdoba", "cant_votos": 3},
                    {"clase_candidatura": "Lista", "id_candidatura": "8", "descripcion_candidatura": "Movimiento de Acci\u00f3n Vecinal", "cant_votos": 0}, 
                    {"clase_candidatura": "Blanco", "id_candidatura": "BLC", "descripcion_candidatura": "Voto en BLANCO", "cant_votos": 12},
                    {"clase_candidatura": "Especial", "id_candidatura": "IMP", "descripcion_candidatura": "Votos IMPUGNADOS", "cant_votos": 0},
                    {"clase_candidatura": "Especial", "id_candidatura": "NUL", "descripcion_candidatura": "Votos NULOS", "cant_votos": 1},
                    {"clase_candidatura": "Especial", "id_candidatura": "REC", "descripcion_candidatura": "Votos RECURRIDOS", "cant_votos": 0}
                ],
                "cant_votantes": 250,
                "porcentaje_participacion": 78.6163,
                "cant_votos_negativos": 1,
                "descripcion_ubicacion": "4902",
                "hora_proceso": "2019-05-12 22:35:01",
                "cant_mesas_procesadas": 1,
                "porcentaje_mesas_procesadas": 100.0,
                "id_ubicacion": "CO.9.8.2.4902",
                "cargo": "GOB",
                "id_publicacion": 48}
        """
        req = requests.get(url_gobernador)
        raw_data = req.text
        try:
            json_data = json.loads(raw_data)
        except Exception as e:
            print('ERROR EN LA MESA {} => {}'.format(mesa_nro, url_gobernador))
            continue

        for k, v in json_data.items():
            if type(v) == list:  # achatar
                for val in v:
                    mesa[val['descripcion_candidatura']] = val['cant_votos']
            else:
                mesa[k] = v

        if fieldnames is None:
            fieldnames = mesa.keys()
            writer = csv.DictWriter(file_csv, fieldnames=fieldnames)
            writer.writeheader()
        
        writer.writerow(mesa)

writer.close()