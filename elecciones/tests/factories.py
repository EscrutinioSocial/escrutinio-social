import factory
from django.contrib.auth.models import User
from factory.django import DjangoModelFactory
from faker import Faker
from elecciones.views import TOTAL
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
    orden = factory.Sequence(lambda n: n + 1)
    nombre = factory.LazyAttribute(lambda obj: f"Partido {obj.orden}")


class OpcionFactory(DjangoModelFactory):
    class Meta:
        model = 'elecciones.Opcion'
        django_get_or_create = ('nombre',)
    nombre = factory.LazyAttribute(lambda obj: f"Opción {obj.orden}")
    partido = factory.SubFactory(PartidoFactory)
    orden = factory.Sequence(lambda n: n + 1)


class EleccionFactory(DjangoModelFactory):
    class Meta:
        model = 'elecciones.Eleccion'
        django_get_or_create = ('id',)
    id = factory.Sequence(lambda n: n)
    nombre = factory.LazyAttribute(lambda obj: f"elecciones-{obj.id}")
    slug = factory.LazyAttribute(lambda obj: obj.nombre)

    @factory.post_generation
    def opciones(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            # A list of groups were passed in, use them
            for opcion in extracted:
                self.opciones.add(opcion)
        else:
            self.opciones.add(OpcionFactory(nombre=TOTAL, partido=None, es_contable=False))
            self.opciones.add(OpcionFactory(nombre='opc1', es_contable=True))
            self.opciones.add(OpcionFactory(nombre='opc2'))
            self.opciones.add(OpcionFactory(nombre='opc3'))



class SeccionFactory(DjangoModelFactory):
    class Meta:
        model = 'elecciones.Seccion'

    numero = factory.Sequence(lambda n: n + 1)
    nombre = factory.LazyAttribute(lambda obj: f"Sección {obj.numero}")


class CircuitoFactory(DjangoModelFactory):
    class Meta:
        model = 'elecciones.Circuito'
    seccion = factory.SubFactory(SeccionFactory)
    numero = factory.Sequence(lambda n: n + 1)
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
    numero = factory.Sequence(lambda n: n + 1)
    lugar_votacion = factory.SubFactory(LugarVotacionFactory)
    circuito = factory.LazyAttribute(lambda obj: obj.lugar_votacion.circuito)
    electores = 100

    @factory.post_generation
    def eleccion(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for eleccion in extracted:
                self.eleccion.add(eleccion)
        else:
            self.eleccion.add(EleccionFactory(id=1))


class FiscalFactory(DjangoModelFactory):
    class Meta:
        model = 'fiscales.Fiscal'
    user = factory.SubFactory(UserFactory)
    estado = 'CONFIRMADO'
    apellido = fake.last_name()
    nombres = fake.first_name()
    dni = factory.Sequence(lambda n: f'{n}00000{n}')


class VotoMesaReportadoFactory(DjangoModelFactory):
    class Meta:
        model = 'elecciones.VotoMesaReportado'
    mesa = factory.SubFactory(MesaFactory)
    eleccion = factory.SubFactory(EleccionFactory, id=1)
    opcion = factory.SubFactory(OpcionFactory)
    fiscal = factory.SubFactory(FiscalFactory)


class AttachmentFactory(DjangoModelFactory):
    class Meta:
        model = 'adjuntos.Attachment'

