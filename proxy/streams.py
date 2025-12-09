"""Bidirectional stream helpers."""


import asyncio
import logging


async def pipe_streams(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    label: str,
    peer_writer: asyncio.StreamWriter,
) -> None:
    """Copy bytes from reader to peer_writer until EOF or error."""
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            peer_writer.write(data)
            await peer_writer.drain()
    except Exception as exc:  # noqa: BLE001 - best-effort logging
        logging.info("Pipe %s stopped: %s", label, exc)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        try:
            peer_writer.close()
            await peer_writer.wait_closed()
        except Exception:
            pass
