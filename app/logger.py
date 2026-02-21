"""
app/logger.py — Structured JSON logging using structlog.
Falls back to stdlib logging if structlog is unavailable.
"""


import logging
import structlog


def get_logger(name: str):
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )

    return structlog.get_logger(name)

# import logging
# import os
# import sys


# def get_logger(name: str):
#     try:
#         import structlog

#         structlog.configure(
#             processors=[
#                 structlog.contextvars.merge_contextvars,
#                 structlog.stdlib.add_log_level,
#                 structlog.stdlib.add_logger_name,
#                 structlog.processors.TimeStamper(fmt="iso"),
#                 structlog.processors.StackInfoRenderer(),
#                 structlog.processors.format_exc_info,
#                 structlog.processors.JSONRenderer(),
#             ],
#             wrapper_class=structlog.make_filtering_bound_logger(
#                 getattr(logging, os.getenv("LOG_LEVEL", "INFO"))
#             ),
#             logger_factory=structlog.PrintLoggerFactory(sys.stdout),
#             cache_logger_on_first_use=True,
#         )
#         return structlog.get_logger(name)
#     except ImportError:
#         logging.basicConfig(
#             stream=sys.stdout,
#             level=os.getenv("LOG_LEVEL", "INFO"),
#             format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}',
#         )
#         return logging.getLogger(name)
