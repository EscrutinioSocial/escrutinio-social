import pandas as pd
from django.http import Http404
from django.shortcuts import get_object_or_404
import math
from elecciones.models import Mesa, Carga, VotoMesaReportado, Opcion, CategoriaOpcion
from django.db import transaction
from django.db.utils import IntegrityError
from django.core.files.uploadedfile import InMemoryUploadedFile
from escrutinio_social import settings
from fiscales.models import Fiscal
import structlog
from threading import Thread
import time
import logging
logger = logging.getLogger('csv_import')

# Primer dato: nombre de la columna, segundo: si es parte de una categoría o no,
# tercero, si es obligatorio o puede no estar (dado que en distintas provincias se votan distintas
# categorías).
COL_CANT_ELECTORES = 'cantidad de electores del padron'
COL_CANT_SOBRES = 'cantidad de sobres en la urna'
COLUMNAS_DEFAULT = [
    # Identificación de la mesa.
    ('seccion', False, True), ('distrito', False, True),
    ('circuito', False, True), ('nro de mesa', False, True),
    # Opción.
    ('nro de lista', False, True),
    # Categorías electivas.
    ('presidente y vice', True, True),
    ('gobernador y vice', True, False),
    ('senadores nacionales', True, False),
    ('diputados nacionales', True, False),
    ('senadores provinciales', True, False),
    ('diputados provinciales', True, False),
    ('legisladores provinciales', True, False),  # Para el caso de legislatura unicameral.
    ('intendentes, concejales y consejeros escolares', True, False),
    # Metadata.
    (COL_CANT_ELECTORES, False, True),
    (COL_CANT_SOBRES, False, True),
]


# Excepciones custom, por si se quieren manejar
class CSVImportacionError(Exception):
    pass


class FormatoArchivoInvalidoError(CSVImportacionError):
    pass


class ColumnasInvalidasError(CSVImportacionError):
    pass


class DatosInvalidosError(CSVImportacionError):
    pass


class PermisosInvalidosError(CSVImportacionError):
    pass


class ErroresAcumulados(CSVImportacionError):
    pass


