from django.core.management.base import BaseCommand
from django.conf import settings
from elecciones.models import Partido, Opcion, Categoria, CategoriaOpcion, Mesa, MesaCategoria


class Command(BaseCommand):
    help = "Establece las categorías prioritarias, las configura y les asigna las opciones prioritarias."

    def handle(self, *args, **options):
        # Categoría Presidente.
        categoria = Categoria.objects.get(nombre=settings.NOMBRE_CATEGORIA_PRESI_Y_VICE)
        self.configurar_categoria_prioritaria(categoria)

        # Categoría Gobernador.
        categoria = Categoria.objects.get(nombre=settings.NOMBRE_CATEGORIA_GOB_Y_VICE_PBA)
        self.configurar_categoria_prioritaria(categoria)

    def configurar_categoria_prioritaria(self, categoria):
        categoria.activa = True
        categoria.sensible = True
        categoria.requiere_cargas_parciales = True
        categoria.prioridad = 2
        categoria.save()

        # Opciones prioritarias.
        for cod_partido in [settings.CODIGO_PARTIDO_NOSOTROS, settings.CODIGO_PARTIDO_ELLOS]:
            categoriaopcion = CategoriaOpcion.objects.get(
                    categoria=categoria,
                    opcion__partido__codigo=cod_partido,
            )
            categoriaopcion.set_prioritaria()

        for opcion in [Opcion.blancos(), Opcion.nulos(), Opcion.total_votos()]:
            categoriaopcion = CategoriaOpcion.objects.get(
                categoria=categoria,
                opcion=opcion,
            )
            categoriaopcion.set_prioritaria()