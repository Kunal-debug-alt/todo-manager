from django.urls import path
from .views import (
    TaskList, TaskCreate, TaskUpdate, TaskDelete, TaskToggleComplete, RegisterPage, LandingView,
    ProjectList, ProjectCreate, ProjectUpdate, ProjectDelete,
    ProjectInvite, ProjectInviteAccept, ProjectJoin, ProjectJoinByCode, ProjectMemberUpdateRole, ProjectMemberRemove,
    NotificationListView, MarkNotificationsReadView,
)

app_name = 'tasks'

urlpatterns = [
    path('', LandingView.as_view(), name='landing'),
    path('dashboard/', TaskList.as_view(), name='task_list'),
    path('project/<int:project_id>/', TaskList.as_view(), name='tasks_in_project'),
    path('register/', RegisterPage.as_view(), name='register'),
    path('create/', TaskCreate.as_view(), name='task_create'),
    path('update/<int:pk>/', TaskUpdate.as_view(), name='task_update'),
    path('toggle/<int:pk>/', TaskToggleComplete.as_view(), name='task_toggle_complete'),
    path('delete/<int:pk>/', TaskDelete.as_view(), name='task_delete'),

    path('projects/', ProjectList.as_view(), name='project_list'),
    path('projects/join/', ProjectJoin.as_view(), name='project_join'),
    path('projects/join/<str:code>/', ProjectJoinByCode.as_view(), name='project_join_by_code'),
    path('projects/create/', ProjectCreate.as_view(), name='project_create'),
    path('projects/update/<int:pk>/', ProjectUpdate.as_view(), name='project_update'),
    path('projects/delete/<int:pk>/', ProjectDelete.as_view(), name='project_delete'),
    path('projects/invite/<int:pk>/', ProjectInvite.as_view(), name='project_invite'),
    path('projects/invite/accept/<str:token>/', ProjectInviteAccept.as_view(), name='project_invite_accept'),
    path('projects/<int:pk>/members/<int:membership_id>/role/', ProjectMemberUpdateRole.as_view(), name='project_member_role'),
    path('projects/<int:pk>/members/<int:membership_id>/remove/', ProjectMemberRemove.as_view(), name='project_member_remove'),

    # Notification API
    path('api/notifications/', NotificationListView.as_view(), name='notifications_list'),
    path('api/notifications/mark-read/', MarkNotificationsReadView.as_view(), name='notifications_mark_read'),
]
