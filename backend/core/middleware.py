"""
core/middleware.py
Thread-local storage for current request and user.
Enables model save guards and audit logging to verify user context.
"""
import threading

_thread_locals = threading.local()


def get_current_user():
    """Retrieve the current user from thread-local storage."""
    return getattr(_thread_locals, 'user', None)


def set_current_user(user):
    """Set the current user in thread-local storage."""
    _thread_locals.user = user


class CurrentUserMiddleware:
    """Middleware that stores the authenticated user in thread-local storage."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_user(getattr(request, 'user', None))
        try:
            response = self.get_response(request)
        finally:
            set_current_user(None)
        return response
