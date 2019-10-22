import requests
import json
from django.core.management.base import BaseCommand
from escrutinio_social import settings
from elecciones.models import (
    Distrito,
    Mesa,
    Carga,
    Seccion,
    Circuito,
    Categoria,
    MesaCategoria,
    VotoMesaReportado,
    CargaOficialControl,
    Opcion,
    CategoriaOpcion
)

 
files_dir = "scraper_data/"
regiones_file = 'regions.json'
request_url = 'https://resultados.gob.ar/'
escuelas_url = f"{request_url}assets/data/precincts/"
mesas_url = f"{request_url}assets/data/totalized_results/"
local_confs_url = f"{files_dir}ids_sistema_web.json"
authorization_header = 'Bearer 31d15a'

# If modifying these scopes, delete the file token.pickle.
API_KEY = '***REMOVED***'
# The ID and range of a sample spreadsheet.
PARAMS = {'key': API_KEY}


class Command(BaseCommand):
    
    help = "Scrapear el sitio oficial"

    mesas_visitadas = []
    escuelas_bajadas = {}
    mesas_sistema_sin_carga = []
    # Los codigos en el sistema de escrutinio
    ids = {}

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout=None, stderr=None, no_color=False, force_color=False)


    def get_opcion_nosotros(self):
        return self.get_opcion(settings.CODIGO_PARTIDO_NOSOTROS)

    def get_opcion_ellos(self):
        return self.get_opcion(settings.CODIGO_PARTIDO_ELLOS)

    # Toma un $value1['distrito'] . $value1['seccion'] . $value1['circuito']  y devuelve si corresponde o no.
    def pasa_filtros_circuitos(self, circuito, kwargs):
        # Las escuelas hay que buscarlas siempre, salvo que ya esté completo el envío de esas mesas....
        # Puedo hacerlo con evaluación lazy ?
        if (kwargs['pais']): 
            return True # Si es el país no sigo viendo nada
        else:
            ret = True
            if (kwargs['distrito'] is not None): # Si no ponen pais y no ponen nada, tomamos como que es pais.
                ret = ret and (kwargs["distrito"] == circuito["distrito"])
                if(kwargs['seccion'] is not None):
                    ret = ret and (kwargs["seccion"] == circuito["seccion"])
                    if (kwargs['circuito'] is not None):
                        ret = ret and (kwargs["circuito"] == circuito["circuito"])
        return ret 

    def cargar_circuitos(self, kwargs):
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
        self.status("Cargando escuelas:...")
        self.escuelas_bajadas = []
        # FIXME TODO: Ponerle un nombre declarativo a key y value. Pero todavia no se que son
        for circuito in self.circuitos:
            if (self.pasa_filtros_circuitos(circuito, kwargs)):
                self.status(f"Se buscan todas las mesas Escrutadas de las escuelas de distrito: {circuito['distrito']}, seccion: {circuito['seccion']}, circuito: {circuito['circuito']}\n")
                # FIXME, esto es feo porque busca descargar todas las escuelas. Habría que filtrar las que ya visitamos segun timestamp o algo asi. Pero necesitamos el file de ejemplo a ver si hay ese dato
                for id_escuela in circuito['escuelas']:
                    self.status(f"Buscando escuela: {id_escuela}")
                    # FIXME Pasarla por el filtro de escuelas y tal vez luego de mesas
                    self.escuelas_bajadas[id_escuela] = self.descargar_json_escuela(id_escuela)

    def descargar_json_escuela(self, id_escuela):
        # FIXME Preguntar: Porque hace. cuándo no entraría en el if ?
        '''
        $id = ($idEscuela / 1000);

        if (($p = strpos($id, '.')) !== false) {
            $id = floatval(substr($id, 0, $p + 1));
        }

        '''

        id = id_escuela if (int(id_escuela) < 1000) else int(id_escuela) // 1000


        # https://resultados.gob.ar/assets/data/precincts/14/s14002.json
        #https://resultados.gob.ar/assets/data/precincts/14/s14010.json
        #https://resultados.gob.ar/assets/data/precincts/7/s7455.json
        #url = f"https://resultados.gob.ar/assets/data/precincts/{id}/s{idEscuela}.json"
        url = f"{escuelas_url}/{id}/s{id_escuela}.json"

        self.status(f"descargando escuela: {url}\n")
        return self.descargar_json(url)

    def descargar_json(self, url):
        self.status(f"por descargar json de: {url}")  
        headers = {}
        headers['Content-type'] = 'application/json'
        headers['Authorization'] = authorization_header 
        
        self.status(f"heades a enviar: {headers}")  
        resp = requests.get(
            url,
            headers = headers
        )
    
        self.status(f"obtenido del get: {resp}")  
        # FIXME: Ver bien cómo viene esta respuesta y que sea lo que quieren el resto. Por ahora tira un 200 solamente y no un json
        return json.loads(resp.text)

    # Busco en la base las que no estan para esa escuela, distrito, etc...
    def mesa_no_visitada(self, id_mesa, distrito, seccion, nro_mesa):
        return (nro_mesa not in self.mesas_sistema_sin_carga.keys()) # Las voy a sacar cuando guarde y luego al volver a cargar no van a volver a aparecer

    def cargar_mesas(self, kwargs):
        self.mesas = []
        for id_escuela, valor1 in self.escuelas_bajadas.items():
            for valor_mesa in valor1:
                distrito = valor_mesa['cc'][:2]
                seccion = valor_mesa['cc'][2:5]
                nro_mesa = valor_mesa['cc'][5:10]
                if(self.mesa_no_visitada(id_mesa, distrito, seccion, nro_mesa)):
                    mesa = {} 
                    mesa['id'] = valor_mesa['c']
                    mesa['distrito'] = distrito 
                    mesa['seccion'] = seccion 
                    mesa['nro_mesa'] = nro_mesa 
                    mesa['url'] = valor_mesa['rf']
                    datos = self.descargar_json_mesa(mesa['url'])
                    mesa['votos'] = datos['rp']
                    mesa['votos_extra'] = datos['ct'] # Datos de blancos, impugnados, etc.
                    '''
                    - cc son los cargos.
                    - pc es el partido
                    - v votos
                    - tot: totales
                    '''
                    self.mesas.append(mesa)

    def descargar_json_mesa(self, url):
        # https://resultados.gob.ar/assets/data/totalized_results/precincts/80/80443.json
        url = f"{mesas_url}{url}" # https://resultados.gob.ar/assets/data/totalized_results/$url
        return self.descargar_json(url)


    def status(self, texto):
        self.stdout.write(f"{texto}")
        # self.stdout.write(self.style.SUCCESS(texto))

    def status_green(self, texto):
        self.stdout.write(self.style.SUCCESS(texto))

    def add_arguments(self, parser):
        parser.add_argument("--escuela",
                            type=str, dest="escuela",
                            help=" Escuela a scrapear "
                            "(default %(default)s).",
                            default=None
                            )
        parser.add_argument("--circuito",
                            type=str, dest="circuito",
                            help="Circuito a scrapear"
                            "(default %(default)s).",
                            default=None
                            )
        parser.add_argument("--seccion",
                            type=str, dest="seccion",
                            help="Seccion a scrapear"
                            "(default %(default)s).",
                            default=None
                            )
        parser.add_argument("--distrito",
                            type=str, dest="distrito",
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
    # FIXME TODO: Voy por aca
    def guardar_mesas(self):
        # Tengo que levantar los circuitos_categoria para las mesas que cargue y las categorias que me importan y guardarlas
        for datos_mesa in self.mesas:
            '''
                   mesa['id'] = value['c']
                    mesa['codigomesa'] = value['cc'][5:5]
                    mesa['url'] = value['rf']
                    datos = self.descargar_json_mesa(mesa['url'])
                    mesa['votos'] = datos['sp']
                    - cc son los cargos.
                    - pc es el partido
                    - v votos
                    - tot: totales
            '''
            
        return

    # Carga las mesas_categoria del sistema que no tengan datos oficiales. Nos interesa solo presidente y gobernador
    def agregar_mesa_categoria_a_mesas_sin_cargar(self, mesa_categoria):
        for mesa_categoria in mesas_categoria_sistema:
            distrito = mesa_categoria.mesa.circuito.seccion.distrito.numero 
            seccion =  mesa_categoria.mesa.circuito.seccion.numero
            circuito = mesa_categoria.mesa.circuito.numero
            self.mesas_sistema_sin_carga[mesa_categoria.mesa.numero] = {}
            self.mesas_sistema_sin_carga[mesa_categoria.mesa.numero]["circuito"] = circuito 
            self.mesas_sistema_sin_carga[mesa_categoria.mesa.numero]["seccion"] = seccion 
            self.mesas_sistema_sin_carga[mesa_categoria.mesa.numero]["distrito"] = distrito 

    def cargar_mesas_sistema(self):
        # FIXME: Esto se debe poder hacer directo en la query. Busco quedarme solo con mesas que no tengan mesa categoria con datos oficiales. Total si no tienen una categoria, no tienen ninguna. Me fijo categoria presidente por las dudas. 
        # FIXME TODO: Ver como hacer un OR
        # FIXME TODO: Deberiamos aca meter los filtros y algún criterio de prioridad
        categoria = Categoria.objects.get(slug=self.ids["slug_cat_presidente_nuestro"])

        mesas_categoria_sistema = MesaCategoria.objects.get(
                                        categoria=categoria
                                    ).filter(carga_oficial__isnull=True) 

        print(mesas_categoria_sistema)
        self.agregar_mesa_categoria_a_mesas_sin_cargar(mesas_categoria_sistema)
        self.mesas_sistema_sin_carga = {} 
        # FIXME TODO: Deberiamos aca meter los filtros y algún criterio de prioridad
        # Cargo ahora los de gobernador
        mesas_categoria_sistema = MesaCategoria.objects.get(
                                        categoria=self.ids["slug_cat_gobernador_nuestro"]
                                    ).filter(carga_oficial__isnull=True) 
        self.agregar_mesa_categoria_a_mesas_sin_cargar(mesas_categoria_sistema)

        return 

    def handle(self, *args, **kwargs):
        with open(local_confs_url) as ids_file:
            self.ids = json.load(ids_file)

        self.filtros = kwargs
        self.asignar_nivel_agregacion(kwargs)
        self.cargar_mesas_sistema()
        self.cargar_circuitos(kwargs)
        self.cargar_escuelas(kwargs)
        self.cargar_mesas(kwargs)
        self.guardar_mesas()
        '''
        self.comparar_con_correo = kwargs['comparar_con_correo']

        self.umbral_analisis_estadisticos = kwargs['umbral_analisis_estadisticos']
        self.umbral_mesas_ganadas = kwargs['umbral_mesas_ganadas']

        self.tipo_de_agregacion = kwargs['tipo_de_agregacion']

        nombre_categoria = kwargs['categoria']
        self.categoria = Categoria.objects.get(slug=nombre_categoria)
        print("Vamos a analizar la categoría:", self.categoria)

        self.analizar_segun_nivel_agregacion()
        '''

    def asignar_nivel_agregacion(self, kwargs):
        # Analizar resultados de acuerdo a los niveles de agregación
        numero_circuito = kwargs['circuito']
        numero_seccion = kwargs['seccion']
        numero_distrito = kwargs['distrito']
        self.distrito = None
        self.seccion = None
        self.circuito = None

        if numero_distrito:
            self.distrito = Distrito.objects.get(numero=numero_distrito)
            if numero_seccion:
                self.seccion = Seccion.objects.get(numero=numero_seccion, distrito=self.distrito)
                if numero_circuito:
                    self.circuito = Circuito.objects.get(numero=numero_circuito, seccion=self.seccion)
