from django.urls import path
from .views import TaskList, TaskCreate, TaskUpdate, TaskDelete, RegisterPage

app_name = 'tasks'

urlpatterns = [
    path('', TaskList.as_view(), name='task_list'),
    path('register/', RegisterPage.as_view(), name='register'),
    path('create/', TaskCreate.as_view(), name='task_create'),
    path('update/<int:pk>/', TaskUpdate.as_view(), name='task_update'),
    path('delete/<int:pk>/', TaskDelete.as_view(), name='task_delete'),
]
