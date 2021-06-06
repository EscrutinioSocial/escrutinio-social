from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.conf.urls import include
from django.contrib import admin
from django.contrib.auth import views as auth_views

from fancy_cache import cache_page

from material.frontend import urls as frontend_urls

from elecciones import urls as elecciones_urls

from problemas import urls as problemas_urls

from fiscales import urls as fiscales_urls
from fiscales.views import (
    choice_home,
    confirmar_email,
    EnviarEmail,
    permission_denied,
    quiero_validar_gracias,
    QuieroSerFiscal,
)
from fiscales.forms import AuthenticationFormCustomError

from api import urls as api_urls
from antitrolling import urls as antitrolling_urls

cached = cache_page(3600 * 24 * 30)

urlpatterns = [
    re_path(r'^$', choice_home, name="home"),
    re_path(r'^permission-denied$', permission_denied, name='permission-denied'),
    re_path(r'^quiero-validar/(?P<codigo_ref>\w+)?$', QuieroSerFiscal.as_view(), name='quiero-validar'),
    re_path(r'^quiero-validar/gracias/$', quiero_validar_gracias, name='quiero-validar-gracias'),
    re_path(r'^quiero-validar/confirmar-email/(?P<uuid>[0-9a-f-]+)$', confirmar_email, name='confirmar-email'),
    re_path(r'^login/$', auth_views.LoginView.as_view(
        authentication_form=AuthenticationFormCustomError
    ), name='login'),
    re_path(r'', include(frontend_urls)),
    re_path(r'', include('django.contrib.auth.urls')),
    re_path(r'^hijack/', include('hijack.urls')),
    re_path('^admin/enviar_email$', EnviarEmail.as_view(), name='enviar-email'),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^fiscales/', include(fiscales_urls)),

    re_path(r'^elecciones/', include(elecciones_urls)),
    re_path(r'^clasificar-actas/', include('adjuntos.urls')),

    re_path(r'^api/', include(api_urls)),
    re_path(r'^problemas/', include(problemas_urls)),
    re_path(r'^antitrolling/', include(antitrolling_urls)),
    re_path(r'^summernote/', include('django_summernote.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if settings.USAR_DJANGO_DEBUG_TOOLBAR:
        import debug_toolbar
        from django.urls import include, path
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
        SHOW_TOOLBAR_CALLBACK = True
