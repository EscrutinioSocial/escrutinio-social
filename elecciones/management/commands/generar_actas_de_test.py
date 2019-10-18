import random

from PIL import Image, ImageDraw, ImageFont
from django.core.management import BaseCommand

from elecciones.models import Distrito, Categoria, Mesa


class Command(BaseCommand):
    help = "Crear Actas para prueba con datos ficticios."

    def add_arguments(self, parser):

        parser.add_argument(
            '--cantidad_mesas',
            default=30,
            type=int,
            help='Cantidad de mesas para generar actas (por defecto: 30)',
        )

    def handle(self, *args, **options):

        cant_mesas = int(options['cantidad_mesas']) // 30

        if cant_mesas < 1:
            raise Exception("El mínimo de mesas no puede ser menor a 1")

        categoria_presi = Categoria.objects.filter(requiere_cargas_parciales=True, nombre__contains="Presidente").get()

        opciones = None
        if categoria_presi is not None:
            opciones = categoria_presi.opciones_actuales(solo_prioritarias=True,
                                                         excluir_optativas=True).values_list('nombre', flat=True)

        distritos = Distrito.objects.all()[:5]
        for distrito in distritos:
            secciones = distrito.get_secciones()[:2]
            for seccion in secciones:
                circuitos = seccion.circuitos.all()[:3]
                for circuito in circuitos:
                    mesas = Mesa.objects.filter(lugar_votacion__circuito=circuito, categorias=categoria_presi)[
                            :cant_mesas]
                    for mesa in mesas:
                        self.generar_acta(distrito, seccion, circuito, mesa, opciones)

    def generar_acta(self, distrito, seccion, circuito, mesa, opciones):
        # draw the message on the background
        img = Image.new('RGB', (480, 480), color='white')

        font = ImageFont.load_default()
        # font = ImageFont.truetype("arial.ttf", 16)


        # starting position of the message

        (x, y) = (50, 50)
        message = "Distrito: " + str(distrito.numero) + " Seccion: " + str(seccion.numero) + "\n" \
                  + " Circuito: " + str(circuito.numero) + " Mesa: " + str(mesa.numero)

        color = 'rgb(0, 0, 0)'  # black color

        draw = ImageDraw.Draw(img)

        draw.text((x, y), message, fill=color, font=font)
        (x, y) = (150, 150)

        lista = ""
        sum = 0
        for opcion in opciones:
            cantidad = random.randint(0, 50)
            if not "total" in opcion:
                sum += cantidad
                lista += opcion + "..." + str(cantidad) + "\n"
            else:
                lista += opcion + "..." + str(sum) + "\n"

        draw.text((x, y), lista, fill=color, font=font)

        # save the edited image
        nombre_acta = "acta_" + str(mesa.numero) + "_" + str(circuito.numero)
        img.save("Actas/" + nombre_acta + '.jpg')
