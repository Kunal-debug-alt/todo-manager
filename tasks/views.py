from django import forms
from django.contrib.auth.models import User
from django.db.models import Q, Count
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from django.views.generic.edit import FormView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.list import ListView
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views import View

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .forms import RegisterForm
from .models import Activity, Notification, Project, ProjectInvitation, ProjectMembership, Task


def accessible_projects_for_user(user):
    return Project.objects.filter(Q(user=user) | Q(memberships__user=user)).distinct()


def editable_projects_for_user(user):
    return Project.objects.filter(
        Q(user=user)
        | Q(
            memberships__user=user,
            memberships__role__in=[ProjectMembership.ROLE_EDITOR, ProjectMembership.ROLE_OWNER],
        )
    ).distinct()


def role_for_project_user(project, user):
    if project.user_id == user.id:
        return ProjectMembership.ROLE_OWNER
    membership = ProjectMembership.objects.filter(project=project, user=user).only('role').first()
    return membership.role if membership else None


def user_can_edit_project(project, user):
    return role_for_project_user(project, user) in [
        ProjectMembership.ROLE_OWNER,
        ProjectMembership.ROLE_EDITOR,
    ]


def member_users_for_project(project):
    return User.objects.filter(
        Q(id=project.user_id) | Q(project_memberships__project=project)
    ).distinct()


def notify_user(user, message, project=None, task=None):
    notification = Notification.objects.create(
        user=user,
        message=message,
        project=project,
        task=task,
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user.id}",
        {
            'type': 'notify',
            'message': notification.message,
            'created_at': notification.created_at.isoformat(),
        },
    )


def broadcast_refresh_for_project(project):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"project_{project.id}",
        {'type': 'refresh', 'project_id': project.id},
    )

    member_ids = list(
        User.objects.filter(
            Q(id=project.user_id) | Q(project_memberships__project=project)
        ).values_list('id', flat=True)
    )
    for user_id in member_ids:
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {'type': 'refresh', 'project_id': project.id},
        )


def broadcast_refresh_for_user(user):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user.id}",
        {'type': 'refresh', 'project_id': None},
    )


def user_is_project_owner(project, user):
    return project.user_id == user.id


def user_can_view_project(project, user):
    return (
        project.user_id == user.id
        or ProjectMembership.objects.filter(project=project, user=user).exists()
    )


class LandingView(TemplateView):
    template_name = 'tasks/landing.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('tasks:task_list')
        return super().get(request, *args, **kwargs)

class RegisterPage(FormView):
    template_name = 'tasks/register.html'
    form_class = RegisterForm
    redirect_authenticated_user = True
    success_url = reverse_lazy('tasks:task_list')

    def form_valid(self, form):
        user = form.save()
        if user is not None:
            login(self.request, user)
        return super(RegisterPage, self).form_valid(form)

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return redirect('tasks:task_list')
        return super(RegisterPage, self).get(*args, **kwargs)

