"""Entry point helpers for running the proxy servers."""


import asyncio
import logging

from config import LISTEN_HOST, MYSQL_LISTEN_PORT, PG_LISTEN_PORT
from mysql_proxy import MySQLProxyServer
from postgres_proxy import PostgresProxyServer


def create_servers() -> tuple[PostgresProxyServer, MySQLProxyServer]:
    """Instantiate protocol servers with configured listen addresses."""
    return (
        PostgresProxyServer(LISTEN_HOST, PG_LISTEN_PORT),
        MySQLProxyServer(LISTEN_HOST, MYSQL_LISTEN_PORT),
    )


async def run_multi_proxy() -> None:
    """Start both Postgres and MySQL proxies concurrently."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    pg_server, mysql_server = create_servers()
    logging.info(
        "Starting multi-proxy: Postgres on %s:%s, MySQL on %s:%s (routing by db prefix).",
        LISTEN_HOST,
        PG_LISTEN_PORT,
        LISTEN_HOST,
        MYSQL_LISTEN_PORT,
    )
    await asyncio.gather(pg_server.start(), mysql_server.start())


def main() -> None:
    try:
        asyncio.run(run_multi_proxy())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
