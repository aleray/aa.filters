import os
from django.conf import settings


CACHE_PATH = getattr(settings, 'AA_CACHE_PATH', os.path.join(settings.MEDIA_ROOT, 'cache'))
