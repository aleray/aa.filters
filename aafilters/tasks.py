"""
Attention: this file is not used for the moment

Where we to want to install the queue,
one would have to uncomment the lines pertaining to django-celery
in requirements.txt
{project}/settings.py (installed apps)
{project}/urls.py
"""



from __future__ import absolute_import
# ^^^ The above is required if you want to import from the celery
# library.  If you don't have this then `from celery.schedules import`
# becomes `proj.celery.schedules` in Python 2.x since it allows
# for relative imports by default.


import os
import requests
import uuid
import mimetypes
import magic

from celery import chain, shared_task
from django.core.cache import cache as memcache
from hashlib import md5
from PIL import Image
from urllib import quote

from .settings import CACHE_PATH


LOCK_EXPIRE = 60 * 5 # Lock expires in 5 minutes


registry = {}

def register(fn):
    registry[fn.__name__] = fn


def normalize_url(url):
    # percent encode url, fixing lame server errors for e.g, like space
    # within url paths.
    # taken from <http://svn.python.org/view/python/trunk/Lib/urllib.py?r1=71780&r2=71779&pathrev=71780>
    return quote(url, safe="%/:=&?~#+!$,;'@()*[]")


def get_lock_id(url=None, pipeline=[]):
    """
    Returns a unique key for memcached. It can also be used to generate unique
    filenames.
    """
    url_hexdigest = md5(url).hexdigest()
    pipeline_hexdigest = md5("|".join(pipeline)).hexdigest()
    return 'lock--{0}--{1}'.format(url_hexdigest, pipeline_hexdigest)


class Bundle(object):
    """
    An object to be passed through the different tasks of a chain.
    """
    def __init__(self, url=None, to_go=[], target_ext=None):
        self.url = url  # TODO: normalize the URL?
        self.to_go = to_go  # the remaining tasks
        self.target_ext = target_ext # the extension for the final file (as requested from the view)
        self.mime = "application/octet-stream"  # A default mimetype
        self.consumed = []  # the tasks already performed

    def consume(self):
        """
        moves one tasks forward
        """
        ret = self.to_go.pop()
        if ret:
            self.consumed.append(ret)

    def url2path(self):
        """
        computes a unique filename based on the url and the consumed tasks list

        It automatically adds the file extension based on mimetype.
        """
        lock_id = get_lock_id(url=self.url, pipeline=self.consumed)
        fn = md5(lock_id).hexdigest() # no longer used
        local_path = self.url
        if len(self.consumed) > 0:
            local_path += u"..%s" % '..'.join(self.consumed)
        # For the final filename, we want the requested extension,
        # so that it gets saved on a predictable location
        if len(self.to_go) == 0:
            if len(self.consumed) == 0:
                pass
            elif self.target_ext:
                ext = self.target_ext
                # Yet we do check if the mimetype of the produced result fits with the
                # requested extension:
                if ext.lower() not in mimetypes.guess_all_extensions(self.mime, strict=False):
                    raise TypeError
                local_path += ext
        else:
            ext = mimetypes.guess_extension(self.mime, strict=False)
            local_path += ext
        print "%d steps to go in pipeline" % len(self.to_go)
        local_folder, local_filename = os.path.split(local_path)
        if not os.path.exists(os.path.join(CACHE_PATH,local_folder)):
            os.makedirs(os.path.join(CACHE_PATH,local_folder))
        return os.path.join(CACHE_PATH, local_path)
        #r = urlsplit(url)
        #ret = r.netloc + '/' + r.path
        #if r.query:
            #ret += '?' + r.query
        #if r.fragment:
            #ret += '#' + r.query
        #return ret


@shared_task
def populate_mime_type(bundle):
    """
    A "private" that sets the bundle mimetype.

    Should be run first, in order to let the next tasks know about the mimetype
    """
    # TODO: use AACore Http sniffer instead to discover the mimetype
    print(u'try task populate mime type by sniffing %s' % bundle.url)
    request = requests.get(bundle.url, stream=True)
    mime = magic.from_buffer(request.iter_content(1024).next(), mime=True)
    bundle.mime = mime
    print("write " + bundle.url2path())
    return bundle


@shared_task
def cache(bundle):
    """
    Saves to disk the given url.

    Should be run right after populate_mime_type

    """
    full_path = bundle.url2path()

    if not os.path.exists(full_path):
        r = requests.get(bundle.url, stream=True)
        if r.status_code == 200:
            #path, filename = os.path.split(full_path)
            #if not os.path.exists(path):
                #os.makedirs(path)

            with open(full_path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

    return bundle


@shared_task
def bw(bundle):
    """
    turns an image in black and white
    """
    accepted_mimetypes = ["image/jpeg", "image/png"]

    if bundle.mime not in accepted_mimetypes:
        raise TypeError

    image_file = Image.open(bundle.url2path())
    bundle.consume()
    image_file = image_file.convert('1')
    image_file.save(bundle.url2path())
    return bundle


@shared_task
def thumb(bundle):
    """
    turns an image into a 100x100 thumbnail
    """
    accepted_mimetypes = ["image/jpeg", "image/png"]

    if bundle.mime not in accepted_mimetypes:
        raise TypeError

    image_file = Image.open(bundle.url2path())
    bundle.consume()
    image_file = image_file.resize((100, 100), Image.NEAREST)
    image_file.save(bundle.url2path())
    return bundle


register(bw)
register(thumb)


@shared_task()
def release_lock(lock_id):
    """
    Deletes the given key from the cache
    """
    memcache.delete(lock_id)


@shared_task()
def serialize(bundle):
    """
    Turns a bundle into a dictionnary.

    This should be the last task of the chain of tasks
    """
    return {'url': bundle.url, 'mime': bundle.mime, 'path': bundle.url2path()}


def process_pipeline(url=None, pipeline=[], target_ext=None, synchronous=False):
    """
    Construct and run the chain of tasks

    returns the ID of the chain task. If a similar tasks is allready
    processing, returns its ID instead.
    """
    lock_id = get_lock_id(url=url, pipeline=pipeline)
    task_id = str(uuid.uuid4())

    acquire_lock = lambda: memcache.add(lock_id, task_id, LOCK_EXPIRE)

    if acquire_lock():
        bundle = Bundle(url=url, to_go=pipeline, target_ext=target_ext)

        cb = release_lock.si(lock_id)

        filters = []
        filters.extend([populate_mime_type.subtask((bundle,), link_error=cb)])
        filters.extend([cache.subtask(link_error=cb)])
        filters.extend([registry[p].subtask(link_error=cb) for p in pipeline])
        filters.extend([serialize.subtask(link_error=cb)])

        result = chain(*filters).apply_async(link=cb, task_id=task_id)

        if synchronous:
            result.wait()
        return task_id

    return memcache.get(lock_id)
