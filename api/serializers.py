from rest_framework import serializers
from elecciones.models import Mesa, Categoria, Opcion
from fiscales.models import Fiscal


class VotoMesaReportadoSerializer(serializers.Serializer):
    opcion = serializers.PrimaryKeyRelatedField(
        queryset=Opcion.objects.all()
    )
    votos = serializers.IntegerField(
        min_value=0
    )


class CargaSerializer(serializers.Serializer):
    adjunto = serializers.ImageField()
    fiscal = serializers.PrimaryKeyRelatedField(
        queryset=Fiscal.objects.all(), 
        allow_null=True, 
        required=False
    )
    votos = VotoMesaReportadoSerializer(
        many=True, 
        required=False
    )


class CargasCSVSerializer(serializers.Serializer):
    archivo = serializers.FileField()

