import pandas as pd

from elecciones.models import Mesa

# TODO chequear si es importante buscar matches parciales ej: seccion en vez de Sección
COLUMNAS_DEFAULT = ['Sección', 'Circuito', 'Nro de mesa', 'Nro de lista', 'Senadores Nacionales',
                    'Diputados Nacionales', 'Senadores Provinciales', 'Diputados Provinciales',
                    'Concejales y Consejeros Escolares', 'Cantidad de electores del padrón',
                    'Cantidad de sobres en la urna', 'Acta arreglada']


# Excepciones custom, por si se quieren manejar
class CSVImportacionError(Exception):
    pass


class FormatoArchivoInvalidoError(CSVImportacionError):
    pass


class FaltanColumnasError(CSVImportacionError):
    pass


class DatosInvalidosError(CSVImportacionError):
    pass


class CSVImporter:
    """
    Permite subir un csv y validar la info que contiene

    """

    # TODO va a ser más útil que reciba un path
    def procesar_archivo(self, archivo):
        # validar la info del archivo
        try:
            df = pd.read_csv(archivo)
            # validar la existencia de los headers mandatorios
            todas_las_columnas = all(elem in df.columns for elem in COLUMNAS_DEFAULT)
            if not todas_las_columnas:
                raise FaltanColumnasError('Faltan columnas en el archivo')

            # Validar que el  número de mesa debe estar dentro del circuito indicado.
            # Obtener todos los combos diferentes de: numero de mesa, circuito, seccion para validar
            mesas_unicas = df.groupby(['Sección', 'Circuito', 'Nro de mesa'])
            # validar que existan las mesas
            self.validar_mesas(mesas_unicas.groups)

        except CSVImportacionError as e:
            raise e
        # para manejar cualquier otro tipo de error
        except Exception:
            raise FormatoArchivoInvalidoError('No es un csv válido')

    def validar_mesas(self, mesas_unicas):
        for mesa in mesas_unicas:
            existe = Mesa.existe_mesa_en_circuito_seccion(mesa[2], mesa[1], mesa[0])
            if not existe:
                raise DatosInvalidosError(f'No existe mesa: {mesa[2]} en circuito: {mesa[1]} y sección: {mesa[0]}')
