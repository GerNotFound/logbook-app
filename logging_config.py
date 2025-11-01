from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        if record.exc_info:
            log_record['exc_info'] = super().formatException(record.exc_info)

        return json.dumps(log_record, ensure_ascii=False)


def setup_logging(level_name: str) -> None:
    """Configure root logger to emit JSON to stdout."""

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

    level = getattr(logging, level_name.upper(), logging.INFO)
    root_logger.setLevel(level)