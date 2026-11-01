from django.urls import path
from . import views
urlpatterns = [
    path('',views.index,name='index'),
    path('documents/<int:pk>/',views.document,name='document'),
    path('documents/<int:pk>/pdf/',views.file_view,name='file_view'),
    path('tables/<int:pk>/',views.table,name='table'),
    path('cells/<int:pk>/edit/',views.edit_cell,name='edit_cell'),
    path('tables/<int:pk>/edit/',views.edit_table,name='edit_table'),
]
