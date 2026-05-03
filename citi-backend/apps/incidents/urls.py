from django.urls import path
from . import views

urlpatterns = [
    path('', views.IncidentListView.as_view()),
    path('simulate/', views.SimulateIncidentView.as_view()),
    path('<str:pk>/', views.IncidentDetailView.as_view()),
    path('<str:pk>/resolve/', views.IncidentResolveView.as_view()),
    path('<str:pk>/snapshot-history/', views.IncidentSnapshotHistoryView.as_view()),
]
