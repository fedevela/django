from django.http import HttpResponse


def empty_view(request, *args, **kwargs):
    return HttpResponse()


def modules(request, format='html'):
    if format is None:
        format = 'html'
    return HttpResponse(format)
