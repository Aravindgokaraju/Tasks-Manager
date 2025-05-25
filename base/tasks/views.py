from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.contrib.auth import get_user_model
from django.db import models
from base.permissions import IsTaskOwnerOrPublic
from ..serializers import TaskSerializer,TaskDetailSerializer
from rest_framework.decorators import action
from ..models import Task

class TaskViewSet(viewsets.ModelViewSet):
    
    """
    API endpoint for managing hierarchical tasks with nested relationships.
    
    Key Features:
    - Full CRUD operations for tasks with hierarchical display
    - Shows complete task hierarchies by default (3 levels deep)
    - Handles task ownership and privacy (private/public)
    - Supports task assignment and dependency checking
    - Provides specialized endpoints for:
      * Viewing nested subtasks
      * Assigning/reassigning owners
      * Getting task timelines
    
    Permissions:
    - Requires authentication
    - Only allows task owners to modify private tasks
    
    Query Parameters:
    - completed=true/false - Filter tasks by completion status
    """

    queryset = Task.objects.all()
    permission_classes = [IsAuthenticated, IsTaskOwnerOrPublic]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TaskDetailSerializer
        return TaskSerializer 

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == 'retrieve':
            context['hide_parent'] = True
        return context

    def perform_create(self, serializer):
        """Auto-set owner to current user if not provided"""
        if 'owner' not in serializer.validated_data:
            serializer.save(owner=self.request.user)
        else:
            serializer.save()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Show private tasks only to their owner
        queryset = queryset.filter(
            models.Q(is_private=False) | 
            models.Q(owner=user)
        )
        
        # Filter by completion status if requested
        completed = self.request.query_params.get('completed')
        if completed in ['true', 'false']:
            queryset = queryset.filter(completed=(completed == 'true'))
        
        # Optimize queries for nested relationships
        queryset = queryset.prefetch_related(
            'subtasks',
            'subtasks__subtasks',
            'subtasks__subtasks__subtasks'  # 3 levels deep by default
        )
        
        return queryset

    def list(self, request, *args, **kwargs):
        """
        Override default list to show all tasks with their complete hierarchies
        """
        # Get all root tasks (tasks without parents)
        root_tasks = self.get_queryset().filter(parent_task__isnull=True)
        
        def build_task_tree(task):
            task_data = TaskDetailSerializer(task, context=self.get_serializer_context()).data
            task_data['subtasks'] = [build_task_tree(subtask) for subtask in task.subtasks.all()]
            return task_data
        
        task_tree = [build_task_tree(task) for task in root_tasks]
        return Response(task_tree)
    
    def check_dependencies(self, task):
        """Check if all dependencies are satisfied"""
        for dependency in task.task_dependencies.all():
            if dependency.condition == 'completed' and not dependency.depends_on.completed:
                return False
            elif dependency.condition == 'not_completed' and dependency.depends_on.completed:
                return False
            elif dependency.condition == 'in_progress' and dependency.depends_on.completed:
                return False
        return True
    
    def perform_create(self, serializer):
        task = serializer.save()
        if task.parent_task and not task.project:
            task.project = task.parent_task.project
            task.save()

    @action(detail=True, methods=['get'])
    def subtasks(self, request, pk=None):
        """Get all subtasks for a specific task (all levels)"""
        task = self.get_object()
        
        def get_nested_subtasks(task):
            subtasks = []
            for subtask in task.subtasks.all():
                subtask_data = TaskDetailSerializer(subtask, context={'request': request, 'hide_parent': True}).data
                subtask_data['subtasks'] = get_nested_subtasks(subtask)
                subtasks.append(subtask_data)
            return subtasks
        
        nested_subtasks = get_nested_subtasks(task)
        return Response(nested_subtasks)
    
    @action(detail=True, methods=['patch'])
    def assign_owner(self, request, pk=None):
        """Custom action to assign/reassign task owner"""
        task = self.get_object()
        new_owner_id = request.data.get('owner_id')
        
        if not new_owner_id:
            return Response(
                {"detail": "owner_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            new_owner = User.objects.get(pk=new_owner_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
            
        task.owner = new_owner
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Get calculated timeline for this task"""
        task = self.get_object()
        dates = task.get_optimal_dates()
        return Response({
            'start_date': dates.get('start_date'),
            'end_date': dates.get('end_date'),
            'duration': task.duration_days
        })
    
    