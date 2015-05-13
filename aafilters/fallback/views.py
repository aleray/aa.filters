from __future__ import absolute_import
# ^^^ The above is required if you want to import from the celery
# library.  If you don't have this then `from celery.schedules import`
# becomes `proj.celery.schedules` in Python 2.x since it allows
# for relative imports by default.

import os

import stat
import posixpath
import re
import mimetypes

from django.shortcuts import redirect

from django.http import (Http404, HttpResponse, HttpResponseRedirect,
    HttpResponseNotModified, StreamingHttpResponse)
from django.template import loader, Template, Context, TemplateDoesNotExist
from django.utils.http import http_date, parse_http_date
from urllib import unquote
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext_noop

from django.conf import settings

"""
This is a simple view that tries to serve a static file, and if not found,
redirects to the process task.

It is based of django.views.static and should not be used in production,
where rather a webserver should take care of this behaviour (ie, for nginx,
stat the files with `try -f`)
"""


from django.core.urlresolvers import reverse


DEFAULT_DIRECTORY_INDEX_TEMPLATE = """
{% load i18n %}
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
    <meta http-equiv="Content-Language" content="en-us" />
    <meta name="robots" content="NONE,NOARCHIVE" />
    <title>{% blocktrans %}Index of {{ directory }}{% endblocktrans %}</title>
  </head>
  <body>
    <h1>{% blocktrans %}Index of {{ directory }}{% endblocktrans %}</h1>
    <ul>
      {% ifnotequal directory "/" %}
      <li><a href="../">../</a></li>
      {% endifnotequal %}
      {% for f in file_list %}
      <li><a href="{{ f|urlencode }}">{{ f }}</a></li>
      {% endfor %}
    </ul>
  </body>
</html>
"""
template_translatable = ugettext_noop("Index of %(directory)s")

def directory_index(path, fullpath):
    try:
        t = loader.select_template(['static/directory_index.html',
                'static/directory_index'])
    except TemplateDoesNotExist:
        t = Template(DEFAULT_DIRECTORY_INDEX_TEMPLATE, name='Default directory index template')
    files = []
    for f in os.listdir(fullpath):
        if not f.startswith('.'):
            if os.path.isdir(os.path.join(fullpath, f)):
                f += '/'
            files.append(f)
    c = Context({
        'directory' : path + '/',
        'file_list' : files,
    })
    return HttpResponse(t.render(c))

def was_modified_since(header=None, mtime=0, size=0):
    """
    Was something modified since the user last downloaded it?

    header
      This is the value of the If-Modified-Since header.  If this is None,
      I'll just return True.

    mtime
      This is the modification time of the item we're talking about.

    size
      This is the size of the item we're talking about.
    """
    try:
        if header is None:
            raise ValueError
        matches = re.match(r"^([^;]+)(; length=([0-9]+))?$", header,
                           re.IGNORECASE)
        header_mtime = parse_http_date(matches.group(1))
        header_len = matches.group(3)
        if header_len and int(header_len) != size:
            raise ValueError
        if int(mtime) > header_mtime:
            raise ValueError
    except (AttributeError, ValueError, OverflowError):
        return True
    return False

def serve(request, path, document_root=None, show_indexes=False):
    """
    Serve static files below a given point in the directory structure.

    To use, put a URL pattern such as::

        (r'^(?P<path>.*)$', 'aafilters.views.serve', {'document_root': '/path/to/my/files/'})

    in your URLconf. You must provide the ``document_root`` param. You may
    also set ``show_indexes`` to ``True`` if you'd like to serve a basic index
    of the directory.  This index view will use the template hardcoded below,
    but if you'd like to override it, you can create a template called
    ``static/directory_index.html``.
    """
    document_root = os.path.join(settings.MEDIA_ROOT, 'cache')
    path = unquote(path) #posixpath.normpath(unquote(path))
    path = path.lstrip('/')
    fullpath = os.path.join(document_root, path)
    if os.path.isdir(fullpath):
        if show_indexes:
            return directory_index(path, fullpath)
        raise Http404(_("Directory indexes are not allowed here."))
    if not os.path.exists(fullpath):
        uri = reverse('process', kwargs={'pipeline_string': path})
        print uri
        return redirect(uri)
    # Respect the If-Modified-Since header.
    statobj = os.stat(fullpath)
    if not was_modified_since(request.META.get('HTTP_IF_MODIFIED_SINCE'),
                              statobj.st_mtime, statobj.st_size):
        return HttpResponseNotModified()
    content_type, encoding = mimetypes.guess_type(fullpath)
    content_type = content_type or 'application/octet-stream'
    response = StreamingHttpResponse(open(fullpath, 'rb'),
                                     content_type=content_type)
    response["Last-Modified"] = http_date(statobj.st_mtime)
    if stat.S_ISREG(statobj.st_mode):
        response["Content-Length"] = statobj.st_size
    if encoding:
        response["Content-Encoding"] = encoding
    return response
