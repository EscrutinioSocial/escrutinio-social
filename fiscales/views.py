"""
define las vistas relacionadas a tareas que realizan los fiscales
como elegir acta a clasificar / a cargar / validar
"""

from io import StringIO
import sys
from django.core import serializers
from django.http import Http404, HttpResponseForbidden, HttpResponse, JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.detail import DetailView
from django.utils.safestring import mark_safe
from django.views.generic.edit import UpdateView, CreateView, FormView
from django.views.generic.list import ListView
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import PasswordChangeView
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from django.utils.safestring import mark_safe
from django.db import IntegrityError, transaction
from django.db.models import Q
from annoying.functions import get_object_or_None
from contacto.forms import MinimoContactoInlineFormset
from .models import Fiscal
from elecciones.models import (
    Mesa, Categoria, MesaCategoria, VotoMesaReportado, Carga, Circuito, LugarVotacion, Seccion
)
from .acciones import ( siguiente_accion )


from django.utils.decorators import method_decorator
from datetime import timedelta
from django.utils import timezone
from formtools.wizard.views import SessionWizardView
from django.template.loader import render_to_string
from html2text import html2text
from django.core.mail import send_mail
from django.contrib.admin.views.decorators import staff_member_required
from django import forms
from sentry_sdk import capture_exception
from .forms import (
    MisDatosForm,
    FiscalFormSimple,
    votomesareportadoformset_factory,
    QuieroSerFiscal1,
    QuieroSerFiscal2,
    QuieroSerFiscal3,
    QuieroSerFiscal4,
    ElegirFiscal,
    FiscalxDNI,
)
from contacto.views import ConContactosMixin
from adjuntos.models import Attachment
from django.conf import settings


# tiempo maximo en minutos que se mantiene la asignacion de un acta hasta ser reasignada
# es para que alguien no se "cuelgue" y quede un acta sin cargar.
WAITING_FOR = 2

NO_PERMISSION_REDIRECT = '/permission-denied/'

@login_required
def post_cargar_resultados(request, mesa, categoria):
    return render(request, 'fiscales/post-cargar-resultados.html', {'mesa': mesa, 'categoria': categoria})


def choice_home(request):
    """
    redirige a una página en funcion del tipo de usuario
    """
    user = request.user
    if not user.is_authenticated:
        return redirect('login')

    es_fiscal = Fiscal.objects.filter(user=request.user).exists()

    result = redirect('siguiente-accion') if user.fiscal.esta_en_grupo('validadores') else render(request, 'fiscales/base.html')

    return result

def permission_denied(request):
    return PermissionDenied

class BaseFiscal(LoginRequiredMixin, DetailView):
    model = Fiscal

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categoria'] = Categoria.objects.first()
        return context

    def get_object(self, *args, **kwargs):
        try:
            return self.request.user.fiscal
        except Fiscal.DoesNotExist:
            raise Http404('no está registrado como fiscal')


