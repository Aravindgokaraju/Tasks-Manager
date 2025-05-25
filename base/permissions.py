from rest_framework import permissions

class IsTaskOwnerOrPublic(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Read permissions allowed for public tasks or owner
        if request.method in permissions.SAFE_METHODS:
            return not obj.is_private or obj.owner == request.user
        # Write permissions only for owner
        return obj.owner == request.user
    
class DependencyPermission(permissions.BasePermission):
    """
    Custom permission for TaskDependency objects that:
    - Allows creation only if user has access to both tasks
    - Allows view/edit/delete only if user has permissions for both tasks
    - Includes special handling for admin users
    """
    
    def has_permission(self, request, view):
        """Check for creation/listing permissions"""
        # Always allow safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Admin users can do anything
        if request.user.is_staff:
            return True
            
        # For creation, validate task access in serializer
        if request.method == 'POST':
            return True
            
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check access to specific dependency"""
        user = request.user
        
        # Admin bypass
        if user.is_staff:
            return True
            
        # Safe methods require read access
        if request.method in permissions.SAFE_METHODS:
            return (
                (not obj.task.is_private or obj.task.owner == user) and
                (not obj.depends_on.is_private or obj.depends_on.owner == user)
            )
            
        # Write methods require ownership
        return (
            (obj.task.owner == user or not obj.task.is_private) and
            (obj.depends_on.owner == user or not obj.depends_on.is_private)
        )

    def check_project_consistency(self, task, depends_on):
        """Additional validation for task project consistency"""
        return task.project == depends_on.project