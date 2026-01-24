"""SQL Server (TDS) proxy implementation."""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Dict, Optional, Tuple

from routing import route_database
from streams import pipe_streams


async def _read_tds_header(reader: asyncio.StreamReader) -> Tuple[int, int, bytes]:
    """Read TDS packet header and return (packet_type, packet_length, header_bytes)."""
    header = await reader.readexactly(8)
    packet_type = header[0]
    length = struct.unpack("!H", header[2:4])[0]
    return packet_type, length, header


def _parse_login_database(payload: bytes) -> Optional[str]:
    """
    Parse the database name from a TDS Login7 payload.
    Offsets are relative to the start of the Login7 packet (after header).
    """
    try:
        # Database length and offset are at bytes 68-69 (length) and 70-71 (offset) for Login7
        db_len = struct.unpack_from("<H", payload, 68)[0]
        db_off = struct.unpack_from("<H", payload, 70)[0]
        if db_len == 0:
            return None
        start = db_off
        end = start + db_len * 2  # UCS-2 chars
        raw = payload[start:end]
        return raw.decode("utf-16le", errors="ignore")
    except Exception:
        return None


class SqlServerProxyServer:
    """Minimal SQL Server proxy that routes on Login7 database name."""

    def __init__(self, listen_host: str, listen_port: int) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port

    async def start(self) -> None:
        server = await asyncio.start_server(
            self._handle_client, host=self.listen_host, port=self.listen_port
        )
        logging.info("SQL Server proxy listening on %s:%s", self.listen_host, self.listen_port)
        async with server:
            await server.serve_forever()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        logging.info("SQL Server client connected: %s", peer)
        try:
            packet_type, length, header = await _read_tds_header(reader)
            # Consume rest of packet
            payload = await reader.readexactly(length - 8)
            if packet_type != 0x10:  # Login7
                logging.error("Unexpected TDS packet type %s; closing", packet_type)
                writer.close()
                await writer.wait_closed()
                return

            db_name = _parse_login_database(payload) or ""
            upstream = route_database(db_name, "sqlserver")
            logging.info(
                "Routing SQL Server connection db=%s to %s:%s",
                db_name,
                upstream.host,
                upstream.port,
            )

            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream.host, upstream.port
            )
            # Forward the original packet upstream.
            upstream_writer.write(header + payload)
            await upstream_writer.drain()

            client_to_server = asyncio.create_task(
                pipe_streams(reader, writer, "tds client->server", upstream_writer)
            )
            server_to_client = asyncio.create_task(
                pipe_streams(upstream_reader, upstream_writer, "tds server->client", writer)
            )
            await asyncio.wait({client_to_server, server_to_client}, return_when=asyncio.FIRST_COMPLETED)
        except Exception as exc:
            logging.exception("SQL Server proxy error: %s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logging.info("SQL Server client disconnected: %s", peer)
