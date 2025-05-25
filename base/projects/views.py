from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.decorators import action
from django.db.models import Q

from ..models import Project
from ..serializers import ProjectSerializer, ProjectDetailSerializer, TaskDetailSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """
    Projects CRUD with nested task listing
    - Public read access for all projects
    - Requires authentication for write operations
    """
    queryset = Project.objects.all()
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
        
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        return super().get_queryset().all()
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def tasks(self, request, pk=None):
        """
        Get project tasks (requires authentication)
        - Shows public tasks or tasks owned by the user
        """
        project = self.get_object()
        
        # Get visible tasks (public or owned by user)
        root_tasks = project.tasks.filter(
            Q(parent_task__isnull=True) & 
            (Q(is_private=False) | Q(owner=request.user))
        )
        
        # Completion stats
        all_tasks = project.tasks.filter(
            Q(is_private=False) | Q(owner=request.user)
        )
        completed_count = all_tasks.filter(completed=True).count()
        total_count = all_tasks.count()
        
        serializer = TaskDetailSerializer(
            root_tasks,
            many=True,
            context={'request': request}
        )
        return Response({
            'tasks': serializer.data,
            'completion_stats': {
                'completed': completed_count,
                'total': total_count,
                'percentage': round((completed_count/total_count*100) if total_count else 0, 2)
            }
        })