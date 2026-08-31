import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'libs'))

from django.core.wsgi import get_wsgi_application  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'analytics_service.settings')

application = get_wsgi_application()
