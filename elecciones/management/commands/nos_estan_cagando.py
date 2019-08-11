import math

from django.core.management.base import BaseCommand

from elecciones.models import Distrito, Seccion, Circuito, Eleccion, Categoria, Mesa, Partido, MesaCategoria, TIPOS_DE_AGREGACIONES, NIVELES_DE_AGREGACION, OPCIONES_A_CONSIDERAR
from elecciones.resultados import Sumarizador
from escrutinio_social import settings


class Command(BaseCommand):
    help = "Generar reportes para evaluar qué urnas hay que pedir recuento definitivo o revisión."

    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout=None, stderr=None, no_color=False, force_color=False)

        # Opciones por default para usar cuando no nos dan parámetros
        self.partido_fdt = Partido.objects.get(codigo=settings.CODIGO_PARTIDO_NOSOTROS)
        self.partido_cambiemos = Partido.objects.get(codigo=settings.CODIGO_PARTIDO_ELLOS)

    def imprimir_mesa(self, mesa):
        circuito = mesa.circuito
        seccion = circuito.seccion
        distrito = seccion.distrito
        return f"D {distrito} - S {seccion} - C {circuito} - M {mesa}: "

    def alerta_mesa(self, mesa, problema):
        mensaje = self.imprimir_mesa(mesa) + problema
        self.stdout.write(self.style.ERROR(f"ALERTA: {mensaje}"))

    def warning(self, problema, encabezado=None):
        mensaje = problema
        if encabezado is not None:
            mensaje = encabezado + mensaje
        self.stdout.write(self.style.WARNING(f"CUIDADO: {mensaje}"))

    def warning_mesa(self, mesa, problema):
        descrp_mesa = ""
        if mesa is not None:
            descrp_mesa = self.imprimir_mesa(mesa)
        self.warning(problema, descrp_mesa)

    def status(self, texto):
        self.stdout.write(f"{texto}")
        # self.stdout.write(self.style.SUCCESS(texto))

    def status_green(self, texto):
        self.stdout.write(self.style.SUCCESS(texto))

    def get_votos_partido(self, resultados, partido):
        return resultados.tabla_positivos()[partido]['votos']

    def get_votos_nuestros(self, resultados):
        return self.get_votos_partido(resultados, self.partido_fdt)

    def get_votos_ellos(self, resultados):
        return self.get_votos_partido(resultados, self.partido_cambiemos)

    def analizar_ceros_mesas(self, mesas):
        """
        Determina si en alguna mesa nosotros o ellos sacamos cero votos.
        """
        for mesa in mesas:
            resultados = self.get_resultados_mesa(mesa)
            votos_nuestros = self.get_votos_nuestros(resultados)
            votos_ellos = self.get_votos_ellos(resultados)
            if votos_nuestros == 0:
                self.alerta_mesa(mesa, "Fernandez en cero votos.")
            if votos_ellos == 0:
                self.warning_mesa(mesa, "Macri en cero votos.")

    def cant_mesas_ganadas(self, mesas):
        """
        Devuelve cuántas de las mesas parámetro fueron ganadas por cada fuerza.
        """
        cant_ganadas_fdt = 0
        cant_ganadas_cambiemos = 0
        for mesa in mesas:
            resultados = self.get_resultados_mesa(mesa)
            votos_nuestros = self.get_votos_nuestros(resultados)
            votos_ellos = self.get_votos_ellos(resultados)

            if votos_nuestros > votos_ellos:
                cant_ganadas_fdt = cant_ganadas_fdt + 1
            elif votos_ellos > votos_nuestros:
                cant_ganadas_cambiemos = cant_ganadas_cambiemos + 1
        return cant_ganadas_fdt, cant_ganadas_cambiemos

    def comparar_mesas_con_correo(self, mesas):
        """
        Determina si en alguna mesa nosotros o ellos tiene diferencia con lo informado en el Correo.
        """
        for mesa in mesas:

            carga_testigo = self.get_carga_testigo(mesa)
            if not carga_testigo:
                self.alerta_mesa(mesa, "No existe carga testigo para la mesa")

            carga_correo = self.get_carga_correo(mesa)
            if not carga_correo:
                # TODO preguntar si vale la pena informar esto
                self.warning_mesa(mesa, f"No existe carga oficial (correo) para la mesa.")

            if carga_testigo and carga_correo:
                if carga_testigo.firma != carga_correo.firma:
                    self.alerta_mesa(mesa, f"Tiene diferencias respecto la carga oficial. Testigo: {carga_testigo.firma}. Correo: {carga_correo.firma}.")
                    if self.get_votos_nuestros_carga(carga_correo) == 0:
                        self.alerta_mesa(mesa, "La carga oficial reporta 0 votos nuestros")

        return

    def get_votos_nuestros_carga(self, carga):
        opcion_votos_nuestros = carga.opcion_votos().filter(opcion__partido=self.partido_fdt)
        votos_nuestros = [voto for (opcion, voto) in opcion_votos_nuestros][0]
        return votos_nuestros

    def get_carga_testigo(self, mesa):
        return MesaCategoria.objects.get(
            mesa=mesa,
            categoria=self.categoria,
        ).carga_testigo

    def get_carga_correo(self, mesa):
        return MesaCategoria.objects.get(
            mesa=mesa,
            categoria=self.categoria,
        ).parcial_oficial

    def reporte_tendencias(self, mesas, cant_mesas_ganadas_por_fdt, cant_mesas_ganadas_por_cambiemos):
        """
        Reporta mesas ganadas por un partido en un circuito donde ganó el otro.
        """
        dif = 1
        if cant_mesas_ganadas_por_cambiemos + cant_mesas_ganadas_por_fdt != 0:
            dif = math.fabs(cant_mesas_ganadas_por_cambiemos - cant_mesas_ganadas_por_fdt) / (
                cant_mesas_ganadas_por_cambiemos + cant_mesas_ganadas_por_fdt)

        if dif < self.umbral_mesas_ganadas:
            # Está parejo, no tiene sentido.
            return

        for mesa in mesas:
            resultados = self.get_resultados_mesa(mesa)
            votos_nuestros = self.get_votos_nuestros(resultados)
            votos_ellos = self.get_votos_ellos(resultados)

            if cant_mesas_ganadas_por_fdt > cant_mesas_ganadas_por_cambiemos:
                if votos_ellos > votos_nuestros:
                    self.alerta_mesa(mesa, f"En el circuito FdT ganó en la mayoría de las mesas pero en "
                                     f"ésta no (FdT: {votos_nuestros} votos, JpC: {votos_ellos} votos).")
                elif votos_nuestros > votos_ellos:
                    self.warning_mesa(mesa,
                                      "En el circuito JpC ganó en la mayoría de las mesas pero en ésta no ("
                                      f"FdT: {votos_nuestros} votos, JpC: {votos_ellos} votos).")

    def reporte_promedio(self, mesas, cant_mesas, promedio_votos_fdt, promedio_votos_cambiemos):
        """
        Reporta mesas en las que estemos a más de 2 std del promedio del circuito.
        """
        suma_diferencias_cuadradas_fdt = 0
        suma_diferencias_cuadradas_cambiemos = 0
        for mesa in mesas:
            resultados = self.get_resultados_mesa(mesa)
            votos_nuestros = self.get_votos_nuestros(resultados)
            votos_ellos = self.get_votos_ellos(resultados)
            suma_diferencias_cuadradas_fdt += math.pow((votos_nuestros - promedio_votos_fdt), 2)
            suma_diferencias_cuadradas_cambiemos += math.pow((votos_ellos - promedio_votos_cambiemos), 2)

        cant_mesas = mesas.count()

        varianza_fdt = suma_diferencias_cuadradas_fdt / cant_mesas
        varianza_cambiemos = suma_diferencias_cuadradas_cambiemos / cant_mesas

        desv_estandard_fdt = math.sqrt(varianza_fdt)
        desv_estandard_cambiemos = math.sqrt(varianza_cambiemos)

        for mesa in mesas:
            resultados = self.get_resultados_mesa(mesa)
            votos_nuestros = self.get_votos_nuestros(resultados)
            votos_ellos = self.get_votos_ellos(resultados)

            dif_a_prom_fdt = math.fabs(votos_nuestros - promedio_votos_fdt)
            if dif_a_prom_fdt > desv_estandard_fdt:
                self.alerta_mesa(
                    mesa,
                    f"Mucha diferencia de votos con promedio (FdT = {votos_nuestros}, prom FdT = {promedio_votos_fdt}, "
                    f"dif = {dif_a_prom_fdt}, dif máxima esperada = {desv_estandard_fdt}"
                )

            dif_a_prom_cambiemos = math.fabs(votos_ellos - promedio_votos_cambiemos)
            if dif_a_prom_cambiemos > desv_estandard_cambiemos:
                self.warning_mesa(
                    mesa,
                    f"Mucha diferencia de votos con promedio (JpC = {votos_ellos}, "
                    f"prom JpC = {promedio_votos_cambiemos}, "
                    f"dif = {dif_a_prom_cambiemos}, dif máxima esperada = {desv_estandard_cambiemos}"
                )

    def analizar_circuito(self, circuito):
        self.sumarizador = self.crear_sumarizador_circuito(circuito)
        resultados_circuito = self.sumarizador.get_resultados(self.categoria)

        total_mesas_del_circuito = resultados_circuito.total_mesas()

        # Si no tiene mesas listas no continuamos.
        if resultados_circuito.total_mesas_escrutadas() == 0:
            return

        # Me quedo con las escrutadas.
        mesas = self.sumarizador.mesas(self.categoria).filter(
            mesacategoria__categoria=self.categoria,
            mesacategoria__carga_testigo__isnull=False
        )

        if self.analizar_ceros:
            self.analizar_ceros_mesas(mesas)

        cant_mesas_listas = mesas.count()
        if self.comparar_con_correo:
            self.comparar_mesas_con_correo(mesas)

        umbral_mesas_superado = cant_mesas_listas > (
            self.umbral_analisis_estadisticos / 100.0 * total_mesas_del_circuito)

        if not umbral_mesas_superado:
            self.warning(f"No se superó el umbral de mesas listas en circuito {circuito.numero} "
                         f"(sólo {cant_mesas_listas} de {total_mesas_del_circuito}).")
            return

        cant_mesas_ganadas_por_fdt, cant_mesas_ganadas_por_cambiemos = self.cant_mesas_ganadas(mesas)

        if self.analizar_tendencias:
            self.reporte_tendencias(mesas, cant_mesas_ganadas_por_fdt, cant_mesas_ganadas_por_cambiemos)

        if self.analizar_promedio:
            total_votos_fdt = self.get_votos_nuestros(resultados_circuito)
            total_votos_cambiemos = self.get_votos_ellos(resultados_circuito)
            promedio_votos_fdt = total_votos_fdt / cant_mesas_listas
            promedio_votos_cambiemos = total_votos_cambiemos / cant_mesas_listas
            self.reporte_promedio(mesas, cant_mesas_listas, promedio_votos_fdt,
                                  promedio_votos_cambiemos)

    def armar_opciones_sumarizador(self, nivel, id):
        opciones = {
            "nivel_de_agregacion": nivel,
            "opciones_a_considerar": OPCIONES_A_CONSIDERAR.prioritarias,
            "tipo_de_agregacion": self.tipo_de_agregacion,
            "ids_a_considerar": [id]
        }
        return opciones

    def crear_sumarizador_circuito(self, circuito):
        opciones = self.armar_opciones_sumarizador(NIVELES_AGREGACION.circuito, circuito.id)
        return Sumarizador(**opciones)

    def get_resultados_circuito(self, circuito):
        return self.crear_sumarizador_circuito(circuito).get_resultados(self.categoria)

    def crear_sumarizador_mesa(self, mesa):
        opciones = self.armar_opciones_sumarizador(NIVELES_DE_AGREGACION.mesa, mesa.id)
        return Sumarizador(**opciones)

    def get_resultados_mesa(self, mesa):
        return self.crear_sumarizador_mesa(mesa).get_resultados(self.categoria)

    def analizar_seccion(self, seccion):
        for circuito in seccion.circuitos.all():
            self.analizar_circuito(circuito)

    def analizar_distrito(self, distrito):
        for seccion in distrito.secciones.all():
            self.analizar_seccion(seccion)

    def analizar_pais(self):
        distritos = Distrito.objects.all()
        for distrito in distritos:
            self.analizar_distrito(distrito)

    def add_arguments(self, parser):
        # Opciones para comparar fraude
        parser.add_argument("--analizar_ceros",
                            action="store_true", dest="analizar_ceros",
                            default=False,
                            help="Busca ceros en votos (default %(default)s)."
                            )
        parser.add_argument("--analizar_tendencias",
                            action="store_true", dest="analizar_tendencias",
                            default=False,
                            help="Busca mesas con cambio de tendencia (default %(default)s).",
                            )
        parser.add_argument("--analizar_promedio",
                            action="store_true", dest="analizar_promedio",
                            default=False,
                            help="Busca mesas a más de un desvío estándar del promedio (default %(default)s).",
                            )
        parser.add_argument("--comparar_con_correo",
                            action="store_true", dest="comparar_con_correo",
                            default=False,
                            help="Compara con los resultados que va publicando el Correo (default %(default)s).",
                            )

        # Umbrales para detectar fraudes
        parser.add_argument("--umbral_analisis_estadisticos",
                            type=int, dest="umbral_analisis_estadisticos",
                            help="Umbral de mesas listas por circuito para comenzar a hacer análisis estadísticos "
                            "(default %(default)s).",
                            default=30
                            )
        parser.add_argument("--umbral_mesas_ganadas",
                            type=float, dest="umbral_mesas_ganadas",
                            help="Porcentaje, umbral, de mesas para considerar dentro del "
                            "circuito que difieren (default %(default)s).",
                            default=0.4
                            )

        # Nivel de agregación a analizar
        parser.add_argument("--solo_seccion", type=int, dest="solo_seccion",
                            help="Analizar sólo la sección indicada (default %(default)s).", default=None)
        parser.add_argument("--solo_circuito", type=int, dest="solo_circuito",
                            help="Analizar sólo el circuito indicado (default %(default)s).", default=None)
        parser.add_argument("--solo_distrito", type=int, dest="solo_distrito",
                            help="Analizar sólo el distrito indicado (default %(default)s).", default=None)
        parser.add_argument("--categoria", type=str, dest="categoria",
                            help="Categoria a analizar (default %(default)s).", default=settings.NOMBRE_CATEGORIA_PRESI_Y_VICE)

        # Opciones a considerar
        parser.add_argument("--tipo_de_agregacion",
                            type=str, dest="tipo_de_agregacion",
                            help="Tipo de agregación del tipo de carga: "
                            f"{TIPOS_DE_AGREGACIONES.todas_las_cargas}, "
                            f"{TIPOS_DE_AGREGACIONES.solo_consolidados}, "
                            f"{TIPOS_DE_AGREGACIONES.solo_consolidados_doble_carga}; "
                            "(default %(default)s).",
                            # Por default sólo se analizan los resultados consolidados
                            default=TIPOS_DE_AGREGACIONES.solo_consolidados
                            )

    def handle(self, *args, **kwargs):
        """
        """
        self.analizar_ceros = kwargs['analizar_ceros']
        self.analizar_tendencias = kwargs['analizar_tendencias']
        self.analizar_promedio = kwargs['analizar_promedio']
        self.comparar_con_correo = kwargs['comparar_con_correo']

        self.umbral_analisis_estadisticos = kwargs['umbral_analisis_estadisticos']
        self.umbral_mesas_ganadas = kwargs['umbral_mesas_ganadas']

        self.tipo_de_agregacion = kwargs['tipo_de_agregacion']

        nombre_categoria = kwargs['categoria']
        self.categoria = Categoria.objects.get(nombre=nombre_categoria)
        print("Vamos a analizar la categoría:", self.categoria)

        self.asignar_nivel_agregacion(kwargs)
        self.analizar_segun_nivel_agregacion()

    def analizar_segun_nivel_agregacion(self):
        if self.circuito:
            self.status("Analizando circuito %s" % self.circuito.numero)
            self.analizar_circuito(self.circuito)
        elif self.seccion:
            self.status("Analizando sección %s" % self.seccion.numero)
            self.analizar_seccion(self.seccion)
        elif self.distrito:
            self.status("Analizando distrito %s" % self.distrito.numero)
            self.analizar_distrito(self.distrito)
        else:
            # Analiza todos los distritos
            self.status("Analizando país -> todos los distritos")
            self.analizar_pais()

    def asignar_nivel_agregacion(self, kwargs):
        # Analizar resultados de acuerdo a los niveles de agregación
        numero_circuito = kwargs['solo_circuito']
        numero_seccion = kwargs['solo_seccion']
        numero_distrito = kwargs['solo_distrito']
        self.distrito = None
        self.seccion = None
        self.circuito = None

        if numero_distrito:
            self.distrito = Distrito.objects.get(numero=numero_distrito)
            if numero_seccion:
                self.seccion = Seccion.objects.get(numero=numero_seccion, distrito=self.distrito)
                if numero_circuito:
                    self.circuito = Circuito.objects.get(numero=numero_circuito, seccion=self.seccion)
