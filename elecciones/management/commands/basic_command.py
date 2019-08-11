from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
from csv import DictReader
from elecciones.models import Distrito, Seccion, Circuito, LugarVotacion, Mesa, Categoria
import datetime

class BaseCommand(BaseCommand):
    
    def log(self, message, level=2, ending='\n'):
        if level <= self.verbosity:
            self.stdout.write(message, ending=ending)
            
    def success(self, msg, level=3, ending='\n'):
        self.log(self.style.SUCCESS(msg), level, ending=ending)

    def warning(self, msg, level=1, ending='\n'):
        self.log(self.style.WARNING(msg), level, ending=ending)

    def error_log(self, msg, ending='\n'):
        self.log(self.style.ERROR(msg), 0, ending=ending)
        
    def log_creacion(self, object, created=True, level=3, ending='\n'):
        modelo = object._meta.model.__name__
        if created:
            self.success(f'Se creó {modelo} {object}', level, ending)
        else:
            self.warning(f'{modelo} {object} ya existe', level-1, ending)

    def to_nat(self, row, field_name, n):
        """ Conversión de un string a un natural. """
        try:
            value = row[field_name]
        except KeyError:
            self.error_log(f'No está {field_name} en la línea {n}.')
            return None

        try:
            value = int(value)
        except ValueError:
            self.error_log(f'El valor {value} del campo {field_name} no es un entero. Línea {n}.')
            return None

        if value <= 0:
            self.error_log(f'El valor {value} del campo {field_name} no es positivo. Línea {n}.')
            return None
        return value

    def to_nat_value(self, value, field_name, n):
        """ Conversión de un string a un natural. """
        try:
            value = int(value)
        except ValueError:
            self.error_log(f'El valor {value} del campo {field_name} no es un entero. Línea {n}.')
            return None

        if value <= 0:
            self.error_log(f'El valor {value} del campo {field_name} no es positivo. Línea {n}.')
            return None
        return value