class ProjectList(LoginRequiredMixin, ListView):
    model = Project
    context_object_name = 'projects'
    template_name = 'tasks/project_list.html'

    def get_queryset(self):
        user = self.request.user
        return (
            accessible_projects_for_user(user)
            .annotate(
                total_tasks=Count('task', distinct=True),
                done_tasks=Count('task', filter=Q(task__completed=True), distinct=True),
                my_pending=Count(
                    'task',
                    filter=Q(task__assignee=user, task__completed=False),
                    distinct=True,
                ),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Total across all projects for sidebar badge
        context['total_my_pending'] = Task.objects.filter(
            project__isnull=False,
            assignee=self.request.user,
            completed=False,
        ).count()
        return context

class ProjectCreate(LoginRequiredMixin, CreateView):
    model = Project
    fields = ['name']
    success_url = reverse_lazy('tasks:project_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class ProjectUpdate(LoginRequiredMixin, UpdateView):
    model = Project
    fields = ['name']
    success_url = reverse_lazy('tasks:project_list')

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)

class ProjectDelete(LoginRequiredMixin, DeleteView):
    model = Project
    success_url = reverse_lazy('tasks:project_list')
    context_object_name = 'project'

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)

class TaskList(LoginRequiredMixin, ListView):
    model = Task
    context_object_name = 'tasks'

    def get_queryset(self):
        user = self.request.user
        accessible_projects = accessible_projects_for_user(user)

        project_id = self.kwargs.get('project_id')
        if project_id:
            # Project view: show ALL tasks in the project (group view)
            project = get_object_or_404(accessible_projects, pk=project_id)
            qs = Task.objects.select_related('project', 'parent', 'assignee').filter(
                project=project
            )
        else:
            # Dashboard: personal tasks (no project) + project tasks assigned to me
            qs = Task.objects.select_related('project', 'parent', 'assignee').filter(
                Q(project__isnull=True, user=user)
                | Q(project__in=accessible_projects, assignee=user)
            )

        tag = self.request.GET.get('tag')
        if tag:
            qs = qs.filter(tags__icontains=tag)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context['editable_project_ids'] = list(
            editable_projects_for_user(user).values_list('id', flat=True)
        )

        qs = context['tasks']
        context['today'] = timezone.localdate()
        context['pending_tasks'] = qs.filter(completed=False)
        context['completed_tasks'] = qs.filter(completed=True)
        context['pending_count'] = context['pending_tasks'].count()
        context['completed_count'] = context['completed_tasks'].count()

        # Total project-assigned pending tasks for sidebar badge
        context['total_my_pending'] = Task.objects.filter(
            project__isnull=False,
            assignee=user,
            completed=False,
        ).count()

        project_id = self.kwargs.get('project_id')
        if project_id:
            project = get_object_or_404(accessible_projects_for_user(self.request.user), pk=project_id)
            context['project'] = project
            context['project_role'] = role_for_project_user(project, self.request.user)
            context['project_can_edit'] = user_can_edit_project(project, self.request.user)

            context['activities'] = Activity.objects.filter(project=project).select_related('actor', 'task')[:10]
            total = Task.objects.filter(project=project).count()
            done = Task.objects.filter(project=project, completed=True).count()
            context['project_total'] = total
            context['project_done'] = done
            context['project_percent'] = int((done / total) * 100) if total else 0

            # My pending tasks in this specific project
            context['my_pending_in_project'] = Task.objects.filter(
                project=project, assignee=user, completed=False
            ).count()

            # Send chats to the template
            context['chat_messages'] = project.chat_messages.select_related('author').order_by('created_at')

        return context


class NotificationListView(LoginRequiredMixin, View):
    """JSON API: returns unread notifications for the logged-in user."""

    def get(self, request):
        notifs = (
            Notification.objects.filter(user=request.user, is_read=False)
            .select_related('project', 'task')
            .order_by('-created_at')[:20]
        )
        data = [
            {
                'id': n.id,
                'message': n.message,
                'project_id': n.project_id,
                'task_id': n.task_id,
                'created_at': n.created_at.isoformat(),
            }
            for n in notifs
        ]
        return JsonResponse({'notifications': data, 'unread_count': len(data)})


class MarkNotificationsReadView(LoginRequiredMixin, View):
    """JSON API: marks all (or specific) notifications as read."""

    def post(self, request):
        import json
        try:
            body = json.loads(request.body)
            ids = body.get('ids')  # optional list of specific IDs
        except Exception:
            ids = None

        qs = Notification.objects.filter(user=request.user, is_read=False)
        if ids:
            qs = qs.filter(id__in=ids)
        qs.update(is_read=True)
        return JsonResponse({'ok': True})


class TaskToggleComplete(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        editable_projects = editable_projects_for_user(user)

        task = get_object_or_404(
            Task.objects.select_related('project'),
            pk=pk,
        )

        # Personal tasks are editable only by their owner. Project tasks require editor/owner.
        if task.project_id is None:
            if task.user_id != user.id:
                return redirect('tasks:task_list')
        else:
            if task.project_id not in set(editable_projects.values_list('id', flat=True)):
                return redirect('tasks:tasks_in_project', project_id=task.project_id)

        completed_value = request.POST.get('completed')
        if completed_value in ('1', 'true', 'True', 'on'):
            task.completed = True
        elif completed_value in ('0', 'false', 'False', 'off'):
            task.completed = False
        else:
            task.completed = not task.completed

        task.save(update_fields=['completed'])

        if task.project_id:
            if task.completed:
                Activity.objects.create(
                    project=task.project,
                    actor=request.user,
                    task=task,
                    message=f"{request.user.username} completed {task.title}",
                )
                if task.assignee_id and task.assignee_id != request.user.id:
                    notify_user(
                        task.assignee,
                        f"{request.user.username} completed: {task.title}",
                        project=task.project,
                        task=task,
                    )

            broadcast_refresh_for_project(task.project)
        else:
            broadcast_refresh_for_user(request.user)

        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)

        if task.project_id:
            return redirect('tasks:tasks_in_project', project_id=task.project_id)
        return redirect('tasks:task_list')

class TaskCreate(LoginRequiredMixin, CreateView):
    model = Task
    fields = ['project', 'assignee', 'parent', 'title', 'description', 'due_date', 'priority', 'tags']
    success_url = reverse_lazy('tasks:task_list')

    def get_initial(self):
        initial = super().get_initial()
        project_id = self.request.GET.get('project')
        if project_id:
            project = Project.objects.filter(pk=project_id).first()
            if project and user_can_edit_project(project, self.request.user):
                initial['project'] = project
        return initial

    def form_valid(self, form):
        project = form.cleaned_data.get('project')
        assignee = form.cleaned_data.get('assignee')

        if project and not user_can_edit_project(project, self.request.user):
            form.add_error('project', 'You do not have permission to add tasks to this project.')
            return self.form_invalid(form)

        if project:
            if assignee and not member_users_for_project(project).filter(pk=assignee.pk).exists():
                form.add_error('assignee', 'Assignee must be a member of this project.')
                return self.form_invalid(form)
        else:
            # Personal task: assignee can only be yourself (or blank).
            if assignee and assignee.pk != self.request.user.pk:
                form.add_error('assignee', 'You can only assign personal tasks to yourself.')
                return self.form_invalid(form)

        form.instance.user = self.request.user
        response = super().form_valid(form)

        task = self.object
        if task.project_id:
            Activity.objects.create(
                project=task.project,
                actor=self.request.user,
                task=task,
                message=f"{self.request.user.username} created {task.title}",
            )
            if task.assignee_id and task.assignee_id != self.request.user.id:
                notify_user(
                    task.assignee,
                    f"{self.request.user.username} assigned you: {task.title}",
                    project=task.project,
                    task=task,
                )
            broadcast_refresh_for_project(task.project)
        else:
            broadcast_refresh_for_user(self.request.user)

        return response

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        editable_projects = editable_projects_for_user(self.request.user)

        if 'description' in form.fields:
            form.fields['description'].widget.attrs.update({'rows': 3, 'style': 'resize: vertical; min-height: 80px;'})

        # Assignee dropdown should show members of the selected project.
        project_id = form.data.get('project') or self.request.GET.get('project')
        project = None
        if project_id:
            project = editable_projects.filter(pk=project_id).first()

        if project:
            form.fields['project'].queryset = editable_projects
            form.fields['parent'].queryset = Task.objects.select_related('project').filter(project=project)
            form.fields['assignee'].queryset = member_users_for_project(project).order_by('username')
        else:
            for field in ['project', 'assignee', 'parent']:
                if field in form.fields:
                    del form.fields[field]

        if 'due_date' in form.fields:
            form.fields['due_date'].widget = forms.DateInput(attrs={'type': 'date'})

        return form

class TaskUpdate(LoginRequiredMixin, UpdateView):
    model = Task
    fields = ['project', 'assignee', 'parent', 'title', 'description', 'due_date', 'priority', 'tags', 'completed']
    success_url = reverse_lazy('tasks:task_list')

    def get_queryset(self):
        user = self.request.user
        editable_projects = editable_projects_for_user(user)
        return Task.objects.filter(Q(project__isnull=True, user=user) | Q(project__in=editable_projects))

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        editable_projects = editable_projects_for_user(self.request.user)

        if 'description' in form.fields:
            form.fields['description'].widget.attrs.update({'rows': 3, 'style': 'resize: vertical; min-height: 80px;'})

        if self.object.project_id:
            form.fields['project'].queryset = editable_projects
            form.fields['parent'].queryset = Task.objects.select_related('project').filter(project=self.object.project).exclude(pk=self.object.pk)
            form.fields['assignee'].queryset = member_users_for_project(self.object.project).order_by('username')
        else:
            for field in ['project', 'assignee', 'parent']:
                if field in form.fields:
                    del form.fields[field]

        if 'due_date' in form.fields:
            form.fields['due_date'].widget = forms.DateInput(attrs={'type': 'date'})
        return form

    def form_valid(self, form):
        old_assignee_id = self.object.assignee_id
        project = form.cleaned_data.get('project')
        assignee = form.cleaned_data.get('assignee')

        if project:
            if assignee and not member_users_for_project(project).filter(pk=assignee.pk).exists():
                form.add_error('assignee', 'Assignee must be a member of this project.')
                return self.form_invalid(form)
        else:
            if assignee and assignee.pk != self.request.user.pk:
                form.add_error('assignee', 'You can only assign personal tasks to yourself.')
                return self.form_invalid(form)

        response = super().form_valid(form)
        task = self.object

        if task.project_id:
            Activity.objects.create(
                project=task.project,
                actor=self.request.user,
                task=task,
                message=f"{self.request.user.username} updated {task.title}",
            )

            if task.assignee_id and task.assignee_id != old_assignee_id and task.assignee_id != self.request.user.id:
                notify_user(
                    task.assignee,
                    f"{self.request.user.username} assigned you: {task.title}",
                    project=task.project,
                    task=task,
                )

            broadcast_refresh_for_project(task.project)
        else:
            broadcast_refresh_for_user(self.request.user)

        return response

class TaskDelete(LoginRequiredMixin, DeleteView):
    model = Task
    context_object_name = 'task'
    success_url = reverse_lazy('tasks:task_list')

    def get_queryset(self):
        user = self.request.user
        editable_projects = editable_projects_for_user(user)
        return Task.objects.filter(Q(project__isnull=True, user=user) | Q(project__in=editable_projects))

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        project = self.object.project
        title = self.object.title

        response = super().delete(request, *args, **kwargs)

        if project:
            Activity.objects.create(
                project=project,
                actor=request.user,
                task=None,
                message=f"{request.user.username} deleted {title}",
            )
            broadcast_refresh_for_project(project)
        else:
            broadcast_refresh_for_user(request.user)

        return response


class ProjectInviteForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100',
                'placeholder': 'member@example.com',
                'required': 'required',
            }
        )
    )
    role = forms.ChoiceField(
        choices=[
            (ProjectMembership.ROLE_EDITOR, 'Editor'),
            (ProjectMembership.ROLE_VIEWER, 'Viewer'),
        ],
        initial=ProjectMembership.ROLE_VIEWER,
        widget=forms.Select(
            attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100',
            }
        ),
    )


