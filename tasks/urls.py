from django.urls import path
from .views import (
    TaskList, TaskCreate, TaskUpdate, TaskDelete, RegisterPage,
    ProjectList, ProjectCreate, ProjectUpdate, ProjectDelete
)

app_name = 'tasks'

urlpatterns = [
    path('', TaskList.as_view(), name='task_list'),
    path('project/<int:project_id>/', TaskList.as_view(), name='tasks_in_project'),
    path('register/', RegisterPage.as_view(), name='register'),
    path('create/', TaskCreate.as_view(), name='task_create'),
    path('update/<int:pk>/', TaskUpdate.as_view(), name='task_update'),
    path('delete/<int:pk>/', TaskDelete.as_view(), name='task_delete'),

    path('projects/', ProjectList.as_view(), name='project_list'),
    path('projects/create/', ProjectCreate.as_view(), name='project_create'),
    path('projects/update/<int:pk>/', ProjectUpdate.as_view(), name='project_update'),
    path('projects/delete/<int:pk>/', ProjectDelete.as_view(), name='project_delete'),
]
