from rest_framework import permissions


def caller_id(user):
    """The authenticated caller's id, as an integer.
    """
    try:
        return int(user.id)
    except (TypeError, ValueError):
        return None


def has_premium(user):
    """Whether this caller is entitled to Premium features.
    """
    if not user:
        return False
    return bool(getattr(user, 'has_premium_access', None) or getattr(user, 'is_premium', False))


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Anyone authenticated may read; only the owner (or staff) may write.
    """
    message = 'You do not own this URL.'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        return obj.owner_id is not None and obj.owner_id == caller_id(request.user)


class IsPremium(permissions.BasePermission):
    """Gate for premium-only features such as analytics.
    """
    message = 'Analytics is available on the Premium tier.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and has_premium(user))
