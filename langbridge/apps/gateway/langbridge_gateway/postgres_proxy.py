"""Postgres proxy implementation."""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Dict, Optional, Tuple

from .routing import UpstreamTarget, route_database
from .streams import pipe_streams


class PostgresProxyServer:
    """Very small Postgres proxy that routes on startup packet database name."""

    SSL_REQUEST_CODE = 80877103

    def __init__(self, listen_host: str, listen_port: int) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port

    async def start(self) -> None:
        server = await asyncio.start_server(
            self._handle_client, host=self.listen_host, port=self.listen_port
        )
        logging.info("Postgres proxy listening on %s:%s", self.listen_host, self.listen_port)
        async with server:
            await server.serve_forever()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        logging.info("Postgres client connected: %s", peer)
        try:
            startup = await self._read_startup_message(reader, writer)
            if startup is None:
                return
            params, raw_packet, version = startup
            db_name = params.get("database") or params.get("dbname")
            user = params.get("user")
            if not db_name and not user:
                await self._send_pg_error(
                    writer,
                    "database or tenant identity in user is required for routing",
                )
                return

            upstream = route_database(db_name or "", "postgres", user_name=user)
            logging.info(
                "Routing Postgres connection db=%s user=%s to %s:%s",
                db_name,
                user,
                upstream.host,
                upstream.port,
            )

            forward_packet = raw_packet
            if upstream.database:
                params["database"] = upstream.database
                forward_packet = _build_startup_packet(params, version)

            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream.host, upstream.port
            )
            upstream_writer.write(forward_packet)
            await upstream_writer.drain()

            client_to_server = asyncio.create_task(
                pipe_streams(reader, writer, "pg client->server", upstream_writer)
            )
            server_to_client = asyncio.create_task(
                pipe_streams(upstream_reader, upstream_writer, "pg server->client", writer)
            )
            await asyncio.wait({client_to_server, server_to_client}, return_when=asyncio.FIRST_COMPLETED)
        except Exception as exc:  # noqa: BLE001
            logging.exception("Postgres proxy error: %s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logging.info("Postgres client disconnected: %s", peer)

    async def _read_startup_message(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> Optional[Tuple[Dict[str, str], bytes, int]]:
        """
        Read and parse the Postgres startup message.

        The startup payload begins with protocol version followed by
        key/value parameters as null-terminated strings, terminated by an
        extra null byte. We reply 'N' to SSL requests and continue.
        """
        while True:
            len_bytes = await reader.readexactly(4)
            length = struct.unpack("!I", len_bytes)[0]
            payload = await reader.readexactly(length - 4)
            version = struct.unpack("!I", payload[:4])[0]
            if version == self.SSL_REQUEST_CODE:
                writer.write(b"N")
                await writer.drain()
                continue

            params: Dict[str, str] = {}
            parts = payload[4:].split(b"\x00")
            for i in range(0, len(parts) - 1, 2):
                if not parts[i]:
                    break
                key = parts[i].decode(errors="ignore")
                val = parts[i + 1].decode(errors="ignore") if i + 1 < len(parts) else ""
                params[key] = val
            raw_packet = len_bytes + payload
            return params, raw_packet, version

    async def _send_pg_error(self, writer: asyncio.StreamWriter, message: str) -> None:
        """Send a minimal Postgres ErrorResponse and close."""
        fields = b"SERROR\x00CXX000\x00M" + message.encode() + b"\x00\x00"
        packet = b"E" + struct.pack("!I", len(fields) + 4) + fields
        writer.write(packet)
        await writer.drain()


def _build_startup_packet(params: Dict[str, str], version: int) -> bytes:
    """Rebuild a Postgres startup packet with updated parameters."""
    payload_parts = [struct.pack("!I", version)]
    for key, val in params.items():
        payload_parts.append(key.encode())
        payload_parts.append(b"\x00")
        payload_parts.append(val.encode())
        payload_parts.append(b"\x00")
    payload_parts.append(b"\x00")
    payload = b"".join(payload_parts)
    length = len(payload) + 4
    return struct.pack("!I", length) + payload
