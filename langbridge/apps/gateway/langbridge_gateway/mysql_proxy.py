"""MySQL proxy implementation."""


import asyncio
import logging
import secrets
import struct
from typing import Dict, Optional, Tuple

from .routing import UpstreamTarget, route_database
from .streams import pipe_streams


# MySQL constants (subset for this proxy).
CLIENT_LONG_PASSWORD = 0x00000001
CLIENT_LONG_FLAG = 0x00000004
CLIENT_CONNECT_WITH_DB = 0x00000008
CLIENT_PROTOCOL_41 = 0x00000200
CLIENT_SECURE_CONNECTION = 0x00008000
CLIENT_PLUGIN_AUTH = 0x00080000
CLIENT_CONNECT_ATTRS = 0x00100000
CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA = 0x00200000
CLIENT_DEPRECATE_EOF = 0x01000000

# Conservative capability set we advertise to clients.
SERVER_CAPABILITIES = (
    CLIENT_LONG_PASSWORD
    | CLIENT_LONG_FLAG
    | CLIENT_CONNECT_WITH_DB
    | CLIENT_PROTOCOL_41
    | CLIENT_SECURE_CONNECTION
    | CLIENT_PLUGIN_AUTH
    | CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA
    | CLIENT_CONNECT_ATTRS
    | CLIENT_DEPRECATE_EOF
)


def _read_lenenc_int(data: bytes, offset: int) -> Tuple[int, int]:
    first = data[offset]
    if first < 0xFB:
        return first, offset + 1
    if first == 0xFC:
        return struct.unpack_from("<H", data, offset + 1)[0], offset + 3
    if first == 0xFD:
        val = struct.unpack_from("<I", data, offset + 1)[0]
        return val & 0xFFFFFF, offset + 4
    if first == 0xFE:
        return struct.unpack_from("<Q", data, offset + 1)[0], offset + 9
    raise ValueError("Invalid length-encoded integer")


def _encode_lenenc_int(value: int) -> bytes:
    if value < 0xFB:
        return struct.pack("B", value)
    if value <= 0xFFFF:
        return b"\xFC" + struct.pack("<H", value)
    if value <= 0xFFFFFF:
        return b"\xFD" + struct.pack("<I", value)[0:3]
    return b"\xFE" + struct.pack("<Q", value)


def _read_null_terminated(data: bytes, offset: int) -> Tuple[bytes, int]:
    end = data.find(b"\x00", offset)
    if end == -1:
        raise ValueError("Null terminator not found")
    return data[offset:end], end + 1


def _build_mysql_packet(payload: bytes, sequence_id: int) -> bytes:
    return struct.pack("<I", len(payload) | (sequence_id << 24))[:3] + bytes([sequence_id]) + payload


async def _read_mysql_packet(reader: asyncio.StreamReader) -> Tuple[bytes, int]:
    header = await reader.readexactly(4)
    length = header[0] | (header[1] << 8) | (header[2] << 16)
    seq = header[3]
    payload = await reader.readexactly(length)
    return payload, seq


def _build_handshake_packet(auth_data: bytes, connection_id: int = 1234) -> bytes:
    """
    Build a simple handshake v10 packet we send to clients.

    We generate our own salt so we can parse the client's handshake response
    before routing.
    """
    part1 = auth_data[:8]
    part2 = auth_data[8:20]
    payload = bytearray()
    payload.append(10)  # protocol version
    payload.extend(b"mysql-proxy-0.1\x00")
    payload.extend(struct.pack("<I", connection_id))
    payload.extend(part1)
    payload.append(0)
    payload.extend(struct.pack("<H", SERVER_CAPABILITIES & 0xFFFF))
    payload.append(33)  # utf8_general_ci
    payload.extend(struct.pack("<H", 0))  # status flags
    payload.extend(struct.pack("<H", (SERVER_CAPABILITIES >> 16) & 0xFFFF))
    payload.append(len(auth_data))
    payload.extend(b"\x00" * 10)
    payload.extend(part2)
    payload.append(0)
    payload.extend(b"mysql_native_password\x00")
    return bytes(payload)


