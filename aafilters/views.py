# -*- coding: utf-8 -*-

from __future__ import absolute_import
# ^^^ The above is required if you want to import from the celery
# library.  If you don't have this then `from celery.schedules import`
# becomes `proj.celery.schedules` in Python 2.x since it allows
# for relative imports by default.

import os
import stat

from django.http import StreamingHttpResponse
from django.utils.http import http_date
from django.shortcuts import redirect

from .filters import process_pipeline


def process(request, pipeline_string):
    """
    With a url like /filters/process/http://s2.lemde.fr/image/2012/05/09/644x322/1698586_3_83ef_francois-hollande-et-nicolas-sarkozy-durant-la_cc28a6e60a381054c901fecf8fe39886.jpg..bw.jpg

    Find:
    url = 'http://s2.lemde.fr/image/2012/05/09/644x322/1698586_3_83ef_francois-hollande-et-nicolas-sarkozy-durant-la_cc28a6e60a381054c901fecf8fe39886.jpg'
    extension = '.jpg'
    pipeline = '[u'bw']'

    And send it of to the filters
    """
    parts = pipeline_string.split('..')
    url = parts[0]
    pipeline = []
    extension=None
    if len(parts) > 1:
        pipeline = parts[1:]
        pipeline[-1], extension = os.path.splitext(pipeline[-1])

    # FIXME: There is redirection loop in the script
    # We temporary redirect to the original URL to avoid it
    else:
        return redirect(url)

    bundle = process_pipeline(url=url, pipeline=pipeline, target_ext=extension)

    """
    At this point, the file should have been generated,
    and the bundle will tell us its path.

    We then serve it with Python—which is not the most efficient
    of strategies, but as long as we do it only once it should
    be fine.
    """
    statobj = os.stat(bundle['path'])
    response = StreamingHttpResponse(open(bundle['path'], 'rb'), content_type=bundle['mime'])
    response["Last-Modified"] = http_date(statobj.st_mtime)
    if stat.S_ISREG(statobj.st_mode):
        response["Content-Length"] = statobj.st_size
    return response

