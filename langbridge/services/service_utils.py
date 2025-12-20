
import contextvars


def internal_service():
    # indicates to service that this can be a internal service call
    # this will bypass certain authorization checks
    # set internal flag in context vars
    contextvars.ContextVar("internal_service").set(True)
    yield
    contextvars.ContextVar("internal_service").set(False)