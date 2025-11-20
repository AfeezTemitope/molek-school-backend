from rest_framework import permissions


class IsAdminOrSuperAdmin(permissions.BasePermission):
    """
    Permission class that only allows admin and superadmin users.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'superadmin']
        )