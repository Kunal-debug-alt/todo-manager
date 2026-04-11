from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin

from .models import Project, Task


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
	list_display = ('name', 'user')
	search_fields = ('name', 'user__username')


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
