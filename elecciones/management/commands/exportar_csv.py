from django.core.management.base import BaseCommand

from elecciones.models import (
    Distrito, Seccion, Circuito, Categoria, VotoMesaReportado,
    TIPOS_DE_AGREGACIONES, NIVELES_DE_AGREGACION, OPCIONES_A_CONSIDERAR
)
from elecciones.sumarizador import Sumarizador
from escrutinio_social import settings


class Command(BaseCommand):
    help = "Exporta por CSV."

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout=None, stderr=None, no_color=False, force_color=False)

        self.headers = "'distrito', seccion', 'circuito', 'mesa', 'opcion', 'votos'"

    def add_arguments(self, parser):
        # Nivel de agregación a exportar
        parser.add_argument("--solo_seccion", type=int, dest="solo_seccion",
                            help="Exportar sólo la sección indicada (default %(default)s).", default=None)
        parser.add_argument("--solo_circuito", type=int, dest="solo_circuito",
                            help="Exportar sólo el circuito indicado (default %(default)s).", default=None)
        parser.add_argument("--solo_distrito", type=int, dest="solo_distrito",
                            help="Exportar sólo el distrito indicado (default %(default)s).", default=None)
        parser.add_argument("--categoria", type=str, dest="categoria",
                            help="Slug categoría a exportar (default %(default)s).", 
                            default=settings.SLUG_CATEGORIA_PRESI_Y_VICE)

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

        filtro_nivel_agregacion = self.get_filtro_nivel_agregacion(kwargs)
        print(filtro_nivel_agregacion)
        votos = self.get_votos(filtro_nivel_agregacion)
        self.exportar(votos)

    def get_filtro_nivel_agregacion(self, kwargs):
        # Analizar resultados de acuerdo a los niveles de agregación

        numero_distrito = kwargs['solo_distrito']
        if not numero_distrito:
            # No se indica distrito => tomar datos de todo el país.
            self.status("Exportando país -> todos los distritos")
            return dict()

        distrito = Distrito.objects.get(numero=numero_distrito)
        numero_seccion = kwargs['solo_seccion']
        if not numero_seccion:
            # No se indica sección => tomar datos de todo el distrito
            self.status("Exportando distrito %s" % distrito.numero)
            return dict(
                nivel_de_agregacion=NIVELES_DE_AGREGACION.distrito,
                ids_a_considerar=[distrito.id],
            )

        seccion = Seccion.objects.get(numero=numero_seccion, distrito=distrito)
        numero_circuito = kwargs['solo_circuito']
        if not numero_circuito:
            # No se indica circuito => tomar datos de toda la sección
            self.status("Exportando sección %s (%s)" % (seccion.nombre, seccion.numero))
            return dict(
                nivel_de_agregacion=NIVELES_DE_AGREGACION.seccion,
                ids_a_considerar=[seccion.id],
            )

        # Filtro por circuito
        circuito = Circuito.objects.get(numero=numero_circuito, seccion=seccion)
        self.status("Exportando circuito %s" % circuito.numero)
        return dict(
            nivel_de_agregacion=NIVELES_DE_AGREGACION.circuito,
            ids_a_considerar=[circuito.id],
        )

    def get_votos(self, filtro_nivel_agregacion):
        sumarizador = Sumarizador(
            opciones_a_considerar=OPCIONES_A_CONSIDERAR.todas,
            tipo_de_agregacion=self.tipo_de_agregacion,
            **filtro_nivel_agregacion,
        )

        return VotoMesaReportado.objects.filter(
            carga__mesa_categoria__categoria=self.categoria,
            carga__es_testigo__isnull=False,
            **sumarizador.cargas_a_considerar_status_filter(self.categoria),
            **sumarizador.lookups_de_mesas("carga__mesa_categoria__mesa__")
        ).values_list(
                'carga__mesa_categoria__mesa__circuito__seccion__distrito__numero',
                'carga__mesa_categoria__mesa__circuito__seccion__numero',
                'carga__mesa_categoria__mesa__circuito__numero',
                'carga__mesa_categoria__mesa__numero',
                'opcion__codigo',
                'votos',
        ).order_by(
            "carga__mesa_categoria__mesa__circuito__seccion__distrito__numero",
            "carga__mesa_categoria__mesa__circuito__seccion__numero",
            "carga__mesa_categoria__mesa__circuito__numero",
            "carga__mesa_categoria__mesa__numero"
        )

    def exportar(self, votos):
        self.file = open(self.filename, 'w+')
        self.file.write(self.headers)
        self.exportar_votos(votos)
        self.file.close()

    def exportar_votos(self, votos):
        for voto in votos:
            fila = ", ".join(str(n) for n in voto)
            # print(fila[0])
            self.file.write(f"{fila}\n")

    def status(self, texto):
        self.stdout.write(f"{texto}")

    def status_green(self, texto):
        self.stdout.write(self.style.SUCCESS(texto))
