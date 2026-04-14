from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/rails/', include('apps.rails.urls')),
    path('api/v1/incidents/', include('apps.incidents.urls')),
    path('api/v1/compliance/', include('apps.compliance.urls')),
    path('api/v1/communications/', include('apps.communications.urls')),
]
