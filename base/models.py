from collections import defaultdict
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone

class Project(models.Model):
    """Represents a project containing tasks, owned by a user with timeline attributes."""
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,  
        blank=True  
    )
    title = models.CharField(
        max_length=200,
        default='Untitled Project'  
    )
    description = models.TextField(blank=True)
    start_date = models.DateField(
        default=timezone.now  
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

   

class Task(models.Model):
    """
    Hierarchical task model with dependencies and completion logic.
    Can belong to a project and/or have parent-child relationships.
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks',
        null=True,
        blank=True
    )
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtasks'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    title = models.CharField(
        max_length=200,
        default='New Task'
    )
    description = models.TextField(blank=True)
    duration_days = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        default=1
    )

    is_private = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=~models.Q(parent_task__isnull=True) | models.Q(project__isnull=False),
                name='has_project_or_parent'
            )
        ]

    def save(self, *args, **kwargs):
        
        if self.parent_task and self.parent_task.is_private:
            self.is_private = True
            
        
        if self.completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.completed and self.completed_at:
            self.completed_at = None
            
        super().save(*args, **kwargs)
        
        
        if self.parent_task:
            self.parent_task.update_completion_status()

    def update_completion_status(self):
        """
        Update completion status based on subtasks.
        If all subtasks are complete, mark parent as complete.
        If any subtask is incomplete, mark parent as incomplete.
        """
        if self.subtasks.exists():
            all_complete = not self.subtasks.filter(completed=False).exists()
            if self.completed != all_complete:
                self.completed = all_complete
                if self.completed:
                    self.completed_at = timezone.now()
                else:
                    self.completed_at = None
                self.save(update_fields=['completed', 'completed_at'])
    
    def mark_complete(self):
        """Mark task as complete and handle project switching"""
        if not self.can_mark_complete():
            return False
        
        self.completed = True
        self.completed_at = timezone.now()
        self.save()
        
        
        user = self.owner
        if user:
            
            other_tasks = Task.objects.filter(
                project=self.project,
                owner=user,
                completed=False
            ).exclude(id=self.id)
            
            if not other_tasks.exists():
                # User can switch projects
                pass  # Could trigger notification or other logic
        
        return True

    def can_mark_complete(self):
        """
        Check if task can be marked complete based on:
        - All subtasks being complete (if any exist)
        - All dependencies being satisfied (if any exist)
        """
        
        if self.subtasks.exists() and self.subtasks.filter(completed=False).exists():
            return False
        
        
        groups = defaultdict(list)
        for dep in self.task_dependencies.all().select_related('depends_on'):
            groups[dep.group_id].append(dep)
        
        
        for group_deps in groups.values():
            if not group_deps:
                continue
                
            
            group_logic = group_deps[0].logic
            satisfied = [dep.is_satisfied() for dep in group_deps]
            
            if group_logic == 'AND' and not all(satisfied):
                return False
            elif group_logic == 'OR' and not any(satisfied):
                return False
                
        return True
        
    def __str__(self):
        return f"{self.title} ({self.project.title if self.project else 'No Project'})"
    
    def get_all_subtasks(self):
        """Recursively get all subtasks"""
        subtasks = list(self.subtasks.all())
        for child in self.subtasks.all():
            subtasks.extend(child.get_all_subtasks())
        return subtasks
    
    
class TaskDependency(models.Model):
    """
    Defines conditional relationships between tasks with logical grouping.
    Supports AND/OR logic and multiple condition types.
    """
    LOGIC_CHOICES = [
        ('AND', 'All dependencies must be satisfied'),
        ('OR', 'Any dependency must be satisfied'),
    ]
    
    CONDITION_CHOICES = [
        ('completed', 'Depends on completion'),
        ('not_completed', 'Depends on not being completed'),
        ('in_progress', 'Depends on being in progress'),
    ]
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='task_dependencies')
    depends_on = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependent_on_me')
    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='completed'
    )
    logic = models.CharField(
        max_length=3,
        choices=LOGIC_CHOICES,
        default='AND',
        help_text="Logical operator for this dependency group"
    )
    group_id = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        help_text="UUID to identify groups of dependencies that share the same logic"
    )
    
    class Meta:
        unique_together = ('task', 'depends_on')
        verbose_name_plural = "Task dependencies"

    def is_satisfied(self):
        """Check if this dependency condition is met"""
        if self.condition == 'completed':
            return self.depends_on.completed
        elif self.condition == 'not_completed':
            return not self.depends_on.completed
        elif self.condition == 'in_progress':
            return not self.depends_on.completed and self.depends_on.started
        return False

    def save(self, *args, **kwargs):
        """Ensure proper grouping when saving"""
        if not self.group_id:
            existing = TaskDependency.objects.filter(
                task=self.task,
                logic=self.logic
            ).exclude(group_id__isnull=True).first()
            
            self.group_id = existing.group_id if existing else str(uuid.uuid4())
        super().save(*args, **kwargs)
        