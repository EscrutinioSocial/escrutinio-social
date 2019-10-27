import requests
import json
from django.core.management.base import BaseCommand
from escrutinio_social import settings
from fiscales.models import Fiscal
from django.db import transaction
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
from datetime import datetime, date
import pytz


files_dir = "scraper_data/"
regiones_file = 'regions.json'
request_url = 'https://resultados.gob.ar/'
escuelas_url = f"{request_url}assets/data/precincts/"
mesas_url = f"{request_url}assets/data/totalized_results/"
local_confs_url = f"{files_dir}ids_sistema_web.json"
authorization_header = 'Bearer 31d15a'
escuela_file = files_dir + 'doc/escuelas/' + '1_1_1_1.json'
mesa_file = files_dir + 'doc/mesas/' + '1_1_1_1.json'
regiones_test_file = 'doc/regions_test.json'
clave_json_agrupacion = 'pc'
clave_json_cant_votos = 'v'
clave_json_blancos_nulos = 'cn'
clave_json_cant_blancos_nulos = 'cv'
key_categorias = 'cc'
key_votantes = 'votos'
key_blancos_nulos = 'votos_extra'

# If modifying these scopes, delete the file token.pickle.
API_KEY = '***REMOVED***'
# The ID and range of a sample spreadsheet.
PARAMS = {'key': API_KEY}