class QuieroSerFiscal(SessionWizardView):
    form_list = [
        QuieroSerFiscal1,
        QuieroSerFiscal2,
        #  QuieroSerFiscal3,
        QuieroSerFiscal4
    ]

    def get_form_initial(self, step):
        if step != '0':
            dni = self.get_cleaned_data_for_step('0')['dni']
            email = self.get_cleaned_data_for_step('0')['email']
            fiscal = (get_object_or_None(Fiscal, dni=dni) or
                      get_object_or_None(Fiscal,
                                         datos_de_contacto__valor=email,
                                         datos_de_contacto__tipo='email'))

        if step == '1' and fiscal:
            if self.steps.current == '0':
                # sólo si acaba de llegar al paso '1' muestro mensaje
                messages.info(self.request, 'Ya estás en el sistema. Por favor, confirmá tus datos.')
            return {
                'nombre': fiscal.nombres,
                'apellido': fiscal.apellido,
                'telefono': fiscal.telefonos[0] if fiscal.telefonos else '',
                # 'disponibilidad': fiscal.disponibilidad,
                # 'movilidad': fiscal.movilidad,
                # 'seccion': fiscal.escuelas[0].circuito.seccion if fiscal.escuelas else None
            }
        # elif step == '2' and fiscal:
        #     seccion = self.get_cleaned_data_for_step('1')['seccion']
        #     seccion_original = fiscal.escuelas[0].circuito.seccion if fiscal.escuelas else None

        #     if seccion_original and seccion == seccion_original:
        #         circuito = fiscal.escuelas[0].circuito
        #     else:
        #         circuito = None

        #     return {
        #         'circuito': circuito
        #     }
        # elif step == '3' and fiscal:
        #     circuito = self.get_cleaned_data_for_step('2')['circuito']
        #     circuito_original = fiscal.escuelas[0].circuito if fiscal.escuelas else None

        #     if circuito_original and circuito == circuito_original:
        #         escuela = fiscal.escuelas[0]
        #     else:
        #         escuela = None

        #     return {
        #         'escuela': escuela
        #     }

        return self.initial_dict.get(step, {})

    # def get_form(self, step=None, data=None, files=None):
    #     form = super().get_form(step, data, files)

    #     # determine the step if not given
    #     if step is None:
    #         step = self.steps.current

    #     if step == '2':
    #         seccion = self.get_cleaned_data_for_step('1')['seccion']
    #         form.fields['circuito'].queryset = Circuito.objects.filter(seccion=seccion)
    #     elif step == '3':
    #         circuito = self.get_cleaned_data_for_step('2')['circuito']
    #         form.fields['escuela'].queryset = LugarVotacion.objects.filter(circuito=circuito)
    #     return form

    def done(self, form_list, **kwargs):
        data = self.get_all_cleaned_data()
        dni = data['dni']
        email = data['email']
        fiscal = (get_object_or_None(Fiscal, dni=dni) or
                  get_object_or_None(Fiscal,
                                     datos_de_contacto__valor=email,
                                     datos_de_contacto__tipo='email'))
        if fiscal:
            fiscal.estado = 'AUTOCONFIRMADO'
        else:
            fiscal = Fiscal(estado='AUTOCONFIRMADO', dni=dni)

        fiscal.dni = dni
        fiscal.nombres = data['nombre']
        fiscal.apellido = data['apellido']
        # fiscal.escuela_donde_vota = data['escuela']
        fiscal.save()
        fiscal.agregar_dato_de_contacto('teléfono', data['telefono'])
        fiscal.agregar_dato_de_contacto('email', email)

        fiscal.user.set_password(data['new_password1'])
        fiscal.user.save()

        body_html = render_to_string('fiscales/email.html',
                                        {'fiscal': fiscal,
                                        'email': settings.DEFAULT_FROM_EMAIL,
                                        'cell_call': settings.DEFAULT_CEL_CALL,
                                        'cell_local': settings.DEFAULT_CEL_LOCAL,
                                        'site_url': settings.FULL_SITE_URL})
        body_text = html2text(body_html)

        send_mail(
            '[NOREPLY] Recibimos tu inscripción como validador/a.',
            body_text,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
            html_message=body_html
        )

        return render(self.request, 'formtools/wizard/wizard_done.html', {
            'fiscal': fiscal, 'email': settings.DEFAULT_FROM_EMAIL,
            'cell_call': settings.DEFAULT_CEL_CALL, 'cell_local': settings.DEFAULT_CEL_LOCAL,
            'site_url': settings.FULL_SITE_URL
        })


