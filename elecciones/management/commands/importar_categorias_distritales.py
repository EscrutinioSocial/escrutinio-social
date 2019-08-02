from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Partido, Opcion, Categoria, CategoriaOpcion, Mesa, MesaCategoria
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/2019/paso-nacional/categorias_distrito.csv'

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
    help = "Importar partidos y opciones."

    def handle(self, *args, **options):
        d='''partido_nombre,partido_nombre_corto,partido_codigo,partido_color,opcion_nombre,opcion_nombre_corto,partido_orden,opcion_orden,distrito_name (no se utiliza),cargo (no se utiliza),categoria_nombre,distrito_nro,candidato1ro (no se utiliza)
            partido republicano federal,partido republicano federal,314,,celeste y blanco,celeste y blanco,1,1,Buenos Aires,Diputados Nacionales,Diputados Nacionales Buenos Aires,2,ROBERTO EDUARDO DAMBORIANA

        '''
        self.stdout.write(self.style.SUCCESS('Leyendo CSV...'))
        reader = DictReader(CSV.open())
        errores = []
        c = 0
        for c,row in enumerate(reader,1):
            print(row)
            partido, created = Partido.objects.get_or_create(   
                nombre=row['partido_nombre'],
                nombre_corto=row['partido_nombre_corto'][:30],
                codigo=row['partido_codigo'],
                color=row['partido_color'],
                orden=int(row['partido_orden'])
                )
            self.log(partido, created)
                                                            
            opcion, created = Opcion.objects.get_or_create(     
                partido=partido,
                nombre=row['opcion_nombre'],
                nombre_corto=row['opcion_nombre_corto'][:20],
                orden=row['opcion_orden'],
                )
            self.log(opcion, created)
            
            categoria, created = Categoria.objects.get_or_create(
                nombre=row['categoria_nombre'],
                slug=row['categoria_nombre'],
                )
            self.log(categoria, created)                  
            
            mesas=Mesa.objects.filter(circuito__seccion__distrito__numero=row['distrito_nro'])
            
            for mesa in mesas:
                mesacategoria, created = MesaCategoria.objects.get_or_create(mesa=mesa, categoria=categoria)
                                             

            categoriaopcion, created = CategoriaOpcion.objects.get_or_create(
                categoria=categoria,
                opcion=opcion,
            )
            self.log(categoriaopcion, created)

        self.stdout.write(self.style.SUCCESS('Leyendo CSV OK.'))
            
                                                                

