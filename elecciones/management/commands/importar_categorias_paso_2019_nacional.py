from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Partido, Opcion, Categoria, CategoriaOpcion, Mesa, MesaCategoria
import datetime

CSV_NACIONAL = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/categorias_nacionales.csv'
CSV_PROVINCIAL = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/categorias_provinciales.csv'

class BaseCommand(BaseCommand):

    def success(self, msg, ending='\n'):
        self.stdout.write(self.style.SUCCESS(msg), ending=ending)

    def warning(self, msg, ending='\n'):
        self.stdout.write(self.style.WARNING(msg), ending=ending)

    def log(self, object, created=True, ending='\n'):
        if created:
            self.success(f'creado {object}', ending=ending)
        else:
            self.warning(f'{object} ya existe', ending=ending)

class Command(BaseCommand):
    help = "Importar categorías nacionales, creando partidos, opciones y asociando mesas"

    def add_arguments(self, parser):
        parser.add_argument('--provinciales', action="store_true", default=False, help='Indica si importa nacionales o distritales.')

    def handle(self, *args, **options):
        provinciales = options['provinciales']
        d='''partido_nombre,partido_nombre_corto,partido_codigo,partido_color,opcion_nombre,opcion_nombre_corto,partido_orden,opcion_orden,categoria_nombre
        FRENTE DE TODOS,FRENTE DE TODOS,136,,CELESTE Y BLANCA A,CELESTE Y BLANCA A,1,1,Presidente y Vicepresidente
        '''
        arch = CSV_PROVINCIAL if provinciales else CSV_NACIONAL

        self.stdout.write(self.style.SUCCESS('Leyendo CSV...'))
        reader = DictReader(arch.open())
        errores = []
        c = 0
        for c, row in enumerate(reader, 1):
            print(row)
            codigo = row['partido_codigo']
            nombre = row['partido_nombre']
            nombre_corto = row['partido_nombre_corto'][:30]
            color = row['partido_color']
            orden = int(row['partido_orden'])
            defaults = {
                'nombre': nombre,
                'nombre_corto': nombre_corto,
                'color': color,
                'orden': orden,
            }
            partido, created = Partido.objects.update_or_create(codigo=codigo, defaults=defaults)
            
            self.log(partido, created)
            
            nombre = row['opcion_nombre']
            nombre_corto = row['opcion_nombre_corto'][:20]
            orden = row['opcion_orden']
            opcion_codigo = row['opcion_codigo']
            defaults = {
                'nombre': nombre,
                'nombre_corto': nombre_corto,
                'orden': orden,
            }        

            opcion, created = Opcion.objects.update_or_create(partido=partido,
                codigo=opcion_codigo,
                defaults=defaults
            )
            self.log(opcion, created)
            
            categoria, created = Categoria.objects.get_or_create(
                nombre=row['categoria_nombre'],
                slug=row['categoria_slug']
            )
            self.log(categoria, created)                  
            
            mesas = Mesa.objects.all() if not provinciales else Mesa.objects.filter(circuito__seccion__distrito__numero=row['distrito_nro'])

            for mesa in mesas:
                mesacategoria, created = MesaCategoria.objects.get_or_create(mesa=mesa, categoria=categoria)
                                             

            categoriaopcion, created = CategoriaOpcion.objects.get_or_create(
                categoria=categoria,
                opcion=opcion,
            )
            self.log(categoriaopcion, created)

        self.stdout.write(self.style.SUCCESS('CVS leído.'))
            
                                                                

