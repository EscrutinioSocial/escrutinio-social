from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth import views as auth_views

from fancy_cache import cache_page

from material.frontend import urls as frontend_urls

from elecciones import urls as elecciones_urls

from fiscales import urls as fiscales_urls
from fiscales.views import choice_home, permission_denied, QuieroSerFiscal, confirmar_email
from fiscales.forms import AuthenticationFormCustomError

from problemas.views import ProblemaCreate

from api import urls as api_urls

cached = cache_page(3600 * 24 * 30)

urlpatterns = [
    url(r'^$', choice_home, name="home"),
    url(r'^permission-denied$', permission_denied, name='permission-denied'),
    url(r'^quiero-ser-fiscal/$', QuieroSerFiscal.as_view(), name='quiero-ser-fiscal'),
    url(r'^quiero-ser-fiscal/confirmar-email/(?P<uuid>[0-9a-f-]+)$', confirmar_email, name='confirmar-email'),
    url(r'^login/$', auth_views.LoginView.as_view(authentication_form=AuthenticationFormCustomError), name='login'),

    url(r'', include(frontend_urls)),
    url(r'', include('django.contrib.auth.urls')),
    url(r'^hijack/', include('hijack.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^fiscales/', include(fiscales_urls)),

    url(r'^elecciones/', include(elecciones_urls)),
    url(r'^clasificar-actas/', include('adjuntos.urls')),
    url('^reportar-problema/(?P<mesa_numero>\d+)$', ProblemaCreate.as_view(), name='reportar-problema'),

    url(r'^api/', include(api_urls))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
