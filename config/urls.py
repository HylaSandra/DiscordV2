from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("core.urls", "core"), namespace="core")),
    path("accounts/", include(("users.urls", "users"), namespace="users")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("chat/", include(("chat.urls", "chat"), namespace="chat")),
]

if settings.DEBUG or settings.SERVE_MEDIA:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "core.views.custom_404"
