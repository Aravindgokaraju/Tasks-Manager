from collections import defaultdict
from time import timezone
import uuid
from rest_framework import serializers
from .models import Project, Task, TaskDependency
from django.contrib.auth.models import User
from django.db import models



class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer exposing safe fields (id, username, email)."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


    
class TaskSerializer(serializers.ModelSerializer):
    """
    Main task serializer with core fields and dependency logic.
    Includes validation for project/parent relationships and completion rules.
    """
    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault(),
        required=False
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), 
        required=False,
        allow_null=True
    )
    parent_task = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        required=False,
        allow_null=True
    )
    title = serializers.CharField(
        max_length=200,
        required=False,
        default='New Task'
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True
    )
    is_private = serializers.BooleanField(
        required=False,
        default=False
    )
    completed = serializers.BooleanField(
        required=False,
        default=False
    )
    duration_days = serializers.IntegerField(
        min_value=1,
        default=1,
        error_messages={'min_value': 'Duration must be at least 1 day.'}
    )
    can_mark_complete = serializers.SerializerMethodField()
    
    dependencies = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'project', 'parent_task', 'owner', 'title', 
            'description', 'duration_days', 'is_private', 'completed',
            'completed_at', 'created_at', 'can_mark_complete', 
            'dependencies'
        ]
        read_only_fields = ['completed_at', 'created_at', 'can_mark_complete']

    def get_dependencies(self, obj):
        deps = obj.task_dependencies.all()
        if not deps.exists():
            return []
            
        grouped = defaultdict(list)
        for dep in deps:
            grouped[dep.logic].append(dep.depends_on_id)
            
        return [{
            'logic': logic,
            'depends_on': task_ids,
            'condition': deps.filter(logic=logic).first().condition
        } for logic, task_ids in grouped.items()]
    
    def get_can_mark_complete(self, obj):
        """Enhanced version with permission check"""
        try:
            user = self.context['request'].user
            if obj.is_private and obj.owner != user:
                return False
            return obj.can_mark_complete() if hasattr(obj, 'can_mark_complete') else False
        except:
            return False

    def validate(self, data):
        """
        Combined validation from both serializers
        """
        if not data.get('project') and not data.get('parent_task'):
            raise serializers.ValidationError(
                "Task must belong to either a project or a parent task."
            )
        
        if data.get('parent_task') and data.get('project'):
            if data['parent_task'].project != data['project']:
                raise serializers.ValidationError(
                    "Subtasks must belong to the same project as their parent."
                )
        
        if 'completed' in data:
            instance = self.instance
            if instance and instance.subtasks.exists() and data['completed']:
                if not instance.can_mark_complete():
                    raise serializers.ValidationError(
                        "Cannot mark task as complete when it has incomplete subtasks."
                    )
        
        
        if self.instance and 'dependencies' in self.context.get('request').data:
            user = self.context['request'].user
            depends_on_ids = self.context['request'].data.get('dependencies', [])
            
            for dep_id in depends_on_ids:
                try:
                    dep_task = Task.objects.get(pk=dep_id)
                    if dep_task.is_private and dep_task.owner != user:
                        raise serializers.ValidationError(
                            f"Cannot depend on private task #{dep_id}"
                        )
                    if dep_task.project != self.instance.project:
                        raise serializers.ValidationError(
                            "Dependencies must be within the same project"
                        )
                except Task.DoesNotExist:
                    raise serializers.ValidationError(f"Task {dep_id} does not exist")

        return data

    def update(self, instance, validated_data):
        """Keep existing update logic"""
        completed = validated_data.get('completed', instance.completed)
        
        if completed and not instance.completed:
            if not instance.can_mark_complete():
                raise serializers.ValidationError(
                    "Cannot mark task as complete when it has incomplete subtasks."
                )
        
        return super().update(instance, validated_data)
    

class TaskDetailSerializer(TaskSerializer):
    """
    Extended task serializer with nested subtask hierarchy.
    Optionally hides parent_task field based on context.
    """
    subtasks = serializers.SerializerMethodField()
    
    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ['subtasks']
        read_only_fields = TaskSerializer.Meta.read_only_fields
        
    def get_subtasks(self, obj):
        """Recursively serialize all subtasks"""
        subtasks = obj.get_all_subtasks()
        return TaskDetailSerializer(
            subtasks, 
            many=True, 
            context=self.context
        ).data
        
    def to_representation(self, instance):
        """Remove parent_task when hide_parent is True"""
        representation = super().to_representation(instance)
        if self.context.get('hide_parent', False):
            representation.pop('parent_task', None)
        return representation

class ProjectSerializer(serializers.ModelSerializer):
    """
    Project serializer with basic fields and root task references.
    Defaults start_date to current date.
    """
    task_ids = serializers.SerializerMethodField()  
    start_date = serializers.DateField(
        required=False, 
         default=lambda: timezone.now().date()
    )
    class Meta:
        model = Project
        fields = ['id', 'owner', 'title', 'description', 'start_date', 'created_at', 'task_ids']  
    
    def get_task_ids(self, obj):
        # Get all root tasks (no parent) that are either public or owned by authenticated user
        tasks = obj.tasks.filter(parent_task__isnull=True)    
        return list(tasks.values_list('id', flat=True))
    