def _parse_handshake_response(payload: bytes) -> Dict[str, object]:
    """
    Parse HandshakeResponse41 from the client to extract database and user.

    The database is present only when CLIENT_CONNECT_WITH_DB is set, which we
    encourage by advertising that capability.
    """
    offset = 0
    capability_flags = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    max_packet = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    charset = payload[offset]
    offset += 1
    offset += 23  # reserved

    username_bytes, offset = _read_null_terminated(payload, offset)
    username = username_bytes.decode(errors="ignore")

    if capability_flags & CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA:
        auth_len, offset = _read_lenenc_int(payload, offset)
        auth_response = payload[offset : offset + auth_len]
        offset += auth_len
    elif capability_flags & CLIENT_SECURE_CONNECTION:
        auth_len = payload[offset]
        offset += 1
        auth_response = payload[offset : offset + auth_len]
        offset += auth_len
    else:
        auth_response_bytes, offset = _read_null_terminated(payload, offset)
        auth_response = auth_response_bytes

    database = ""
    if capability_flags & CLIENT_CONNECT_WITH_DB:
        db_bytes, offset = _read_null_terminated(payload, offset)
        database = db_bytes.decode(errors="ignore")

    plugin_name = "mysql_native_password"
    if capability_flags & CLIENT_PLUGIN_AUTH:
        plugin_bytes, offset = _read_null_terminated(payload, offset)
        if plugin_bytes:
            plugin_name = plugin_bytes.decode(errors="ignore")

    attrs: Optional[bytes] = None
    if capability_flags & CLIENT_CONNECT_ATTRS:
        attr_len, offset = _read_lenenc_int(payload, offset)
        attrs = payload[offset : offset + attr_len]

    return {
        "capability_flags": capability_flags,
        "max_packet": max_packet,
        "charset": charset,
        "username": username,
        "database": database,
        "auth_response": auth_response,
        "plugin_name": plugin_name,
        "attrs": attrs,
    }


def _parse_upstream_handshake(payload: bytes) -> Dict[str, object]:
    """Extract auth salt, plugin, and capabilities from upstream handshake."""
    offset = 0
    protocol_version = payload[offset]
    if protocol_version != 10:
        raise ValueError(f"Unsupported MySQL protocol version {protocol_version}")
    offset += 1
    _, offset = _read_null_terminated(payload, offset)  # server version
    offset += 4  # connection id
    auth_part1 = payload[offset : offset + 8]
    offset += 8
    offset += 1  # filler
    cap_lower = struct.unpack_from("<H", payload, offset)[0]
    offset += 2
    charset = payload[offset]
    offset += 1
    status_flags = struct.unpack_from("<H", payload, offset)[0]
    offset += 2
    cap_upper = struct.unpack_from("<H", payload, offset)[0]
    offset += 2
    capability_flags = cap_lower | (cap_upper << 16)
    auth_plugin_data_len = payload[offset] if capability_flags & CLIENT_PLUGIN_AUTH else 0
    offset += 1
    offset += 10  # reserved
    remaining = payload[offset:]

    part2_len = max(13, auth_plugin_data_len - 8) if auth_plugin_data_len else 12
    auth_part2 = remaining[:part2_len]
    auth_data = auth_part1 + auth_part2
    plugin_name = "mysql_native_password"
    plugin_offset = part2_len
    if capability_flags & CLIENT_PLUGIN_AUTH and plugin_offset < len(remaining):
        plugin_bytes, _ = _read_null_terminated(remaining, plugin_offset + offset - offset)
        if plugin_bytes:
            plugin_name = plugin_bytes.decode(errors="ignore")

    return {
        "capability_flags": capability_flags,
        "charset": charset,
        "status_flags": status_flags,
        "auth_data": auth_data,
        "plugin_name": plugin_name,
    }


def _build_auth_switch_request(plugin_name: str, auth_data: bytes) -> bytes:
    """Request the client to re-send auth data using the upstream salt/plugin."""
    return b"\xFE" + plugin_name.encode() + b"\x00" + auth_data


def _build_handshake_response(
    client_info: Dict[str, object],
    auth_response: bytes,
    capability_flags: int,
    plugin_name: str,
) -> bytes:
    """Reconstruct a HandshakeResponse41 using the client's details."""
    parts = [
        struct.pack("<I", capability_flags),
        struct.pack("<I", int(client_info["max_packet"])),
        struct.pack("B", int(client_info["charset"])),
        b"\x00" * 23,
        client_info["username"].encode() + b"\x00",
    ]

    if capability_flags & CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA:
        parts.append(_encode_lenenc_int(len(auth_response)))
        parts.append(auth_response)
    elif capability_flags & CLIENT_SECURE_CONNECTION:
        parts.append(struct.pack("B", len(auth_response)))
        parts.append(auth_response)
    else:
        parts.append(auth_response + b"\x00")

    if capability_flags & CLIENT_CONNECT_WITH_DB:
        parts.append(client_info["database"].encode() + b"\x00")

    if capability_flags & CLIENT_PLUGIN_AUTH:
        parts.append(plugin_name.encode() + b"\x00")

    if capability_flags & CLIENT_CONNECT_ATTRS:
        attrs = client_info.get("attrs") or b""
        parts.append(_encode_lenenc_int(len(attrs)))
        parts.append(attrs)

    payload = b"".join(parts)
    return _build_mysql_packet(payload, sequence_id=1)


