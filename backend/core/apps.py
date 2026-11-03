import sys
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Skip automatic startup abort during tests so pytest can use its own fixtures
        if 'pytest' in sys.modules or any('test' in arg for arg in sys.argv):
            return

        # Skip during build / management commands (collectstatic, migrate, etc.)
        # Production validation is enforced when the HTTP/ASGI server boots
        build_commands = {
            'collectstatic', 'migrate', 'makemigrations',
            'check_default_passwords', 'seed_data', 'shell',
            'showmigrations', 'sqlmigrate'
        }
        if any(arg in build_commands for arg in sys.argv):
            return

        from .security_checks import validate_production_settings
        validate_production_settings()

