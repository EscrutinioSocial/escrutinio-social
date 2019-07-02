from io import StringIO
import sys
from django.http import Http404, HttpResponseForbidden, HttpResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.detail import DetailView
from django.utils.safestring import mark_safe
from django.views.generic.edit import UpdateView, CreateView, FormView
from django.views.generic.list import ListView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
    votomeesareportadoformset_factory,
    QuieroSerFiscal1,
    QuieroSerFiscal2,
    QuieroSerFiscal3,
    QuieroSerFiscal4,
    ElegirFiscal,
    FiscalxDNI,
)
from contacto.views import ConContactosMixin
from adjuntos.models import Attachment
from adjuntos.forms import SubirAttachmentModelForm
from django.conf import settings


# tiempo maximo en minutos que se mantiene la asignacion de un acta hasta ser reasignada
# es para que alguien no se "cuelgue" y quede un acta sin cargar.
WAITING_FOR = 2


def choice_home(request):
    """
    redirige a una página en funcion del tipo de usuario
    """
    user = request.user
    if not user.is_authenticated:
        return redirect('login')

    es_fiscal = Fiscal.objects.filter(user=request.user).exists()

    return redirect('elegir-acta-a-cargar')


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
            '[NOREPLY] Recibimos tu inscripción como fiscal digital',
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


def email(request):
    return render(request, 'fiscales/email.html', {'fiscal': request.user.fiscal,
                                                    'email': settings.DEFAULT_FROM_EMAIL,
                                                    'cell_call': settings.DEFAULT_CEL_CALL,
                                                    'cell_local': settings.DEFAULT_CEL_LOCAL,
                                                    'site_url': settings.FULL_SITE_URL})


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
def elegir_acta_a_cargar(request):
    # se eligen mesas que nunca se intentaron cargar o que se asignaron a
    mesas = Mesa.con_carga_pendiente().order_by(
        'orden_de_carga', '-lugar_votacion__circuito__electores'
    )
    if mesas.exists():
        mesa = mesas[0]
        # se marca que se inicia una carga
        mesa.taken = timezone.now()
        mesa.save(update_fields=['taken'])

        # que pasa si ya no hay elecciones.sin carga?
        # estamos teniendo un error
        siguiente_categoria = mesa.siguiente_categoria_sin_carga()
        if siguiente_categoria is None:
            return render(request, 'fiscales/sin-actas.html')
        siguiente_id = siguiente_categoria.id

        return redirect(
            'mesa-cargar-resultados',
            categoria_id=siguiente_id,
            mesa_numero=mesa.numero
        )

    return render(request, 'fiscales/sin-actas.html')



@login_required
def cargar_resultados(request, categoria_id, mesa_numero, carga_id=None):
    fiscal = get_object_or_404(Fiscal, user=request.user)
    categoria = get_object_or_404(Categoria, id=categoria_id)
    mesa = get_object_or_404(Mesa, categoria=categoria, numero=mesa_numero)
    if carga_id:
        carga = get_object_or_404(Carga, id=carga_id, mesa=mesa, categoria=categoria)
    else:
        carga = None

    VotoMesaReportadoFormset = votomeesareportadoformset_factory(min_num=categoria.opciones.count())

    def fix_opciones(formset):
        # hack para dejar sólo la opcion correspondiente a cada fila en los choicesfields
        # se podria hacer "disabled" pero ese caso quita el valor del
        # cleaned_data y luego lo exige por ser requerido.
        for i, (opcion, form) in enumerate(zip(categoria.opciones_actuales(), formset), 1):
            form.fields['opcion'].choices = [(opcion.id, str(opcion))]

            # esto hace que la navegacion mediante Tabs priorice los inputs de "votos"
            # por sobre los combo de "opcion"
            form.fields['opcion'].widget.attrs['tabindex'] = 99 + i
            form.fields['votos'].widget.attrs['tabindex'] = i

            # si la opcion es obligatoria, se llenan estos campos
            if opcion.obligatorio:
                form.fields['votos'].required = True
            if i == 1:
                form.fields['votos'].widget.attrs['autofocus'] = True
    data = request.POST if request.method == 'POST' else None

    qs = VotoMesaReportado.objects.filter(carga=carga) if carga else None
    initial = [{'opcion': o} for o in categoria.opciones_actuales()]
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
                if carga:
                    carga.fiscal = fiscal
                    carga.save()
                else:
                    carga = Carga.objects.create(
                        mesa=mesa, fiscal=fiscal, categoria=categoria
                    )

                for form in formset:
                    vmr = form.save(commit=False)
                    vmr.carga = carga
                    vmr.save()
            messages.success(request, f'Guardada categoria {categoria} para {mesa}')
        except IntegrityError as e:
            # hubo otra carga previa.
            capture_exception(e)
            messages.error(request, 'Alguien cargó esta mesa con anterioridad')
            return redirect('elegir-acta-a-cargar')

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

        return redirect('elegir-acta-a-cargar')


    return render(
        request, "fiscales/carga.html",
        {'formset': formset, 'categoria': categoria, 'object': mesa, 'is_valid': is_valid or request.method == 'GET'}
    )


@login_required
def chequear_resultado(request):
    """vista que elige una mesa con cargas a confirmar y redirige a la url correspondiente"""
    mesa = Mesa.con_carga_a_confirmar().order_by('?').first()
    if not mesa:
        return render(request, 'fiscales/sin-actas-cargadas.html')
    try:
        categoria = mesa.siguiente_categoria_a_confirmar()
    except Exception:
        return render(request, 'fiscales/sin-actas-cargadas.html')

    if not categoria:
        return render(request, 'fiscales/sin-actas-cargadas.html')

    return redirect('chequear-resultado-mesa', categoria_id=categoria.id, mesa_numero=mesa.numero)


@login_required
def chequear_resultado_mesa(request, categoria_id, mesa_numero, carga_id=None):
    """muestra la carga actual de la categoria para la mesa"""
    me = get_object_or_404(
        MesaCategoria,
        mesa__numero=mesa_numero,
        categoria__id=categoria_id,
        categoria__activa=True
    )
    mesa = me.mesa
    categoria = me.categoria

    if carga_id:
        carga = get_object_or_404(Carga, id=carga_id, mesa=mesa, categoria=categoria)
    else:
        # redirijo a la primera carga
        carga = get_object_or_404(Carga, mesa=mesa, categoria=categoria)
        # return redirect(
        #     'chequear-resultado-mesa',
        #     categoria_id=categoria.id,
        #     mesa_numero=mesa.numero,
        #     carga_id=carga.id
        # )

    data = request.POST if request.method == 'POST' else None
    if data and 'confirmar' in data:
        me.confirmada = True
        me.save(update_fields=['confirmada'])
        messages.success(request, f'Confirmaste la categoria {categoria} para {mesa}')
        return redirect('chequear-resultado')

    reportados = carga.votomesareportado_set.order_by('opcion__orden')
    return render(
        request,
        "fiscales/chequeo_mesa.html",
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
    fiscal = get_object_or_404(Fiscal, id=fiscal_id, estado='AUTOCONFIRMADO')
    fiscal.estado = 'CONFIRMADO'
    fiscal.save()
    url = reverse('admin:fiscales_fiscal_change', args=(fiscal_id,))
    msg = f'<a href="{url}">{fiscal}</a> ha sido confirmado en la escuela {fiscal.escuela_donde_vota}'
    messages.info(request, mark_safe(msg))
    return redirect(request.META.get('HTTP_REFERER'))
