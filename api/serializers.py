from rest_framework import serializers
from elecciones.models import (
    Categoria, Opcion
)
from fiscales.models import Fiscal


class ActaSerializer(serializers.Serializer):
    foto = serializers.ImageField(help_text='La foto del acta')


class MesaSerializer(serializers.Serializer):
    numero_distrito = serializers.IntegerField(min_value=0)
    numero_seccion = serializers.IntegerField(min_value=0)
    numero_circuito = serializers.CharField()
    numero_mesa = serializers.CharField()


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
