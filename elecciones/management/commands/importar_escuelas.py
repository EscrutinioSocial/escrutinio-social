from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Distrito, Seccion, Circuito, LugarVotacion, Mesa, Categoria
import datetime

CSV = Path(settings.BASE_DIR) / 'elecciones/data/cartamarina-escuelas-elecciones-2015-cordoba.csv'

def to_float(val):
    try:
        return float(val.replace(',', '.'))
    except:
        return None


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
    ''' formato de archivo:
    Seccion Nro,Seccion Nombre,Circuito Nro,Circuito Nombre,Escuela,Mesas,Desde,Hasta,Electores
    1,CAPITAL,1,SECCIONAL PRIMERA,CENTRO EDUC.NIVEL MEDIO ADULTO - DEAN FUNES 417,7,1,7,2408
    '''
    help = "Importar carta marina"

    def handle(self, *args, **options):
        # por ahora hardcodeado; TODO: leer de argv
        distrito = Distrito(numero=4,nombre="Córdoba",electores=0,prioridad=3)
        distrito.save()
        fecha = datetime.datetime(2019, 5, 12, 8, 0)

        reader = DictReader(CSV.open())

#        categoria_gobernador_cordoba, created = Categoria.objects.get_or_create(slug='gobernador-cordoba-2019', nombre='Gobernador Córdoba 2019', fecha=fecha) # comento lo que falla para probar
#        categoria_gobernador_cordoba, created = Categoria.objects.get_or_create(slug='gobernador-cordoba-2019', nombre='Gobernador Córdoba 2019')#, fecha=fecha)
#        categoria_intendente_cordoba, created = Categoria.objects.get_or_create(slug='intendente-cordoba-2019', nombre='Intendente Córdoba 2019', fecha=fecha)
#        categoria_intendente_cordoba, created = Categoria.objects.get_or_create(slug='intendente-cordoba-2019', nombre='Intendente Córdoba 2019')#, fecha=fecha)
#        categoria_legisladores_distrito_unico, created = Categoria.objects.get_or_create(slug='legisladores-dist-unico-cordoba-2019', nombre='Legisladores Distrito Único Córdoba 2019', fecha=fecha)
#        categoria_legisladores_distrito_unico, created = Categoria.objects.get_or_create(slug='legisladores-dist-unico-cordoba-2019', nombre='Legisladores Distrito Único Córdoba 2019')#, fecha=fecha)
#        categoria_tribunal_de_cuentas_provincial, created = Categoria.objects.get_or_create(slug='tribunal-cuentas-prov-cordoba-2019', nombre='Tribunal de Cuentas Provincia de Córdoba 2019', fecha=fecha, activa=False)

        for c, row in enumerate(reader, 1):
            print ('row:',c)
            depto = row['Seccion Nombre']
            numero_de_seccion = int(row['Seccion Nro'])
            seccion, created = Seccion.objects.get_or_create(distrito=distrito,nombre=depto, numero=numero_de_seccion)
            self.log(seccion, created)
 
            circuito, created = Circuito.objects.get_or_create(nombre=row['Circuito Nombre'], numero=row['Circuito Nro'], seccion=seccion)
            self.log(circuito, created)

            esc=row['Escuela'].split(' - ')
            if len(esc)<2: esc.append('n/d') # esto es porque hay casos en que no esta dividida por - o no hay direccion
            escuela, created = LugarVotacion.objects.get_or_create(
                circuito=circuito,
                nombre=esc[0],
                direccion=esc[1]
                   
#                ciudad=row['Ciudad'] or '',
#                barrio=row['Barrio'] or ''
                )

            escuela.electores = int(row['Electores'])
            
            x='''
            coordenadas = [to_float(row['Longitud']), to_float(row['Latitud'])]
            if coordenadas[0] and coordenadas[1]:
                geom = {'type': 'Point', 'coordinates': coordenadas}
                if row['Estado Geolocalizacion'] == 'Match':
                    estado_geolocalizacion = 9
                elif row['Estado Geolocalizacion'] == 'Partial Match':
                    estado_geolocalizacion = 5
            else:
                geom = None
                estado_geolocalizacion = 0
            escuela.geom = geom
            escuela.estado_geolocalizacion = estado_geolocalizacion
            '''
            escuela.save()

            self.log(escuela, created)

            for mesa_nro in range(int(row['Desde']), int(row['Hasta']) + 1):
            #ojo habia caso mesas con numeros no consecutivos - prever
            #tal vez agregar las mesas en otra instancia y solo guardar los valores
                mesa, created = Mesa.objects.get_or_create(numero=mesa_nro)  # EVITAR duplicados en limpiezas de escuelas y otros
                mesa.lugar_votacion=escuela
                mesa.circuito=circuito
                mesa.save()

                self.log(mesa, created)


        x=""" hay 3 mesas que son de una escuela y no son nros consecutivos
            Se requiere copiar la mesa 1 3 veces antes de tirar este comando para que no falten esos tres datos


        mesa_8651 = Mesa.objects.get(numero=1)
        mesa_8651.pk = None
        mesa_8651.numero = 8651
        mesa_8651.save()

        mesa_8652 = Mesa.objects.get(numero=1)
        mesa_8652.pk = None
        mesa_8652.numero = 8652
        mesa_8652.save()

        mesa_8653 = Mesa.objects.get(numero=1)
        mesa_8653.pk = None
        mesa_8653.numero = 8653
        mesa_8653.save()
        """
