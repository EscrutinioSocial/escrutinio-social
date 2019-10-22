import structlog

from adjuntos.models import Attachment
from elecciones.models import Categoria, Circuito, MesaCategoria
from elecciones.basic_command import BaseCommand

from scheduling.scheduler import scheduler

logger = structlog.get_logger('scheduler')


class Command(BaseCommand):
    help = "Toma una lista de circuitos y la prioriza."

    def priorizar_circuito(self, lugar_en_cola, linea, slug_cat, nro_distrito, nro_seccion, nro_circuito, cant_mesas_necesarias):
        try:
            categoria = Categoria.objects.get(slug=slug_cat)
        except Circuito.DoesNotExist:
            logger.error("No existe la categoría con slug {slug_cat} (línea {linea}).")
            return lugar_en_cola

        try:
            circuito = Circuito.objects.get(
                numero=nro_circuito, seccion__numero=nro_seccion,
                seccion__distrito__numero=nro_distrito
            )
        except Circuito.DoesNotExist:
            logger.error("No existe el circuito nro {nro_circuito} en la sección nro {nro_seccion} y distrito {nro_distrito}  (línea {linea}).")
            return lugar_en_cola

        lugar_en_cola = self.priorizar_circuito_y_cat(lugar_en_cola, categoria, circuito, cant_mesas_necesarias)

        return lugar_en_cola

    def priorizar_circuito_y_cat(self, lugar_en_cola, categoria, circuito, cant_mesas_necesarias):
        cant_mesas_existentes = MesaCategoria.objects.filter(
            categoria=categoria,
            mesa__circuito=circuito,
            carga_testigo__isnull=False,
            status__in=[
                MesaCategoria.STATUS.parcial_consolidada_dc, MesaCategoria.STATUS.parcial_consolidada_csv
            ]
        ).count()

        if cant_mesas_existentes >= cant_mesas_necesarias:
            return

        # Tengo que priorizar.
        cant_necesarias = cant_mesas_necesarias - cant_mesas_existentes

        nuevo_lugar_en_cola = self.priorizar_mesacats(lugar_en_cola, circuito, cant_necesarias)
        cant_necesarias = nuevo_lugar_en_cola - lugar_en_cola
        if cant_necesarias > 0:
            lugar_en_cola = self.priorizar_fotos(lugar_en_cola, circuito, cant_necesarias)
        else:
            # No priorizo fotos porque ya hay mesas identificadas.
            lugar_en_cola = nuevo_lugar_en_cola

        return lugar_en_cola

    def priorizar_fotos(self, lugar_en_cola, circuito, cant_necesarias):
        # XXX Faltan las de la sección que contiene al circuito.
        attachments = Attachment.objects.filter(
            status=Attachment.STATUS.sin_identificar,
            pre_identificacion__circuito=circuito
        )[0:cant_necesarias]

        for attachment in attachments:
            ColaCargasPendientes(
                attachment=attachment,
                orden=lugar_en_cola,
                numero_carga=10,  # Esto es un truco para que si el scheduler normal la puso, no se pise.
                distrito=attachment.distrito_preidentificacion,
                seccion=attachment.seccion_preidentificacion
            )
            lugar_en_cola += 1

        return lugar_en_cola

    def priorizar_mesacats(self, lugar_en_cola, circuito, cant_necesarias):
        mcs = MesaCategoria.objects.filter(
            status=Attachment.STATUS.sin_identificar,
            pre_identificacion__circuito=circuito
        )[0:cant_necesarias]

        mcs = MesaCategoria.objects.filter(
            categoria=categoria,
            mesa__circuito=circuito,
            status__in=MesaCategoria.status_carga_parcial
        )

        for mc in mcs:
            ColaCargasPendientes(
                mesa_categoria=mc,
                orden=lugar_en_cola,
                numero_carga=10,  # Esto es un truco para que si el scheduler normal la puso, no se pise.
                distrito=mc.mesa.distrito,
                seccion=mc.mesa.seccion
            )
            lugar_en_cola += 1

        return lugar_en_cola

    def handle(self, *args, **options):
        super().handle(*args, **options)

        reader = DictReader(self.CSV.open())

        lugar_en_cola = 0
        for linea, row in enumerate(reader, 1):
            slug_cat = row['slug_cat']
            nro_distrito = row['nro_distrito']
            nro_seccion = row['nro_seccion']
            nro_circuito = row['nro_circuito']
            cant_mesas_necesarias = row['cant_mesas_necesarias']
            lugar_en_cola = self.priorizar_circuito(lugar_en_cola, linea, slug_cat, nro_distrito, nro_seccion, nro_circuito, cant_mesas_necesarias)
