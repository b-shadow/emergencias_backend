from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class TrackingWsManager:
    def __init__(self) -> None:
        self._order_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._solicitud_clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect_order(self, order_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._order_clients[str(order_id)].add(websocket)

    async def connect_solicitud(self, solicitud_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._solicitud_clients[str(solicitud_id)].add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        for clients in self._order_clients.values():
            clients.discard(websocket)
        for clients in self._solicitud_clients.values():
            clients.discard(websocket)

    async def broadcast(self, order_id: UUID, solicitud_id: UUID, payload: dict) -> None:
        order_key = str(order_id)
        sol_key = str(solicitud_id)
        for ws in list(self._order_clients.get(order_key, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(ws)
        for ws in list(self._solicitud_clients.get(sol_key, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(ws)


tracking_ws_manager = TrackingWsManager()
