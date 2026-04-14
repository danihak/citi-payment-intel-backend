import json
from channels.generic.websocket import AsyncWebsocketConsumer


class RailUpdateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time rail health updates.
    All connected clients (ops analysts, client services, MD dashboard)
    receive the same broadcast group.

    Message types:
      rail.update     — new rail health snapshot (every 30s)
      incident.new    — new incident classified by AI
      rerouting.update — rerouting advisor output
      compliance.update — OC-215 watchdog output
      comms.ready     — communication drafts ready for approval
    """

    GROUP_NAME = 'rail_updates'

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection.established',
            'message': 'Connected to India Payment Intelligence Hub',
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data):
        """Handle messages from frontend (e.g. manual poll trigger)."""
        try:
            data = json.loads(text_data)
            if data.get('action') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except Exception:
            pass

    # Handlers for each broadcast type from agents

    async def rail_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def incident_new(self, event):
        await self.send(text_data=json.dumps(event))

    async def rerouting_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def compliance_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def comms_ready(self, event):
        await self.send(text_data=json.dumps(event))
