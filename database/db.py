import os
import threading
import socket
import ssl

import mysql.connector
from mysql.connector import pooling


def _load_env_file():
    """Load simple KEY=VALUE pairs from .env without requiring python-dotenv."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_paths = [
        os.path.join(root_dir, ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]

    for env_path in env_paths:
        if not os.path.exists(env_path):
            continue
        try:
            with open(env_path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            continue


_load_env_file()

_POOL_LOCK = threading.Lock()
_CONNECTION_POOL = None
_POOL_WARMING = False

_ACTIVE_CONFIG = None   # "aiven" | "local" | None
_CONFIG_LOCK = threading.Lock()

# ── Status callback ───────────────────────────────────────────────────────────

_status_callback = None
_status_lock = threading.Lock()


def set_status_callback(fn):
    global _status_callback
    with _status_lock:
        _status_callback = fn


def _notify(source: str, status: str, color: str):
    with _status_lock:
        cb = _status_callback
    if cb:
        try:
            cb(source, status, color)
        except Exception:
            pass


# ── Config definitions ────────────────────────────────────────────────────────

def _ca_path():
    """Always resolves ca.pem relative to this file (database/ca.pem)."""
    return os.path.join(os.path.dirname(__file__), "ca.pem")


def _aiven_config():
    return {
        "host":               os.getenv("BAKEWISE_DB_HOST",     ""),
        "port":               int(os.getenv("BAKEWISE_DB_PORT", "22463")),
        "user":               os.getenv("BAKEWISE_DB_USER",     ""),
        "password":           os.getenv("BAKEWISE_DB_PASSWORD", ""),
        "database":           os.getenv("BAKEWISE_DB_NAME",     "defaultdb"),
        "connection_timeout": 5,
        "ssl_ca":             _ca_path(),
        "ssl_verify_cert":    True,
        "ssl_verify_identity": False,
    }


def _local_config():
    return {
        "host":               os.getenv("BAKEWISE_LOCAL_HOST",     "localhost"),
        "port":               int(os.getenv("BAKEWISE_LOCAL_PORT", "3307")),
        "user":               os.getenv("BAKEWISE_LOCAL_USER",     "root"),
        "password":           os.getenv("BAKEWISE_LOCAL_PASSWORD", ""),
        "database":           os.getenv("BAKEWISE_LOCAL_DB",       "bakewise"),
        "connection_timeout": 2,
    }


# ── Reachability probe ────────────────────────────────────────────────────────

def _is_aiven_reachable() -> bool:
    """Fast TCP probe — 2s timeout max."""
    cfg = _aiven_config()
    try:
        with socket.create_connection((cfg["host"], cfg["port"]), timeout=2):
            return True
    except OSError:
        return False


# ── Background startup probe ──────────────────────────────────────────────────

def probe_and_connect():
    global _ACTIVE_CONFIG
    _notify("Connecting...", "", "#6B7280")
    if _is_aiven_reachable():
        with _CONFIG_LOCK:
            _ACTIVE_CONFIG = "aiven"
        _warm_pool_async()
        _notify("Aiven MySQL", "Connected", "#10B981")
        print("[BakeWise] Connected to Aiven MySQL.")
    else:
        with _CONFIG_LOCK:
            _ACTIVE_CONFIG = "local"
        _warm_pool_async()
        print("[BakeWise] Aiven unreachable — using Local MySQL.")
        _notify("Local MySQL", "Connected (offline)", "#F59E0B")


def start_probe():
    threading.Thread(target=probe_and_connect, daemon=True).start()


# ── Config selection ──────────────────────────────────────────────────────────

def _db_config():
    global _ACTIVE_CONFIG

    with _CONFIG_LOCK:
        current = _ACTIVE_CONFIG

    if current == "aiven":
        return _aiven_config()
    if current == "local":
        return _local_config()

    # Not probed yet — inline probe
    if _is_aiven_reachable():
        with _CONFIG_LOCK:
            _ACTIVE_CONFIG = "aiven"
        _notify("Aiven MySQL", "Connected", "#10B981")
        return _aiven_config()
    else:
        with _CONFIG_LOCK:
            _ACTIVE_CONFIG = "local"
        print("[BakeWise] Aiven unreachable — using Local MySQL.")
        _notify("Local MySQL", "Connected (offline)", "#F59E0B")
        return _local_config()


def _reset_active_config():
    global _ACTIVE_CONFIG
    with _CONFIG_LOCK:
        _ACTIVE_CONFIG = None


def _switch_to_local():
    global _ACTIVE_CONFIG
    with _CONFIG_LOCK:
        _ACTIVE_CONFIG = "local"
    print("[BakeWise] Network interrupted — switched to Local MySQL.")
    _notify("Local MySQL", "Switched (offline)", "#F97316")


# ── Pool helpers ──────────────────────────────────────────────────────────────

def _pool_name():
    return os.getenv("BAKEWISE_DB_POOL_NAME", f"bakewise_pool_{os.getpid()}")

def _pool_size():
    return max(int(os.getenv("BAKEWISE_DB_POOL_SIZE", "8")), 1)

def _create_pool(config=None):
    cfg = config or _db_config()
    return pooling.MySQLConnectionPool(
        pool_name=_pool_name(),
        pool_size=_pool_size(),
        pool_reset_session=True,
        **cfg,
    )

def _create_direct_connection(config=None):
    cfg = config or _db_config()
    return mysql.connector.connect(**cfg)


def _warm_pool_async():
    global _CONNECTION_POOL, _POOL_WARMING
    with _POOL_LOCK:
        if _CONNECTION_POOL is not None or _POOL_WARMING:
            return
        _POOL_WARMING = True

    def builder():
        global _CONNECTION_POOL, _POOL_WARMING
        try:
            pool = _create_pool()
        except Exception:
            pool = None
        with _POOL_LOCK:
            if pool is not None and _CONNECTION_POOL is None:
                _CONNECTION_POOL = pool
            _POOL_WARMING = False

    threading.Thread(target=builder, daemon=True).start()


def _get_pool():
    global _CONNECTION_POOL
    if _CONNECTION_POOL is None:
        with _POOL_LOCK:
            if _CONNECTION_POOL is None:
                _CONNECTION_POOL = _create_pool()
    return _CONNECTION_POOL


# ── Public API ────────────────────────────────────────────────────────────────

def get_connection(prefer_direct=False):
    global _CONNECTION_POOL

    cfg = _db_config()

    if prefer_direct:
        try:
            conn = _create_direct_connection(cfg)
            _warm_pool_async()
            return conn
        except Exception:
            pass

    pool = _CONNECTION_POOL
    if pool is not None:
        try:
            return pool.get_connection()
        except Exception:
            pass

    try:
        conn = _create_direct_connection(cfg)
        _warm_pool_async()
        return conn
    except Exception:
        pass

    # All attempts failed — switch strategy
    with _CONFIG_LOCK:
        was_aiven = _ACTIVE_CONFIG == "aiven"

    if was_aiven:
        _notify("Local MySQL", "Reconnecting...", "#F97316")
        _switch_to_local()
        reset_connection_pool()
        cfg = _local_config()
    else:
        _notify("Local MySQL", "Reconnecting...", "#F97316")
        _reset_active_config()
        reset_connection_pool()
        cfg = _db_config()

    try:
        return _get_pool().get_connection()
    except Exception:
        pass

    try:
        return _create_direct_connection(cfg)
    except Exception:
        pass

    with _POOL_LOCK:
        _CONNECTION_POOL = _create_pool(cfg)
        return _CONNECTION_POOL.get_connection()


def reset_connection_pool():
    global _CONNECTION_POOL, _POOL_WARMING
    with _POOL_LOCK:
        _CONNECTION_POOL = None
        _POOL_WARMING = False
