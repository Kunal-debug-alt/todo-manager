import secrets

from django.contrib.auth.models import User
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey

class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    invite_code = models.CharField(max_length=12, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.invite_code:
            # Short, URL-safe code for sharing. Regenerate on collision.
            for _ in range(10):
                candidate = secrets.token_urlsafe(9)[:12]
                if not Project.objects.filter(invite_code=candidate).exists():
                    self.invite_code = candidate
                    break
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProjectMembership(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_EDITOR = 'editor'
    ROLE_VIEWER = 'viewer'

    ROLE_CHOICES = (
        (ROLE_OWNER, 'Owner'),
        (ROLE_EDITOR, 'Editor'),
        (ROLE_VIEWER, 'Viewer'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('project', 'user')

    def __str__(self):
        return f"{self.user.username} → {self.project.name} ({self.role})"


class ProjectInvitation(models.Model):
    ROLE_EDITOR = ProjectMembership.ROLE_EDITOR
    ROLE_VIEWER = ProjectMembership.ROLE_VIEWER

    ROLE_CHOICES = (
        (ROLE_EDITOR, 'Editor'),
        (ROLE_VIEWER, 'Viewer'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    token = models.CharField(max_length=64, unique=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_project_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_project_invitations',
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('project', 'email')

    def save(self, *args, **kwargs):
        if not self.token:
            for _ in range(10):
                candidate = secrets.token_urlsafe(32)[:64]
                if not ProjectInvitation.objects.filter(token=candidate).exists():
                    self.token = candidate
                    break
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Invite {self.email} → {self.project.name} ({self.role})"


class Activity(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    task = models.ForeignKey('Task', on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
    task = models.ForeignKey('Task', on_delete=models.CASCADE, null=True, blank=True)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message


class Task(MPTTModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    PRIORITY_HIGH = 'high'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_LOW = 'low'
    PRIORITY_CHOICES = (
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_LOW, 'Low'),
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    # Comma-separated tags, used for lightweight filtering.
    tags = models.CharField(max_length=200, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['tree_id', 'lft']

    class MPTTMeta:
        order_insertion_by = ['title']
