from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.urls import path
from .models import CommunicationDraft


class CommunicationDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationDraft
        fields = '__all__'


class CommunicationListView(APIView):
    """GET /api/v1/communications/ — all drafts, filterable by incident."""

    def get(self, request):
        qs = CommunicationDraft.objects.all()
        incident_id = request.query_params.get('incident_id')
        if incident_id:
            qs = qs.filter(incident_id=incident_id)
        serializer = CommunicationDraftSerializer(qs.order_by('-created_at')[:50], many=True)
        return Response(serializer.data)


class CommunicationApproveView(APIView):
    """
    POST /api/v1/communications/{id}/approve/
    Human-in-the-loop approval gate.
    No communication leaves Citi without a human approving this endpoint.
    """

    def post(self, request, pk):
        try:
            draft = CommunicationDraft.objects.get(id=pk)
        except CommunicationDraft.DoesNotExist:
            return Response({'error': 'Draft not found'}, status=404)

        approved_by = request.data.get('approved_by', 'ops_analyst')
        draft.status = 'approved'
        draft.approved_by = approved_by
        draft.approved_at = timezone.now()
        draft.save()

        return Response({
            'status': 'approved',
            'draft_id': str(draft.id),
            'approved_by': approved_by,
            'approved_at': draft.approved_at.isoformat(),
            'message': 'Draft approved. Ready for distribution.',
        })


class CommunicationRejectView(APIView):
    """POST /api/v1/communications/{id}/reject/ — send back for revision."""

    def post(self, request, pk):
        try:
            draft = CommunicationDraft.objects.get(id=pk)
        except CommunicationDraft.DoesNotExist:
            return Response({'error': 'Draft not found'}, status=404)

        draft.status = 'rejected'
        draft.tone_notes = request.data.get('reason', 'Needs revision')
        draft.save()
        return Response({'status': 'rejected', 'reason': draft.tone_notes})


urlpatterns = [
    path('', CommunicationListView.as_view()),
    path('<str:pk>/approve/', CommunicationApproveView.as_view()),
    path('<str:pk>/reject/', CommunicationRejectView.as_view()),
]
