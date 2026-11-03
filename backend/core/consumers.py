import json
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_from_scope(scope):
    """Resolve authenticated user from scope session, query string token, or auth header."""
    user = scope.get('user')
    if user and user.is_authenticated:
        return user

    # Try query string ?token=<jwt>
    query_string = scope.get('query_string', b'').decode('utf-8')
    params = parse_qs(query_string)
    token_list = params.get('token')
    if token_list:
        try:
            token = token_list[0]
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')
            from .models import User
            return User.objects.get(id=user_id)
        except Exception:
            return AnonymousUser()

    # Try Authorization header: Bearer <jwt>
    headers = dict(scope.get('headers', []))
    auth_header = headers.get(b'authorization', b'').decode('utf-8')
    if auth_header.startswith('Bearer '):
        try:
            token = auth_header.split(' ')[1]
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')
            from .models import User
            return User.objects.get(id=user_id)
        except Exception:
            return AnonymousUser()

    return AnonymousUser()


def check_chat_access_sync(user, request_id):
    """
    Verify society membership and participation for accessing a request's chat.
    Returns True if allowed, False otherwise.
    """
    from .models import ServiceRequest, Membership
    try:
        req = ServiceRequest.objects.select_related('society').get(id=request_id)
    except Exception:
        return False

    if user.role == 'DIRECTOR':
        return True

    if user.role == 'WORKER':
        return req.assignments.filter(worker__user=user).exists()

    # User must have an active membership in the request's society
    has_membership = Membership.objects.filter(
        user=user, society=req.society, is_active=True
    ).exists()
    if not has_membership:
        return False

    # Participants allowed: Reporter, Chairman, or Supervisor of this society
    is_reporter = str(req.reporter_id) == str(user.id)
    is_ops = Membership.objects.filter(
        user=user, society=req.society, role__in=('CHAIRMAN', 'SUPERVISOR'), is_active=True
    ).exists()
    return is_reporter or is_ops


check_chat_access = database_sync_to_async(check_chat_access_sync)


def check_location_access_sync(user, worker_id):
    """
    Verify permission to access a worker's live location stream.
    Workers can only track themselves; Ops and Clients can only track assigned workers.
    """
    from .models import WorkerProfile, Assignment, Membership
    try:
        worker = WorkerProfile.objects.get(id=worker_id)
    except Exception:
        return False

    if user.role == 'DIRECTOR':
        return True

    if user.role == 'WORKER':
        return str(worker.user_id) == str(user.id)

    user_society_ids = list(Membership.objects.filter(
        user=user, is_active=True
    ).values_list('society_id', flat=True))

    if not user_society_ids:
        return False

    if user.role == 'SUPERVISOR':
        return Assignment.objects.filter(
            worker=worker,
            request__society__in=user_society_ids
        ).exists()

    if user.role in ('MEMBER', 'CHAIRMAN'):
        return Assignment.objects.filter(
            worker=worker,
            request__reporter=user,
            request__society__in=user_society_ids
        ).exists()

    return False


check_location_access = database_sync_to_async(check_location_access_sync)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = await get_user_from_scope(self.scope)
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.room_name = self.scope['url_route']['kwargs']['request_id']
        can_access = await check_chat_access(user, self.room_name)
        if not can_access:
            await self.close(code=4403)
            return

        self.room_group_name = f'chat_{self.room_name}'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        user = await get_user_from_scope(self.scope)
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        text_data_json = json.loads(text_data)
        message = text_data_json.get('message', '')
        sender = user.username

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender': sender
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))


class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = await get_user_from_scope(self.scope)
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.worker_id = self.scope['url_route']['kwargs']['worker_id']
        can_access = await check_location_access(user, self.worker_id)
        if not can_access:
            await self.close(code=4403)
            return

        self.group_name = f'location_{self.worker_id}'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        user = await get_user_from_scope(self.scope)
        # Only the worker themselves can broadcast live location updates
        if not user or user.role != 'WORKER':
            return

        data = json.loads(text_data)
        lat = data.get('lat')
        lng = data.get('lng')

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'location_update',
                'lat': lat,
                'lng': lng
            }
        )

    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            'lat': event['lat'],
            'lng': event['lng']
        }))