class ProjectInvite(LoginRequiredMixin, FormView):
    template_name = 'tasks/project_invite.html'
    form_class = ProjectInviteForm

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(accessible_projects_for_user(request.user), pk=kwargs.get('pk'))
        self.is_owner = self.project.user_id == request.user.id
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('tasks:project_invite', args=[self.project.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.project
        context['is_owner'] = self.is_owner
        if self.is_owner:
            context['invite_code'] = self.project.invite_code
            context['join_url'] = self.request.build_absolute_uri(
                reverse('tasks:project_join_by_code', args=[self.project.invite_code])
            )

        context['created_message'] = getattr(self, 'created_message', None)
        context['created_invite_url'] = getattr(self, 'created_invite_url', None)
        context['owner_user'] = self.project.user
        memberships_qs = (
            ProjectMembership.objects.filter(project=self.project)
            .select_related('user')
            .order_by('user__username')
        )
        if self.is_owner:
            context['memberships'] = memberships_qs
        else:
            context['memberships'] = memberships_qs.filter(user=self.request.user)
        return context

    def form_valid(self, form):
        if not self.is_owner:
            return redirect('tasks:tasks_in_project', project_id=self.project.pk)

        email = form.cleaned_data['email']
        role = form.cleaned_data['role']

        invited_user = User.objects.filter(email__iexact=email).first()
        if not invited_user:
            invitation, _created = ProjectInvitation.objects.update_or_create(
                project=self.project,
                email=email,
                defaults={
                    'role': role,
                    'created_by': self.request.user,
                    'accepted_by': None,
                    'accepted_at': None,
                },
            )

            self.created_message = 'Invite link created. Share it with the person to join.'
            self.created_invite_url = self.request.build_absolute_uri(
                reverse('tasks:project_invite_accept', args=[invitation.token])
            )
            return self.render_to_response(self.get_context_data(form=form))

        if invited_user.pk == self.request.user.pk:
            form.add_error('email', 'You are already the owner of this project.')
            return self.form_invalid(form)

        ProjectMembership.objects.update_or_create(
            project=self.project,
            user=invited_user,
            defaults={'role': role},
        )

        self.created_message = f"{invited_user.username} added to the project as {role.title()}."
        return self.render_to_response(self.get_context_data(form=form))


class ProjectInviteAccept(LoginRequiredMixin, View):
    def get(self, request, token):
        invitation = get_object_or_404(ProjectInvitation.objects.select_related('project'), token=token)

        user_email = (request.user.email or '').strip()
        if user_email.lower() != invitation.email.lower():
            return redirect('tasks:project_join')

        # Ensure the user is a member with the invited role.
        ProjectMembership.objects.update_or_create(
            project=invitation.project,
            user=request.user,
            defaults={'role': invitation.role},
        )

        invitation.accepted_by = request.user
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_by', 'accepted_at'])

        return redirect('tasks:tasks_in_project', project_id=invitation.project_id)


class ProjectJoinForm(forms.Form):
    code = forms.CharField(
        max_length=12,
        widget=forms.TextInput(
            attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100',
                'placeholder': 'Paste project code',
            }
        ),
    )


class ProjectJoin(LoginRequiredMixin, FormView):
    template_name = 'tasks/project_join.html'
    form_class = ProjectJoinForm

    def form_valid(self, form):
        code = form.cleaned_data['code']
        project = get_object_or_404(Project, invite_code=code)

        if project.user_id != self.request.user.id:
            ProjectMembership.objects.get_or_create(
                project=project,
                user=self.request.user,
                defaults={'role': ProjectMembership.ROLE_VIEWER},
            )

        return HttpResponseRedirect(reverse('tasks:tasks_in_project', args=[project.pk]))


class ProjectJoinByCode(LoginRequiredMixin, View):
    def get(self, request, code):
        project = get_object_or_404(Project, invite_code=code)

        if project.user_id != request.user.id:
            ProjectMembership.objects.get_or_create(
                project=project,
                user=request.user,
                defaults={'role': ProjectMembership.ROLE_VIEWER},
            )

        return HttpResponseRedirect(reverse('tasks:tasks_in_project', args=[project.pk]))


class ProjectMemberUpdateRole(LoginRequiredMixin, View):
    def post(self, request, pk, membership_id):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        membership = get_object_or_404(ProjectMembership, pk=membership_id, project=project)

        new_role = request.POST.get('role')
        if new_role not in (ProjectMembership.ROLE_EDITOR, ProjectMembership.ROLE_VIEWER):
            return redirect('tasks:project_invite', pk=project.pk)

        membership.role = new_role
        membership.save(update_fields=['role'])
        return redirect('tasks:project_invite', pk=project.pk)


class ProjectMemberRemove(LoginRequiredMixin, View):
    def post(self, request, pk, membership_id):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        membership = get_object_or_404(ProjectMembership, pk=membership_id, project=project)
        membership.delete()
        return redirect('tasks:project_invite', pk=project.pk)
