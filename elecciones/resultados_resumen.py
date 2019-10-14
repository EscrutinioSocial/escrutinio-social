from functools import reduce

from escrutinio_social import settings
from elecciones.models import Mesa, MesaCategoria, Seccion, Distrito
from adjuntos.models import Attachment, PreIdentificacion


class SinRestriccion():
    def nombre(self):
        return 'Sin restricción'

    def restringe_algo(self):
        return False


class RestriccionPorDistrito():
    def __init__(self, distrito_id):
        self.distrito_id = distrito_id

    def nombre(self):
        distrito = Distrito.objects.filter(id=self.distrito_id).first()
        return distrito.nombre

    def restringe_algo(self):
        return True

    def aplicar_restriccion_mesas(self, query):
        return query.filter(circuito__seccion__distrito__id=self.distrito_id)

    def aplicar_restriccion_preidentificaciones(self, query):
        return query.filter(distrito__id=self.distrito_id)


class RestriccionPorSeccion():
    def __init__(self, seccion_id):
        self.seccion_id = seccion_id

    def nombre(self):
        seccion = Seccion.objects.filter(id=self.seccion_id).first()
        return f'{seccion.nombre} ({seccion.distrito.nombre})'

    def restringe_algo(self):
        return True

    def aplicar_restriccion_mesas(self, query):
        return query.filter(circuito__seccion__id=self.seccion_id)

    def aplicar_restriccion_preidentificaciones(self, query):
        return query.filter(seccion__id=self.seccion_id)




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


class GeneradorDatosFotosConRestriccion(GeneradorDatosFotos):
    def __init__(self, restriccion):
        super().__init__()
        self.restriccion = restriccion

    def query_inicial_mesas(self):
        return self.restriccion.aplicar_restriccion_mesas(Mesa.objects)


class NoGeneradorDatosFotos():
    def __init__(self):
        self.cantidad_mesas = None
        self.mesas_con_foto_identificada = None

    def calcular(self):
        pass