def confirmar_email(request, uuid):
    fiscal = get_object_or_None(Fiscal, codigo_confirmacion=uuid)
    if not fiscal:
        texto = mark_safe('El código de confirmación es inválido. '
                          'Por favor copiá y pegá el link que te enviamos'
                          ' por email en la barra de direcciones'
                          'Si seguís con problemas, env '
                          '<a href="mailto:{email}">'
                          '{email}</a>'.format(email=settings.DEFAULT_FROM_EMAIL))

    elif fiscal.email_confirmado:
        texto = 'Tu email ya estaba confirmado. Gracias.'
    else:
        fiscal.email_confirmado = True
        fiscal.save(update_fields=['email_confirmado'])
        texto = 'Confirmamos tu email exitosamente. ¡Gracias!'

    return render(
        request, 'fiscales/confirmar_email.html',
        {'texto': texto, 'fiscal': fiscal,
            'email': settings.DEFAULT_FROM_EMAIL,
            'cell_call': settings.DEFAULT_CEL_CALL,
            'cell_local': settings.DEFAULT_CEL_LOCAL,
            'site_url': settings.FULL_SITE_URL}
    )



class MisDatos(BaseFiscal):
    template_name = "fiscales/mis-datos.html"


class MisDatosUpdate(ConContactosMixin, UpdateView, BaseFiscal):
    """muestras los contactos para un fiscal"""
    form_class = MisDatosForm
    template_name = "fiscales/mis-datos-update.html"

    def get_success_url(self):
        return reverse('mis-datos')


@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('validadores'), login_url=NO_PERMISSION_REDIRECT)
def realizar_siguiente_accion(request):
    """
    Lanza la siguiente acción a realizar, que puede ser
    - identificar una foto (attachment)
    - cargar una mesa/categoría
    Si no hay ninguna acción pendiente, entonces muestra un mensaje al respecto
    """
    return siguiente_accion(request).ejecutar()



@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('validadores'), login_url=NO_PERMISSION_REDIRECT)
def cargar_resultados(
    request, categoria_id, mesa_numero, tipo='total', carga_id=None
):
    """
    Es la vista que muestra y procesa el formset de carga de datos para una categoria-mesa
    """
    fiscal = get_object_or_404(Fiscal, user=request.user)
    mesa_categoria = get_object_or_404(
        MesaCategoria,
        categoria_id=categoria_id,
        mesa__numero=mesa_numero
    )

    solo_prioritarias = tipo == 'parcial'
    mesa = mesa_categoria.mesa
    categoria = mesa_categoria.categoria
    if carga_id:
        carga = get_object_or_404(
            Carga, id=carga_id, carga__mesa_categoria=mesa_categoria
        )
    else:
        carga = None

    VotoMesaReportadoFormset = votomesareportadoformset_factory(
        min_num=categoria.opciones_actuales(solo_prioritarias).count()
    )

    def fix_opciones(formset):
        # hack para dejar sólo la opcion correspondiente a cada fila en los choicefields
        # se podria hacer "disabled" pero ese caso quita el valor del
        # cleaned_data y luego lo exige por ser requerido.
        for i, (opcion, form) in enumerate(zip(categoria.opciones_actuales(solo_prioritarias), formset), 1):
            form.fields['opcion'].choices = [(opcion.id, str(opcion))]

            # esto hace que la navegacion mediante Tabs priorice los inputs de "votos"
            # por sobre los combo de "opcion"
            form.fields['opcion'].widget.attrs['tabindex'] = 99 + i
            form.fields['votos'].widget.attrs['tabindex'] = i

            form.fields['votos'].required = True
            if i == 1:
                form.fields['votos'].widget.attrs['autofocus'] = True
    data = request.POST if request.method == 'POST' else None

    qs = VotoMesaReportado.objects.filter(carga=carga) if carga else VotoMesaReportado.objects.none()
    initial = [{'opcion': o} for o in categoria.opciones_actuales(solo_prioritarias)]
    formset = VotoMesaReportadoFormset(data, queryset=qs, initial=initial, mesa=mesa)
    fix_opciones(formset)
    is_valid = False
    if qs:
        formset.convert_warnings = True  # monkepatch

    if request.method == 'POST' or qs:
        is_valid = formset.is_valid()

    if is_valid:

        try:
            with transaction.atomic():
                # se guardan los datos. El contenedor `carga`
                # y los votos del formset asociados.
                if carga:
                    carga.fiscal = fiscal
                    carga.save()
                else:
                    carga = Carga.objects.create(
                        mesa_categoria=mesa_categoria,
                        status=tipo,
                        fiscal=fiscal,
                    )
                for form in formset:
                    vmr = form.save(commit=False)
                    vmr.carga = carga
                    vmr.save()
            carga.actualizar_firma()
            messages.success(
                request,
                f'Guardada categoría {categoria} para {mesa}')
        except IntegrityError as e:
            # hubo otra carga previa.
            capture_exception(e)
            messages.error(request, 'Alguien cargó esta mesa con anterioridad')
            return redirect('siguiente-accion')

        # hay que cargar otra categoria (categoria) de la misma mesa?
        # si es asi, se redirige a esa carga
        siguiente = mesa.siguiente_categoria_sin_carga()
        if siguiente:
            # vuelvo a marcar un token
            mesa.taken = timezone.now()
            mesa.save(update_fields=['taken'])

            return redirect(
                'mesa-cargar-resultados',
                categoria_id=siguiente.id,
                mesa_numero=mesa.numero
            )
        return redirect('post-cargar-resultados', mesa=mesa.numero, categoria=categoria.nombre)

    # llega hasta aca si hubo error
    return render(
        request, "fiscales/carga.html", {
            'formset': formset,
            'categoria': categoria,
            'object': mesa,
            'is_valid': is_valid or request.method == 'GET'
        }
    )