def _build_mysql_error(message: str, sequence_id: int) -> bytes:
    """Minimal ERR_Packet."""
    payload = bytearray()
    payload.append(0xFF)
    payload.extend(struct.pack("<H", 1049))  # ER_BAD_DB_ERROR (placeholder)
    payload.append(ord("#"))
    payload.extend(b"08S01")
    payload.extend(message.encode())
    return _build_mysql_packet(bytes(payload), sequence_id)


def _parse_mysql_error(payload: bytes) -> str:
    """
    Decode a minimal ERR_Packet for logging purposes.
    """
    try:
        # payload[0] is 0xFF
        code = struct.unpack_from("<H", payload, 1)[0]
        sql_state_marker = chr(payload[3])
        sql_state = payload[4:9].decode(errors="ignore")
        msg = payload[9:].decode(errors="ignore")
        return f"ERR code={code} state={sql_state_marker}{sql_state} msg={msg}"
    except Exception:
        return f"ERR raw={payload!r}"


class MySQLProxyServer:
    """Minimal MySQL proxy that peeks at login to choose an upstream."""

    def __init__(self, listen_host: str, listen_port: int) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port

    async def start(self) -> None:
        server = await asyncio.start_server(
            self._handle_client, host=self.listen_host, port=self.listen_port
        )
        logging.info("MySQL proxy listening on %s:%s", self.listen_host, self.listen_port)
        async with server:
            await server.serve_forever()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        logging.info("MySQL client connected: %s", peer)
        try:
            initial_salt = secrets.token_bytes(20)
            handshake_payload = _build_handshake_packet(initial_salt)
            writer.write(_build_mysql_packet(handshake_payload, sequence_id=0))
            await writer.drain()

            client_payload, client_seq = await _read_mysql_packet(reader)
            client_info = _parse_handshake_response(client_payload)
            db_name = client_info.get("database") or ""
            username = str(client_info.get("username") or "")
            if not db_name and not username:
                writer.write(
                    _build_mysql_error(
                        "database or tenant identity in user is required for routing",
                        client_seq + 1,
                    )
                )
                await writer.drain()
                return

            try:
                upstream = route_database(db_name, "mysql", user_name=username)
            except ValueError as exc:
                writer.write(_build_mysql_error(str(exc), client_seq + 1))
                await writer.drain()
                return

            logging.info(
                "Routing MySQL connection db=%s user=%s to %s:%s",
                db_name,
                username,
                upstream.host,
                upstream.port,
            )

            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream.host, upstream.port
            )
            upstream_handshake_payload, _ = await _read_mysql_packet(upstream_reader)
            upstream_info = _parse_upstream_handshake(upstream_handshake_payload)
            # Override database presented upstream if configured.
            target_db = upstream.database or ""
            if target_db:
                client_info["database"] = target_db

            # Ask the client to send auth for the upstream salt/plugin so we can reuse it.
            auth_switch_payload = _build_auth_switch_request(
                upstream_info["plugin_name"], upstream_info["auth_data"]
            )
            writer.write(_build_mysql_packet(auth_switch_payload, sequence_id=client_seq + 1))
            await writer.drain()

            auth_switch_response, auth_resp_seq = await _read_mysql_packet(reader)

            capability_flags = (
                int(client_info["capability_flags"]) & int(upstream_info["capability_flags"])
            )

            handshake_response = _build_handshake_response(
                client_info,
                auth_switch_response,
                capability_flags=capability_flags,
                plugin_name=upstream_info["plugin_name"],
            )
            upstream_writer.write(handshake_response)
            await upstream_writer.drain()

            upstream_reply, _ = await _read_mysql_packet(upstream_reader)
            if upstream_reply and upstream_reply[0] == 0xFF:
                logging.error(
                    "Upstream MySQL returned error after auth: %s",
                    _parse_mysql_error(upstream_reply),
                )
            # Align sequence id for the client side handshake completion.
            writer.write(_build_mysql_packet(upstream_reply, sequence_id=auth_resp_seq + 1))
            await writer.drain()

            client_to_server = asyncio.create_task(
                pipe_streams(reader, writer, "mysql client->server", upstream_writer)
            )
            server_to_client = asyncio.create_task(
                pipe_streams(upstream_reader, upstream_writer, "mysql server->client", writer)
            )
            await asyncio.wait({client_to_server, server_to_client}, return_when=asyncio.FIRST_COMPLETED)
        except Exception as exc:  # noqa: BLE001
            logging.exception("MySQL proxy error: %s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logging.info("MySQL client disconnected: %s", peer)
