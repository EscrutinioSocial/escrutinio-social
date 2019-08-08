"""
Generar agrupaciones de circuitos que se utilizarán para las
proyecciones.

Cada AgrupacionCircuitos tiene el nombre: nro-distrito.sección.
"""
from django.core.management.base import BaseCommand
from elecciones.models import Seccion, AgrupacionCircuitos, TecnicaProyeccion


def crear_agrupacion(nombre,proyeccion,minimo_mesas,circuitos):
    """Crea una agrupación de los circuitos que se le pasa como
    último argumento"""
    agrupacion = AgrupacionCircuitos(nombre=nombre,
                                     proyeccion=proyeccion,
                                     minimo_mesas=minimo_mesas,
    )
    agrupacion.save()
    for c in circuitos:
        agrupacion.circuitos.add(c) 
    return agrupacion
    

def agrupacion_por_seccion(seccion, proyeccion, minimo_mesas):
    nombre = f'{seccion.distrito.numero}-{seccion.nombre}'
    existe = AgrupacionCircuitos.objects.filter(nombre=nombre,proyeccion=proyeccion).exists()
    if existe:
        msg = f'Ya existía la agrupación {nombre} para la técnica {proyeccion}'
        self.stdout.write(self.style.WARNING(msg))
        return None
    crear_agrupacion(nombre,proyeccion,minimo_mesas,seccion.circuitos.all())


    
class Command(BaseCommand):
    help = "Crear agrupaciones de circuitos para proyecciones."

    def add_arguments(self, parser):

        parser.add_argument(
            '--mesas',
            default=7,
            type=int,
            help='Cantidad mínima de mesas, no puede ser menor a 3 (por defecto: 7)',
        )
        
        parser.add_argument(
            'tecnica-proyeccion',
            help='Nombre de la técnica de proyección'
        )
        
    
    def handle(self, *args, **options):
        tecnica = str(options['tecnica-proyeccion'])
        minimo_mesas = int(options['mesas'])
        verbosity = int(options['verbosity'])

        if minimo_mesas < 3:
            raise Exception("El mínimo de mesas no puede ser menor a 3")
            
        proyeccion, created = TecnicaProyeccion.objects.get_or_create(nombre=tecnica)
        
        for seccion in Seccion.objects.all():
            agrupacion_por_seccion(seccion,proyeccion,minimo_mesas)
            if verbosity > 2:
                self.stdout.write(self.style.SUCCESS(f'Creada agrupación: {seccion.nombre}'))
       
        self.stdout.write(self.style.SUCCESS('Terminado'))