class Command(BaseCommand):

    help = "Scrapear el sitio oficial"

    escuelas_bajadas = {}
    mesas_sistema_sin_carga = []
    mesas = {}
    # Los codigos en el sistema de escrutinio
    ids = {}

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout=None, stderr=None, no_color=False, force_color=False)

    def get_opcion(self, codigo_partido, categoria):
        return CategoriaOpcion.objects.get(opcion__partido__codigo=codigo_partido, categoria=categoria).opcion

    def get_opcion_nosotros(self, categoria):
        return self.get_opcion(settings.CODIGO_PARTIDO_NOSOTROS, categoria)

    def get_opcion_ellos(self, categoria):
        return self.get_opcion(settings.CODIGO_PARTIDO_ELLOS, categoria)

    #----------------------------------------------------------#
    # Para testing
    #----------------------------------------------------------#
    def cargar_escuela_prueba(self):
        with open(escuela_file) as escuela_prueba:
            return json.load(escuela_prueba)

    def cargar_mesa_prueba(self):
        with open(mesa_file) as mesa_prueba:
            return json.load(mesa_prueba)

    #----------------------------------------------------------#
    # Hasta aca Para testing
    #----------------------------------------------------------#

    # Toma un $value1['distrito'] . $value1['seccion'] . $value1['circuito']  y devuelve si corresponde o no.
    def pasa_filtros_circuitos(self, circuito, kwargs):
        # Las escuelas hay que buscarlas siempre, salvo que ya esté completo el envío de esas mesas....
        # Puedo hacerlo con evaluación lazy ?
        if kwargs['pais']:
            return True  # Si es el país no sigo viendo nada
        else:
            ret = True
            if kwargs['distrito'] is not None:  # Si no ponen pais y no ponen nada, tomamos como que es pais.
                ret = ret and (int(kwargs["distrito"]) == int(circuito["distrito"]))
                if(kwargs['seccion'] is not None):
                    ret = ret and (int(kwargs["seccion"]) == int(circuito["seccion"]))
                    if (kwargs['circuito'] is not None):
                        # print (f'{kwargs["circuito"]}- {circuito["circuito"]}')
                        ret = ret and (kwargs["circuito"] == circuito["circuito"])
        return ret

    def cargar_circuitos(self):
        self.circuitos = []
        if self.test:
            regiones = f"{files_dir}{regiones_test_file}"
        else:
            regiones = f"{files_dir}{regiones_file}"
        with open(regiones) as json_file:
            valores = json.load(json_file)
            for value in valores:
                if value['tp'] == 'R' and value['l'] == 4:  # OJO: en el original estaba como value['TP'], pero veo  el regions en minúsculas
                    circuito = {}
                    circuito['distrito'] = value['cc'][:2]
                    circuito['seccion'] = value['cc'][2:5]
                    circuito['circuito'] = value['cc'][5:11]
                    circuito['nombreCircuito'] = value['n']
                    circuito['escuelas'] = value['chd']
                    self.status(f"Circuito a agregar: {circuito}")
                    self.circuitos.append(circuito)

    def cargar_escuelas(self, kwargs):
        self.status("Cargando escuelas:...")
        self.escuelas_bajadas = {}
        for circuito in self.circuitos:
            if self.pasa_filtros_circuitos(circuito, kwargs):
                self.status(f"Se buscan las escuelas de distrito: {circuito['distrito']}, seccion: {circuito['seccion']}, circuito: {circuito['circuito']}\n")
                # FIXME, esto es feo porque busca descargar todas las escuelas. Habría que filtrar las que ya visitamos segun timestamp o algo asi. Pero necesitamos el file de ejemplo a ver si hay ese dato
                for id_escuela in circuito['escuelas']:
                    self.status(f"Buscando escuela: {id_escuela}")
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
        if (self.test):
            return self.cargar_escuela_prueba()

        return self.descargar_json(url)

    def descargar_json(self, url):
        self.status(f"por descargar json de: {url}")
        headers = {}
        headers['Content-type'] = 'application/json'
        headers['Authorization'] = authorization_header

        self.status(f"heades a enviar: {headers}")
        resp = requests.get(
            url,
            headers=headers
        )

        self.status(f"obtenido del get: {resp}")
        # FIXME: Ver bien cómo viene esta respuesta y que sea lo que quieren el resto. Por ahora tira un 200 solamente y no un json
        return json.loads(resp.text)

    # Busco en la base las que no estan para esa escuela, distrito, etc...
    def mesa_sin_resultado_oficial(self, distrito, seccion, nro_mesa):
        # FIXME: TODO: Esto es horrible
        # Las voy a sacar cuando guarde y luego al volver a cargar el command no van a volver a aparecer

        clave_mesa = self.get_clave_mesa(distrito, seccion, nro_mesa)
        return clave_mesa in self.mesas_sistema_sin_carga

    def cargar_mesas(self, kwargs):
        self.mesas = {}
        self.status("Descargando mesas - Distrito - seccion - id_escuela - mesa")
        for id_escuela, valor1 in self.escuelas_bajadas.items():
            for valor_mesa in valor1:
                distrito = int(valor_mesa['cc'][:2])
                seccion = int(valor_mesa['cc'][2:5])
                nro_mesa = int(valor_mesa['cc'][5:11])
                # Si estoy en modo test va a bajar siempre la misma escuela (aunque piense que son distintas) y entonces esto se a a repetir
                if self.mesa_sin_resultado_oficial(distrito, seccion, nro_mesa):
                    mesa = {}
                    self.status(f"{distrito} - {seccion} - {id_escuela} - {nro_mesa}")
                    mesa['id'] = valor_mesa['c']
                    mesa['distrito'] = distrito
                    mesa['seccion'] = seccion
                    mesa['nro_mesa'] = nro_mesa
                    mesa['url'] = valor_mesa['rf']
                    datos = self.descargar_json_mesa(mesa['url'])
                    mesa['votos'] = datos['rp']
                    mesa['votos_extra'] = datos['ct']  # Datos de blancos, impugnados, etc.
                    '''
                    - cc son los cargos.
                    - pc es el partido
                    - v votos
                    - tot: totales
                    '''
                    self.mesas[f"{distrito}{seccion}{nro_mesa}"] = mesa  # Para buscarla despues

    def descargar_json_mesa(self, url):
        # https://resultados.gob.ar/assets/data/totalized_results/precincts/80/80443.json
        url = f"{mesas_url}{url}"  # https://resultados.gob.ar/assets/data/totalized_results/$url
        if (self.test):
            self.status(f"Usando json de mesa: {url}")
            return self.cargar_mesa_prueba()
        return self.descargar_json(url)

    def status(self, texto):
        self.stdout.write(f"{texto}")
        # self.stdout.write(self.style.SUCCESS(texto))

    def status_green(self, texto):
        self.stdout.write(self.style.SUCCESS(texto))

    def status_error(self, texto):
        self.stdout.write(self.style.ERROR(texto))

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
        # Para habilitar testar
        parser.add_argument("--test",
                            action="store_true", dest="test",
                            default=False,
                            help="Testear contra jsons de prueba en vez de sistema online. Ojo que si se corre en productivo guarda datos en la DB"
                            )

    def get_clave_mesa(self, distrito, seccion, nro_mesa):
        return f"{distrito}{seccion}{nro_mesa}"

    # en el json busca los votos segun el dato pasado
    def parse_voto_web(self, datos_mesa_web, key_array, id_cat_ellos, key_dato, id_dato, key_valor):
        print(datos_mesa_web)
        datos = datos_mesa_web[key_array]  # El array donde estan los datos (rp o st)
        for resultado in datos:
            if (resultado[key_categorias] == id_cat_ellos) and (resultado[key_dato] == id_dato):
                return resultado[key_valor]

    def guardar_voto(self, datos_mesa_web, nro_distrito, nro_seccion, nro_circuito, nro_mesa, id_cat_ellos, slug_categoria, id_agrupacion_ellos, id_agrupacion_nosotros):
        categoria = Categoria.objects.get(slug=slug_categoria)
        print("Vamos a guardar la categoría:", categoria)

        ultima_guardada_con_exito = None
        tz = pytz.timezone('America/Argentina/Buenos_Aires')

        # acá se debería consultar la fecha y hora del último registro guardado
        # para luego filtrar las filas nuevas
        fecha_ultimo_registro = CargaOficialControl.objects.filter(categoria=categoria).first()
        if fecha_ultimo_registro:
            date_format = '%d/%m/%Y %H:%M:%S'
            fd = datetime.strptime(fecha_ultimo_registro.fecha_ultimo_registro, date_format)

        fiscal = Fiscal.objects.get(id=1)
        tipo = 'parcial_oficial'

        opcion_nosotros = self.get_opcion_nosotros(categoria)
        opcion_ellos = self.get_opcion_ellos(categoria)
        opcion_blancos = Opcion.blancos()
        opcion_nulos = Opcion.nulos()
        opcion_total = Opcion.total_votos()

        try:
            distrito = Distrito.objects.get(numero=nro_distrito)
            seccion = Seccion.objects.get(numero=nro_seccion, distrito=distrito)
            circuito = Circuito.objects.get(numero=nro_circuito, seccion=seccion)
            mesa = Mesa.objects.get(numero=nro_mesa, circuito=circuito)
            mesa_categoria = MesaCategoria.objects.get(mesa=mesa, categoria=categoria)
            opciones_votos = [opcion_nosotros, opcion_ellos]
            opciones_blanco_nulos = [opcion_blancos, opcion_nulos, opcion_total]
            with transaction.atomic():
                carga = Carga.objects.create(
                    mesa_categoria=mesa_categoria,
                    tipo=tipo,
                    fiscal=fiscal,
                    origen=Carga.SOURCES.web
                )

                votos_a_crear = []
                for id_dato, opcion in zip ([id_agrupacion_nosotros, id_agrupacion_ellos], opciones_votos):
                    votos=self.parse_voto_web(datos_mesa_web, key_votantes, id_cat_ellos, clave_json_agrupacion, id_dato, clave_json_cant_votos)
                    votos_a_crear.append(
                        VotoMesaReportado(
                            carga=carga, opcion=opcion,
                            votos=votos
                        )
                    )
                    self.status(f"creando votos utiles para id agrupacion: {id_dato}. Valor cargado: {votos}")
                for id_dato, opcion in zip([self.ids["id_blancos"], self.ids["id_nulos"], self.ids["id_total"]], opciones_blanco_nulos):
                    votos=self.parse_voto_web(datos_mesa_web, key_blancos_nulos, id_cat_ellos, clave_json_blancos_nulos, id_dato, clave_json_cant_blancos_nulos)
                    votos_a_crear.append(
                        VotoMesaReportado(
                            carga=carga, opcion=opcion,
                            votos=votos
                        )
                    )
                    self.status(f"creando votos blancos nulos para id agrupacion: {id_dato}. Valor cargado: {votos}")
                VotoMesaReportado.objects.bulk_create(votos_a_crear)
                # actualizo la firma así no es necesario correr consolidar_identificaciones_y_cargas
                carga.actualizar_firma()

                # Si hay cargas repetidas esto hace que se tome la última
                # en el proceso de comparar_mesas_con_correo.
                mesa_categoria.actualizar_parcial_oficial(carga)
            # Pongo fecha de ahora ??
            today = datetime.today().replace(tzinfo=tz)
            print(today)
            print(today.strftime('%d/%m/%Y %H:%M:%S'))
            ultima_guardada_con_exito = today  #today.strftime('%d/%m/%Y %H:%M:%S')

        except Distrito.DoesNotExist:
            self.warning(f'No existe el distrito {nro_distrito}')
        except Seccion.DoesNotExist:
            self.warning(f'No existe la sección {nro_seccion} en el distrito {nro_distrito}')
        except Circuito.DoesNotExist:
            self.warning(f'No existe el circuito {nro_circuito} - seccion: {nro_seccion}')

        if ultima_guardada_con_exito:
            if fecha_ultimo_registro:
                fecha_ultimo_registro.fecha_ultimo_registro = ultima_guardada_con_exito
                fecha_ultimo_registro.save()
            else:
                CargaOficialControl.objects.create(fecha_ultimo_registro=ultima_guardada_con_exito, categoria=categoria)

    # Guarda las mesas que tenemos hacia el django
    def guardar_mesas(self):
        # Tengo que levantar los circuitos_categoria para las mesas que cargue y las categorias que me importan y guardarlas
        for key_mesa, datos_mesa_web in self.mesas.items():
            datos_mesa_sistema = self.mesas_sistema_sin_carga[key_mesa]
            # FIXME TODO: Poner el map para las categorias, o directo repetir como aca :)
            # Guardo votos para Presidente
            self.guardar_voto(
                datos_mesa_web,
                datos_mesa_sistema["distrito"],
                datos_mesa_sistema["seccion"],
                datos_mesa_sistema["circuito"],
                datos_mesa_sistema["nro_mesa"],
                self.ids["id_cat_presidente"],
                self.ids["slug_cat_presidente_nuestro"],
                self.ids["id_agrupacion_ellos_presidente"],
                self.ids["id_agrupacion_nosotros_presidente"]
            )

        return

    # Carga las mesas_categoria del sistema que no tengan datos oficiales. Nos interesa solo presidente y gobernador
    def agregar_mesa_categoria_a_mesas_sin_cargar(self, mesas_categoria_sistema):
        self.status("Mesas categoria: distrito - seccion - circuito - nro_mesa")
        for mesa_categoria in mesas_categoria_sistema:
            # Paso a int para no tener problemas luego con diferencias entre las bases.
            distrito = int(mesa_categoria.mesa.circuito.seccion.distrito.numero)
            seccion = int(mesa_categoria.mesa.circuito.seccion.numero)
            circuito = mesa_categoria.mesa.circuito.numero
            nro_mesa = int(mesa_categoria.mesa.numero)
            self.status(f'{distrito} - {seccion} - {circuito} - {mesa_categoria.mesa.numero}')
            clave_mesa = self.get_clave_mesa(distrito, seccion, nro_mesa)
            self.mesas_sistema_sin_carga[clave_mesa] = {}
            self.mesas_sistema_sin_carga[clave_mesa]["circuito"] = circuito
            self.mesas_sistema_sin_carga[clave_mesa]["seccion"] = seccion
            self.mesas_sistema_sin_carga[clave_mesa]["distrito"] = distrito
            self.mesas_sistema_sin_carga[clave_mesa]["nro_mesa"] = nro_mesa

    def cargar_mesas_sistema(self):
        # Busco quedarme solo con mesas que no tengan mesa categoria con datos oficiales. Total si no tienen una categoria, no tienen ninguna. Me fijo categoria presidente por las dudas. 
        # FIXME TODO: Ver como hacer un OR
        # FIXME TODO: Deberiamos aca meter los filtros y algún criterio de prioridad
        self.mesas_sistema_sin_carga = {}
        categoria = Categoria.objects.get(slug=self.ids["slug_cat_presidente_nuestro"])
        mesas_categoria_sistema = MesaCategoria.objects.filter(
            categoria=categoria,
            carga_oficial__isnull=True
        )

        self.agregar_mesa_categoria_a_mesas_sin_cargar(mesas_categoria_sistema)
        return

    def handle(self, *args, **kwargs):
        with open(local_confs_url) as ids_file:
            self.ids = json.load(ids_file)
        self.test = kwargs['test']
        self.filtros = kwargs
        self.asignar_nivel_agregacion(kwargs)
        self.cargar_mesas_sistema()
        self.cargar_circuitos()
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
        numero_seccion = int(kwargs['seccion'])
        numero_distrito = int(kwargs['distrito'])
        self.distrito = None
        self.seccion = None
        self.circuito = None

        try:
            if numero_distrito:
                self.distrito = Distrito.objects.get(numero=numero_distrito)
                if numero_seccion:
                    self.seccion = Seccion.objects.get(numero=numero_seccion, distrito=self.distrito)
                    if numero_circuito:
                        self.circuito = Circuito.objects.get(numero=numero_circuito, seccion=self.seccion)
        except:
            self.status_error(f"No existe combinacion de distrito: {numero_distrito} - seccion: {numero_seccion} - circuito: {numero_circuito}")
