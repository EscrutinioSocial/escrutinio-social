import math

from django.core.management.base import BaseCommand
import django_excel as excel

from elecciones.models import Distrito, Seccion, Circuito, Eleccion, Categoria, Mesa, Partido, MesaCategoria, TIPOS_DE_AGREGACIONES, NIVELES_DE_AGREGACION, OPCIONES_A_CONSIDERAR
from elecciones.sumarizador import Sumarizador
from escrutinio_social import settings


class Command(BaseCommand):
    help = "Exporta por CSV."

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout=None, stderr=None, no_color=False, force_color=False)

        self.headers = "'seccion', 'numero seccion', 'circuito', 'codigo circuito', 'centro de votacion', 'mesa', 'opcion', 'votos'"
        self.csv_list = [self.headers]

    def status(self, texto):
        self.stdout.write(f"{texto}")
        # self.stdout.write(self.style.SUCCESS(texto))

    def status_green(self, texto):
        self.stdout.write(self.style.SUCCESS(texto))

    def exportar_circuito(self, circuito):
        sumarizador = self.crear_sumarizador_circuito(circuito)
        mesas = sumarizador.mesas(self.categoria)
        votos = sumarizador.votos_reportados(self.categoria, mesas)
        self.exportar_votos(votos)

    def exportar_votos(self, votos):

        filas = []
        for voto_mesa in votos:
            mesa = voto_mesa.carga.mesa
            opcion = voto_mesa.opcion.codigo
            votos = voto_mesa.votos
            fila = (
                #f'{mesa.lugar_votacion.circuito.seccion.nombre}, '
                f'{mesa.lugar_votacion.circuito.seccion.numero}, '
                #f'{mesa.lugar_votacion.circuito.nombre}, '
                f'{mesa.lugar_votacion.circuito.numero}, '
                #f'{mesa.lugar_votacion.nombre}, '
                f'{mesa.numero}, '
                f'{opcion}, '
                f"{votos}\n"
            )
            filas.append(fila)
        self.file.write("".join(filas))

    def armar_opciones_sumarizador(self, nivel, id):
        opciones = {
            "nivel_de_agregacion": nivel,
            "opciones_a_considerar": OPCIONES_A_CONSIDERAR.todas, #prioritarias,
            "tipo_de_agregacion": self.tipo_de_agregacion,
            "ids_a_considerar": [id]
        }
        return opciones

    def crear_sumarizador_circuito(self, circuito):
        opciones = self.armar_opciones_sumarizador(NIVELES_DE_AGREGACION.circuito, circuito.id)
        return Sumarizador(**opciones)

    def crear_sumarizador_seccion(self, seccion):
        opciones = self.armar_opciones_sumarizador(NIVELES_DE_AGREGACION.seccion, seccion.id)
        return Sumarizador(**opciones)

    def exportar_seccion(self, seccion):
        sumarizador = self.crear_sumarizador_seccion(seccion)
        mesas = sumarizador.mesas(self.categoria)
        #votos = sumarizador.votos_reportados(self.categoria, mesas)
        votos = sumarizador.votos_reportados_por_seccion(self.categoria, self.seccion)
        self.exportar_votos(votos)
        # for circuito in seccion.circuitos.all():
        #     self.exportar_circuito(circuito)

    def exportar_distrito(self, distrito):
        for seccion in distrito.secciones.all():
            self.exportar_seccion(seccion)

    def exportar_pais(self):
        distritos = Distrito.objects.all()
        for distrito in distritos:
            self.exportar_distrito(distrito)

    def add_arguments(self, parser):
        # Nivel de agregación a exportar
        parser.add_argument("--solo_seccion", type=int, dest="solo_seccion",
                            help="Exportar sólo la sección indicada (default %(default)s).", default=None)
        parser.add_argument("--solo_circuito", type=int, dest="solo_circuito",
                            help="Exportar sólo el circuito indicado (default %(default)s).", default=None)
        parser.add_argument("--solo_distrito", type=int, dest="solo_distrito",
                            help="Exportar sólo el distrito indicado (default %(default)s).", default=None)
        parser.add_argument("--categoria", type=str, dest="categoria",
                            help="Slug categoría a exportar (default %(default)s).", default=settings.SLUG_CATEGORIA_PRESI_Y_VICE)

        parser.add_argument("--file", type=str, default='/tmp/exportacion.csv',
                            help="Archivo de salida (default %(default)s)")

        # Opciones a considerar
        parser.add_argument("--tipo_de_agregacion",
                            type=str, dest="tipo_de_agregacion",
                            help="Tipo de agregación del tipo de carga: "
                            f"{TIPOS_DE_AGREGACIONES.todas_las_cargas}, "
                            f"{TIPOS_DE_AGREGACIONES.solo_consolidados}, "
                            f"{TIPOS_DE_AGREGACIONES.solo_consolidados_doble_carga}; "
                            "(default %(default)s).",
                            # Por default sólo se analizan los resultados consolidados
                            default=TIPOS_DE_AGREGACIONES.solo_consolidados
                            )

    def handle(self, *args, **kwargs):
        """
        """
        self.tipo_de_agregacion = kwargs['tipo_de_agregacion']
        self.filename = kwargs['file']

        nombre_categoria = kwargs['categoria']
        self.categoria = Categoria.objects.get(slug=nombre_categoria)
        print("Vamos a exportar la categoría:", self.categoria)

        self.asignar_nivel_agregacion(kwargs)
        self.exportar_segun_nivel_agregacion()

    def exportar_segun_nivel_agregacion(self):
        self.file = open(self.filename, 'w+')
        self.file.write(self.headers)

        if self.circuito:
            self.status("Exportando circuito %s" % self.circuito.numero)
            self.exportar_circuito(self.circuito)
        elif self.seccion:
            self.status("Exportando sección %s (%s)" % (self.seccion.nombre, self.seccion.numero))
            self.exportar_seccion(self.seccion)
        elif self.distrito:
            self.status("Exportando distrito %s" % self.distrito.numero)
            self.exportar_distrito(self.distrito)
        else:
            self.status("Exportando país -> todos los distritos")
            self.exportar_pais()
        self.file.close()

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
