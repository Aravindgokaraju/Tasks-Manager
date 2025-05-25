from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from ..serializers import UserSerializer

User = get_user_model()

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Provides read-only user information
    Accessible only to authenticated users
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
