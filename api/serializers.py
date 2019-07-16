from rest_framework import serializers
from elecciones.models import (
    Categoria, Opcion, 
    Distrito, Seccion, Circuito, Mesa
)
from fiscales.models import Fiscal


class ActaSerializer(serializers.Serializer):
    foto = serializers.ImageField(help_text='La foto del acta')


class VotoSerializer(serializers.Serializer):
    id_categoria = serializers.PrimaryKeyRelatedField(
        queryset=Categoria.objects.all()
    )
    id_opcion = serializers.PrimaryKeyRelatedField(
        queryset=Opcion.objects.all()
    )
    votos = serializers.IntegerField(
        min_value=0
    )

class ListarCategoriasQuerySerializer(serializers.Serializer):
    prioridad = serializers.IntegerField(default=2)


class CategoriaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class ListarOpcionesQuerySerializer(serializers.Serializer):
    solo_prioritarias = serializers.BooleanField(default=True)


class OpcionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    nombre_corto = serializers.CharField()


class DistritoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    numero = serializers.IntegerField(min_value=0)
    nombre = serializers.CharField()


class SeccionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    numero = serializers.IntegerField(min_value=0)
    nombre = serializers.CharField()


class CircuitoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    numero = serializers.CharField()
    nombre = serializers.CharField()


class MesaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    numero = serializers.CharField(read_only=True)
