from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.RailCurrentStatusView.as_view()),
    path('poll/', views.TriggerPollView.as_view()),
    path('<str:rail_name>/history/', views.RailHistoryView.as_view()),
]
