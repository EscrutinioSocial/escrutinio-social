from rest_framework import serializers
from elecciones.models import (
    Categoria, Opcion, 
    Distrito, Seccion, Circuito, Mesa
)
from fiscales.models import Fiscal


class ActaSerializer(serializers.Serializer):
    foto = serializers.ImageField(help_text='La foto del acta')


class MesaSerializer(serializers.Serializer):
    distrito = serializers.PrimaryKeyRelatedField(
        queryset=Distrito.objects.all()
    )
    seccion = serializers.PrimaryKeyRelatedField(
        queryset=Seccion.objects.all()
    )
    circuito = serializers.PrimaryKeyRelatedField(
        queryset=Circuito.objects.all()
    )
    mesa = serializers.PrimaryKeyRelatedField(
        queryset=Mesa.objects.all()
    )


class VotoSerializer(serializers.Serializer):
    categoria = serializers.PrimaryKeyRelatedField(
        queryset=Categoria.objects.all()
    )
    opcion = serializers.PrimaryKeyRelatedField(
        queryset=Opcion.objects.all()
    )
    votos = serializers.IntegerField(
        min_value=0
    )
