import math
import requests
import json
from django.core.management.base import BaseCommand

from elecciones.models import Distrito, Seccion, Circuito, Eleccion, Categoria, Mesa, Partido, MesaCategoria, TIPOS_DE_AGREGACIONES, NIVELES_DE_AGREGACION, OPCIONES_A_CONSIDERAR
from elecciones.resultados import Sumarizador
from escrutinio_social import settings

files_dir = 'scraper/'
regiones_file = 'regions.json'
request_url = 'https://resultados.gob.ar/'
escuelas_url = f"{request_url}assets/data/precincts/"
mesas_url = f"{request_url}assets/data/totalized_results/"

authorization_header = 'Bearer 31d15a'

class Command(BaseCommand):
    
    help = "Scrapear el sitio oficial"

    mesas_visitadas = []
    escuelas_bajadas = {}

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout=None, stderr=None, no_color=False, force_color=False)


    # Toma un $value1['distrito'] . $value1['seccion'] . $value1['circuito']  y devuelve si corresponde o no.
    # FIXME TODO: Por ahora no tenemos filtros. Acá habría que hacer los filtros de usuario
    def pasa_filtros(self, escuela, kwargs):
        # Las escuelas hay que buscarlas siempre, salvo que ya esté completo el envío de esas mesas....
        return true

    def cargar_circuitos(self, kwargs):
        #FIXME TODO: Voy por aca
        self.circuitos = []
        with open(f"{files_dir}{regiones_file}") as json_file:
            valores = json.load(json_file)
            for value in valores:
                if(value['tp'] == 'R' and value['l'] == 4): # OJO: en el original estaba como value['TP'], pero veo  el regions en minúsculas
                    circuito = {}
                    circuito['distrito'] = value['cc'][:2]
                    circuito['seccion'] = value['cc'][2:3]
                    circuito['circuito'] = value['cc'][5:6]
                    circuito['nombreCircuito'] = value['n']
                    circuito['escuelas'] = value['chd']
                    self.status(f"Circuito a agregar: {circuito}")
                    self.circuitos.append(circuito)

    def cargar_escuelas(self, kwargs):
        self.escuelas = []
        # FIXME TODO: Ponerle un nombre declarativo a key y value. Pero todavia no se que son
        for key_circuito, escuela in self.circuitos.items():
            if (self.pasa_filtros(escuela, kwargs):
                self.status(f"Se buscan todas las mesas Escrutadas del distrito: {escuela['distrito']}, seccion: {escuela['seccion']}, circuito: {escuela['circuito']}\n")
                # FIXME, esto es feo porque busca descargar todas las escuelas. Habría que filtrar las que ya visitamos
                for key_escuela, id_escuela in escuela['escuelas'].items():
                    self.escuelas_bajadas[id_escuela] = self.descargar_json_escuela(id_escuela)

    def descargar_json_escuela(self, id_escuela):
        # FIXME Preguntar: Porque hace. cuándo no entraría en el if ?
        '''
        $id = ($idEscuela / 1000);

        if (($p = strpos($id, '.')) !== false) {
            $id = floatval(substr($id, 0, $p + 1));
        }

        '''

        id = id_escuela if (id_escuela < 1000) else id_escuela // 1000


        # https://resultados.gob.ar/assets/data/precincts/14/s14002.json
        #https://resultados.gob.ar/assets/data/precincts/14/s14010.json
        #https://resultados.gob.ar/assets/data/precincts/7/s7455.json
        #url = f"https://resultados.gob.ar/assets/data/precincts/{id}/s{idEscuela}.json"
        url = f"{self.escuelas_url}/{id}/s{id_escuela}.json"

        self.status(f"descargando escuela: {url}\n")
        return self.descargar_json(url)

    def descargar_json(self, url):
        self.status(f"por descargar json de: {url}")  
        headers['Content-type'] = 'application/json'
        headers['Authorization'] = authorization_header 
        
        self.status(f"heades a enviar: {resp}")  
        resp = requests.get(
            url,
            headers = headers
        )
    
        self.status(f"obtenido del get: {resp}")  
        return json.loads(resp)
    }

    def cargar_mesas(self):
        self.mesas = []
        for key, value1 in self.escuelas_bajadas.items():
            for id_mesa, value in value1['datos']:
                mesa = {} 
                mesa['id'] = value['c']
                mesa['codigomesa'] = value['cc'][5:5]
                mesa['url'] = value['rf']
                datos = self.descargar_json_mesa(mesa['url'])
                mesa['empadronados'] = datos['st'][0]['v_exp_abs']
                self.mesas.append(mesa)

    def descargar_json_mesa(self, url):
        # https://resultados.gob.ar/assets/data/totalized_results/precincts/80/80443.json
        url = f"{mesas_url}{url}" # https://resultados.gob.ar/assets/data/totalized_results/$url
        echo url
        return self.descargar_json(url)


    def status(self, texto):
        self.stdout.write(f"{texto}")
        # self.stdout.write(self.style.SUCCESS(texto))

    def status_green(self, texto):
        self.stdout.write(self.style.SUCCESS(texto))

    # FIXME- Esto es lo que sirve para obtener la mesa segun el correo
    def get_carga_correo(self, mesa):
        return MesaCategoria.objects.get(
            mesa=mesa,
            categoria=self.categoria,
        ).parcial_oficial

    '''
    def get_mesas_sin_scrapear_escuela(self, escuela):
    def get_mesas_sin_scrapear_provincia(self, provincia):
    def get_mesas_sin_scrapear_circuito(self, circuito):
    def get_mesas_sin_scrapear_seccion(self, provincia):
    def get_mesas_sin_scrapear_distrito(self, provincia):
    def get_mesas_sin_scrapear_pais(self):
    '''
    def analizar_pais(self):
        distritos = Distrito.objects.all()
        for distrito in distritos:
            self.analizar_distrito(distrito)

    def add_arguments(self, parser):
        parser.add_argument("--escuela",
                            type=int, dest="escuela",
                            help=" Escuela a scrapear "
                            "(default %(default)s).",
                            default=None
                            )
        parser.add_argument("--provincia",
                            type=int, dest="provincia",
                            help="Provincia a scrapear"
                            "(default %(default)s).",
                            default=None
                            )
        parser.add_argument("--circuito",
                            type=int, dest="circuito",
                            help="Circuito a scrapear"
                            "(default %(default)s).",
                            default=None
                            )
        parser.add_argument("--seccion",
                            type=int, dest="seccion",
                            help="Seccion a scrapear"
                            "(default %(default)s).",
                            default=None
                            )
        parser.add_argument("--distrito",
                            type=int, dest="distrito",
                            help="Distrito a scrapear"
                            "(default %(default)s).",
                            default=None
                            )
        parser.add_argument("--pais",
                            action="store_true", dest="pais",
                            default=False,
                            help="Busca todo el país (default %(default)s)."
                            )

        parser.add_argument("--procesos",
                            type=int, dest="procesos",
                            help="Cantidad de procesos a utilizar en el scraping"
                            "(default %(default)s).",
                            default=1

                            )

    # Guarda las mesas que tenemos hacia el django
    def guardar_mesas(self):
        return

    def handle(self, *args, **kwargs):
        # FIXME TODO: Agregar los filtros
        self.filtros = kwargs
        self.cargar_circuitos()
        self.cargar_escuelas()
        self.cargar_mesas()
        self.guardar_mesas()
    }

        '''
        self.comparar_con_correo = kwargs['comparar_con_correo']

        self.umbral_analisis_estadisticos = kwargs['umbral_analisis_estadisticos']
        self.umbral_mesas_ganadas = kwargs['umbral_mesas_ganadas']

        self.tipo_de_agregacion = kwargs['tipo_de_agregacion']

        nombre_categoria = kwargs['categoria']
        self.categoria = Categoria.objects.get(slug=nombre_categoria)
        print("Vamos a analizar la categoría:", self.categoria)

        self.asignar_nivel_agregacion(kwargs)
        self.analizar_segun_nivel_agregacion()
        '''

    def asignar_nivel_agregacion(self, kwargs):
        # Analizar resultados de acuerdo a los niveles de agregación
        numero_circuito = kwargs['solo_circuito']
        numero_seccion = kwargs['solo_seccion']
        numero_distrito = kwargs['solo_distrito']
        self.distrito = None
        self.seccion = None
        self.circuito = None

        if numero_distrito:
            self.distrito = Distrito.objects.get(numero=numero_distrito)
            if numero_seccion:
                self.seccion = Seccion.objects.get(numero=numero_seccion, distrito=self.distrito)
                if numero_circuito:
                    self.circuito = Circuito.objects.get(numero=numero_circuito, seccion=self.seccion)
