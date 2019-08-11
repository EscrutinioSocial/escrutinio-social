from django.db import models
from model_utils import Choices
from model_utils.models import TimeStampedModel
from antitrolling.efecto import efecto_scoring_troll_descartar_problema


class ReporteDeProblema(TimeStampedModel):
    """
    Esta clase representa el reporte individual de un usuario sobre un problema.
    """

    TIPOS_DE_PROBLEMA = Choices(
        ('spam', 'La foto no es ni de un acta ni de un certificado. Parece subida maliciosamente.'),
        ('ilegible', 'La foto es de un acta pero no la puedo leer con claridad.'),
        ('falta_foto', 'La parte que es necesario cargar no está entre las fotos presentes.'),
        ('falta_identificador', 'El sistema no tiene la sección, circuito o mesa. Indicá el dato faltante en la descripción.' ),
        ('falta_lista', ("El sistema no tiene una de las listas o agrupaciones que aparecen en el acta o "
                         "certificado. Indicá el dato faltante en la descripción.")
        ),
        ('otro', 'El problema no encaja en ninguna de las anteriores; describilo en la descripción.')
    )

    # Spam: cuando no corresponde a un acta de escrutinio, o se sospecha que es con un objetivo malicioso.
    # Ilegible: es un acta, pero la parte pertinente de la información no se puede leer.
    # Falta foto: la parte que es necesario cargar no está entre las fotos presentes.
    # Falta identificador: es genérico para señalar la ausencia de una opción de localización de la mesa.
    # Falta lista: una de las opciones que figuran en el acta no está en el sistema.

    tipo_de_problema = models.CharField(
        max_length=100, null=True, blank=False,
        choices=TIPOS_DE_PROBLEMA,
        default=TIPOS_DE_PROBLEMA.ilegible
    )

    descripcion = models.TextField(null=True, blank=True)
    es_reporte_fake = models.BooleanField(default=False) # Se completa desde el admin.
    problema = models.ForeignKey('Problema', on_delete=models.CASCADE, related_name='reportes')
    identificacion = models.ForeignKey('adjuntos.Identificacion', null=True, blank=True, related_name='problemas', on_delete=models.CASCADE)
    carga = models.ForeignKey('elecciones.Carga', null=True, blank=True, related_name='problemas', on_delete=models.CASCADE)
    reportado_por = models.ForeignKey('fiscales.Fiscal', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.tipo_de_problema}: {self.descripcion} (vía {self.reportado_por})'


class Problema(TimeStampedModel):
    ESTADOS = Choices(
        'potencial',                # Todavía no se confirmó que exista de verdad.
        'descartado',               # No era realmente un problema, se usa para antitrolling.
        'pendiente',                # Confirmado y no se resolvió aún.
        ('en_curso', 'en curso'),   # Ídem anterior pero ya fue visto.
        'resuelto',
    )

    # O bien tiene un attach o una mesa.
    attachment = models.ForeignKey('adjuntos.Attachment', null=True, blank=True, related_name='problemas', on_delete=models.CASCADE)
    mesa = models.ForeignKey('elecciones.Mesa', null=True, blank=True, related_name='problemas', on_delete=models.CASCADE)

    estado = models.CharField(max_length=100, null=True, blank=True, choices=ESTADOS)
    resuelto_por = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL
    )

    @classmethod
    def confirmar_problema(cls, carga=None, identificacion=None):
        """
        Toma el problema asociado a la carga.mesa o a identificacion.attachment y
        lo confirma.
        """
        mesa = carga.mesa if carga else None
        attachment = identificacion.attachment if identificacion else None

        problema = cls.objects.filter(
            mesa=mesa, attachment=attachment
        ).exclude(
            # Puede haber tenido otros problemas previos.
            estado__in=[cls.ESTADOS.resuelto, cls.ESTADOS.descartado]
        ).first()
        problema.confirmar()

    @classmethod
    def resolver_problema_falta_hoja(cls, mesa):
        """
        Este método debe ser ejecutado cuando llega un nuevo attachment.
        Su función es marcar como resuelto un problema de falta de hoja.
        """
        problema = cls.objects.filter(
            mesa=mesa
        ).exclude(
            # Me quedo con los problemas abiertos.
            estado__in=[cls.ESTADOS.resuelto, cls.ESTADOS.descartado]
        ).filter(
            # Tienen algún reporte de que falta foto.
            reportes__tipo_de_problema__in=[ReporteDeProblema.TIPOS_DE_PROBLEMA.falta_foto]
        ).first()

        if problema:
            problema.resolver(None)     # Pongo None como quien lo resolvió.

    def confirmar(self):
        self.estado = self.ESTADOS.pendiente
        self.save(update_fields=['estado'])

    def aceptar(self):
        self.estado = self.ESTADOS.en_curso
        self.save(update_fields=['estado'])

    def resolver(self, resuelto_por):
        self.resolver_con_estado(self.ESTADOS.resuelto, resuelto_por)

    def descartar(self, resuelto_por):
        self.resolver_con_estado(self.ESTADOS.descartado, resuelto_por)
        for reporte in self.reportes.all():
            efecto_scoring_troll_descartar_problema(reporte.reportado_por, self)

    def resolver_con_estado(self, estado, resuelto_por):
        self.estado = estado
        self.resuelto_por = resuelto_por
        self.save(update_fields=['estado', 'resuelto_por'])

        for reporte in self.reportes.all():
            # Invalido todas las identificaciones asociadas al problema.
            if reporte.identificacion:
                reporte.identificacion.invalidar()

            # Ídem con las cargas.
            if reporte.carga:
                reporte.carga.invalidar()

    @classmethod
    def reportar_problema(cls, reportado_por, descripcion, tipo_de_problema, carga=None, identificacion=None):
        """
        Tiene que pasar carga xor identificacion.
        """
        mesa = carga.mesa if carga else None
        attachment = identificacion.attachment if identificacion else None

        # Me fijo si ya existe problema no resuelto ni descartado para esa mesa o attachment.
        problema = Problema.objects.filter(
            mesa=mesa, attachment=attachment
        ).exclude(
            estado=cls.ESTADOS.resuelto
        ).exclude(
            estado=cls.ESTADOS.descartado
        ).first()

        if not problema:
            estado_nuevo_problema = cls.ESTADOS.descartado if (reportado_por.troll) else cls.ESTADOS.potencial
            # Lo creo
            problema = Problema.objects.create(
                mesa=mesa, attachment=attachment,
                estado=estado_nuevo_problema
            )

        ReporteDeProblema.objects.create(
            tipo_de_problema=tipo_de_problema,
            descripcion=descripcion,
            reportado_por=reportado_por,
            identificacion=identificacion,
            carga=carga,
            problema=problema
        )
