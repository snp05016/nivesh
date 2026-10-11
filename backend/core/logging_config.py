"""
Task 57: Structured logging via structlog.
Import and call configure_logging() at app startup (main.py).
Usage in any module:
    import structlog
    logger = structlog.get_logger()
    logger.info("event", ticker="RELIANCE", score=88)
"""
import logging
import os


def configure_logging() -> None:
    """Set up structlog with JSON rendering in production, console in dev."""
    try:
        import structlog

        shared_processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
        ]

        from core.config_guard import is_production
        if is_production():
            # JSONRenderer can't serialise exc_info, so render tracebacks to text first.
            # ConsoleRenderer renders exceptions itself and warns if this is present.
            shared_processors.append(structlog.processors.format_exc_info)
            renderer = structlog.processors.JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer()

        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
        root_logger.setLevel(level)

    except ImportError:
        # structlog not installed — fall back to stdlib logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )


def get_logger(name: str = "nivesh"):
    """Return a structlog logger, falling back to stdlib if structlog absent."""
    try:
        import structlog
        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)
