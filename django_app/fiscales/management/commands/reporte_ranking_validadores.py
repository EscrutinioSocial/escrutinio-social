import datetime

from django.core.management.base import BaseCommand
from django.db.models import Count

from elecciones.models import Carga
from fiscales.models import Fiscal


class Command(BaseCommand):
    help = "Genera el reporte ordenado de validadores segun sus cargas parciales consolidadas"

    def handle(self, *args, **options):
        nombre_archivo = "reporte_ranking_" + str(datetime.date.today()) + ".csv"
        print("Empieza a generar el archivo", nombre_archivo)

        cargas = Carga.objects.values("fiscal").filter(invalidada=False,
                                                       procesada=True,
                                                       mesa_categoria__status="parcial_consolidada_dc",
                                                       ).annotate(
            participaciones=Count('mesa_categoria')).order_by('-participaciones')

        archivo = open(nombre_archivo, "w")
        archivo.write("participaciones" + "," + "nombre" + "," + "apellido" + "," + "email" + "," + "telefono" + "\n")

        for carga in cargas:
            id_fiscal = carga["fiscal"]
            participaciones = carga["participaciones"]
            fiscal = Fiscal.objects.get(id=id_fiscal)
            nombre = fiscal.nombres
            apellido = fiscal.apellido
            datos = fiscal.datos_de_contacto
            telefono = "-"
            email = "-"

            if datos is not None:
                telefono_0 = datos.values("valor").filter(tipo="teléfono")
                if telefono_0.count() != 0:
                    telefono = telefono_0.get()["valor"]

                email_0 = datos.values("valor").filter(tipo="email")
                if email_0.count() != 0:
                    email = email_0.get()["valor"]

            archivo.write(str(participaciones) + "," + nombre + "," + apellido + "," + email + "," + telefono + "\n")

        archivo.close()

        print("Se terminó de escribir el archivo exitosamente")
