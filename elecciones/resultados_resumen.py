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

    def datos_comunes(self):
        return [
            DatoAvanceDeCargaResumen("Cantidad de mesas", self.cantidad_mesas, self.cantidad_mesas),
            DatoAvanceDeCargaResumen("Mesas con foto identificada",
                                    self.mesas_con_foto_identificada, self.cantidad_mesas),
        ]

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



    # def query_inicial_preidentificaciones(self):
    #     return PreIdentificacion.objects
    # def query_inicial_preidentificaciones(self):
    #     return PreIdentificacion.objects.filter(distrito__numero=self.distrito)


class DatoAvanceDeCargaResumen():
    def __init__(self, texto, cantidad, cantidad_total):
        self.texto = texto
        self.cantidad = cantidad
        porcentaje_calculado = 100 if cantidad == cantidad_total else (cantidad * 100) / cantidad_total
        self.porcentaje = round(porcentaje_calculado, 2)

