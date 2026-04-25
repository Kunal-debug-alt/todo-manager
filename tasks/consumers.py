from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async

from .models import Project, ChatMessage


class RealtimeConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or user.is_anonymous:
            await self.close(code=4401)
            return

        self.user_group = f"user_{user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        self.project_group = None
        self.project_id = None
        project_id = self.scope.get('url_route', {}).get('kwargs', {}).get('project_id')
        if project_id is not None:
            # Validate access to the project before joining its broadcast group.
            project = await Project.objects.filter(pk=project_id).only('id', 'user_id').afirst()
            if not project:
                await self.close(code=4403)
                return

            if project.user_id != user.id:
                has_membership = await project.memberships.filter(user_id=user.id).aexists()
                if not has_membership:
                    await self.close(code=4403)
                    return

            self.project_id = project_id
            self.project_group = f"project_{project_id}"
            await self.channel_layer.group_add(self.project_group, self.channel_name)

        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'user_group') and self.user_group:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        if hasattr(self, 'project_group') and self.project_group:
            await self.channel_layer.group_discard(self.project_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope.get('user')
        msg_type = content.get('type')

        if msg_type == 'chat_message' and self.project_id:
            text = content.get('text', '').strip()
            if text:
                # Save to DB
                msg_obj = await sync_to_async(ChatMessage.objects.create)(
                    project_id=self.project_id,
                    author=user,
                    text=text
                )
                # Broadcast back to the group with timestamp
                await self.channel_layer.group_send(
                    self.project_group,
                    {
                        'type': 'chat_broadcast',
                        'author': user.username,
                        'text': text,
                        'ts': msg_obj.created_at.isoformat(),
                    }
                )
        elif msg_type == 'clear_chat' and self.project_id:
            # Delete all chat messages for this project
            await sync_to_async(lambda: ChatMessage.objects.filter(project_id=self.project_id).delete())()
            # Broadcast the clear action to the group
            await self.channel_layer.group_send(
                self.project_group,
                {
                    'type': 'chat_clear_broadcast',
                }
            )
        elif msg_type == 'typing_start' and self.project_id:
            # Broadcast typing indicator to group (excluding self via JS)
            await self.channel_layer.group_send(
                self.project_group,
                {
                    'type': 'typing_broadcast',
                    'author': user.username,
                    'action': 'start',
                }
            )
        elif msg_type == 'typing_stop' and self.project_id:
            await self.channel_layer.group_send(
                self.project_group,
                {
                    'type': 'typing_broadcast',
                    'author': user.username,
                    'action': 'stop',
                }
            )

    async def chat_clear_broadcast(self, event):
        await self.send_json({
            'type': 'clear_chat',
        })

    async def chat_broadcast(self, event):
        await self.send_json({
            'type': 'chat_message',
            'author': event.get('author'),
            'text': event.get('text'),
            'ts': event.get('ts'),
        })

    async def typing_broadcast(self, event):
        action = event.get('action', 'stop')
        await self.send_json({
            'type': 'typing_start' if action == 'start' else 'typing_stop',
            'author': event.get('author'),
        })

    async def notify(self, event):
        await self.send_json(
            {
                'type': 'notify',
                'message': event.get('message'),
                'created_at': event.get('created_at'),
            }
        )

    async def refresh(self, event):
        await self.send_json(
            {
                'type': 'refresh',
                'project_id': event.get('project_id'),
            }
        )
