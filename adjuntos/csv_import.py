import pandas as pd

from elecciones.models import Mesa

# TODO chequear si es importante buscar matches parciales ej: seccion en vez de Sección
# Mapeo entre columnas y sus tipos para poder validar
COLUMNAS_DEFAULT = [('Sección', None), ('Circuito', None), ('Nro de mesa', None), ('Nro de lista', None),
                    ('Senadores Nacionales', int), ('Diputados Nacionales', int), ('Senadores Provinciales', int),
                    ('Diputados Provinciales', int), ('Concejales y Consejeros Escolares', int),
                    ('Cantidad de electores del padrón', int), ('Cantidad de sobres en la urna', int),
                    ('Acta arreglada', bool)]


# Excepciones custom, por si se quieren manejar
class CSVImportacionError(Exception):
    pass


class FormatoArchivoInvalidoError(CSVImportacionError):
    pass


class ColumnasInvalidasError(CSVImportacionError):
    pass


class DatosInvalidosError(CSVImportacionError):
    pass


class CSVImporter:

    # TODO va a ser más útil que reciba un path
    def validar_archivo(self, archivo):
        """
        Permite validar la info que contiene un archivos CSV
        Validaciones:
            - Existencia de ciertas columnas
            - Columnas no duplicadas
            - Tipos de datos
            - De negocio: que la mesa + circuito + seccion existan en la bd

        """
        try:
            valores_vacios = ["n/a", "na", "-"]
            df = pd.read_csv(archivo, na_values=valores_vacios)
            self.validar_columnas(df)
            self.validar_tipos_de_datos(df)
            self.validar_mesas(df)

        except CSVImportacionError as e:
            raise e
        # para manejar cualquier otro tipo de error
        except Exception as e:
            print(str(e))
            raise FormatoArchivoInvalidoError('No es un csv válido')

    def validar_tipos_de_datos(self, df):
        """
        Valida que las columnas tengan valores del tipo esperado, por ahora solo se validan la enteras y positivas
        para las cantidades de votos
        """
        # Validar que los tipos de datos sean correctos
        columnas_numericas = list(map(lambda x: x[0], filter(lambda x: x[1] == int, COLUMNAS_DEFAULT)))
        for columna in columnas_numericas:
            no_vacios = filter(lambda x: pd.notna(x), df[columna])
            columnas_numericas_validas = all(isinstance(valor, float) and valor.is_integer() and valor > 0 for valor in no_vacios)
            if not columnas_numericas_validas:
                raise ColumnasInvalidasError('Hay columnas con valores no numéricos')

    def validar_columnas(self, df):
        """
        Valida que estén las columnas en el archivo y que no hayan columnas repetidas.
        """
        headers = (elem[0] for elem in COLUMNAS_DEFAULT)
        # validar la existencia de los headers mandatorios
        todas_las_columnas = all(elem in df.columns for elem in headers)
        if not todas_las_columnas:
            faltantes = list(filter(lambda x: x not in df.columns, headers))
            raise ColumnasInvalidasError(f'Faltan las columnas: {faltantes} en el archivo')
        # las columnas duplicadas en Panda se especifican como ‘X’, ‘X.1’, …’X.N’
        columnas_candidatas = list(map(lambda x: x.replace('.1', ''), filter(lambda x: x.endswith('.1'), df.columns)))
        columnas_duplicadas = any(elem in columnas_candidatas for elem in headers)
        if columnas_duplicadas:
            raise ColumnasInvalidasError('Hay columnas duplicadas en el archivo')

    def validar_mesas(self, df):
        """
        Valida que el  número de mesa debe estar dentro del circuito y secccion indicados.
        Dichas validaciones se realizar revisando la info en la bd
        """

        # Obtener todos los combos diferentes de: numero de mesa, circuito, seccion para validar
        grupos_mesas = df.groupby(['Sección', 'Circuito', 'Nro de mesa'])
        for mesa, grupo in grupos_mesas:
            existe = Mesa.existe_mesa_en_circuito_seccion(mesa[2], mesa[1], mesa[0])
            if not existe:
                raise DatosInvalidosError(f'No existe mesa: {mesa[2]} en circuito: {mesa[1]} y sección: {mesa[0]}')
