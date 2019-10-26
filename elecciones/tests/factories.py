import factory
import random
from PIL import Image
from io import BytesIO
from django.contrib.auth.models import User
from factory.django import DjangoModelFactory
from faker import Faker
from django.conf import settings
from elecciones.models import Opcion, CategoriaOpcion

fake = Faker('es_ES')


class UserFactory(DjangoModelFactory):

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Sequence(lambda n: f'user{n}@foo.com')
    password = factory.PostGenerationMethodCall('set_password', 'password')
    is_staff = True


class PartidoFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.Partido'

    nombre = factory.Sequence(lambda n: f'Partido {n + 1}')


class OpcionFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.Opcion'
        django_get_or_create = ('nombre', )

    nombre = factory.Sequence(lambda n: f'Opción {n + 1}')
    partido = factory.SubFactory(PartidoFactory)


class CategoriaGeneralFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.CategoriaGeneral'
        django_get_or_create = ('nombre', 'slug', )

    nombre = factory.Sequence(lambda n: f'Categoría general {n + 1}')
    slug = factory.Sequence(lambda n: f'categoría_general_{n + 1}')


class CategoriaFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.Categoria'
        django_get_or_create = ('nombre', )

    categoria_general = factory.SubFactory(CategoriaGeneralFactory)
    nombre = factory.Sequence(lambda n: f'Categoría {n + 1}')
    slug = factory.LazyAttribute(lambda obj: obj.nombre)

    @factory.post_generation
    def opciones(self, create, extracted, **kwargs):

        if not create:
            return

        # Toda categoría debe tener las opciones no partidarias.
        orden = 1000  # Las mandamos 'al fondo' en el orden.
        for nombre in Opcion.opciones_no_partidarias():
            opcion, created = Opcion.objects.get_or_create(**getattr(settings, nombre))
            if created:
                opcion.nombre = opcion.nombre_corto
                opcion.save(update_fields=['nombre'])
            defaults = {'orden': orden, 'prioritaria': True}
            CategoriaOpcion.objects.get_or_create(categoria=self, opcion=opcion, defaults=defaults)
            orden += 1

        if extracted is not None:
            #
            for opcion in extracted:
                CategoriaOpcionFactory(categoria=self, opcion=opcion)
        else:
            # Por defecto se crean cuatro opciones partidarias
            CategoriaOpcionFactory(categoria=self, opcion=OpcionFactory(nombre='opc1'))
            CategoriaOpcionFactory(categoria=self, opcion=OpcionFactory(nombre='opc2'))
            CategoriaOpcionFactory(categoria=self, opcion=OpcionFactory(nombre='opc3'))
            CategoriaOpcionFactory(categoria=self, opcion=OpcionFactory(nombre='opc4'))


class CategoriaOpcionFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.CategoriaOpcion'
        django_get_or_create = ('categoria', 'opcion')

    categoria = factory.SubFactory(CategoriaFactory, nombre='default')
    opcion = factory.SubFactory(OpcionFactory)
    orden = factory.Sequence(lambda n: n + 1)
    prioritaria = True


class DistritoFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.Distrito'
        django_get_or_create = ('nombre', )

    numero = factory.Sequence(lambda n: str(n + 1))
    nombre = factory.LazyAttribute(lambda obj: f"Distrito {obj.numero}")


class SeccionFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.Seccion'

    # notar que el distrito por default
    # ya existe porque se crea via migracion 0026 de eleccion
    # y get_or_create de distrito aplica por nombre
    distrito = factory.SubFactory(DistritoFactory, nombre='Distrito único')
    numero = factory.Sequence(lambda n: str(n + 1))
    nombre = factory.LazyAttribute(lambda obj: f"Sección {obj.numero}")


class CircuitoFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.Circuito'

    seccion = factory.SubFactory(SeccionFactory)
    numero = factory.Sequence(lambda n: str(n + 1))
    nombre = factory.LazyAttribute(lambda obj: f"Circuito {obj.seccion.numero}.{obj.numero}")


class LugarVotacionFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.LugarVotacion'

    circuito = factory.SubFactory(CircuitoFactory)
    nombre = factory.Sequence(lambda n: f"Escuela {n}")
    direccion = 'direccion'


class MesaFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.Mesa'

    # 5 es un nro arbitrario para que no coincida con el id y salten potenciales errores.
    numero = factory.Sequence(lambda n: str(n + 5))
    lugar_votacion = factory.SubFactory(LugarVotacionFactory)
    circuito = factory.LazyAttribute(lambda obj: obj.lugar_votacion.circuito)
    electores = 100

    @factory.post_generation
    def categorias(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for categoria in extracted:
                MesaCategoriaFactory(mesa=self, categoria=categoria)
        else:
            MesaCategoriaDefaultFactory(mesa=self)


class MesaCategoriaFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.MesaCategoria'
        django_get_or_create = ('mesa', 'categoria')

    mesa = factory.SubFactory(MesaFactory)
    categoria = factory.SubFactory(CategoriaFactory)


class MesaCategoriaDefaultFactory(MesaCategoriaFactory):
    categoria = factory.SubFactory(CategoriaFactory, nombre='default')


class FiscalFactory(DjangoModelFactory):

    class Meta:
        model = 'fiscales.Fiscal'

    user = factory.SubFactory(UserFactory)
    estado = 'CONFIRMADO'
    apellido = fake.last_name()
    nombres = fake.first_name()
    dni = factory.Sequence(lambda n: f'{n}00000{n}')


class CargaFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.Carga'

    mesa_categoria = factory.SubFactory(MesaCategoriaFactory)
    fiscal = factory.SubFactory(FiscalFactory)


class VotoMesaReportadoFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.VotoMesaReportado'

    carga = factory.SubFactory(CargaFactory)
    opcion = factory.SubFactory(OpcionFactory)


def get_random_image():
    """
    devuelve una imagen jpg de 30x30 con un color aleatorio
    """
    image = Image.new('RGB', (30, 30), f'#{random.randint(0, 0xFFFFFF):06x}')
    output = BytesIO()
    image.save(output, format="JPEG")
    return output


class AttachmentFactory(DjangoModelFactory):

    class Meta:
        model = 'adjuntos.Attachment'

    foto = factory.django.ImageField(from_func=get_random_image)


class IdentificacionFactory(DjangoModelFactory):

    class Meta:
        model = 'adjuntos.Identificacion'

    mesa = factory.SubFactory(MesaFactory)
    attachment = factory.SubFactory(AttachmentFactory)
    fiscal = factory.SubFactory(FiscalFactory)


class PreidentificacionFactory(DjangoModelFactory):
    class Meta:
        model = 'adjuntos.PreIdentificacion'


class ProblemaFactory(DjangoModelFactory):

    class Meta:
        model = 'problemas.Problema'

    reportado_por = factory.SubFactory(FiscalFactory)
    mesa = factory.SubFactory(MesaFactory)
    attachment = factory.SubFactory(AttachmentFactory)
    estado = 'potencial'


class TecnicaProyeccionFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.TecnicaProyeccion'

    nombre = factory.Sequence(lambda n: f'tecnica{n}')


class AgrupacionCircuitosFactory(DjangoModelFactory):

    class Meta:
        model = 'elecciones.AgrupacionCircuitos'

    proyeccion = factory.SubFactory(TecnicaProyeccionFactory)
    nombre = factory.Sequence(lambda n: f'user{n}')
    minimo_mesas = 1


class ConfiguracionComputoFactory(DjangoModelFactory):
    class Meta:
        model = 'elecciones.ConfiguracionComputo'

    fiscal = factory.SubFactory(FiscalFactory)


class ConfiguracionComputoDistritoFactory(DjangoModelFactory):
    class Meta:
        model = 'elecciones.ConfiguracionComputoDistrito'
