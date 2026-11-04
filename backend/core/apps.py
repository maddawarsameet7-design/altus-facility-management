import sys
from django.apps import AppConfig


from django.conf import settings


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Skip automatic startup abort during tests so pytest can use its own fixtures
        if 'test' in settings.SETTINGS_MODULE.lower() or getattr(settings, 'TESTING', False) or os.environ.get('TESTING'):
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

