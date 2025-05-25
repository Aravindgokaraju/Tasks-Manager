from datetime import date, timedelta
from collections import defaultdict, deque
import logging
from typing import Dict, List, Optional
from django.apps import apps
from django.utils import timezone




logger = logging.getLogger(__name__)

class GlobalParallelScheduler:
    """
    A global task scheduler that manages parallel task execution across multiple projects.
    
    Features:
    - Manages user availability tracking (next available dates)
    - Handles project prioritization via project ordering
    - Builds and validates task dependency graphs
    - Detects circular dependencies
    - Generates optimized schedules considering:
      * Task dependencies
      * User availability
      * Project priorities
    
    Data Structures:
    - user_availability: Tracks when users are next available {user_id: datetime}
    - project_order: Maintains project priority order {project_id: int} 
    - schedule: Stores final scheduled tasks
    
    Note: This is a base scheduler class meant to be extended with specific scheduling logic.
    """
    def __init__(self):
        self.user_availability = {}
        self.project_order = {}  
        self.schedule = []

    def _get_task_model(self):
        return apps.get_model('base', 'Task')
    
    def _get_project_model(self):
        return apps.get_model('base', 'Project')

    def _build_dependency_graph(self, tasks):
        """Build dependency graph and in-degree count for tasks"""
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        task_map = {}
        
        for task in tasks:
            task_map[task.id] = task
            in_degree[task.id] = 0
            
        for task in tasks:
            for dep in task.task_dependencies.all():
                graph[dep.depends_on_id].append(task.id)
                in_degree[task.id] += 1
        
        return graph, in_degree, task_map

    def _check_circular_dependencies(self, graph):
        """Check for circular dependencies using DFS"""
        visited = set()
        path = set()
        
        def dfs(node):
            if node in path:
                return True
            if node in visited:
                return False
                
            visited.add(node)
            path.add(node)
            
            for neighbor in graph.get(node, []):
                if dfs(neighbor):
                    return True
                    
            path.remove(node)
            return False
            
        for node in graph:
            if dfs(node):
                raise ValueError(f"Circular dependency detected involving task {node}")

    def _schedule_project(self, project, project_start_date):
        """Schedule all tasks for a single project"""
        Task = self._get_task_model()
        tasks = Task.objects.filter(project=project).select_related('owner').prefetch_related('task_dependencies')
        
        if not tasks.exists():
            return []

        # Build dependency graph
        graph, in_degree, task_map = self._build_dependency_graph(tasks)
        self._check_circular_dependencies(graph)
        
        # Initialize scheduling structures
        project_schedule = []
        queue = deque([tid for tid in in_degree if in_degree[tid] == 0])
        current_date = project_start_date
        
        # Get all unique users in this project
        users = {task.owner for task in tasks if task.owner}
        user_queue = deque(users)
        
        while queue:
            # Assign one task to each available user
            for _ in range(len(user_queue)):
                if not queue:
                    break
                    
                task_id = queue.popleft()
                task = task_map[task_id]
                
                if task.owner:
                    # Get user's next available time
                    start_date = max(
                        current_date,
                        self.user_availability.get(task.owner.id, current_date)
                    )
                    end_date = start_date + timedelta(days=task.duration_days)
                    
                    # Update user availability
                    self.user_availability[task.owner.id] = end_date
                    
                    # Add to schedule
                    project_schedule.append({
                        'id': task.id,
                        'title': task.title,
                        'start_date': start_date,
                        'end_date': end_date,
                        'assignee': task.owner.username,
                        'duration_days': task.duration_days,
                        'project_id': project.id,
                        'project_title': project.title
                    })
                    
                    # Update queue with newly available tasks
                    for neighbor in graph[task_id]:
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            queue.append(neighbor)
                else:
                    # Unassigned task - schedule sequentially
                    start_date = current_date
                    end_date = start_date + timedelta(days=task.duration_days)
                    current_date = end_date
                    
                    project_schedule.append({
                        'id': task.id,
                        'title': task.title,
                        'start_date': start_date,
                        'end_date': end_date,
                        'assignee': None,
                        'duration_days': task.duration_days,
                        'project_id': project.id,
                        'project_title': project.title
                    })
                    
                    # Update queue with newly available tasks
                    for neighbor in graph[task_id]:
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            queue.append(neighbor)
            
            # Move to next day if there are still tasks to schedule
            if queue:
                current_date += timedelta(days=1)
                
        return project_schedule

    def generate_schedule(self):
        """Generate schedule for all projects ordered by their priority"""
        try:
            Project = self._get_project_model()
            
            # Get all projects ordered by their 'order' field
            projects = Project.objects.all().order_by('id')
            
            if not projects.exists():
                return {'schedule': []}
            
            # Reset scheduling state
            self.user_availability = {}
            self.schedule = []
            
            # Schedule each project sequentially
            for project in projects:
                project_start = project.start_date if project.start_date else timezone.now().date()
                project_schedule = self._schedule_project(project, project_start)
                self.schedule.extend(project_schedule)
            
            return {
                'schedule': sorted(self.schedule, key=lambda x: x['start_date']),
                'start_date': min(task['start_date'] for task in self.schedule) if self.schedule else None,
                'end_date': max(task['end_date'] for task in self.schedule) if self.schedule else None
            }
            
        except Exception as e:
            logger.error(f"Global schedule generation failed: {str(e)}")
            raise ValueError(f"Failed to generate global schedule: {str(e)}")
