from django.http import HttpResponse
from django.urls import path


def health(_request):
    return HttpResponse("ok", content_type="text/plain")


def home(_request):
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Portal</title></head><body>"
        "<h1>Lab portal (Django)</h1><p>Flask app: use <a href='/'>main site</a> "
        "or <a href='/api/demo/csrf'>/api/…</a>.</p></body></html>"
    )
    return HttpResponse(html, content_type="text/html; charset=utf-8")


urlpatterns = [
    path("health/", health, name="health"),
    path("", home, name="home"),
]
