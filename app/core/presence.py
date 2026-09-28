from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class TripPresenceManager:
    """여행별 현재 접속 사용자와 WebSocket 연결을 메모리에서 관리한다."""

    def __init__(self) -> None:
        self._connections: dict[int, dict[int, set[WebSocket]]] = defaultdict(
            lambda: defaultdict(set)
        )
        self._users: dict[int, dict[int, dict[str, object]]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(
        self,
        trip_id: int,
        user_id: int,
        display_name: str,
        websocket: WebSocket,
    ) -> None:
        """연결을 수락하고 접속자 목록을 전체에게 알린다."""
        await websocket.accept()

        async with self._lock:
            self._connections[trip_id][user_id].add(websocket)
            self._users[trip_id][user_id] = {
                "id": user_id,
                "display_name": display_name,
            }

        await self.broadcast_presence(trip_id)

    async def disconnect(
        self,
        trip_id: int,
        user_id: int,
        websocket: WebSocket,
    ) -> None:
        """연결을 제거하고, 마지막 탭이 닫힌 사용자만 접속자 목록에서 제거한다."""
        async with self._lock:
            trip_connections = self._connections.get(trip_id)
            if trip_connections is None:
                return

            user_connections = trip_connections.get(user_id)
            if user_connections is not None:
                user_connections.discard(websocket)

                if not user_connections:
                    trip_connections.pop(user_id, None)
                    self._users[trip_id].pop(user_id, None)

            if not trip_connections:
                self._connections.pop(trip_id, None)
                self._users.pop(trip_id, None)

        await self.broadcast_presence(trip_id)

    async def broadcast_presence(self, trip_id: int) -> None:
        """같은 여행을 보고 있는 모든 브라우저에 현재 접속자 목록을 전송한다."""
        async with self._lock:
            users = list(self._users.get(trip_id, {}).values())
            sockets = [
                websocket
                for user_connections in self._connections.get(trip_id, {}).values()
                for websocket in user_connections
            ]

        message = {
            "type": "presence",
            "users": users,
        }

        disconnected_sockets: list[WebSocket] = []

        for websocket in sockets:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected_sockets.append(websocket)

        for websocket in disconnected_sockets:
            await self._remove_dead_socket(trip_id, websocket)

    async def _remove_dead_socket(self, trip_id: int, websocket: WebSocket) -> None:
        """네트워크 오류 등으로 끊긴 소켓을 내부 목록에서 제거한다."""
        async with self._lock:
            trip_connections = self._connections.get(trip_id)
            if trip_connections is None:
                return

            for user_id, user_connections in list(trip_connections.items()):
                if websocket not in user_connections:
                    continue

                user_connections.discard(websocket)

                if not user_connections:
                    trip_connections.pop(user_id, None)
                    self._users[trip_id].pop(user_id, None)

                break

            if not trip_connections:
                self._connections.pop(trip_id, None)
                self._users.pop(trip_id, None)


presence_manager = TripPresenceManager()