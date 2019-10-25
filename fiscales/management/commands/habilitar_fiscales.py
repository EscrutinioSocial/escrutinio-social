from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group

from fiscales.models import Fiscal

class Command(BaseCommand):
    help = "Habilita fiscales anotados pasándolos al estado CONFIRMADO y agregándolos al grupo Validadores."

    def success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def warning(self, msg):
        self.stdout.write(self.style.WARNING(msg))

    def handle(self, *args, **options):
        # Consideramos los siguientes estados como iniciales.
        estados_previos = [ 'PRE-INSCRIPTO', Fiscal.ESTADOS.AUTOCONFIRMADO ]  # Lo ponemos a mano porque con - no funca.
        validadores = Group.objects.get(name='validadores')

        # Excluimos explícitamente les trolls.
        fiscales = Fiscal.objects.filter(
            estado__in=estados_previos, troll=False
        )

        # Nuevos validadores son quienes no estaban en el grupo.
        cantidad = fiscales.count()
        usuarios = User.objects.filter(
            id__in=fiscales.values_list('user__id', flat=True)
        ).exclude(
            id__in=validadores.user_set.all().values_list('id', flat=True)
        )

        cant_validadores = usuarios.count()
        nuevo_estado = Fiscal.ESTADOS.CONFIRMADO
        
        with transaction.atomic():
            validadores.user_set.add(*list(usuarios))
            fiscales.update(estado=nuevo_estado)
        
        self.success(f"Listo, se activaron {cantidad} fiscales poniendo"
                     f"su estado en {nuevo_estado} y agregando {cant_validadores} al grupo {validadores}.")
        
