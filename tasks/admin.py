from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin

from .models import Activity, Notification, Project, ProjectMembership, Task


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
	list_display = ('name', 'user', 'invite_code')
	search_fields = ('name', 'user__username', 'invite_code')


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
	list_display = ('project', 'user', 'role', 'created_at')
	list_filter = ('role',)
	search_fields = ('project__name', 'user__username', 'user__email')


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
	list_display = ('project', 'actor', 'message', 'created_at')
	list_filter = ('project',)
	search_fields = ('message', 'actor__username', 'project__name')
	date_hierarchy = 'created_at'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ('user', 'message', 'is_read', 'created_at')
	list_filter = ('is_read',)
	search_fields = ('message', 'user__username', 'user__email')
	date_hierarchy = 'created_at'


@admin.register(Task)
class TaskAdmin(DraggableMPTTAdmin):
	list_display = (
		'tree_actions',
		'indented_title',
		'completed',
		'project',
		'user',
		'created_at',
		'updated_at',
	)
	list_display_links = ('indented_title',)
	list_filter = ('completed', 'project')
	search_fields = ('title', 'description', 'user__username', 'project__name')
