"""SQLite proxy placeholder.

SQLite is file-based and does not have a native network protocol to proxy. This
module exists to keep the proxy surface consistent, but raises an error if used.
"""

class SQLiteProxyServer:
    def __init__(self, *args, **kwargs) -> None:
        raise RuntimeError("SQLite proxy is not supported (SQLite is file-based).")
