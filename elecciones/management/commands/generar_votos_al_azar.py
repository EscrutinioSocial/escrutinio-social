import math
import random
from django.core.management.base import BaseCommand
from fiscales.models import Fiscal
from elecciones.models import (
    Distrito, Seccion,
    Circuito, Eleccion, Categoria, Mesa, Partido, MesaCategoria,
    Mesa, Carga, VotoMesaReportado, CategoriaOpcion, Opcion
    )
from escrutinio_social import settings


class Command(BaseCommand):
    help = "Generar votos al azar."

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout=None, stderr=None, no_color=False, force_color=False)


    def imprimir_mesa(self, mesa):
        circuito = mesa.circuito
        seccion = circuito.seccion
        distrito = seccion.distrito
        return f"D {distrito} - S {seccion} - C {circuito} - M {mesa}: "

    def alerta_mesa(self, mesa, problema):
        mensaje = self.imprimir_mesa(mesa) + problema
        self.stdout.write(self.style.ERROR(f"ALERTA: {mensaje}"))


    def status(self, texto):
        self.stdout.write(f"{texto}")
        # self.stdout.write(self.style.SUCCESS(texto))

    def status_green(self, texto):
        self.stdout.write(self.style.SUCCESS(texto))

    def poblar_mesa(self, mesa):
        mesa_categoria = MesaCategoria.objects.get(categoria=self.categoria, mesa=mesa)
        fiscal = Fiscal.objects.all().first()

        cargas = []
        for i in range(self.cant_cargas):
            cargas.append(
                Carga.objects.create(
                    tipo=Carga.TIPOS.parcial,
                    fiscal=fiscal,
                    origen=Carga.SOURCES.csv,
                    mesa_categoria=mesa_categoria
                )
            )
        opciones = self.categoria.opciones_actuales(
            solo_prioritarias=True, excluir_optativas=True
        )

        total_votos = random.randint(1, 101)  # Valor inicial = votos de categorías no prioritarias
        for opcion in opciones:
            if opcion != Opcion.total_votos():
                votos_opcion = random.randint(1, 101)
                total_votos += votos_opcion
                self.poblar_opcion(mesa, opcion, cargas, votos_opcion)

        self.poblar_opcion(mesa, Opcion.total_votos(), cargas, total_votos)

    def poblar_opcion(self, mesa, opcion, cargas, cant_votos):
        self.alerta_mesa(mesa, "Poblando opción %s" % opcion)
        votos = []
        for i in range(self.cant_cargas):
            votos.append(
                VotoMesaReportado(
                    carga=cargas[i],
                    opcion=opcion,
                    votos=cant_votos
                )
            )
        VotoMesaReportado.objects.bulk_create(votos, ignore_conflicts=True)

    def poblar_circuito(self, circuito):
        for mesa in circuito.mesas.all():
            self.poblar_mesa(mesa)

    def poblar_seccion(self, seccion):
        for circuito in seccion.circuitos.all():
            self.poblar_circuito(circuito)

    def poblar_distrito(self, distrito):
        for seccion in distrito.secciones.all():
            self.poblar_seccion(seccion)

    def poblar_pais(self):
        distritos = Distrito.objects.all()
        for distrito in distritos:
            self.poblar_distrito(distrito)

    def add_arguments(self, parser):

        # Nivel de agregación a analizar
        parser.add_argument("--solo_seccion", type=int, dest="solo_seccion",
                            help="Poblar sólo la sección indicada (default %(default)s).", default=None)
        parser.add_argument("--solo_circuito", type=int, dest="solo_circuito",
                            help="Poblar sólo el circuito indicado (default %(default)s).", default=None)
        parser.add_argument("--solo_distrito", type=int, dest="solo_distrito",
                            help="Poblar sólo el distrito indicado (default %(default)s).", default=None)
        parser.add_argument("--categoria", type=str, dest="categoria",
                            help="Slug categoría a poblar (default %(default)s).", default=settings.SLUG_CATEGORIA_PRESI_Y_VICE)

        parser.add_argument("--cant_cargas", type=int, dest="cant_cargas",
                            help="Cuántas cargas generar (sirve para que consolide, default %(default)s).", default=1)

    def handle(self, *args, **kwargs):
        """
        """
        slug_categoria = kwargs['categoria']
        self.categoria = Categoria.objects.get(slug=slug_categoria)
        print("Vamos a poblar la categoría:", self.categoria)

        self.asignar_nivel_agregacion(kwargs)
        self.cant_cargas = kwargs['cant_cargas']
        self.poblar_segun_nivel_agregacion()

    def poblar_segun_nivel_agregacion(self):
        if self.circuito:
            self.status("Poblando circuito %s" % self.circuito.numero)
            self.poblar_circuito(self.circuito)
        elif self.seccion:
            self.status("Poblando sección %s" % self.seccion.numero)
            self.poblar_seccion(self.seccion)
        elif self.distrito:
            self.status("Poblando distrito %s" % self.distrito.numero)
            self.poblar_distrito(self.distrito)
        else:
            # Analiza todos los distritos
            self.status("Poblando país -> todos los distritos")
            self.poblar_pais()

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
