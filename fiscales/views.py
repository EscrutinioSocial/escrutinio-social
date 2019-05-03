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
from .models import Fiscal, AsignacionFiscalGeneral, AsignacionFiscalDeMesa
from elecciones.models import (
    Mesa, Eleccion, VotoMesaReportado, Circuito, LugarVotacion, Seccion
)
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
    VotoMesaReportadoFormset,
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

    if user.is_staff and es_fiscal:
        return redirect('elegir-acta-a-cargar')

    elif es_fiscal:
        return redirect('donde-fiscalizo')
    elif user.groups.filter(name='contacto').exists():
        return redirect('/contacto/')
    else:
        return redirect('/admin/')


class BaseFiscal(LoginRequiredMixin, DetailView):
    model = Fiscal

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['eleccion'] = Eleccion.actual()
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
            fiscal = Fiscal(estado='AUTOCONFIRMADO', tipo='de_mesa', dni=dni)

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


class MisContactos(BaseFiscal):
    template_name = "fiscales/mis-contactos.html"


class MisVoluntarios(LoginRequiredMixin, ListView):
    template_name = "fiscales/mis-voluntarios.html"
    model = Fiscal

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['eleccion'] = Eleccion.actual()
        return context

    def get_queryset(self):
        try:
            fiscal = get_object_or_404(Fiscal, user=self.request.user, tipo=Fiscal.TIPO.general)
        except Fiscal.DoesNotExist:
            raise Http404('no está registrado como fiscal general')


        return Fiscal.objects.filter(
            escuela_donde_vota__in=fiscal.escuelas
        ).exclude(
            id=fiscal.id
        ).order_by('escuela_donde_vota')


@login_required
def asignacion_estado(request, tipo, pk):
    fiscal = get_object_or_404(Fiscal, user=request.user)

    if tipo == 'de_mesa':
        asignacion = get_object_or_404(AsignacionFiscalDeMesa, id=pk)
        if asignacion.mesa not in fiscal.mesas_asignadas:
            raise Http404()
    else:
        asignacion = get_object_or_404(AsignacionFiscalGeneral, id=pk, fiscal=fiscal)

    comida_post = 'comida' in request.POST
    comida_get = 'comida' in request.GET     # fiscal general
    if comida_post or comida_get:
        asignacion.comida = 'recibida'
        asignacion.save(update_fields=['comida'])
        messages.info(request, '¡Buen provecho!' if comida_post else '¡Gracias!')

    elif not asignacion.ingreso:
        # llega por primera vez
        asignacion.ingreso = timezone.now()
        asignacion.egreso = None
        messages.info(request, 'Tu presencia se registró ¡Gracias!')
    elif asignacion.ingreso and not asignacion.egreso:
        # se retiró
        asignacion.egreso = timezone.now()
        messages.info(request, 'Anotamos el retiro, ¡Gracias!')
    elif asignacion.ingreso and asignacion.egreso:
        asignacion.ingreso = timezone.now()
        asignacion.egreso = None
        messages.info(request, 'Vamos a volver!')
    asignacion.save()
    mesa = request.GET.get('mesa')
    if mesa:
        return redirect(asignacion.mesa.get_absolute_url())
    return redirect('donde-fiscalizo')