class GeneradorDatosFotosConsolidado():
    def __init__(self, restriccion=None):
        super().__init__()
        self.nacion = GeneradorDatosFotosNacional()
        self.pba = GeneradorDatosFotosDistrital(settings.DISTRITO_PBA)
        if restriccion and restriccion.restringe_algo():
            self.restringido = GeneradorDatosFotosConRestriccion(restriccion)
        else:
            self.restringido = NoGeneradorDatosFotos()


    def datos_nacion_pba_restriccion(self):
        self.nacion.calcular()
        self.pba.calcular()
        self.restringido.calcular()
        print(
            f'Después de calcular datos de fotos, restringido da {self.restringido.cantidad_mesas} - {self.restringido.mesas_con_foto_identificada}')
        print(self.restringido)
        return [
            DatoTriple("Cantidad de mesas",
                       self.nacion.cantidad_mesas, self.nacion.cantidad_mesas, 
                       self.pba.cantidad_mesas, self.pba.cantidad_mesas,
                       self.restringido.cantidad_mesas, self.restringido.cantidad_mesas),
            DatoTriple("Mesas con foto identificada", 
                       self.nacion.mesas_con_foto_identificada, self.nacion.cantidad_mesas, 
                       self.pba.mesas_con_foto_identificada, self.pba.cantidad_mesas,
                       self.restringido.mesas_con_foto_identificada, self.restringido.cantidad_mesas),
        ]

    def datos_solo_nacion(self):
        self.nacion.calcular()
        return [
            DatoTriple("Fotos en proceso de identificación",
                                     self.nacion.fotos_en_proceso, self.nacion.cantidad_mesas),
            DatoTriple("Fotos sin acciones de identificación",
                                     self.nacion.fotos_sin_acciones, self.nacion.cantidad_mesas),
            DatoTriple("Mesas sin foto (estimado)",
                              self.nacion.mesas_sin_foto, self.nacion.cantidad_mesas),
            DatoTriple("Fotos con problema confirmado",
                      self.nacion.fotos_con_problema_confirmado, self.nacion.cantidad_mesas),
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


class NoGeneradorDatosPreidentificaciones():
    def __init__(self):
        self.cantidad_total = None
        self.identificadas = None
        self.sin_identificar = None

    def calcular(self):
        pass


class GeneradorDatosPreidentificacionesConsolidado():
    def __init__(self, restriccion):
        super().__init__()
        self.nacion = GeneradorDatosPreidentificaciones()
        self.pba = GeneradorDatosPreidentificaciones(
            PreIdentificacion.objects.filter(distrito__numero=settings.DISTRITO_PBA))
        if restriccion and restriccion.restringe_algo():
            self.restringido = GeneradorDatosPreidentificaciones(
                restriccion.aplicar_restriccion_preidentificaciones(PreIdentificacion.objects))
        else:
            self.restringido = NoGeneradorDatosPreidentificaciones()

    def datos(self):
        self.nacion.calcular()
        self.pba.calcular()
        self.restringido.calcular()
        return [
            DatoTriple("Total", self.nacion.cantidad_total,
                       self.nacion.cantidad_total, self.pba.cantidad_total, self.pba.cantidad_total,
                       self.restringido.cantidad_total, self.restringido.cantidad_total),
            DatoTriple("Con identificación consolidada", 
                       self.nacion.identificadas, self.nacion.cantidad_total, 
                       self.pba.identificadas, self.pba.cantidad_total,
                       self.restringido.identificadas, self.restringido.cantidad_total),
            DatoTriple("Sin identificación consolidada", 
                              self.nacion.sin_identificar, self.nacion.cantidad_total, 
                              self.pba.sin_identificar, self.pba.cantidad_total,
                       self.restringido.sin_identificar, self.restringido.cantidad_total),
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
        self.query_base = MesaCategoria.objects
        self.crear_categorias()

    def query_inicial(self, slug_categoria):
        return self.query_base.filter(categoria__slug=slug_categoria)

    def set_query_base(self, query):
        self.query_base = query
        self.crear_categorias()
        
    def calcular(self):
        self.pv.calcular()
        self.gv.calcular()

    def datos(self):
        self.calcular()
        return [
            DatoTriple("Total de mesas", self.pv.dato_total, self.pv.dato_total,
                      self.gv.dato_total, self.gv.dato_total),
            DatoTriple("Con carga confirmada", self.pv.dato_carga_confirmada, self.pv.dato_total,
                      self.gv.dato_carga_confirmada, self.gv.dato_total),
            DatoTriple("Con carga desde CSV sin confirmar", self.pv.dato_carga_csv, self.pv.dato_total,
                      self.gv.dato_carga_csv, self.gv.dato_total),
            DatoTriple("Con otras cargas sin confirmar", self.pv.dato_carga_en_proceso, self.pv.dato_total,
                      self.gv.dato_carga_en_proceso, self.gv.dato_total),
            DatoTriple("Sin carga", self.pv.dato_carga_sin_carga, self.pv.dato_total,
                      self.gv.dato_carga_sin_carga, self.gv.dato_total),
            DatoTriple("Con problemas", self.pv.dato_carga_con_problemas, self.pv.dato_total,
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


class DatoTriple():
    def __init__(self, texto, cantidad_1, cantidad_total_1, cantidad_2=None, cantidad_total_2=None, cantidad_3=None, cantidad_total_3=None):
        self.texto = texto
        self.cantidad_1 = cantidad_1
        self.porcentaje_1 = porcentaje(cantidad_1, cantidad_total_1)
        if (cantidad_2 != None):
            self.cantidad_2 = cantidad_2
            self.porcentaje_2 = porcentaje(cantidad_2, cantidad_total_2)
        if (cantidad_3 != None):
            self.cantidad_3 = cantidad_3
            self.porcentaje_3 = porcentaje(cantidad_3, cantidad_total_3)


def porcentaje(parcial, total):
    porcentaje_calculado = 0 if total == 0 else (100 if parcial == total else (parcial * 100) / total)
    return round(porcentaje_calculado, 2)
