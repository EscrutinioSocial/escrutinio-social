from elecciones.models import Distrito, Seccion

class BusquedaDistritoOSeccion():
    def __init__(self):
        self.limite_cantidad_resultados = 50
        self._resultados = None

    def set_valor_busqueda(self, valor):
        self.valor_busqueda = valor
        self._resultados = None
    
    def realizar_busqueda(self):
        if not self._resultados:
            self._resultados = []
            for distrito in Distrito.objects.filter(nombre__icontains=self.valor_busqueda):
                self._resultados.append(ResultadoBusquedaDistrito(distrito))
            for seccion in Seccion.objects.filter(nombre__icontains=self.valor_busqueda):
                self._resultados.append(ResultadoBusquedaSeccion(seccion))

    def resultados(self):
        self.realizar_busqueda()
        return self._resultados


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
