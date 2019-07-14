from django.shortcuts import redirect, render
from django.utils import timezone

from adjuntos.models import Attachment
from elecciones.models import Mesa


def siguiente_accion(request):
    """
    Elige la siguiente accion a ejecutarse
    - si hay actas en el queryset :meth:`Attachment.sin asignar`,
      entonces la accion es identificar una al azar
    - si hay mesas con carga pendiente (es decir, que tienen categorias sin cargar),
      se elige una por orden de prioridad y tamaño del circuito
    - caso contrario, no hay nada para hacer
    """
    accion = None

    if accion is None:
        foto = foto_a_identificar(request.user.fiscal)
        if not (foto is None):
            accion = IdentificacionDeFoto(request, foto)

    if accion is None:
        mesa_y_categoria = mesa_y_categoria_a_cargar()
        if not (mesa_y_categoria is None):
            accion = CargaCategoriaEnActa(request, mesa_y_categoria['mesa'], mesa_y_categoria['categoria'])

    if accion is None:
        accion = NoHayAccion(request)

    return accion


def foto_a_identificar(fiscal):
    attachments = Attachment.sin_identificar(0, fiscal)
    if attachments.exists():
        return attachments.order_by('?').first()
    
    return None


def mesa_y_categoria_a_cargar(): 
    mesa_elegida = None
    categoria_elegida = None
    hay_mesas_posibles = True
    while (mesa_elegida is None) and hay_mesas_posibles:
        mesas = Mesa.con_carga_pendiente().order_by(
            'orden_de_carga', '-lugar_votacion__circuito__electores'
        )
        hay_mesas_posibles = mesas.exists()
        if hay_mesas_posibles:
            mesa_elegida = mesas[0]
            categoria_elegida = mesa_elegida.siguiente_categoria_sin_carga()
            if categoria_elegida is None:
                mesa_elegida.marcar_todas_las_categorias_cargadas()
                mesa_elegida = None

    return None if (mesa_elegida is None) else { 'mesa': mesa_elegida, 'categoria': categoria_elegida }


"""
Accion sobre una foto (attachment):
estampa el tiempo de "asignación" para que se excluya durante el periodo
de guarda y redirige a la vista para su clasificación
"""
class IdentificacionDeFoto():
    attachment = None

    def __init__(self, _request, _attachment):
        self.attachment = _attachment

    def ejecutar(self):
        # se marca el adjunto
        self.attachment.taken = timezone.now()
        self.attachment.save(update_fields=['taken'])
        # se realiza el redirect
        return redirect('asignar-mesa', attachment_id=self.attachment.id)


"""
Accion sobre una mesa y una categoría:
estampa en la mesa el tiempo de "asignación" para que se excluya durante el periodo
de guarda y redirige a la vista para la carga de la mesa/categoría
"""
class CargaCategoriaEnActa():
    mesa = None
    categoria = None

    def __init__(self, _request, _mesa, _categoria):
        self.mesa = _mesa
        self.categoria = _categoria
    
    def ejecutar(self):
        # se marca que se inicia una carga
        self.mesa.taken = timezone.now()
        self.mesa.save(update_fields=['taken'])
        # se realiza el redirect
        return redirect(
            'mesa-cargar-resultados',
            categoria_id=self.categoria.id,
            mesa_numero=self.mesa.numero
        )


"""
Accion sobre una mesa y una categoría:
redirige a la vista para la carga de la mesa/categoría
"""
class ConfirmacionCategoriaEnActa():
    mesa = None
    categoria = None

    def __init__(self, _request, _mesa, _categoria):
        self.mesa = _mesa
        self.categoria = _categoria

    def ejecutar(self):
        # se realiza el redirect
        return redirect(
            'chequear-resultado-mesa',
            categoria_id=self.categoria.id,
            mesa_numero=self.mesa.numero
        )



class NoHayAccion():
    request = None
    
    def __init__(self, _request):
        self.request = _request

    def ejecutar(self):
        return render(self.request, 'fiscales/sin-actas.html')


