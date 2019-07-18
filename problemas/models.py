from django.db import models
from model_utils import Choices
from model_utils.models import TimeStampedModel



class ReporteDeProblema(TimeStampedModel):
    """
    Esta clase representa el reporte individual de un usuario sobre un problema.
    """

    TIPOS_DE_PROBLEMA = Choices(
        ('spam', 'Es SPAM'),
        ('invalida', 'Es inválida'),
        ('ilegible', 'No se entiende')
    )
    # Inválidas: si la información que contiene no puede cargarse de acuerdo a las validaciones del sistema.
    #     Es decir, cuando el acta viene con un error de validación en la propia acta o la foto con contiene
    #     todos los datos de identificación.
    # Spam: cuando no corresponde a un acta de escrutinio, o se sospecha que es con un objetivo malicioso.
    # Ilegible: es un acta, pero la parte pertinente de la información no se puede leer.

    tipo_de_problema = models.CharField(max_length=100, null=True, blank=True, choices=TIPOS_DE_PROBLEMA)

    reportado_por = models.ForeignKey('fiscales.Fiscal', on_delete=models.CASCADE)
    descripcion = models.TextField(null=True, blank=True)
    es_reporte_fake = models.BooleanField(default=False) # Se completa desde el admin.
    problema = models.ForeignKey('Problema', on_delete=models.CASCADE, related_name='reportes')
    identificacion = models.ForeignKey('adjuntos.Identificacion', null=True, related_name='problemas', on_delete=models.CASCADE)
    carga = models.ForeignKey('elecciones.Carga', null=True, related_name='problemas', on_delete=models.CASCADE)


class Problema(TimeStampedModel):
    ESTADOS = Choices(
        'potencial', # Todavía no se confirmó que exista de verdad.
        'pendiente'
        'en_curso',
        'resuelto',
    )

    # O bien tiene un attach o una mesa.
    attachment = models.ForeignKey('adjuntos.Attachment', null=True, related_name='problemas', on_delete=models.CASCADE)
    mesa = models.ForeignKey('elecciones.Mesa', null=True, related_name='problemas', on_delete=models.CASCADE)

    estado = models.CharField(max_length=100, null=True, blank=True, choices=ESTADOS)
    resuelto_por = models.ForeignKey(
        'auth.User', null=True, on_delete=models.SET_NULL
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
            estado=ESTADOS.resuelto
        ).first()

        problema.confirmar()


    def confirmar(self):
        self.estado = ESTADOS.pendiente
        self.save(update_fields=['estado'])

    def resolver(self):
        self.estado = ESTADOS.resuelto
        self.save(update_fields=['estado'])

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

        # Me fijo si ya existe problema no resuelto para esa mesa o attachment.
        problema = Problema.objects.filter(
            mesa=mesa, attachment=attachment
        ).exclude(
            estado=ESTADOS.resuelto
        )

        if not problema:
            # Lo creo
            problema = Problema.objects.create(
                mesa=mesa, attachment=attachment,
                estado=ESTADOS.potencial
            )

        reporte = ReporteDeProblema.objects.create(
            tipo_de_problema=tipo_de_problema,
            descripcion=descripcion,
            reportado_por=reportado_por,
            identificacion=identificacion,
            carga=carga,
            problema=problema
        )