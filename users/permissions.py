from rest_framework import permissions


class IsAdminOrSuperAdmin(permissions.BasePermission):
    """
    Permission class that only allows admin and superadmin users.
    Used for all admin-only endpoints.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'superadmin']
        )

    def has_object_permission(self, request, view, obj):
        """Check object-level permissions"""
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'superadmin']
        )


class IsSuperAdmin(permissions.BasePermission):
    """
    Permission class for superadmin-only actions.
    Use this for sensitive operations like creating superadmins.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'superadmin'
        )