class CSVImporter:
    """
    Clase encargada de procesar un archivo CSV y validarlo.
    Recibe por parámetro el file o path al file y el usuario que sube el archivo.
    """
    def __init__(self, archivo, usuario, debug=False):
        self.debug = debug
        self.logger = logger
        self.archivo = archivo
        converters = {
            'Distrito': self.canonizar,
            'Sección': self.canonizar,
            'Seccion': self.canonizar,
            'Circuito': self.canonizar,
            'Nro de mesa': self.canonizar,
            'Nro de lista': self.canonizar,
        }
        # Para evitar el warning de "Both a converter and dtype were specified",
        # mapeo de la columna 5 en adelante a string, evitando las primeras que tienen converter.
        dtype_dict = {i: str for i in range(5, len(COLUMNAS_DEFAULT) + 1)}
        separador = self.autodetectar_separador(archivo)
        self.df = pd.read_csv(self.archivo,
            na_values=["n/a", "na", "-"],
            dtype=dtype_dict,
            converters=converters,
            index_col=False,  # La primera columna no es el índice.
            sep=separador,
        )
        self.usuario = usuario
        self.fiscal = None
        self.mesas = []
        self.mesas_matches = {}
        self.carga_total = None
        self.carga_parcial = None
        self.log_debug(f"Importando archivo '{archivo}'.")
        self.cant_errores = 0
        self.cant_mesas_importadas = 0
        self.cant_mesas_parcialmente_importadas = 0
        self.errores = []
        self.procesamiento_terminado = False

    def leer_fragmento_de_in_memory_uploaded_file(self, archivo):
        for chunk in archivo.chunks():
            return str(chunk)

    def autodetectar_separador(self, archivo):
        """
        Esta función infiere el caracter de separación en base a la primera línea del archivo.
        Lo hacemos de esta manera porque los mecanismos de autodetección de Pandas, al igual
        que los de uso de múltiples caracteres de separación traen diversos problemas.
        """
        if type(archivo) == InMemoryUploadedFile:
            # Es un archivo in memory.
            line = self.leer_fragmento_de_in_memory_uploaded_file(archivo)
            # Lo reseteamos.
            archivo.seek(0)
        else:
            # Es un archivo normal.
            f = open(archivo, "r")
            line = f.readline()
            f.close()
        separador = ','
        max = 0
        for candidato in [',', ';', '\t']:
            cant = line.count(candidato)
            if cant > max:
                max = cant
                separador = candidato

        self.log_debug(f"Usando {separador} como separador.")
        return separador

    def resultados(self, cant_errores_ya_entregados=0):
        """
        Devuelve la cantidad de mesas importadas como primer componente de la tupla,
        la cantidad de mesas de las que se importó al menos una categoría como segundo,
        y como tercero todos aquellos errores que se pueden reportar en batch.
        """
        errores_pendientes = self.errores[cant_errores_ya_entregados:]
        errores = None if len(errores_pendientes) == 0 else '\n'.join(errores_pendientes)
        return self.cant_mesas_importadas, self.cant_mesas_parcialmente_importadas, errores

    def procesar(self):
        self.validar()
        return self.procesar_post_validar()

    def procesar_post_validar(self):
        if self.cant_errores > 0:
            # Si hay errores en la validación no seguimos.
            self.procesamiento_terminado = True  # Para que termine el thread de yield.
            return self.resultados()

        self.validar_mesas()
        self.cargar_info()
        self.procesamiento_terminado = True
        return self.resultados()

    def yield_errores(self):
        """
        Entrega los errores gradualmente.
        """
        cant_errores_entregados = 0
        while not self.procesamiento_terminado:
            # Espero a que se produzca un nuevo error o que se termine.
            while (
                not self.procesamiento_terminado and
                cant_errores_entregados == self.cant_errores
            ):
                # Dormimos unos segundos para no hacer busy-waiting y dar tiempo a que
                # termine o se produzcan errores.
                time.sleep(5)
            if not self.procesamiento_terminado:
                yield self.cant_mesas_importadas, self.cant_mesas_parcialmente_importadas, self.errores[cant_errores_entregados]
                cant_errores_entregados += 1
        yield self.resultados(cant_errores_entregados)

    def procesar_parcialmente(self):
        try:
            self.validar()
        except Exception as e:
            self.anadir_error(str(e))
            yield self.resultados()
            return
        t = Thread(target=self.procesar_post_validar)
        t.daemon = False
        t.start()
        return self.yield_errores()

    def anadir_error(self, error):
        self.cant_errores += 1
        texto_error = f'{self.cant_errores} - {error}'
        self.errores.append(texto_error)

    def log_debug(self, mensaje):
        if not self.debug:
            return
        self.logger.debug(mensaje)

    def validar(self):
        """
        Permite validar la info que contiene un archivos CSV
        Validaciones:
            - Existencia de ciertas columnas
            - Columnas no duplicadas
            - Tipos de datos

        """
        try:
            self.validar_usuario()
            self.validar_columnas()

        except PermisosInvalidosError as e:
            raise e

        except CSVImportacionError as e:
            raise e
        # para manejar cualquier otro tipo de error
        # except Exception as e:
        #     raise FormatoArchivoInvalidoError('No es un CSV válido.')

    def validar_columnas(self):
        """
        Valida que estén las columnas obligatorias en el archivo y que no hayan columnas repetidas.
        """
        # Normalizamos las columnas para evitar comparaciones con espacios/acentos.
        self.df.columns = self.df.columns.str.strip().str.lower().str.replace('ó', 'o')

        headers_obligatorios = list(elem[0] for elem in COLUMNAS_DEFAULT if elem[2])

        # Validamos la existencia de los headers mandatorios.
        columnas_obligatorias = all(elem in self.df.columns for elem in headers_obligatorios)
        if not columnas_obligatorias:
            faltantes = [columna for columna in headers_obligatorios if columna not in self.df.columns]
            raise ColumnasInvalidasError(f'Faltan las columnas: {faltantes} en el archivo.')

        # Las columnas duplicadas en Pandas se especifican como ‘X’, ‘X.1’, …’X.N’
        columnas_candidatas = [columna.replace('.1', '') for columna in self.df.columns
                               if columna.endswith('.1')]
        columnas_duplicadas = any(elem in columnas_candidatas for elem in headers_obligatorios)
        if columnas_duplicadas:
            raise ColumnasInvalidasError('Hay columnas duplicadas en el archivo.')

    def validar_mesas(self):
        """
        Valida que el número de mesa debe estar dentro del circuito y seccción indicados.
        Dichas validaciones se realizar revisando la info en la bd
        """
        # Obtener todos los combos diferentes de: número de mesa, circuito, sección, distrito para validar
        grupos_mesas = self.df.groupby(['seccion', 'circuito', 'nro de mesa', 'distrito'])
        mesa_circuito_seccion_distrito = list(mesa for mesa, grupo in grupos_mesas)
        for seccion, circuito, nro_de_mesa, distrito in mesa_circuito_seccion_distrito:
            try:
                match_mesa = Mesa.obtener_mesa_en_circuito_seccion_distrito(
                    nro_de_mesa, circuito, seccion, distrito)
            except Mesa.DoesNotExist:
                self.anadir_error(
                    f'No existe mesa {nro_de_mesa} en circuito {circuito}, sección {seccion} y '
                    f'distrito {distrito}.'
                )
                self.log_debug(f'No existe mesa {nro_de_mesa} en circuito {circuito}, sección {seccion} y '
                               f'distrito {distrito}.')
                continue
            self.mesas_matches[nro_de_mesa] = match_mesa
            self.mesas.append(match_mesa)

    def canonizar(self, valor):
        """
        Pasa a mayúsculas y elimina espacios.
        Si se trata de un número, elimina los ceros previos.
        """
        valor = valor.upper().strip()
        try:
            nro = int(valor)  # Esto elimina ceros.
            valor = str(nro)  # Y acá volvemos a string.
        except Exception as e:
            pass
        return valor

    def cargar_mesa(self, mesa, filas_de_la_mesa, columnas_categorias):
        self.log_debug(f"- Procesando mesa '{mesa}'.")
        try:
            # Obtengo la mesa correspondiente.
            mesa_bd = self.mesas_matches[mesa[2]]
        except KeyError:
            self.log_debug(f"-- Mesa {mesa} no tiene match.")
            # Si la mesa no existe no la importamos.
            # No acumulamos el error porque ya se hizo en la validación.
            return

        mesa_ok = True
        alguna_cat_ok = False
        for mesa_categoria in mesa_bd.mesacategoria_set.all():
            try:
                self.cargar_mesa_categoria(mesa, filas_de_la_mesa, mesa_categoria, columnas_categorias)
                alguna_cat_ok = True
                self.log_debug(f"-- {mesa_categoria.categoria} importada.")
            except ErroresAcumulados:
                # Es sólo para evitar el commit.
                mesa_ok = False
                self.log_debug(f"-- {mesa_categoria.categoria} no importada.")

        if mesa_ok:
            self.cant_mesas_importadas += 1
        elif alguna_cat_ok:
            self.cant_mesas_parcialmente_importadas += 1

    @transaction.atomic
    def cargar_mesa_categoria(self, mesa, filas_de_la_mesa, mesa_categoria, columnas_categorias):
        cant_errores_al_empezar = self.cant_errores

        carga_parcial, carga_total = self.carga_basica_mesa_categoria(mesa,
                filas_de_la_mesa, mesa_categoria, columnas_categorias)

        if carga_parcial:
            carga_total = self.copiar_carga_parcial_en_total(carga_parcial, carga_total)

        # A todas las cargas le tengo que agregar el total de electores y de sobres.
        self.agregar_electores_y_sobres(mesa, carga_parcial)
        self.agregar_electores_y_sobres(mesa, carga_total)

        if settings.OPCIONES_CARGAS_TOTALES_COMPLETAS and carga_total:
            self.log_debug("----+ Validando carga total.")
            # Si el flag de cargas totales está activo y hay carga total, entonces verificamos que estén
            # todas las opciones de la categoría en la carga total.
            self.validar_carga_total(mesa, carga_total, mesa_categoria.categoria)

        if carga_parcial:
            self.log_debug("----+ Validando carga parcial.")
            # Si se cargaron las cargas parciales, entonces verificamos que estén las opciones
            # prioritarias en la carga parcial.
            self.validar_carga_parcial(mesa, carga_parcial, mesa_categoria.categoria)

        self.borrar_carga_anterior(carga_parcial)
        self.borrar_carga_anterior(carga_total)

        if self.cant_errores > cant_errores_al_empezar:
            # Para que no se haga el commit.
            raise ErroresAcumulados()

    def borrar_carga_anterior(self, carga):
        """
        Si ya existía una carga de CSV para la misma mesa categoría, del mismo usuario,
        la borramos.
        """
        if not carga:
            return

        try:
            carga_previa = Carga.objects.get(
                id__lt=carga.id,  # Tiene que tener un id menor.
                tipo=carga.tipo,
                origen=Carga.SOURCES.csv,
                mesa_categoria=carga.mesa_categoria,
                fiscal=carga.fiscal,
            )
        except Carga.DoesNotExist:
            # No hay carga previa.
            return

        self.log_debug(f"----+ Borrando carga previa ({carga_previa.id}) de tipo {carga_previa.tipo}.")
        carga_previa.delete()

    def carga_basica_mesa_categoria(self, mesa, filas_de_la_mesa, mesa_categoria, columnas_categorias):
        """
        Realiza la carga correspondiente a una mesa y una categoría (sólo leer el archivo y generar
        los votos, no los análisis de completitud, etc).
        Devuelve la carga parcial y la total generadas.
        """
        categoria_bd = mesa_categoria.categoria
        categoria_general = categoria_bd.categoria_general
        self.log_debug(f"-- Procesando categoría '{categoria_bd}' (corresponde con '{categoria_general}').")

        self.carga_total = None
        self.carga_parcial = None
        self.cantidad_electores_mesa = None
        self.cantidad_sobres_mesa = None

        seccion, circuito, mesa, distrito = mesa

        # Buscamos el nombre de la columna asociada a esta categoría
        matcheos = [columna for columna in columnas_categorias if columna.lower()
                    in categoria_general.nombre.lower()]

        if len(matcheos) == 0:
            self.anadir_error(
                f'Faltan datos en el archivo de la siguiente '
                f'categoría: {categoria_general.nombre}.'
            )
            return None, None

        columna_de_la_categoria = matcheos[0]

        # Se encontró la categoría de la mesa en el archivo.
        votos_a_cargar = []
        # Los votos son por partido así que debemos iterar por todas las filas.
        for indice, fila in filas_de_la_mesa.iterrows():
            if indice == 0:
                # Me fijo si existe la columna de la categoría.
                try:
                    # Trato de acceder a la columna.
                    prueba = fila[columna_de_la_categoria]
                except KeyError:
                    self.anadir_error(
                        f'Faltan datos en el archivo de la siguiente '
                        f'categoría: {categoria_general.nombre}.'
                    )
                    return None, None

            codigo_lista_en_csv = fila['nro de lista']
            self.celda_analizada = CeldaCSVImporter(
                seccion, circuito, mesa, distrito, codigo_lista_en_csv, columna_de_la_categoria)

            # Primero chequeamos si esta fila corresponde a metadata verificando el
            # número de lista que está en cero cuando se trata de metadata.
            if codigo_lista_en_csv == '0':
                # Nos quedamos con la metadata.
                self.cantidad_electores_mesa = fila[COL_CANT_ELECTORES]
                self.cantidad_sobres_mesa = fila[COL_CANT_SOBRES]

            else:
                self.cargar_mesa_categoria_y_lista(
                    fila, codigo_lista_en_csv, columna_de_la_categoria, mesa_categoria, categoria_bd, votos_a_cargar)

        VotoMesaReportado.objects.bulk_create(votos_a_cargar)

        return self.carga_parcial, self.carga_total

    def cargar_mesa_categoria_y_lista(self, fila, codigo_lista_en_csv, columna_de_la_categoria, mesa_categoria, categoria_bd, votos_a_cargar):
        """
        Analiza los votos de una mesa dada, una categoría dada y una fila dada.
        """
        cantidad_votos = fila[columna_de_la_categoria]

        try:
            if self.dato_ausente(cantidad_votos):
                # La celda está vacía.
                return

            cantidad_votos = int(cantidad_votos)
            if cantidad_votos < 0:
                self.anadir_error(
                    f'Los resultados deben ser números enteros positivos. Revise la siguiente celda '
                    f'a {self.celda_analizada}.')
                return
        except ValueError:
            self.anadir_error(
                f'Los resultados deben ser números enteros positivos. Revise la siguiente celda '
                f'a {self.celda_analizada}.')
            return

        # Buscamos este nro de lista dentro de las opciones asociadas a
        # esta categoría.
        match_codigo_lista = [una_opcion for una_opcion in categoria_bd.opciones.all()
                              if una_opcion.codigo and una_opcion.codigo.strip().lower()
                              == codigo_lista_en_csv.strip().lower()]
        opcion_bd = match_codigo_lista[0] if len(match_codigo_lista) > 0 else None

        if not opcion_bd and cantidad_votos > 0:
            self.anadir_error(f'El número de lista {codigo_lista_en_csv} no fue '
                              f'encontrado asociado a la categoría '
                              f'{categoria_bd.nombre}, revise que sea '
                              f'el correcto ({self.celda_analizada}).')
            return
        elif not opcion_bd and cantidad_votos == 0:
            # Me están reportando cero votos para una opción no asociada a la categoría.
            # La ignoro.
            return

        opcion_categoria = opcion_bd.categoriaopcion_set.filter(
            categoria=categoria_bd
        ).first()
        self.cargar_votos(cantidad_votos, opcion_categoria, mesa_categoria,
                          opcion_bd, votos_a_cargar)

    def copiar_carga_parcial_en_total(self, carga_parcial, carga_total):
        """
        Esta función se encarga de copiar los votos de la carga parcial a la total
        si corresponde.
        """
        if not carga_total:
            return

        votos_a_cargar = []
        for voto_mesa_reportado_parcial in carga_parcial.reportados.all():
            votos_a_cargar.append(VotoMesaReportado(votos=voto_mesa_reportado_parcial.votos,
                                             opcion=voto_mesa_reportado_parcial.opcion, carga=carga_total))

        VotoMesaReportado.objects.bulk_create(votos_a_cargar)
        return carga_total

    def agregar_electores_y_sobres(self, mesa, carga):
        if not carga:
            return

        # XXX Ver qué hacemos con la cantidad de electores.
        # if self.dato_ausente(self.cantidad_electores_mesa):

        # Si no hay sobres no pasa nada.
        if self.dato_ausente(self.cantidad_sobres_mesa):
            return

        opcion_sobres = Opcion.sobres()

        cantidad_votos = int(self.cantidad_sobres_mesa)
        VotoMesaReportado.objects.create(carga=carga,
                                         votos=cantidad_votos,
                                         opcion=opcion_sobres
                                         )
        self.log_debug(f"---- Agregando {cantidad_votos} votos a {opcion_sobres} en carga {carga.tipo}.")

    def dato_ausente(self, dato):
        """
        Responde si un dato está o no presente, considerando las particularidades del parsing del CSV.
        """
        return not dato or math.isnan(float(dato))

    def cargar_info(self):
        """
        Carga la info del archivo CSV en la base de datos.
        Si hay errores, los reporta a través de excepciones cuando impiden continuar.
        Si no impiden continuar los acumula para reportarlos como strings todos juntos.
        """
        self.celda_analizada = None
        # La carga es por mesa y categoría, entonces nos conviene ir analizando grupos de mesas.
        grupos_mesas = self.df.groupby(['seccion', 'circuito', 'nro de mesa', 'distrito'])
        columnas_categorias = [i[0] for i in COLUMNAS_DEFAULT if i[1]]

        for mesa, filas_de_la_mesa in grupos_mesas:
            try:
                self.cargar_mesa(mesa, filas_de_la_mesa, columnas_categorias)
            except IntegrityError as e:
                if 'votomesareportado_votos_check' in str(e):
                    self.anadir_error(
                        f'Los resultados deben ser números positivos. Revise la celda correspondiente '
                        f'a {self.celda_analizada}.'
                    )
                elif 'duplicate key' in str(e):
                    self.anadir_error(
                        f'Hay partidos/listas repetidas. Revise la celda correspondiente '
                        f'a {self.celda_analizada}. Detalle: {e}'
                    )
                else:
                    self.anadir_error(
                        f'Error al guardar los resultados. Revise la celda correspondiente '
                        f'a {self.celda_analizada}. Detalle: {e}'
                    )
            except ValueError as e:
                self.anadir_error(
                    f'Revise que los datos de resultados sean numéricos. Revise la celda correspondiente '
                    f'a {self.celda_analizada}: {e}')
            except Exception as e:
                raise e

    def cargar_votos(self, cantidad_votos, opcion_categoria, mesa_categoria, opcion_bd, votos_a_cargar):
        if opcion_categoria.prioritaria:
            if not self.carga_parcial:
                self.carga_parcial = Carga.objects.create(
                    tipo=Carga.TIPOS.parcial,
                    origen=Carga.SOURCES.csv,
                    mesa_categoria=mesa_categoria,
                    fiscal=self.fiscal
                )
                self.log_debug("--- Creando carga parcial.")
            carga = self.carga_parcial
        else:
            if not self.carga_total:
                self.carga_total = Carga.objects.create(
                    tipo=Carga.TIPOS.total,
                    origen=Carga.SOURCES.csv,
                    mesa_categoria=mesa_categoria,
                    fiscal=self.fiscal
                )
                self.log_debug("--- Creando carga total.")
            carga = self.carga_total

        self.log_debug(f"---- Agregando {cantidad_votos} votos a {opcion_bd} en carga {carga.tipo}.")
        votos_a_cargar.append(VotoMesaReportado(carga=carga, votos=cantidad_votos, opcion=opcion_bd))

    def validar_usuario(self):
        try:
            self.fiscal = get_object_or_404(Fiscal, user=self.usuario)
        except Http404:
            raise PermisosInvalidosError('Fiscal no encontrado.')
        if not self.usuario or not self.usuario.fiscal.esta_en_grupo('unidades basicas'):
            raise PermisosInvalidosError('Su usuario no tiene los permisos necesarios para realizar '
                                         'esta acción.')

    def validar_carga(self, mesa, carga, categoria, es_parcial):
        """
        Valida que la carga tenga todas las opciones disponibles para votar en esa mesa.
        Si corresponde a una carga parcial se valida que estén las opciones correspondientes
        a las categorías prioritarias.
        Si es una carga total, se verifica que estén todas las opciones para esa mesa-cat.

        :param parcial: Booleano, sirve para describir si se quiere validar una carga parcial
        (correspondiente a los partidos prioritarios).
        :param categoria: Objeto de tipo Categoria que queremos verificar que esté completo.
        """
        opciones_de_la_categoria = categoria.opciones_actuales(
            solo_prioritarias=es_parcial, excluir_optativas=True
        ).values_list('id', flat=True)
        opciones_votadas = carga.listado_de_opciones()
        opciones_faltantes = set(opciones_de_la_categoria) - set(opciones_votadas)

        if len(opciones_faltantes) > 0:
            nombres_opciones_faltantes = list(Opcion.objects.filter(
                id__in=opciones_faltantes).values_list('nombre', flat=True))
            tipo_carga = "parcial" if es_parcial else "total"
            self.anadir_error(
                f'Los resultados para la carga {tipo_carga} de la categoría {categoria.categoria_general} '
                f'deben estar completos. '
                f'Faltan las opciones: {nombres_opciones_faltantes} en la mesa {mesa}.')

    def validar_carga_parcial(self, mesa, carga_parcial, categoria):
        self.validar_carga(mesa, carga_parcial, categoria, True)

    def validar_carga_total(self, mesa, carga_total, categoria):
        self.validar_carga(mesa, carga_total, categoria, False)


class CeldaCSVImporter:
    def __init__(self, seccion, circuito, mesa, distrito, codigo_lista, columna):
        self.mesa = mesa
        self.seccion = seccion
        self.circuito = circuito
        self.distrito = distrito
        self.codigo_lista = codigo_lista
        self.columna = columna

    def __str__(self):
        return (
            f"Mesa: {self.mesa} - sección: {self.seccion} - circuito: {self.circuito} - "
            f"distrito: {self.distrito} - lista: {self.codigo_lista} - columna: {self.columna}"
        )
