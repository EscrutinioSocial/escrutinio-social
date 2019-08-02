from collections import defaultdict
from rest_framework import serializers

from adjuntos.models import Attachment
from elecciones.models import Categoria, Opcion


class ActaSerializer(serializers.Serializer):
    foto = serializers.ImageField(help_text='La foto del acta', write_only=True)
    foto_digest = serializers.CharField(read_only=True)

    def save(self, subido_por):
        foto = self.validated_data['foto']

        attachment = Attachment()
        attachment.subido_por = subido_por
        attachment.foto.save(foto.name, foto, save=False)
        attachment.save()

        return attachment


class MesaSerializer(serializers.Serializer):
    codigo_distrito = serializers.CharField()
    codigo_seccion = serializers.CharField()
    codigo_circuito = serializers.CharField()
    codigo_mesa = serializers.CharField()


class VotosListSerializer(serializers.ListSerializer):
    def validate(self, data):
        opciones = defaultdict(list)
        for votos in data:
            opciones[votos['categoria']].append(votos['opcion'])

        for categoria, opciones in opciones.items():
            prioritarias = categoria.opciones_actuales(solo_prioritarias=True)
            faltantes = [opc for opc in prioritarias if opc not in opciones]
            if faltantes:
                raise serializers.ValidationError(
                    'Se deben cargar todas las opciones prioritarias para cada categoría.'
                )

        return data


class VotoSerializer(serializers.Serializer):
    categoria = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all())
    opcion = serializers.PrimaryKeyRelatedField(queryset=Opcion.objects.all())
    votos = serializers.IntegerField(min_value=0)

    class Meta:
        list_serializer_class = VotosListSerializer


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
    codigo = serializers.CharField()
