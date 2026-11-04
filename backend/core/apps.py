import os
import sys
from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Startup-check skip depends ONLY on an explicit TESTING environment variable.
        # App must refuse to start if TESTING is set while DEBUG=False.
        testing_active = os.environ.get('TESTING', '').strip().lower() in ('true', '1', 't', 'yes')
        if testing_active:
            if not getattr(settings, 'DEBUG', False):
                raise ImproperlyConfigured("TESTING environment variable cannot be active when DEBUG=False.")
            return

        # Skip during build / management commands (collectstatic, migrate, etc.)
        # Production validation is enforced when the HTTP/ASGI server boots
        build_commands = {
            'collectstatic', 'migrate', 'makemigrations',
            'check_default_passwords', 'seed_data', 'shell',
            'showmigrations', 'sqlmigrate', 'bootstrap_prod_user'
        }
        if any(arg in build_commands for arg in sys.argv):
            return

        from .security_checks import validate_production_settings
        validate_production_settings()

        # Self-healing database initialization: ensure tables and admin user exist on startup
        try:
            from django.core.management import call_command
            from core.models import User
            if not User.objects.filter(username='admin').exists():
                call_command('bootstrap_prod_user', interactive=False)
        except Exception:
            try:
                from django.core.management import call_command
                call_command('migrate', interactive=False)
                call_command('bootstrap_prod_user', interactive=False)
            except Exception as init_err:
                import logging
                logging.warning(f"Startup database auto-init skipped: {init_err}")

