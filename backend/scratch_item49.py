import contextvars
import logging

correlation_id_var = contextvars.ContextVar("correlation_id", default="-")

class CorrelationIDFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id_var.get()
        return True

# Then in the middleware:
# correlation_id_var.set(correlation_id)
