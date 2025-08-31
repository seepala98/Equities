from django.urls import path
from . import views

urlpatterns = [
    path('<str:symbol>/latest/', views.latest, name='latest')
]

urlpatterns += [
    path('', views.home, name='home'),
    path('etf-analysis/', views.etf_analysis, name='etf_analysis'),
    path('etf-holdings/', views.etf_holdings, name='etf_holdings'),
    path('asset-classification/', views.asset_classification, name='asset_classification'),
    path('sector-analysis/', views.sector_analysis, name='sector_analysis'),
]
