from django.conf.urls import patterns, url


urlpatterns = patterns('aafilters',
    url(r'^process/(?P<pipeline_string>.*)$', 'views.process', name="process"),
    url(r'^processed/(?P<path>.*)$', 'fallback.views.serve', name="processed"),
   # url(r'^process/$', 'process', name="process"),
)
