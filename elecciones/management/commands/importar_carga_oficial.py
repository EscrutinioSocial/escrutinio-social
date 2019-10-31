import structlog
import time

from csv import DictReader
from fiscales.models import Fiscal
from elecciones.models import Categoria, Circuito, Mesa, MesaCategoria, Carga, VotoMesaReportado, CategoriaOpcion, Opcion
from elecciones.management.commands.basic_command import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Importa la carga oficial."

    def add_arguments(self, parser):
        super().add_arguments(parser)

        # Categoria
        parser.add_argument(
            "--categoria",
            type=str,
            dest="categoria",
            help="Categoría (slug) de los votos a cargar",
            default=settings.SLUG_CATEGORIA_PRESI_Y_VICE
        )

    def get_mesa(self, nro_distrito, nro_seccion, nro_circuito, nro_mesa):
        try:
            mesa = Mesa.objects.get(
                numero=nro_mesa, circuito__numero=nro_circuito,
                circuito__seccion__numero=nro_seccion,
                circuito__seccion__distrito__numero=nro_distrito
            )
        except Mesa.DoesNotExist:
            self.warning(f"No existe la mesa nro {nro_mesa} en el circuito {nro_circuito}, la sección nro {nro_seccion} y distrito {nro_distrito}.")
            return None

        return mesa

    def get_mesa_categoria(self, mesa, categoria):
        try:
            return MesaCategoria.objects.get(
                mesa=mesa,
                categoria=categoria
            )
        except MesaCategoria.DoesNotExist:
            self.warning(f"No existe la MesaCategoria para la mesa {mesa.numero} en el circuito {mesa.circuito}, la sección {mesa.seccion} y el distrito {mesa.distrito}")
            return None

    def handle(self, *args, **options):
        super().handle(*args, **options)
        self.procesar(**options)

    def armar_voto(self, opcion, carga, votos):
        return VotoMesaReportado(
            opcion=opcion,
            votos=votos,
            carga=carga
        )

    def procesar(self, **options):

        reader = DictReader(self.CSV.open())

        categoria = Categoria.objects.get(slug=options['categoria'])
        opcion_nosotros = CategoriaOpcion.objects.get(
            categoria=categoria,
            opcion__partido__codigo=settings.CODIGO_PARTIDO_NOSOTROS,
        ).opcion
        opcion_ellos = CategoriaOpcion.objects.get(
            categoria=categoria,
            opcion__partido__codigo=settings.CODIGO_PARTIDO_ELLOS,
        ).opcion

        fiscal = Fiscal.objects.get(id=1)

        for linea, row in enumerate(reader, 1):
            # Estas líneas son para importar los datos de gobernador
            # el csv viene con espacios en los nombres de columna

            # nro_distrito = int(row['distrito '])
            # nro_seccion = int(row[' seccion '])
            # nro_circuito = row[' circuito '].strip().lstrip('0')
            # nro_mesa = int(row[' mesa '])
            # cant_blanco = int(row[' blanco '])
            # cant_nulos = int(row[' nulo '])
            # total_votos = int(row[' total_electores '])
            # cant_nosotros = int(row[' vot_kicilove '])
            # cant_ellos = int(row[' vot_vidal'])

            # Las columnas de presidente no tienen espacios, 
            # pero tal vez haya que corregir cambiar macri por alferdez.
            nro_distrito = int(row['distrito'])
            nro_seccion = int(row['seccion'])
            nro_circuito = row['circuito'].strip().lstrip('0')
            nro_mesa = int(row['mesa'])
            cant_blanco = int(row['blanco'])
            cant_nulos = int(row['nulo'])
            total_votos = int(row['total_electores'])
            cant_nosotros = int(row['vot_alferdez'])
            cant_ellos = int(row['vot_macri'])

            mesa = self.get_mesa(nro_distrito, nro_seccion, nro_circuito, nro_mesa)
            if not mesa:
                continue

            mesa_categoria = self.get_mesa_categoria(mesa, categoria)
            if not mesa_categoria:
                continue

            carga, creada = Carga.objects.get_or_create(
                mesa_categoria=mesa_categoria,
                tipo=Carga.TIPOS.parcial_oficial,
                fiscal=fiscal,
                origen=Carga.SOURCES.web
            )

            if creada:
                votos = []
                votos.append(self.armar_voto(Opcion.blancos(), carga, cant_blanco))
                votos.append(self.armar_voto(Opcion.nulos(), carga, cant_nulos))
                votos.append(self.armar_voto(Opcion.total_votos(), carga, total_votos))
                votos.append(self.armar_voto(opcion_nosotros, carga, cant_nosotros))
                votos.append(self.armar_voto(opcion_ellos, carga, cant_ellos))
                VotoMesaReportado.objects.bulk_create(votos)

                carga.actualizar_firma()

                mesa_categoria.parcial_oficial = carga
                mesa_categoria.save(update_fields=['parcial_oficial'])
                self.success(f"Insertando votos en mesa {mesa}.")

            else:
                self.warning(f"Ignorando votos de mesa {mesa}")