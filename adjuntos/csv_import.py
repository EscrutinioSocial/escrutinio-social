import pandas as pd
from django.shortcuts import get_object_or_404

from elecciones.models import Mesa, Carga, VotoMesaReportado
from django.db import IntegrityError, transaction
from fiscales.models import Fiscal

COLUMNAS_DEFAULT = [('seccion', False), ('distrito', False), ('circuito', False), ('nro de mesa', False),
                    ('nro de lista', False), ('presidente y vice', True), ('gobernador y vice', True),
                    ('senadores nacionales', True), ('diputados nacionales', True), ('legisladores provinciales', True),
                    ('senadores provinciales', True), ('diputados provinciales', True),
                    ('intendentes, concejales y consejeros escolares', True),
                    ('cantidad de electores del padron', False), ('cantidad de sobres en la urna', False),
                    ('acta arreglada', False)]


# Excepciones custom, por si se quieren manejar
class CSVImportacionError(Exception):
    pass


class FormatoArchivoInvalidoError(CSVImportacionError):
    pass


class ColumnasInvalidasError(CSVImportacionError):
    pass


class DatosInvalidosError(CSVImportacionError):
    pass


"""
Clase encargada de procesar un archivo CSV y validarlo
Recibe  por parámetro el file o path al file y el usuario que sube el archivo
"""


class CSVImporter:

    def __init__(self, archivo, usuario):
        self.archivo = archivo
        self.df = pd.read_csv(self.archivo, na_values=["n/a", "na", "-"])
        self.usuario = usuario
        self.mesas = []
        self.mesas_matches = {}

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
            - De negocio: que la mesa + circuito + seccion existan en la bd

        """
        try:
            self.validar_columnas()
            self.validar_mesas()

        except CSVImportacionError as e:
            raise e
        # para manejar cualquier otro tipo de error
        except Exception as e:
            print(str(e))
            raise FormatoArchivoInvalidoError('No es un csv válido')

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
            faltantes = list(filter(lambda x: x not in self.df.columns, headers))
            raise ColumnasInvalidasError(f'Faltan las columnas: {faltantes} en el archivo')
        # las columnas duplicadas en Panda se especifican como ‘X’, ‘X.1’, …’X.N’
        columnas_candidatas = list(
            map(lambda x: x.replace('.1', ''), filter(lambda x: x.endswith('.1'), self.df.columns)))
        columnas_duplicadas = any(elem in columnas_candidatas for elem in headers)
        if columnas_duplicadas:
            raise ColumnasInvalidasError('Hay columnas duplicadas en el archivo')

    def validar_mesas(self):
        """
        Valida que el  número de mesa debe estar dentro del circuito y secccion indicados.
        Dichas validaciones se realizar revisando la info en la bd
        """
        # Obtener todos los combos diferentes de: numero de mesa, circuito, seccion, distrito para validar
        grupos_mesas = self.df.groupby(['seccion', 'circuito', 'nro de mesa', 'distrito'])
        mesa_circuito_seccion_distrito = list(mesa for mesa, grupo in grupos_mesas)

        for mesa in mesa_circuito_seccion_distrito:
            try:
                match_mesa = Mesa.obtener_mesa_en_circuito_seccion_distrito(mesa[2], mesa[1], mesa[0], mesa[3])
            except Mesa.DoesNotExist:
                raise DatosInvalidosError(
                    f'No existe mesa: {mesa[2]} en circuito: {mesa[1]}, sección: {mesa[0]} y distrito: {mesa[3]}')
            self.mesas_matches[mesa] = match_mesa
            self.mesas.append(match_mesa)

    def cargar_info(self):
        """
        Carga la info del archivo csv en la base de datos.
        Si hay errores, los reporta a traves de excepciones
        """
        try:
            with transaction.atomic():
                fiscal = get_object_or_404(Fiscal, user=self.usuario)
                # se guardan los datos. El contenedor `carga` y los votos del archivo
                # la carga es por mesa y categoria entonces nos conviene ir analizando grupos de mesas
                grupos_mesas = self.df.groupby(['seccion', 'circuito', 'nro de mesa', 'distrito'])
                columnas_categorias = list(map(lambda x: x[0], filter(lambda x: x[1], COLUMNAS_DEFAULT)))
                for mesa, grupos in grupos_mesas:
                    # obtengo la mesa correspondiente
                    mesa_bd = self.mesas_matches[mesa]
                    # Analizo por categoria, y por cada categoria, todos los partidos posibles
                    # TODO ver tema performance
                    for mesa_categoria in mesa_bd.mesacategoria_set.all():
                        carga = Carga.objects.create(
                            status=Carga.STATUS.total,
                            origen=Carga.SOURCES.csv,
                            mesa_categoria=mesa_categoria,
                            fiscal=fiscal
                        )
                        # buscamos el nombre de la columna asociada a esta categoria
                        matcheos = list(
                            columna for columna in columnas_categorias if columna.lower() in mesa_categoria.categoria.nombre.lower())
                        # TODO: Importa controlar el no matcheo? puedo tirar excepcion
                        if len(matcheos) != 0:
                            mesa_columna = matcheos[0]
                            # los votos son por partido así que debemos iterar por todas las filas
                            for indice, fila in grupos.iterrows():
                                cantidad_votos = fila[mesa_columna]
                                opcion = fila['nro de lista']
                                # TODO: Bocha de dudas con esta parte donde tengo que cargar la opcion,
                                #  no se con que mapea el Nrolista
                                votos = VotoMesaReportado(carga=carga, votos=cantidad_votos)
                                votos.save()


        except Exception as e:
            print(e)
            raise e
        except IntegrityError as e:
            print(e)
