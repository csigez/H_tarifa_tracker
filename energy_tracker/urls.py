from django.urls import path
from . import views

app_name = 'energy_tracker'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('reading/add/', views.MeterReadingCreateView.as_view(), name='add_reading'),
    path('reading/add-func/', views.add_reading, name='add_reading_func'),
    path('reading/<int:pk>/', views.MeterReadingDetailView.as_view(), name='reading_detail'),
]
