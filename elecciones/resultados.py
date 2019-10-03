from django.conf import settings
from functools import lru_cache
from attrdict import AttrDict
from collections import OrderedDict
from .models import (
    Opcion,
    OPCIONES_A_CONSIDERAR,
)


def porcentaje(numerador, denominador):
    """
    Expresa la razón numerador/denominador como un string correspondiente
    al porcentaje con 2 dígitos decimales.
    Si no puede calcularse, devuelve '-'.

    """
    if denominador and denominador > 0:
        return f'{numerador*100/denominador:.2f}'
    return '-'


def porcentaje_numerico(parcial, total):
    """
    Función utilitaria para el cálculo de un porcentaje, así se hace igual en todos lados
    """
    return 0 if total == 0 else round((parcial * 100) / total, 2)


class ResultadosBase():
    """
    Clase base para el comportamiento común entre los resultados de una sumarización / proyección y 
    la sumatoria de muchos resultados en un ResultadoCombinado
    """
    def __init__(self, resultados):
        print("---- Creating ", self, "----")
        self.resultados = resultados

    def data(self):
        """
        Devuelve los datos de resultados 'crudos' para permitir que los distintos sumarizadores
        pasen información al template directamente sin obligar a que esta clase oficie de pasamanos.
        """
        return dict(self.resultados)

    def __str__(self):
        return f"Resultados: ({self.tabla_positivos}, {self.tabla_no_positivos})"

    @lru_cache(128)
    def tabla_positivos(self):
        """
        Devuelve toda la información sobre los votos positivos para mostrar.
        Para cada partido incluye:
            - votos: total de votos del partido
            - detalle: los votos de cada opción dentro del partido (recordar que
              es una PASO).
                Para cada opción incluye:
                    - votos: cantidad de votos para esta opción.
                    - porcentaje: porcentaje sobre el total del del partido.
                    - porcentaje_positivos: porcentaje sobre el total de votos
                      positivos.
                    - porcentaje_validos: porcentaje sobre el total de votos
                      positivos y en blanco.
                    - porcentaje_total: porcentaje sobre el total de votos.
        """
        votos_positivos = {}
        blancos = self.total_blancos() if self.total_blancos() != '-' else 0
        for partido, votos_por_opcion in self.resultados.votos_positivos.items():
            total_partido = sum(filter(None, votos_por_opcion.values()))
            votos_positivos[partido] = {
                'votos': total_partido,
                'porcentaje_positivos': porcentaje(total_partido, self.total_positivos()),
                'porcentaje_validos': porcentaje(total_partido, self.total_positivos() + blancos),
                'porcentaje_total': porcentaje(total_partido, self.votantes()),
                'detalle': {
                    opcion: {
                        'votos': votos_opcion,
                        'porcentaje': porcentaje(votos_opcion, total_partido),
                        'porcentaje_positivos': porcentaje(votos_opcion, self.total_positivos()),
                        'porcentaje_validos': porcentaje(votos_opcion, self.total_positivos() + blancos),
                        'porcentaje_total': porcentaje(votos_opcion, self.votantes()),
                    }
                    for opcion, votos_opcion in votos_por_opcion.items()
                }
            }

        return OrderedDict(
            sorted(votos_positivos.items(), key=lambda partido: float(partido[1]["votos"]), reverse=True)
        )

    @lru_cache(128)
    def tabla_no_positivos(self):
        """
        Devuelve un diccionario con la cantidad de votos para cada una de las opciones no positivas.
        Incluye a todos los positivos agrupados como una única opción adicional.
        También incluye porcentajes calculados sobre el total de votos de la mesa.
        """
        # TODO Falta un criterio de ordenamiento para las opciones no positivas.
        tabla_no_positivos = {
            nombre_opcion: {
                "votos": votos,
                "porcentaje_total": porcentaje(votos, self.votantes())
            }
            for nombre_opcion, votos in self.resultados.votos_no_positivos.items()
        }

        # Esta key es especial porque la vista la muestra directamente en pantalla.
        tabla_no_positivos[settings.KEY_VOTOS_POSITIVOS] = {
            "votos": self.total_positivos(),
            "porcentaje_total": porcentaje(self.total_positivos(), self.votantes())
        }

        return tabla_no_positivos

    @lru_cache(128)
    def votantes(self):
        """
        Total de personas que votaron.
        """
        return self.total_positivos() + self.total_no_positivos()

    def electores(self):
        return self.resultados.electores

    def electores_en_mesas_escrutadas(self):
        return self.resultados.electores_en_mesas_escrutadas

    def porcentaje_mesas_escrutadas(self):
        return porcentaje(self.total_mesas_escrutadas(), self.total_mesas())

    def porcentaje_escrutado(self):
        return porcentaje(self.resultados.electores_en_mesas_escrutadas, self.resultados.electores)

    def porcentaje_participacion(self):
        return porcentaje(self.votantes(), self.resultados.electores_en_mesas_escrutadas)

    def total_mesas_escrutadas(self):
        return self.resultados.total_mesas_escrutadas

    def total_mesas(self):
        return self.resultados.total_mesas

    def total_blancos(self):
        return self.resultados.votos_no_positivos.get(settings.OPCION_BLANCOS['nombre_corto'], '-')

    def total_nulos(self):
        return self.resultados.votos_no_positivos.get(settings.OPCION_NULOS['nombre_corto'], '-')

    def total_votos(self):
        return self.resultados.votos_no_positivos.get(settings.OPCION_TOTAL_VOTOS['nombre_corto'], '-')

    def total_sobres(self):
        return self.resultados.votos_no_positivos.get(settings.OPCION_TOTAL_SOBRES['nombre_corto'], '-')

    def porcentaje_positivos(self):
        return porcentaje(self.total_positivos(), self.votantes())

    def porcentaje_blancos(self):
        blancos = self.total_blancos()
        return porcentaje(blancos, self.votantes()) if blancos != '-' else '-'

    def porcentaje_nulos(self):
        nulos = self.total_nulos()
        return porcentaje(nulos, self.votantes()) if nulos != '-' else '-'


