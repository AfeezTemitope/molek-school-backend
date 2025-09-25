from rest_framework import permissions

class IsAdminOrSuperAdmin(permissions.BasePermission):
    """
    Allow access only to Super Admin or Admin/Teacher.
    """
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.role in ['superadmin', 'admin', 'teacher']