class ProjectDetailSerializer(ProjectSerializer):
    """
    Detailed project serializer including visible root tasks.
    Filters private tasks based on current user permissions.
    """
    tasks = serializers.SerializerMethodField()
    
    def get_tasks(self, obj):
        """Get all root tasks visible to the current user"""
        user = self.context['request'].user
        tasks = obj.tasks.filter(
            models.Q(is_private=False) | 
            models.Q(owner=user),
            parent_task__isnull=True
        )
        return TaskSerializer(tasks, many=True, context=self.context).data

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ['tasks'] 

class TaskListSerializer(serializers.ModelSerializer):
    """Minimal task serializer for list views with essential fields only."""
    class Meta:
        model = Task
        fields = ['id', 'title', 'project', 'owner', 'completed', 'duration_days']


class SmartDependencySerializer(serializers.Serializer):
    """
    Advanced dependency serializer with circular reference prevention.
    Features:
    - Logical grouping (AND/OR)
    - Condition validation
    - Automatic group management
    - Circular dependency detection
    """
    id = serializers.IntegerField(read_only=True) 
    task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all())
    depends_on = serializers.PrimaryKeyRelatedField(  
        queryset=Task.objects.all(),
        help_text="Task ID this task depends on"
    )
    logic = serializers.ChoiceField(
        choices=TaskDependency.LOGIC_CHOICES,
        default='AND',
    )
    condition = serializers.ChoiceField(
        choices=TaskDependency.CONDITION_CHOICES,
        required=False,
        default='completed'
    )

    def validate(self, data):
        task = data['task']
        depends_on = data['depends_on']
        user = self.context['request'].user
        errors = {}

        if task.is_private and task.owner != user:
            errors['task'] = "No access to private task"
        if depends_on.is_private and depends_on.owner != user:
            errors['depends_on'] = "No access to private dependency task"
        
        if task.project != depends_on.project:
            errors['project'] = "Tasks must be in the same project"
        
        if depends_on.id == task.id:
            errors['circular'] = "Task cannot depend on itself"
        elif self._creates_circular_dependency(task, depends_on):
            errors['circular'] = "This would create a circular dependency"
        
        if TaskDependency.objects.filter(
            task=task,
            depends_on=depends_on,
            logic=data['logic']
        ).exists():
            errors['duplicate'] = "This dependency already exists"

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def _creates_circular_dependency(self, task, depends_on):
        """Check if adding this dependency would create a loop"""
        if TaskDependency.objects.filter(
            task=depends_on,
            depends_on=task
        ).exists():
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

    def create(self, validated_data):
        task = validated_data['task']
        depends_on = validated_data['depends_on']
        logic = validated_data['logic']
        condition = validated_data.get('condition', 'completed')
        
        group_id = self._get_or_create_group_id(task, logic)
        
        dep, created = TaskDependency.objects.update_or_create(
            task=task,
            depends_on=depends_on,
            logic=logic,
            defaults={
                'condition': condition,
                'group_id': group_id
            }
        )
        
        return dep

    def _get_or_create_group_id(self, task, logic):
        """Returns existing group ID or creates new one"""
        existing_group = TaskDependency.objects.filter(
            task=task,
            logic=logic
        ).exclude(group_id__isnull=True).first()
        
        return existing_group.group_id if existing_group else str(uuid.uuid4())
    
    def update(self, instance, validated_data):
            task = validated_data.get('task', instance.task)
            depends_on = validated_data.get('depends_on', instance.depends_on)
            new_logic = validated_data.get('logic', instance.logic)
            new_condition = validated_data.get('condition', instance.condition)

            # Case 1: Only condition changed (simple update)
            if (instance.logic == new_logic and 
                instance.depends_on == depends_on):
                instance.condition = new_condition
                instance.save()
                return instance

            # Case 2: Logic changed (move to new group)
            if new_logic != instance.logic:
                old_group_id = instance.group_id
                new_dep = TaskDependency.objects.create(
                    task=task,
                    depends_on=depends_on,
                    logic=new_logic,
                    condition=new_condition,
                    group_id=self._get_or_create_group_id(task, new_logic)
                )
                instance.delete()
                self._cleanup_empty_group(old_group_id)
                return new_dep

            if depends_on != instance.depends_on:
                if self._creates_circular_dependency(task, depends_on):
                    raise serializers.ValidationError(
                        "This would create a circular dependency"
                    )
            instance.depends_on = depends_on
            # Case 3: depends_on changed but same logic (update in-place)
            instance.depends_on = depends_on
            instance.condition = new_condition
            instance.save()
            return instance

    def _cleanup_empty_group(self, group_id):
        """Remove group_id if no dependencies remain in the group"""
        if group_id and not TaskDependency.objects.filter(group_id=group_id).exists():
            TaskDependency.objects.filter(group_id=group_id).update(group_id=None)