from django.http import HttpResponse


def empty_view(request, *args, **kwargs):
    return HttpResponse()


def modules(request, format='html'):
    return HttpResponse(format)


def positional(request, first, second):
    return HttpResponse('%s,%s' % (first, second))
