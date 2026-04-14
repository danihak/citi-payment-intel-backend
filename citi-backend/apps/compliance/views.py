from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from django.urls import path
from .models import ApiComplianceMetric, ComplianceViolation


class ApiComplianceMetricSerializer(serializers.ModelSerializer):
    utilisation_pct = serializers.SerializerMethodField()

    class Meta:
        model = ApiComplianceMetric
        fields = '__all__'

    def get_utilisation_pct(self, obj):
        if obj.tps_limit == 0:
            return 0
        return round(float(obj.tps_current) / float(obj.tps_limit) * 100, 1)


class ComplianceViolationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceViolation
        fields = '__all__'


class ComplianceDashboardView(APIView):
    """GET /api/v1/compliance/dashboard/ — OC-215 status for all APIs."""

    def get(self, request):
        apis = ['check_transaction_status', 'initiate_payment', 'balance_enquiry', 'validate_vpa']
        result = []
        for api in apis:
            latest = ApiComplianceMetric.objects.filter(
                api_name=api
            ).order_by('-measured_at').first()
            if latest:
                s = ApiComplianceMetricSerializer(latest)
                result.append(s.data)
        return Response(result)


class ComplianceViolationListView(APIView):
    """GET /api/v1/compliance/violations/ — audit log of all OC-215 violations."""

    def get(self, request):
        violations = ComplianceViolation.objects.order_by('-occurred_at')[:50]
        serializer = ComplianceViolationSerializer(violations, many=True)
        return Response(serializer.data)


urlpatterns = [
    path('dashboard/', ComplianceDashboardView.as_view()),
    path('violations/', ComplianceViolationListView.as_view()),
]
