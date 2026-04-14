from django.urls import path
from .views import ComplianceDashboardView, ComplianceViolationListView

urlpatterns = [
    path('dashboard/', ComplianceDashboardView.as_view()),
    path('violations/', ComplianceViolationListView.as_view()),
]
