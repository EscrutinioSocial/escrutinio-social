import factory
from django.contrib.auth.models import User
from factory.django import DjangoModelFactory
from faker import Faker
from elecciones.views import TOTAL, POSITIVOS
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
    id = factory.Sequence(lambda n: n + 3)
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
    eleccion = factory.SubFactory(EleccionFactory, id=1)
    numero = factory.Sequence(lambda n: n + 1)
    lugar_votacion = factory.SubFactory(LugarVotacionFactory)
    circuito = factory.LazyAttribute(lambda obj: obj.lugar_votacion.circuito)
    electores = 100


class FiscalGeneralFactory(DjangoModelFactory):
    class Meta:
        model = 'fiscales.Fiscal'
    user = factory.SubFactory('User')
    estado = 'CONFIRMADO'
    apellido = fake.last_name_male()
    nombres = fake.first_name_male()
    dni = factory.Sequence(lambda n: f'{n}00000{n}')
    tipo = 'general'



class FiscalDeMesaFactory(FiscalGeneralFactory):
    tipo = 'de_mesa'



class VotoMesaReportadoFactory(DjangoModelFactory):
    class Meta:
        model = 'elecciones.VotoMesaReportado'
    mesa = factory.SubFactory(MesaFactory)
    opcion = factory.SubFactory(OpcionFactory)
    fiscal = factory.SubFactory(FiscalDeMesaFactory)


class AsignacionFiscalGeneralFactory(DjangoModelFactory):
    class Meta:
        model = 'fiscales.AsignacionFiscalGeneral'
    lugar_votacion = factory.SubFactory(LugarVotacionFactory)
    eleccion = factory.SubFactory(EleccionFactory, id=1)
    fiscal = factory.SubFactory(FiscalGeneralFactory)


class AsignacionFiscalDeMesaFactory(DjangoModelFactory):
    class Meta:
        model = 'fiscales.AsignacionFiscalDeMesa'
    mesa = factory.SubFactory(MesaFactory)
    fiscal = factory.SubFactory(FiscalDeMesaFactory)


class AttachmentFactory(DjangoModelFactory):
    class Meta:
        model = 'adjuntos.Attachment'

