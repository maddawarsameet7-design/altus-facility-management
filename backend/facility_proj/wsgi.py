"""
WSGI config for facility_proj project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facility_proj.settings')

application = get_wsgi_application()
