from functools import reduce

from escrutinio_social import settings
from elecciones.models import Mesa, MesaCategoria
from adjuntos.models import Attachment, PreIdentificacion


class GeneradorDatosFotos():
    def __init__(self):
        self.cantidad_mesas = None

    def calcular(self):
        if (self.cantidad_mesas == None):
            self.cantidad_mesas = self.query_inicial_mesas().count()
            self.mesas_con_foto_identificada = self.query_inicial_mesas().exclude(attachments=None).count()



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
            DatoDoble("Cantidad de mesas", self.nacion.cantidad_mesas,
                              self.nacion.cantidad_mesas, self.pba.cantidad_mesas, self.pba.cantidad_mesas),
            DatoDoble("Mesas con foto identificada", 
                                self.nacion.mesas_con_foto_identificada, self.nacion.cantidad_mesas, 
                                self.pba.mesas_con_foto_identificada, self.pba.cantidad_mesas),
        ]

    def datos_solo_nacion(self):
        self.nacion.calcular()
        self.pba.calcular()
        return [
            DatoDoble("Fotos con problema confirmado",
                                     self.nacion.fotos_con_problema_confirmado, self.nacion.cantidad_mesas),
            DatoDoble("Fotos en proceso de identificación",
                                     self.nacion.fotos_en_proceso, self.nacion.cantidad_mesas),
            DatoDoble("Fotos sin acciones de identificación",
                                     self.nacion.fotos_sin_acciones, self.nacion.cantidad_mesas),
            DatoDoble("Mesas sin foto (estimado)",
                              self.nacion.mesas_sin_foto, self.nacion.cantidad_mesas)
        ]


class GeneradorDatosPreidentificaciones():
    def __init__(self, query_inicial=PreIdentificacion.objects):
        self.cantidad_total = None
        self.query_inicial = query_inicial

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
            DatoDoble("Total", self.nacion.cantidad_total,
                              self.nacion.cantidad_total, self.pba.cantidad_total, self.pba.cantidad_total),
            DatoDoble("Con identificación a mesa consolidada", 
                              self.nacion.identificadas, self.nacion.cantidad_total, 
                              self.pba.identificadas, self.pba.cantidad_total),
            DatoDoble("Sin identificación a mesa consolidada", 
                              self.nacion.sin_identificar, self.nacion.cantidad_total, 
                              self.pba.sin_identificar, self.pba.cantidad_total),
        ]


class GeneradorDatosCarga():
    def __init__(self, query_inicial):
        self.query_inicial = query_inicial
        self.dato_total = None

    def calcular(self):
        if (self.dato_total == None):
            self.dato_total = self.crear_dato(self.query_inicial)
            self.dato_carga_confirmada = self.crear_dato(self.restringir_por_statuses(self.statuses_carga_confirmada()))
            self.dato_carga_csv = self.crear_dato(self.restringir_por_statuses(self.statuses_carga_csv()))
            self.dato_carga_en_proceso = self.crear_dato(self.restringir_por_statuses(self.statuses_carga_en_proceso()))
            self.dato_carga_sin_carga = self.crear_dato(self.restringir_por_statuses(self.statuses_sin_carga()))
            self.dato_carga_con_problemas=self.crear_dato(self.restringir_por_statuses(self.statuses_con_problemas()))
            
    def restringir_por_statuses(self, statuses):
        if len(statuses) == 0:
            return self.query_inicial

        queries_por_status = [self.query_inicial.filter(status=status) for status in statuses]
        return reduce(lambda x,y: x | y, queries_por_status)

    def crear_dato(self, query):
        return query.count()

    def statuses_con_problemas(self):
        return [MesaCategoria.STATUS.con_problemas]


