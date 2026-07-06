import logging
import sys
from pathlib import Path

_LOG_DIR = Path.home() / ".zefiro_split" / "logs"
_LOG_FILE = _LOG_DIR / "zefiro_split.log"

_MAX_BYTES = 2 * 1024 * 1024  # 2 MB por arquivo
_BACKUP_COUNT = 3


def setup() -> logging.Logger:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("zefiro")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Arquivo com rotação
    try:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        print(f"[ZefiroSplit] Não foi possível criar log em arquivo: {e}", file=sys.stderr)

    # Console (apenas WARNING+)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


def get() -> logging.Logger:
    return logging.getLogger("zefiro")


def log_path() -> Path:
    return _LOG_FILE
