from django.core.management.base import BaseCommand
from django.conf import settings
from elecciones.models import Partido, Opcion, Categoria, CategoriaOpcion, Mesa, MesaCategoria


class Command(BaseCommand):
    help = "Establece las categorías prioritarias, las configura y les asigna las opciones prioritarias."

    def handle(self, *args, **options):
        # Categoría Presidente.
        categoria = Categoria.objects.get(slug=settings.SLUG_CATEGORIA_PRESI_Y_VICE)
        codigos = [settings.CODIGO_PARTIDO_NOSOTROS, settings.CODIGO_PARTIDO_ELLOS]
        self.configurar_categoria_prioritaria(categoria, codigos)

        # Categoría Gobernador.
        categoria = Categoria.objects.get(slug=settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA)
        codigos = [settings.CODIGO_PARTIDO_NOSOTROS, settings.CODIGO_PARTIDO_ELLOS_BA]
        self.configurar_categoria_prioritaria(categoria, codigos)

    def configurar_categoria_prioritaria(self, categoria, codigos):
        categoria.activa = True
        categoria.sensible = True
        categoria.requiere_cargas_parciales = True
        categoria.prioridad = 2
        categoria.save()

        # Opciones prioritarias.
        for cod_partido in codigos:
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
