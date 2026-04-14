from django.urls import path
from .views import CommunicationListView, CommunicationApproveView, CommunicationRejectView

urlpatterns = [
    path('', CommunicationListView.as_view()),
    path('<str:pk>/approve/', CommunicationApproveView.as_view()),
    path('<str:pk>/reject/', CommunicationRejectView.as_view()),
]
