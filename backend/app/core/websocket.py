"""WebSocket handler with JWT auth and Redis pub/sub streaming."""
from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from fastapi import WebSocket, WebSocketDisconnect, status

from app.core.security import decode_access_token

logger = structlog.get_logger(__name__)


async def _authenticate_ws(websocket: WebSocket) -> dict | None:
    """Authenticate WebSocket connection via ?token=<jwt> query param."""
    token = websocket.query_params.get("token")
    if not token:
        return None
    payload = decode_access_token(token)
    return payload


async def ws_engagement_handler(websocket: WebSocket, engagement_id: str) -> None:
    """Handle WebSocket connection for engagement streaming.

    Authenticates via JWT query param, subscribes to Redis pub/sub
    channel `engagement:{id}:stream`, and streams events to the client.

    Event types: output, progress, finding, error, done
    """
    # Authenticate
    payload = await _authenticate_ws(websocket)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    channel = f"engagement:{engagement_id}:stream"

    logger.info(
        "ws.connected",
        engagement_id=engagement_id,
        user_id=user_id,
        channel=channel,
    )

    # Try to connect to Redis pub/sub
    redis_conn = None
    pubsub = None
    try:
        from app.config import get_settings

        settings = get_settings()
        import redis.asyncio as aioredis

        redis_conn = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
        pubsub = redis_conn.pubsub()
        await pubsub.subscribe(channel)

        # Stream messages from Redis to WebSocket
        async def _stream_redis():
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                        except (json.JSONDecodeError, TypeError):
                            data = {"type": "output", "data": str(message["data"])}
                        await websocket.send_json(data)
                        if data.get("type") == "done":
                            break
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.warning("ws.redis_stream_error", error=str(e))

        # Listen for client messages (ping/pong, commands)
        async def _receive_client():
            try:
                while True:
                    data = await websocket.receive_text()
                    try:
                        msg = json.loads(data)
                    except json.JSONDecodeError:
                        msg = {"type": "text", "data": data}

                    if msg.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "engagement_id": engagement_id,
                        })
            except WebSocketDisconnect:
                pass

        # Run both tasks concurrently
        redis_task = asyncio.create_task(_stream_redis())
        client_task = asyncio.create_task(_receive_client())

        done, pending = await asyncio.wait(
            [redis_task, client_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    except ImportError:
        # Redis not available — fallback to simple echo mode for development
        logger.warning("ws.redis_unavailable", msg="Falling back to echo mode")
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({
                    "type": "echo",
                    "engagement_id": engagement_id,
                    "data": data,
                })
        except WebSocketDisconnect:
            pass
    except Exception as e:
        logger.warning("ws.redis_connect_error", error=str(e))
        # Fallback to echo mode
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({
                    "type": "echo",
                    "engagement_id": engagement_id,
                    "data": data,
                })
        except WebSocketDisconnect:
            pass
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception:
                pass
        if redis_conn:
            try:
                await redis_conn.close()
            except Exception:
                pass

        logger.info(
            "ws.disconnected",
            engagement_id=engagement_id,
            user_id=user_id,
        )


async def publish_to_engagement(
    engagement_id: str | uuid.UUID, event: dict
) -> None:
    """Publish an event to an engagement's WebSocket channel via Redis.

    Used by the orchestrator/plugins to push events to connected clients.
    """
    channel = f"engagement:{engagement_id}:stream"
    try:
        from app.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.publish(channel, json.dumps(event, default=str))
        await r.close()
    except Exception as e:
        logger.warning("ws.publish_error", channel=channel, error=str(e))
