from rest_framework.permissions import IsAuthenticated
from rest_framework import status, viewsets
from django.db import models
from base.permissions import DependencyPermission
from ..serializers import SmartDependencySerializer 
from ..models import TaskDependency
from rest_framework.decorators import action
import uuid
from rest_framework.response import Response


class TaskDependencyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing task dependencies with group support.
    
    Features:
    - Handles creation/updating/deletion of task dependencies
    - Groups related dependencies with the same logic (AND/OR)
    - Prevents circular dependencies
    - Provides group management endpoints
    - Filters dependencies based on user permissions
    
    Permissions:
    - Requires authentication
    - Uses custom DependencyPermission for object-level access control
    """
    queryset = TaskDependency.objects.all()
    permission_classes = [IsAuthenticated, DependencyPermission]

    def get_serializer_class(self):
        return SmartDependencySerializer

    def get_queryset(self):
        user = self.request.user
        return TaskDependency.objects.filter(
            models.Q(task__is_private=False) | models.Q(task__owner=user),
            models.Q(depends_on__is_private=False) | models.Q(depends_on__owner=user)
        ).distinct()


    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        group_id = self._get_or_create_group_id(data['task'], data['logic'])
        
        dependency, created = TaskDependency.objects.update_or_create(
            task=data['task'],
            depends_on=data['depends_on'],
            logic=data['logic'],
            defaults={
                'condition': data.get('condition', 'completed'),
                'group_id': group_id
            }
        )
        
        return Response(
            self.get_serializer(dependency).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def _get_or_create_group_id(self, task, logic):
        """
        Returns an existing compatible group_id or creates a new one
        Ensures no group contains mixed AND/OR logic
        """
        # First try to find existing group with matching logic
        existing_group = TaskDependency.objects.filter(
            task=task,
            logic=logic
        ).exclude(group_id__isnull=True).first()
        
        if existing_group:
            return existing_group.group_id
            
        # Check for any groups with different logic
        conflicting_group = TaskDependency.objects.filter(
            task=task,
            group_id__isnull=False
        ).exclude(logic=logic).exists()
        
        # Create new group if conflicts exist or no groups found
        return str(uuid.uuid4()) if conflicting_group or not existing_group else existing_group.group_id

    def update(self, request, *args, **kwargs):
        """
        Custom update to handle group reassignment validation
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Check if changes would create circular dependencies
        new_depends_on = serializer.validated_data.get('depends_on', instance.depends_on)
        if new_depends_on != instance.depends_on:
            task = serializer.validated_data.get('task', instance.task)
            if self._creates_circular_dependency(task, new_depends_on):
                return Response(
                    {"detail": "This change would create a circular dependency"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        updated_instance = serializer.save()
        return Response(self.get_serializer(updated_instance).data)

    
    def _creates_circular_dependency(self, task, depends_on):
        """Check if the new dependency would create a loop"""
        if depends_on.id == task.id:
            return True
            
        visited = set()
        queue = [depends_on]
        
        while queue:
            current = queue.pop()
            if current.id == task.id:
                return True
            if current.id in visited:
                continue
            visited.add(current.id)
            
            dependencies = TaskDependency.objects.filter(
                task=current
            ).select_related('depends_on')
            
            queue.extend([dep.depends_on for dep in dependencies])
        
        return False

    def destroy(self, request, *args, **kwargs):
        """
        Custom delete that:
        1. Removes the dependency
        2. Cleans up empty groups
        3. Maintains data consistency
        """
        instance = self.get_object()
        group_id = instance.group_id
        
        # Delete the instance
        self.perform_destroy(instance)
        
        # Clean up the group if empty
        self._cleanup_group(group_id)
        
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _cleanup_group(self, group_id):
        """Simplified group cleanup"""
        if group_id:
            TaskDependency.objects.filter(group_id=group_id).delete()

    @action(detail=True, methods=['get'])
    def groups(self, request, pk=None):
        task = self.get_object()
        groups = TaskDependency.objects.filter(task=task)\
            .values('group_id', 'logic')\
            .annotate(
                dependencies=models.Count('id'),
                task_ids=models.ArrayAgg('depends_on_id')  # PostgreSQL-only
            ).order_by('logic')
        
        return Response(groups)

    