@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('validadores'), login_url=NO_PERMISSION_REDIRECT)
def detalle_mesa_categoria(request, categoria_id, mesa_numero, carga_id=None):
    """
    Muestra la carga actual de la categoria para la mesa
    """
    mc = get_object_or_404(
        MesaCategoria,
        mesa__numero=mesa_numero,
        categoria__id=categoria_id,
        carga_testigo__isnull=False,
    )
    mesa = mc.mesa
    categoria = mc.categoria
    carga = mc.carga_testigo
    reportados = carga.reportados.order_by('opcion__orden')
    return render(
        request,
        "fiscales/detalle_mesa_categoria.html",
        {
            'reportados': reportados,
            'object': mesa,
            'categoria': categoria
        }
    )



class CambiarPassword(PasswordChangeView):
    template_name = "fiscales/cambiar-contraseña.html"
    success_url = reverse_lazy('mis-datos')

    def form_valid(self, form):
        messages.success(self.request, 'Tu contraseña se cambió correctamente')
        return super().form_valid(form)


@login_required
def confirmar_fiscal(request, fiscal_id):
    """
    cambia el estado del fiscal con el id dado a CONFIRMADO y redirige a
    a la página previa con un mensaje
    """
    fiscal = get_object_or_404(Fiscal, id=fiscal_id, estado='AUTOCONFIRMADO')
    fiscal.estado = 'CONFIRMADO'
    fiscal.save(update_fields=['estado'])
    url = reverse('admin:fiscales_fiscal_change', args=(fiscal_id,))
    msg = f'<a href="{url}">{fiscal}</a> ha sido confirmado'
    messages.info(request, mark_safe(msg))
    return redirect(request.META.get('HTTP_REFERER'))


class AutocompleteBaseListView(LoginRequiredMixin, ListView):

    def get(self, request, *args, **kwargs):
        data = {'options': [{'value': o.id, 'text': str(o)} for o in self.get_queryset()]}
        return JsonResponse(data, status=200, safe=False)


class SeccionListView(AutocompleteBaseListView):
    model = Seccion

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(distrito__id=self.request.GET['parent_id'])


class CircuitoListView(AutocompleteBaseListView):
    model = Circuito

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(seccion__id=self.request.GET['parent_id'])


class MesaListView(AutocompleteBaseListView):
    model = Mesa

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(lugar_votacion__circuito__id=self.request.GET['parent_id'])

