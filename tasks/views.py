from django.shortcuts import redirect, get_object_or_404
from django.views.generic.edit import FormView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from .models import Project, Task

class RegisterPage(FormView):
    template_name = 'tasks/register.html'
    form_class = UserCreationForm
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
        return Project.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = context['projects'].filter(user=self.request.user)
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
        qs = Task.objects.filter(user=self.request.user).select_related('project', 'parent')

        project_id = self.kwargs.get('project_id')
        if project_id:
            project = get_object_or_404(Project, pk=project_id, user=self.request.user)
            qs = qs.filter(project=project)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = context['tasks']
        context['pending_tasks'] = qs.filter(completed=False)
        context['completed_tasks'] = qs.filter(completed=True)
        context['pending_count'] = context['pending_tasks'].count()
        context['completed_count'] = context['completed_tasks'].count()

        project_id = self.kwargs.get('project_id')
        if project_id:
            context['project'] = get_object_or_404(Project, pk=project_id, user=self.request.user)

        return context

class TaskCreate(LoginRequiredMixin, CreateView):
    model = Task
    fields = ['project', 'parent', 'title', 'description']
    success_url = reverse_lazy('tasks:task_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['project'].queryset = Project.objects.filter(user=self.request.user)
        form.fields['parent'].queryset = Task.objects.filter(user=self.request.user)
        return form

class TaskUpdate(LoginRequiredMixin, UpdateView):
    model = Task
    fields = ['project', 'parent', 'title', 'description', 'completed']
    success_url = reverse_lazy('tasks:task_list')

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['project'].queryset = Project.objects.filter(user=self.request.user)
        form.fields['parent'].queryset = Task.objects.filter(user=self.request.user).exclude(pk=self.object.pk)
        return form

class TaskDelete(LoginRequiredMixin, DeleteView):
    model = Task
    context_object_name = 'task'
    success_url = reverse_lazy('tasks:task_list')

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user)
