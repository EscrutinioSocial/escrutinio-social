from rest_framework import serializers

from adjuntos.models import Attachment
from elecciones.models import Categoria, Opcion


class ActaSerializer(serializers.Serializer):
    foto = serializers.ImageField(help_text='La foto del acta', write_only=True)
    foto_digest = serializers.CharField(read_only=True)

    def save(self):
        foto = self.validated_data['foto']

        attachment = Attachment()
        attachment.foto.save(foto.name, foto, save=False)
        attachment.save()

        return attachment


class MesaSerializer(serializers.Serializer):
    codigo_distrito = serializers.IntegerField()
    codigo_seccion = serializers.IntegerField()
    codigo_circuito = serializers.CharField()
    codigo_mesa = serializers.CharField()


class VotoSerializer(serializers.Serializer):
    categoria = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all())
    opcion = serializers.PrimaryKeyRelatedField(queryset=Opcion.objects.all())
    votos = serializers.IntegerField(min_value=0)


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
