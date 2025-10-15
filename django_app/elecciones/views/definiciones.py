from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404

from elecciones.models import (
    Seccion,
    Circuito,
    Categoria,
    LugarVotacion,
    Mesa,
)

ESTRUCTURA = {None: Seccion, Seccion: Circuito, Circuito: LugarVotacion, LugarVotacion: Mesa, Mesa: None}


class StaffOnlyMixing:
    """
    Mixin para que sólo usuarios tipo "staff"
    accedan a la vista.
    """
    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class VisualizadoresOnlyMixin(AccessMixin):
    """
    Mixin para que sólo usuarios visualizadores
    accedan a la vista.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.fiscal.esta_en_grupo('visualizadores'):
            return self.handle_no_permission()
        pk = kwargs.get('pk')
        categoria = get_object_or_404(Categoria, id=pk)

        if categoria.sensible and not request.user.fiscal.esta_en_grupo('visualizadores_sensible'):
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