class GeneradorDatosCargaParcial(GeneradorDatosCarga):
    def statuses_carga_confirmada(self):
        return [
                MesaCategoria.STATUS.parcial_consolidada_dc,
                MesaCategoria.STATUS.total_sin_consolidar,
                MesaCategoria.STATUS.total_en_conflicto,
                MesaCategoria.STATUS.total_consolidada_dc
            ]

    def statuses_carga_csv(self):
        return [MesaCategoria.STATUS.parcial_consolidada_csv,
                MesaCategoria.STATUS.total_consolidada_csv]

    def statuses_carga_en_proceso(self):
        return [MesaCategoria.STATUS.parcial_en_conflicto, MesaCategoria.STATUS.parcial_sin_consolidar]

    def statuses_sin_carga(self):
        return [MesaCategoria.STATUS.sin_cargar]


class GeneradorDatosCargaTotal(GeneradorDatosCarga):
    def statuses_carga_confirmada(self):
        return [MesaCategoria.STATUS.total_consolidada_dc]

    def statuses_carga_csv(self):
        return [MesaCategoria.STATUS.total_consolidada_csv]

    def statuses_carga_en_proceso(self):
        return [MesaCategoria.STATUS.total_en_conflicto, MesaCategoria.STATUS.total_sin_consolidar]

    def statuses_sin_carga(self):
        return [
            MesaCategoria.STATUS.parcial_consolidada_dc,
            MesaCategoria.STATUS.parcial_consolidada_csv,
            MesaCategoria.STATUS.parcial_en_conflicto,
            MesaCategoria.STATUS.parcial_sin_consolidar,
            MesaCategoria.STATUS.sin_cargar
        ]


class GeneradorDatosCargaConsolidado():
    def __init__(self):
        super().__init__()
        self.crear_categorias()

    def query_inicial(self, slug_categoria):
        return MesaCategoria.objects.filter(categoria__slug=slug_categoria)

    def datos(self):
        self.pv.calcular()
        self.gv.calcular()
        return [
            DatoDoble("Total de mesas", self.pv.dato_total, self.pv.dato_total,
                      self.gv.dato_total, self.gv.dato_total),
            DatoDoble("Con carga confirmada", self.pv.dato_carga_confirmada, self.pv.dato_total,
                      self.gv.dato_carga_confirmada, self.gv.dato_total),
            DatoDoble("Con carga desde CSV", self.pv.dato_carga_csv, self.pv.dato_total,
                      self.gv.dato_carga_csv, self.gv.dato_total),
            DatoDoble("Con otras cargas sin confirmar", self.pv.dato_carga_en_proceso, self.pv.dato_total,
                      self.gv.dato_carga_en_proceso, self.gv.dato_total),
            DatoDoble("Sin carga", self.pv.dato_carga_sin_carga, self.pv.dato_total,
                      self.gv.dato_carga_sin_carga, self.gv.dato_total),
            DatoDoble("Con problemas", self.pv.dato_carga_con_problemas, self.pv.dato_total,
                      self.gv.dato_carga_con_problemas, self.gv.dato_total),
        ]


class GeneradorDatosCargaParcialConsolidado(GeneradorDatosCargaConsolidado):
    def crear_categorias(self):
        self.pv = GeneradorDatosCargaParcial(self.query_inicial(settings.SLUG_CATEGORIA_PRESI_Y_VICE))
        self.gv = GeneradorDatosCargaParcial(self.query_inicial(settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA))


class GeneradorDatosCargaTotalConsolidado(GeneradorDatosCargaConsolidado):
    def crear_categorias(self):
        self.pv = GeneradorDatosCargaTotal(self.query_inicial(settings.SLUG_CATEGORIA_PRESI_Y_VICE))
        self.gv = GeneradorDatosCargaTotal(self.query_inicial(settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA))


class DatoDoble():
    def __init__(self, texto, cantidad_1, cantidad_total_1, cantidad_2=None, cantidad_total_2=None):
        self.texto = texto
        self.cantidad_1 = cantidad_1
        self.porcentaje_1 = porcentaje(cantidad_1, cantidad_total_1)
        if (cantidad_2 != None):
            self.cantidad_2 = cantidad_2
            self.porcentaje_2 = porcentaje(cantidad_2, cantidad_total_2)


def porcentaje(parcial, total):
    porcentaje_calculado = 100 if parcial == total else (parcial * 100) / total
    return round(porcentaje_calculado, 2)
