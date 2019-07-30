import pandas as pd
from django.http import Http404
from django.shortcuts import get_object_or_404
import math
from elecciones.models import Mesa, Carga, VotoMesaReportado, Opcion, CategoriaOpcion
from django.db import transaction
from django.db.utils import IntegrityError

from escrutinio_social import settings
from escrutinio_social.settings import OPCION_TOTAL_SOBRES, OPCION_TOTAL_VOTOS
from fiscales.models import Fiscal

# Primer dato: nombre de la columna, segundo: si es parte de una categoría o no.
COLUMNAS_DEFAULT = [('seccion', False), ('distrito', False), ('circuito', False), ('nro de mesa', False),
                    ('nro de lista', False), ('presidente y vice', True), ('gobernador y vice', True),
                    ('senadores nacionales', True), ('diputados nacionales', True),
                    ('senadores provinciales', True),
                    ('diputados provinciales', True),
                    ('intendentes, concejales y consejeros escolares', True),
                    ('cantidad de electores del padron', False), ('cantidad de sobres en la urna', False)]


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


"""
Clase encargada de procesar un archivo CSV y validarlo
Recibe por parámetro el file o path al file y el usuario que sube el archivo
"""


class CSVImporter:

    def __init__(self, archivo, usuario):
        self.archivo = archivo
        self.df = pd.read_csv(self.archivo, na_values=["n/a", "na", "-"], dtype=str)
        self.usuario = usuario
        self.fiscal = None
        self.mesas = []
        self.mesas_matches = {}
        self.carga_total = None
        self.carga_parcial = None

    def procesar(self):
        self.validar()
        self.cargar_info()

    def validar(self):
        """
        Permite validar la info que contiene un archivos CSV
        Validaciones:
            - Existencia de ciertas columnas
            - Columnas no duplicadas
            - Tipos de datos
            - De negocio: que la mesa + circuito + sección + distrito existan en la bd

        """
        try:
            self.validar_usuario()
            self.validar_columnas()
            self.validar_mesas()

        except PermisosInvalidosError as e:
            raise e

        except CSVImportacionError as e:
            raise e
        # para manejar cualquier otro tipo de error
        # except Exception as e:
        #     raise FormatoArchivoInvalidoError('No es un CSV válido.')

    def validar_columnas(self):
        """
        Valida que estén las columnas en el archivo y que no hayan columnas repetidas.
        """
        headers = list(elem[0] for elem in COLUMNAS_DEFAULT)
        # normalizar las columnas para evitar comparaciones con espacios/acentos
        self.df.columns = self.df.columns.str.strip().str.lower().str.replace('ó', 'o')
        # validar la existencia de los headers mandatorios
        todas_las_columnas = all(elem in self.df.columns for elem in headers)
        if not todas_las_columnas:
            faltantes = [columna for columna in headers if columna not in self.df.columns]
            raise ColumnasInvalidasError(f'Faltan las columnas: {faltantes} en el archivo.')
        # las columnas duplicadas en Panda se especifican como ‘X’, ‘X.1’, …’X.N’
        columnas_candidatas = [columna.replace('.1', '') for columna in self.df.columns
                               if columna.endswith('.1')]
        columnas_duplicadas = any(elem in columnas_candidatas for elem in headers)
        if columnas_duplicadas:
            raise ColumnasInvalidasError('Hay columnas duplicadas en el archivo.')

    def validar_mesas(self):
        """
        Valida que el número de mesa debe estar dentro del circuito y secccion indicados.
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
                raise DatosInvalidosError(
                    f'No existe mesa {nro_de_mesa} en circuito {circuito}, sección {seccion} y '
                    f'distrito {distrito}.')
            self.mesas_matches[nro_de_mesa] = match_mesa
            self.mesas.append(match_mesa)

    def cargar_mesa_categoria(self, mesa, filas_de_la_mesa, mesa_categoria, columnas_categorias):
        """
        Realiza la carga correspondiente a una mesa y una categoría.
        Devuelve la carga parcial y la total generadas.
        """
        categoria_bd = mesa_categoria.categoria

        self.carga_total = None
        self.carga_parcial = None
        seccion, circuito, mesa, distrito = mesa

        # Buscamos el nombre de la columna asociada a esta categoría
        matcheos = [columna for columna in columnas_categorias if columna.lower()
                    in categoria_bd.nombre.lower()]

        if len(matcheos) == 0:
            raise DatosInvalidosError(f'Faltan datos en el archivo de la siguiente '
                                      f'categoría: {categoria_bd.nombre}.')

        # Se encontró la categoría de la mesa en el archivo.
        columna_de_la_categoria = matcheos[0]
        # Los votos son por partido así que debemos iterar por todas las filas
        for indice, fila in filas_de_la_mesa.iterrows():
            codigo_lista_en_csv = fila['nro de lista']
            self.celda_analizada = CeldaCSVImporter(
                seccion, circuito, mesa, distrito, codigo_lista_en_csv, columna_de_la_categoria)

            # Primero chequeamos si esta fila corresponde a metadata verificando el
            # número de lista que está en cero cuando se trata de metadata.
            if codigo_lista_en_csv == '0':
                # Nos quedamos con la metadata.
                self.cantidad_electores_mesa = fila['cantidad de electores del padron']
                self.cantidad_sobres_mesa = fila['cantidad de sobres en la urna']

            else:
                cantidad_votos = fila[columna_de_la_categoria]

                if self.dato_ausente(cantidad_votos):
                    # La celda está vacía.
                    continue

                try:
                    cantidad_votos = int(cantidad_votos)
                except ValueError:
                    raise DatosInvalidosError(
                        f'Los resultados deben ser números positivos. Revise la siguiente celda '
                        f'a {self.celda_analizada}.')

                # Buscamos este nro de lista dentro de las opciones asociadas a
                # esta categoría.
                match_codigo_lista = [una_opcion for una_opcion in categoria_bd.opciones.all()
                                      if una_opcion.codigo and una_opcion.codigo.strip().lower()
                                      == codigo_lista_en_csv.strip().lower()]
                opcion_bd = match_codigo_lista[0] if len(match_codigo_lista) > 0 else None
                if not opcion_bd:
                    raise DatosInvalidosError(f'El número de lista {codigo_lista_en_csv} no fue '
                                              f'encontrado asociado la categoría '
                                              f'{categoria_bd.nombre}, revise que sea '
                                              f'el correcto.')
                opcion_categoria = opcion_bd.categoriaopcion_set. \
                    filter(categoria=categoria_bd).first()
                self.cargar_votos(cantidad_votos, opcion_categoria, mesa_categoria,
                                  opcion_bd)

        return self.carga_parcial, self.carga_total

    def copiar_carga_parcial_en_total(self, carga_parcial, carga_total):
        """
        Esta función se encarga de copiar los votos de la carga parcial a la total
        si corresponde.
        """
        if not carga_total:
            carga_total = Carga.objects.create(
                tipo=Carga.TIPOS.total,
                origen=Carga.SOURCES.csv,
                mesa_categoria=carga_parcial.mesa_categoria,
                fiscal=self.fiscal
            )

        for voto_mesa_reportado_parcial in carga_parcial.reportados.all():
            voto_mesa_reportado_total = VotoMesaReportado.objects.create(
                votos=voto_mesa_reportado_parcial.votos,
                opcion=voto_mesa_reportado_parcial.opcion,
                carga=carga_total
            )

        return carga_total

    def cargar_mesa(self, mesa, filas_de_la_mesa, columnas_categorias):
        # Obtengo la mesa correspondiente.
        mesa_bd = self.mesas_matches[mesa[2]]
        self.cantidad_electores_mesa = None
        self.cantidad_sobres_mesa = None

        # Vamos a acumular las cargas.
        cargas = []

        # Analizo por categoria-mesa, y por cada categoria-mesa, todos los partidos posibles
        for mesa_categoria in mesa_bd.mesacategoria_set.all():
            cargas.append((mesa_categoria.categoria,
                           self.cargar_mesa_categoria(mesa, filas_de_la_mesa, mesa_categoria,
                                                      columnas_categorias)))

        # Esto lo puedo hacer recién acá porque tengo que iterar por todas las "categorías" primero
        # para encontrar la de la metadata.
        for categoria, (carga_parcial, carga_total) in cargas:
            # A todas las cargas le tengo que agregar el total de votantes y de sobres.
            self.agregar_total_de_votantes_y_sobres(mesa, carga_parcial)

            if carga_parcial:
                self.validar_carga_parcial(categoria, carga_parcial)

            # Si tengo que verificar entonces veo que las cargas totales sean completas.
            if settings.TOTALES_COMPLETAS and carga_total:
                self.validar_carga_total(categoria, carga_total)

            if carga_parcial:
                carga_total = self.copiar_carga_parcial_en_total(carga_parcial, carga_total)

    def agregar_total_de_votantes_y_sobres(self, mesa, carga_parcial):
        if not carga_parcial:
            return

        if self.dato_ausente(self.cantidad_electores_mesa):
            raise DatosInvalidosError(f'Falta el reporte de total de votantes para la mesa {mesa}.')

        opcion_total_votos = carga_parcial.mesa_categoria.categoria.get_opcion_total_votos()
        VotoMesaReportado.objects.create(carga=carga_parcial,
                                         votos=int(self.cantidad_electores_mesa),
                                         opcion=opcion_total_votos
                                         )

        # Si no hay sobres no pasa nada.
        if self.dato_ausente(self.cantidad_sobres_mesa):
            return

        opcion_sobres = carga_parcial.mesa_categoria.categoria.get_opcion_total_sobres()
        VotoMesaReportado.objects.create(carga=carga_parcial,
                                         votos=int(self.cantidad_sobres_mesa),
                                         opcion=opcion_sobres
                                         )

    def dato_ausente(self, dato):
        """
        Responde si un dato está o no presente, considerando las particularidades del parsing del CSV.
        """
        return not dato or math.isnan(float(dato))

    def cargar_info(self):
        """
        Carga la info del archivo CSV en la base de datos.
        Si hay errores, los reporta a través de excepciones.
        """
        self.celda_analizada = None
        # se guardan los datos: El contenedor `carga` y los votos del archivo
        # la carga es por mesa y categoría entonces nos conviene ir analizando grupos de mesas
        grupos_mesas = self.df.groupby(['seccion', 'circuito', 'nro de mesa', 'distrito'])
        columnas_categorias = [i[0] for i in COLUMNAS_DEFAULT if i[1]]

        try:
            with transaction.atomic():

                for mesa, filas_de_la_mesa in grupos_mesas:
                    self.cargar_mesa(mesa, filas_de_la_mesa, columnas_categorias)

        except IntegrityError as e:
            # fixme ver mejor forma de manejar estos errores
            if 'votomesareportado_votos_check' in str(e):
                raise DatosInvalidosError(
                    f'Los resultados deben ser números positivos. Revise la celda correspondiente '
                    f'a {self.celda_analizada}.')
            raise DatosInvalidosError(f'Error al guardar los resultados. Revise la celda correspondiente '
                                      f'a {self.celda_analizada}.')
        except ValueError as e:
            raise DatosInvalidosError(
                f'Revise que los datos de resultados sean numéricos. Revise la celda correspondiente '
                f'a {self.celda_analizada}: {e}')
        except Exception as e:
            raise e

    def cargar_votos(self, cantidad_votos, opcion_categoria, mesa_categoria, opcion_bd):
        if opcion_categoria.prioritaria:
            if not self.carga_parcial:
                self.carga_parcial = Carga.objects.create(
                    tipo=Carga.TIPOS.parcial,
                    origen=Carga.SOURCES.csv,
                    mesa_categoria=mesa_categoria,
                    fiscal=self.fiscal
                )
            carga = self.carga_parcial
        else:
            if not self.carga_total:
                self.carga_total = Carga.objects.create(
                    tipo=Carga.TIPOS.total,
                    origen=Carga.SOURCES.csv,
                    mesa_categoria=mesa_categoria,
                    fiscal=self.fiscal
                )
            carga = self.carga_total
        print(carga, opcion_bd)
        VotoMesaReportado.objects.create(carga=carga, votos=cantidad_votos, opcion=opcion_bd)

    def validar_usuario(self):
        try:
            self.fiscal = get_object_or_404(Fiscal, user=self.usuario)
        except Http404:
            raise PermisosInvalidosError('Fiscal no encontrado.')
        if not self.usuario or not self.usuario.fiscal.esta_en_grupo('unidades basicas'):
            raise PermisosInvalidosError('Su usuario no tiene los permisos necesarios para realizar '
                                         'esta acción.')

    def validar_carga(self, carga, categoria, parcial):
        opciones_votadas = carga.listado_de_opciones()
        mi_categoria = carga.categoria
        opciones_de_la_categoria = CategoriaOpcion.objects.filter(categoria=mi_categoria,
                                                                  prioritaria=parcial
                                                                  ).values_list('opcion__id', flat=True)
        opciones_faltantes = set(opciones_de_la_categoria) - set(opciones_votadas)
        if opciones_faltantes != set():
            nombres_opciones_faltantes = Opcion.objects.filter(
                id__in=opciones_faltantes).values_list('nombre', flat=True)
            raise DatosInvalidosError(
                f'Los resultados para las opciones parciales para la categoría {categoria} '
                f'deben estar completos. '
                f'Faltan las opciones: {nombres_opciones_faltantes}.')

    def validar_carga_parcial(self, categoria, carga_parcial):
        self.validar_carga(carga_parcial, categoria, parcial=True)

    def validar_carga_total(self, categoria, carga_total):
        self.validar_carga(carga_total, categoria, parcial=False)


class CeldaCSVImporter:
    def __init__(self, seccion, circuito, mesa, distrito, codigo_lista, columna):
        self.mesa = mesa
        self.seccion = seccion
        self.circuito = circuito
        self.distrito = distrito
        self.codigo_lista = codigo_lista
        self.columna = columna

    def __str__(self):
        return f"Mesa: {self.mesa} - sección: {self.seccion} - circuito: {self.circuito} - " \
            f"distrito: {self.distrito} - lista: {self.codigo_lista} - columna: {self.columna}"