class Resultados(ResultadosBase):
    """
    Esta clase contiene los resultados de una sumarización o proyección.
    """

    def __init__(self, opciones_a_considerar, resultados):
        super().__init__(resultados)
        self.opciones_a_considerar = opciones_a_considerar

    @lru_cache(128)
    def total_positivos(self):
        """
        Devuelve el total de votos positivos, sumando los votos de cada una de las opciones de cada partido
        en el caso self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas.

        En el caso self.self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.prioritarias
        obtiene la opción de total
        """
        if self.opciones_a_considerar == OPCIONES_A_CONSIDERAR.todas:
            total_positivos = sum(
                sum(votos for votos in opciones_partido.values() if votos)
                for opciones_partido in self.resultados.votos_positivos.values()
            )
        else:
            nombre_opcion_total = Opcion.total_votos().nombre_corto
            total = self.resultados.votos_no_positivos[nombre_opcion_total]
            total_no_positivos = self.total_no_positivos()
            total_positivos = max(total - total_no_positivos, 0)

        return total_positivos

    @lru_cache(128)
    def total_no_positivos(self):
        """
        Devuelve el total de votos no positivos, sumando los votos a cada opción no partidaria
        y excluyendo la opción que corresponde a totales (como el total de votantes o de sobres).
        """
        nombre_opcion_total = Opcion.total_votos().nombre_corto
        nombre_opcion_sobres = Opcion.sobres().nombre_corto
        return sum(
            votos for opcion, votos in self.resultados.votos_no_positivos.items()
            if opcion not in (nombre_opcion_total, nombre_opcion_sobres)
        )


class ResultadoCombinado(ResultadosBase):
    _total_positivos = 0
    _total_no_positivos = 0

    def __init__(self):
        super().__init__(AttrDict({
            'total_mesas': 0,
            'total_mesas_escrutadas': 0,
            'electores': 0,
            'electores_en_mesas_escrutadas': 0,
            'votos_positivos': {},

            'votos_no_positivos': {opcion['nombre_corto']: 0 for opcion in [
                settings.OPCION_BLANCOS,
                settings.OPCION_NULOS,
                settings.OPCION_TOTAL_VOTOS,
                settings.OPCION_TOTAL_SOBRES,
            ]}
        }))

    def __add__(self, other):
        self._total_positivos += other.total_positivos()
        self._total_no_positivos += other.total_no_positivos()

        # Sumar los votos no positivos
        self.resultados.votos_no_positivos = {
            key: value + other.resultados.votos_no_positivos.get(key, 0)
            for key, value in self.resultados.votos_no_positivos.items()
        }

        self.resultados.votos_positivos = {
            partido: {
                opcion: votos_opcion + self.resultados.votos_positivos.get(partido, {}).get(opcion, 0)
                for opcion, votos_opcion in votos_partido.items()
            }
            for partido, votos_partido in other.resultados.votos_positivos.items()
        }
        print(self.resultados.votos_positivos)

        # Sumar el resto de los atributos en resultados
        for attr in ['total_mesas', 'total_mesas_escrutadas', 'electores', 'electores_en_mesas_escrutadas']:
            self.resultados[attr] += other.resultados[attr]

        # TODO falta pasar agrupaciones no consideradas

        return self

    def total_positivos(self):
        return self._total_positivos

    def total_no_positivos(self):
        return self._total_no_positivos



