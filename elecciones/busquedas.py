from elecciones.models import Distrito, Seccion

class BusquedaDistritoOSeccion():
    def __init__(self):
        self.limite_cantidad_resultados = 30
        self.limpiar_resultados()

    def set_valor_busqueda(self, valor):
        self.valor_busqueda = valor
        self.limpiar_resultados()

    def limpiar_resultados(self):
        self._resultados = None
        self._demasiados_resultados = False

    def realizar_busqueda(self):
        if not self._resultados:
            self._resultados = []
            query_distrito = Distrito.objects.filter(nombre__icontains=self.valor_busqueda)
            query_seccion = Seccion.objects.filter(nombre__icontains=self.valor_busqueda)
            if query_distrito.count() + query_seccion.count() > self.limite_cantidad_resultados:
                self._demasiados_resultados = True
            else:
                for distrito in query_distrito:
                    self._resultados.append(ResultadoBusquedaDistrito(distrito))
                for seccion in query_seccion:
                    self._resultados.append(ResultadoBusquedaSeccion(seccion))

    def resultados(self):
        self.realizar_busqueda()
        return self._resultados

    def hay_demasiados_resultados(self):
        self.realizar_busqueda()
        return self._demasiados_resultados


class ResultadoBusquedaDistrito():
    def __init__(self, distrito):
        self.nombre_distrito = distrito.nombre
        self.id_entidad = distrito.id
        self.tipo_entidad = 'Distrito'
        self.id_opcion = "Distrito-" + str(self.id_entidad)
        

class ResultadoBusquedaSeccion():
    def __init__(self, seccion):
        self.nombre_distrito = seccion.distrito.nombre
        self.nombre_seccion = seccion.nombre
        self.id_entidad = seccion.id
        self.tipo_entidad = 'Seccion'
        self.id_opcion = "Seccion-" + str(self.id_entidad)
