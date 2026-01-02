from rest_framework.permissions import BasePermission


class IsAdminOrSuperAdmin(BasePermission):
    """Allow only admin or superadmin users"""

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                hasattr(request.user, 'role') and
                request.user.role in ['admin', 'superadmin']
        )