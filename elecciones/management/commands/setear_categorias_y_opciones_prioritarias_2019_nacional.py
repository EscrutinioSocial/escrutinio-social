from django.core.management.base import BaseCommand
from django.conf import settings
from elecciones.models import Partido, Opcion, Categoria, CategoriaOpcion, Mesa, MesaCategoria


class Command(BaseCommand):
    help = "Establece las categorías prioritarias, las configura y les asigna las opciones prioritarias."

    def handle(self, *args, **options):

        # Categoría Presidente.
        codigos = [settings.CODIGO_PARTIDO_NOSOTROS, settings.CODIGO_PARTIDO_ELLOS]
        categoria = Categoria.objects.get(slug=settings.SLUG_CATEGORIA_PRESI_Y_VICE)
        self.configurar_categoria_prioritaria(categoria, codigos, True)

        # Categoría Gobernador.
        categoria = Categoria.objects.get(slug=settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA)
        codigos = [settings.CODIGO_PARTIDO_NOSOTROS_BA, settings.CODIGO_PARTIDO_ELLOS_BA]
        self.configurar_categoria_prioritaria(categoria, codigos, True)

        # En el resto de las categorías activas.
        codigos = [settings.CODIGO_PARTIDO_NOSOTROS, settings.CODIGO_PARTIDO_ELLOS]
        categorias = Categoria.objects.filter(
            activa=True
        ).exclude(
            slug=settings.SLUG_CATEGORIA_PRESI_Y_VICE
        ).exclude(
            slug=settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA
        )
        for categoria in categorias:
            self.configurar_categoria_prioritaria(categoria, codigos, False)

    def configurar_categoria_prioritaria(self, categoria, codigos, sensible):
        categoria.activa = True
        categoria.sensible = sensible
        categoria.requiere_cargas_parciales = True
        if sensible:
            categoria.prioridad = 2
        categoria.save()

        # Opciones prioritarias.
        for cod_partido in codigos:
            categoriaopcion = CategoriaOpcion.objects.get(
                categoria=categoria,
                opcion__partido__codigo=cod_partido,
            )
            categoriaopcion.set_prioritaria()

        opciones_obligatorias = [
            Opcion.blancos(), Opcion.nulos(), Opcion.total_votos(), Opcion.sobres(),
            Opcion.recurridos(), Opcion.id_impugnada(), Opcion.comando_electoral(),
        ]
        for opcion in opciones_obligatorias:
            categoriaopcion = CategoriaOpcion.objects.get(
                categoria=categoria,
                opcion=opcion,
            )
            categoriaopcion.set_prioritaria()
