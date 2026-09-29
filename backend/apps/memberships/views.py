from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Membership
from .serializers import MembershipSerializer


class MembershipListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = Membership.objects.filter(
            student=request.user
        )

        serializer = MembershipSerializer(
            memberships,
            many=True
        )

        return Response(serializer.data)