class MiAsignableMixin:
    def dispatch(self, *args, **kwargs):
        self.fiscal = get_object_or_404(Fiscal, user=self.request.user)
        self.asignable = self.get_asignable()
        if (('mesa_numero' in self.kwargs and self.asignable not in self.fiscal.mesas_asignadas) or
            ('escuela_id' in self.kwargs and self.asignable not in self.fiscal.escuelas)):
            return HttpResponseForbidden()
        return super().dispatch(*args, **kwargs)

    def get_asignable(self):
        if 'escuela_id' in self.kwargs:
            return get_object_or_404(LugarVotacion, id=self.kwargs['escuela_id'])
        else:
            return get_object_or_404(Mesa, eleccion__id=self.kwargs['eleccion_id'], numero=self.kwargs['mesa_numero'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asignable'] = self.asignable
        if isinstance(self.asignable, Mesa):
            context['url_crear_fiscal'] = reverse(
                'mesa-cargar-fiscal', args=(3, self.asignable.numero)
            )
        else:
            context['url_crear_fiscal'] = reverse(
                'escuela-cargar-fiscal', args=(3, self.asignable.id)
            )
        return context

    def verificar_fiscal_existente(self, fiscal):
        return fiscal


class MesaActa(BaseFiscal, FormView):
    template_name = "fiscales/cargar-foto.html"
    form_class = SubirAttachmentModelForm

    def get_object(self):
        return get_object_or_404(Mesa, eleccion__id=self.kwargs['eleccion_id'], numero=self.kwargs['mesa_numero'])

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['object'] = self.get_object()
        return context

    def form_valid(self, form):
        mesa = self.get_object()
        Attachment.objects.filter(mesa=mesa).delete()
        attach = form.save(commit=False)
        attach.mesa = self.get_object()
        attach.save()
        messages.success(self.request, 'Foto subida correctamente ¡Gracias!')
        return redirect(mesa.get_absolute_url())


class BaseFiscalSimple(LoginRequiredMixin, MiAsignableMixin, ConContactosMixin):
    """muestras los contactos para un fiscal"""
    form_class = FiscalFormSimple
    inline_formset_class = MinimoContactoInlineFormset
    model = Fiscal
    template_name = "fiscales/cargar-fiscal.html"

    def dispatch(self, *args, **kwargs):
        d = super().dispatch(*args, **kwargs)
        if 'mesa_numero' in self.kwargs and not self.asignable.asignacion_actual:
            messages.error(self.request, 'No se registra fiscal')
            return redirect(self.asignable.get_absolute_url())
        return d

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['eleccion'] = Eleccion.actual()
        if self.kwargs.get('tipo') == 'de_mesa':
            context['mesa'] = self.get_asignable()
        else:
            context['escuela'] = self.get_asignable()
        return context

    def form_valid(self, form):
        fiscal = form.save(commit=False)
        fiscal.tipo = self.kwargs.get('tipo')
        fiscal = self.verificar_fiscal_existente(fiscal)
        fiscal.save()
        asignable = self.get_asignable()
        eleccion = Eleccion.actual()
        if asignable.asignacion_actual:
            asignacion = asignable.asignacion_actual
            asignacion.fiscal = fiscal
            asignacion.save()
        elif isinstance(asignable, LugarVotacion):
            asignacion = AsignacionFiscalGeneral.objects.create(fiscal=fiscal,
                                                                lugar_votacion=asignable,
                                                                eleccion=eleccion )
            asignacion.save()

        messages.success(self.request, 'Fiscal cargado correctamente')
        return redirect(asignable.get_absolute_url())


class AsignarFiscalView(MiAsignableMixin, FormView):
    form_class = ElegirFiscal
    template_name = "fiscales/asignar-fiscal.html"

    def get_success_url(self):
        return self.asignable.get_absolute_url()

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if isinstance(self.asignable, Mesa):
            # fiscal general puede asignar fiscales de mesa
            # que prefieren esa escuela
            escuela = self.asignable.lugar_votacion
        else:
            escuela = self.asignable
        qs = Fiscal.objects.filter(
            estado=Fiscal.ESTADOS.CONFIRMADO,
            escuela_donde_vota=escuela
        ).exclude(id=self.request.user.fiscal.id)
        form.fields['fiscal'].queryset = qs
        return form

    def form_valid(self, form):
        fiscal = form.cleaned_data['fiscal']
        fiscal.asignar_a(self.asignable)
        return super().form_valid(form)


class FiscalSimpleCreateView(BaseFiscalSimple, CreateView):

    def dispatch(self, *args, **kwargs):
        d = super().dispatch(*args, **kwargs)
        if 'mesa_numero' in self.kwargs and not self.asignable.asignacion_actual:
            messages.error(self.request, 'No se registra fiscal en esta mesa ')
            return redirect(self.asignable.get_absolute_url())
        return d

    def verificar_fiscal_existente(self, fiscal):
        existente = get_object_or_None(
            Fiscal,
            dni=fiscal.dni,
            tipo_dni=fiscal.tipo_dni
        )

        if existente:
            fiscal = existente
            messages.info(self.request, 'Ya teniamos datos de esta persona')

        fiscal.estado = "CONFIRMADO"
        if 'mesa_numero' in self.kwargs:
            fiscal.escuela_donde_vota = self.asignable.lugar_votacion
        fiscal.save()
        return fiscal


class FiscalSimpleUpdateView(BaseFiscalSimple, UpdateView):

    def get_object(self):
        asignable = self.get_asignable()
        asignacion_id = self.kwargs.get('asignacion_id')
        if isinstance(asignable, LugarVotacion) and asignacion_id:
            asignacion_id = self.kwargs['asignacion_id']
            asignacion = get_object_or_404(
                AsignacionFiscalGeneral,
                id=asignacion_id,
                lugar_votacion=asignable)
        elif isinstance(asignable, Mesa) and asignacion_id:
            asignacion = get_object_or_404(
                AsignacionFiscalDeMesa,
                id=asignacion_id,
                mesa=asignable)
        else:
            asignacion = asignable.asignacion_actual
        if asignacion.fiscal:
            return asignacion.fiscal
        raise Http404


@login_required
def eliminar_asignacion_f_mesa(request, eleccion_id, mesa_numero=None):
    mesa    = get_object_or_404(Mesa, eleccion__id=eleccion_id, numero=mesa_numero)

    asignacion = mesa.asignacion_actual
    if asignacion:
        asignacion.delete()
        messages.success(request, 'La asignación se eliminó')
    else:
        messages.error(request, 'La asignación NO se eliminó')

    return redirect(mesa.get_absolute_url())


@login_required
def eliminar_asignacion_f_general(request, eleccion_id, escuela_id=None, asignacion_id=None):

    fiscal = get_object_or_404(Fiscal, user=request.user)
    circuitos = fiscal.es_referente_de_circuito.all()
    asignable = get_object_or_404(LugarVotacion,
                                  id=escuela_id,
                                  circuito__in=circuitos,
                                  asignacion__id=asignacion_id)
    if asignable not in fiscal.escuelas:
        return HttpResponseForbidden()

    asignacion = AsignacionFiscalGeneral.objects.get(id=asignacion_id)

    asignacion.delete()
    messages.success(request, 'La asignación se eliminó')
    return redirect(asignable.get_absolute_url())


@login_required
def tengo_fiscal(request, eleccion_id, mesa_numero):
    fiscal = get_object_or_404(Fiscal, tipo='general', user=request.user)
    mesa = get_object_or_404(Mesa, eleccion__id=eleccion_id, numero=mesa_numero)
    if mesa not in fiscal.mesas_asignadas:
        return HttpResponseForbidden()

    _, created = AsignacionFiscalDeMesa.objects.get_or_create(
        mesa=mesa,
        defaults={'ingreso': timezone.now(), 'egreso': None}
    )
    if created:
        messages.info(request, 'Registramos que la mesa tiene fiscal')
    else:
        messages.warning(request, 'Esta mesa ya tiene un fiscal registrado')
    return redirect(mesa.get_absolute_url())



@login_required
def mesa_cambiar_estado(request, eleccion_id, mesa_numero, estado):
    fiscal = get_object_or_404(Fiscal, user=request.user)
    mesa = get_object_or_404(Mesa, eleccion__id=eleccion_id, numero=mesa_numero)
    if mesa not in fiscal.mesas_asignadas:
        return HttpResponseForbidden()
    mesa.estado = estado
    mesa.save()
    success_msg = "El estado de la mesa se cambió correctamente"
    messages.success(request, success_msg)
    return redirect(mesa.get_absolute_url())


class DondeFiscalizo(BaseFiscal):
    template_name = "fiscales/donde-fiscalizo.html"


class MesaDetalle(LoginRequiredMixin, MiAsignableMixin, DetailView):
    template_name = "fiscales/mesa-detalle.html"
    slug_field = 'numero'
    model = Mesa
    fiscal_sel_field = None

    def get_voluntarios_queryset(self):
        try:
            fiscal = get_object_or_404(Fiscal, user=self.request.user, tipo=Fiscal.TIPO.general)
        except Fiscal.DoesNotExist:
            raise Http404('no está registrado como fiscal general')

        return Fiscal.objects.filter(
            escuela_donde_vota__in=fiscal.escuelas
        ).exclude(
            id=fiscal.id
        ).order_by('escuela_donde_vota')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs_voluntarios = self.get_voluntarios_queryset()
        context['qs_voluntarios'] = qs_voluntarios
        #for v in context['qs_voluntarios']:
        #    print(type(v), v, v.pk)

        return context

    def get_object(self, *args, **kwargs):
        mesa_numero = self.kwargs['mesa_numero']

        return get_object_or_404(
            Mesa,
            numero=mesa_numero,
            eleccion__id=self.kwargs['eleccion_id']
        )


@staff_member_required
def elegir_acta_a_cargar(request):

    # se eligen mesas que nunca se intentaron cargar o que se asignaron a

    mesas = Mesa.con_carga_pendiente().order_by('orden_de_carga')

    if mesas.exists():
        mesa = mesas[0]
        # se marca el adjunto
        mesa.taken = timezone.now()
        mesa.save(update_fields=['taken'])
        return redirect(
            'mesa-cargar-resultados',
            eleccion_id=mesa.eleccion.id,
            mesa_numero=mesa.numero
        )

    return render(request, 'fiscales/sin-actas.html')



@staff_member_required
def cargar_resultados(request, eleccion_id, mesa_numero):
    fiscal = get_object_or_404(Fiscal, user=request.user)

    def fix_opciones(formset):
        # hack para dejar sólo la opcion correspondiente a cada fila
        # se podria hacer "disabled" pero ese caso quita el valor del
        # cleaned_data y luego lo exige por ser requerido.
        for i, (opcion, form) in enumerate(
            zip(Eleccion.opciones_actuales(), formset), 1):
            form.fields['opcion'].choices = [(opcion.id, str(opcion))]

            form.fields['opcion'].widget.attrs['tabindex'] = 99 + i
            form.fields['votos'].widget.attrs['tabindex'] = i
            # si la opcion es obligatoria, se llenan estos campos
            if opcion.obligatorio:
                form.fields['votos'].required = True
            if i == 1:
                form.fields['votos'].widget.attrs['autofocus'] = True

    mesa = get_object_or_404(Mesa, eleccion__id=eleccion_id, numero=mesa_numero)
    data = request.POST if request.method == 'POST' else None
    qs = VotoMesaReportado.objects.filter(mesa=mesa)        # , fiscal=fiscal)
    initial = [{'opcion': o} for o in Eleccion.opciones_actuales()]
    formset = VotoMesaReportadoFormset(data, queryset=qs, initial=initial, mesa=mesa)

    fix_opciones(formset)
    is_valid = False
    if qs:
        formset.convert_warnings = True  # monkepatch

    if request.method == 'POST' or qs:
        is_valid = formset.is_valid()

    # eleccion = Eleccion.objects.last()
    if is_valid:

        try:
            with transaction.atomic():
                for form in formset:
                    vmr = form.save(commit=False)
                    vmr.mesa = mesa
                    vmr.fiscal = fiscal
                    # vmr.eleccion = eleccion
                    vmr.save()
            messages.success(request, 'Guardados los resultados de la mesa ')
        except IntegrityError as e:
            # hubo otra carga previa.
            capture_exception(e)
            messages.error(request, 'Alguien cargó esta mesa con anterioridad')


        return redirect('elegir-acta-a-cargar')


    return render(
        request, "fiscales/carga.html",
        {'formset': formset, 'object': mesa, 'is_valid': is_valid or request.method == 'GET'}
    )


@staff_member_required
def chequear_resultado(request):
    mesa = Mesa.con_carga_a_confirmar().order_by('?').first()
    if not mesa:
        return redirect('elegir-acta-a-cargar')
    return redirect('chequear-resultado-mesa', eleccion_id=1, mesa_numero=mesa.numero)



@staff_member_required
def chequear_resultado_mesa(request, eleccion_id, mesa_numero):
    mesa = get_object_or_404(Mesa, eleccion__id=eleccion_id, numero=mesa_numero)
    data = request.POST if request.method == 'POST' else None
    if data and 'confirmar' in data:

        mesa.carga_confirmada = True
        mesa.save(update_fields=['carga_confirmada'])
        return redirect('chequear-resultado')

    reportados = mesa.votomesareportado_set.all().order_by('opcion__orden')
    return render(
        request,
        "fiscales/chequeo_mesa.html",
        {
            'reportados': reportados,
            'object': mesa
        }
    )



class CambiarPassword(PasswordChangeView):
    template_name = "fiscales/cambiar-contraseña.html"
    success_url = reverse_lazy('mis-datos')

    def form_valid(self, form):
        messages.success(self.request, 'Tu contraseña se cambió correctamente')
        return super().form_valid(form)


@staff_member_required
def confirmar_fiscal(request, fiscal_id):
    fiscal = get_object_or_404(Fiscal, id=fiscal_id, estado='AUTOCONFIRMADO')
    fiscal.estado = 'CONFIRMADO'
    fiscal.save()
    url = reverse('admin:fiscales_fiscal_change', args=(fiscal_id,))
    msg = f'<a href="{url}">{fiscal}</a> ha sido confirmado en la escuela {fiscal.escuela_donde_vota}'
    messages.info(request, mark_safe(msg))
    return redirect(request.META.get('HTTP_REFERER'))


@staff_member_required
def exportar_emails(request):
    out = StringIO()
    call_command('export_emails', f='email', stdout=out)

    text = '\n'.join(l for l in out.getvalue().split('\n') if '@' in l)
    return HttpResponse(text, content_type="text/plain; charset=utf-8")


@staff_member_required
def datos_fiscales_por_seccion(request):
    generales = {}
    de_mesa = {}
    for seccion in Seccion.objects.all():

        generales[seccion] = Fiscal.objects.filter(tipo='general', escuela_donde_vota__circuito__seccion=seccion).distinct()
        de_mesa[seccion] = Fiscal.objects.filter(tipo='de_mesa', escuela_donde_vota__circuito__seccion=seccion).distinct()


    return render(request, 'fiscales/datos_fiscales_por_seccion.html', {'generales': generales, 'de_mesa': de_mesa})

