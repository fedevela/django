from django.http import HttpResponse


def empty_view(request, *args, **kwargs):
    return HttpResponse()


def modules(request, format='html', *args, **kwargs):
    return HttpResponse()
