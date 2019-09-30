from escrutinio_social import settings
from elecciones.models import Mesa
from adjuntos.models import Attachment, PreIdentificacion


class GeneradorDatosFotos():
    def __init__(self):
        self.cantidad_mesas = None

    def datos(self):
        self.calcular()
        return [*self.datos_comunes(), *self.datos_particulares()]

    def calcular(self):
        if (self.cantidad_mesas == None):
            self.cantidad_mesas = self.query_inicial_mesas().count()
            self.mesas_con_foto_identificada = self.query_inicial_mesas().exclude(attachments=None).count()


    def datos_particulares(self):
        return []


class GeneradorDatosFotosNacional(GeneradorDatosFotos):
    def query_inicial_mesas(self):
        return Mesa.objects

    def calcular(self):
        super().calcular()
        self.fotos_con_problema_confirmado = Attachment.objects.filter(
            status=Attachment.STATUS.problema).count()
        self.fotos_en_proceso = Attachment.objects.filter(
            status=Attachment.STATUS.sin_identificar).exclude(identificaciones=None).count()
        self.fotos_sin_acciones = Attachment.objects.filter(
            status=Attachment.STATUS.sin_identificar).filter(identificaciones=None).count()
        self.mesas_sin_foto = self.cantidad_mesas - (
            self.mesas_con_foto_identificada + self.fotos_con_problema_confirmado + self.fotos_en_proceso + self.fotos_sin_acciones
        )

    def datos_particulares(self):
        return [
            DatoAvanceDeCargaResumen("Fotos con problema confirmado",
                                     self.fotos_con_problema_confirmado, self.cantidad_mesas),
            DatoAvanceDeCargaResumen("Fotos en proceso de identificación",
                                     self.fotos_en_proceso, self.cantidad_mesas),
            DatoAvanceDeCargaResumen("Fotos sin acciones de identificación",
                                     self.fotos_sin_acciones, self.cantidad_mesas),
            DatoAvanceDeCargaResumen("Mesas sin foto (estimado)", self.mesas_sin_foto, self.cantidad_mesas)
        ]


class GeneradorDatosFotosDistrital(GeneradorDatosFotos):
    def __init__(self, distrito):
        super().__init__()
        self.distrito = distrito

    def query_inicial_mesas(self):
        return Mesa.objects.filter(circuito__seccion__distrito__numero=self.distrito)


class GeneradorDatosFotosConsolidado():
    def __init__(self):
        super().__init__()
        self.nacion = GeneradorDatosFotosNacional()
        self.pba = GeneradorDatosFotosDistrital(settings.DISTRITO_PBA)

    def datos_nacion_pba(self):
        self.nacion.calcular()
        self.pba.calcular()
        return [
            DatoConNacionYPBA("Cantidad de mesas", self.nacion.cantidad_mesas,
                              self.nacion.cantidad_mesas, self.pba.cantidad_mesas, self.pba.cantidad_mesas),
            DatoConNacionYPBA("Mesas con foto identificada", 
                                self.nacion.mesas_con_foto_identificada, self.nacion.cantidad_mesas, 
                                self.pba.mesas_con_foto_identificada, self.pba.cantidad_mesas),
        ]

    def datos_solo_nacion(self):
        self.nacion.calcular()
        self.pba.calcular()
        return [
            DatoConNacionYPBA("Fotos con problema confirmado",
                                     self.nacion.fotos_con_problema_confirmado, self.nacion.cantidad_mesas),
            DatoConNacionYPBA("Fotos en proceso de identificación",
                                     self.nacion.fotos_en_proceso, self.nacion.cantidad_mesas),
            DatoConNacionYPBA("Fotos sin acciones de identificación",
                                     self.nacion.fotos_sin_acciones, self.nacion.cantidad_mesas),
            DatoConNacionYPBA("Mesas sin foto (estimado)",
                              self.nacion.mesas_sin_foto, self.nacion.cantidad_mesas)
        ]


class GeneradorDatosPreidentificaciones():
    def __init__(self, query_inicial=PreIdentificacion.objects):
        self.cantidad_total = None
        self.query_inicial = query_inicial

    def datos(self):
        self.calcular()
        return [
            DatoAvanceDeCargaResumen("Total", self.cantidad_total, self.cantidad_total),
            DatoAvanceDeCargaResumen("Identificación a mesa confirmada",
                                     self.identificadas, self.cantidad_total),
            DatoAvanceDeCargaResumen("Sin identificación a mesa confirmada",
                                     self.sin_identificar, self.cantidad_total),
        ]

    def calcular(self):
        if (self.cantidad_total == None):
            self.cantidad_total = self.query_inicial.count()
            self.identificadas = self.query_inicial.filter(attachment__status=Attachment.STATUS.identificada).count()
            self.sin_identificar = self.cantidad_total - self.identificadas


class GeneradorDatosPreidentificacionesConsolidado():
    def __init__(self):
        super().__init__()
        self.nacion = GeneradorDatosPreidentificaciones()
        self.pba = GeneradorDatosPreidentificaciones(
            PreIdentificacion.objects.filter(distrito__numero=settings.DISTRITO_PBA))

    def datos(self):
        self.nacion.calcular()
        self.pba.calcular()
        return [
            DatoConNacionYPBA("Total", self.nacion.cantidad_total,
                              self.nacion.cantidad_total, self.pba.cantidad_total, self.pba.cantidad_total),
            DatoConNacionYPBA("Con identificación a mesa consolidada", 
                              self.nacion.identificadas, self.nacion.cantidad_total, 
                              self.pba.identificadas, self.pba.cantidad_total),
            DatoConNacionYPBA("Sin identificación a mesa consolidada", 
                              self.nacion.sin_identificar, self.nacion.cantidad_total, 
                              self.pba.sin_identificar, self.pba.cantidad_total),
        ]


    # def query_inicial_preidentificaciones(self):
    #     return PreIdentificacion.objects
    # def query_inicial_preidentificaciones(self):
    #     return PreIdentificacion.objects.filter(distrito__numero=self.distrito)


class DatoConNacionYPBA():
    def __init__(self, texto, cantidad_nacion, cantidad_total_nacion, cantidad_pba=None, cantidad_total_pba=None):
        self.texto = texto
        self.cantidad_nacion = cantidad_nacion
        self.porcentaje_nacion = porcentaje(cantidad_nacion, cantidad_total_nacion)
        if (cantidad_pba != None):
            self.cantidad_pba = cantidad_pba
            self.porcentaje_pba = porcentaje(cantidad_pba, cantidad_total_pba)


def porcentaje(parcial, total):
    porcentaje_calculado = 100 if parcial == total else (parcial * 100) / total
    return round(porcentaje_calculado, 2)
