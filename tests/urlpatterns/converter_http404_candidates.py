from django.urls import path, register_converter

from . import converters, views

register_converter(converters.DynamicConverter, 'dynamic')


urlpatterns = [
    path('candidate-miss/<dynamic:value>/', views.empty_view, name='candidate-miss-first'),
    path('candidate-miss/<slug:value>/', views.empty_view, name='candidate-miss-fallback'),
    path('candidate-all-miss/<dynamic:value>/', views.empty_view, name='candidate-all-miss-first'),
    path('candidate-all-miss/<int:value>/', views.empty_view, name='candidate-all-miss-second'),
    path('candidate-success/<dynamic:value>/', views.empty_view, name='candidate-success-first'),
    path('candidate-success/<int:value>/', views.empty_view, name='candidate-success-second'),
]
