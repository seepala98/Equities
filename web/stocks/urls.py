from django.urls import path
from . import views

urlpatterns = [
    path('<str:symbol>/latest/', views.latest, name='latest')
]

urlpatterns += [
    path('', views.home, name='home'),
]
