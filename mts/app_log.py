import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from .constants import APP_LOG_FILE

logger = logging.getLogger(__name__)


def setup():
    """Writes everything logged - the Logs window's events, plus warnings and uncaught
    exceptions from any thread - to app_log.txt. The built exe has no console, so
    without this, errors go nowhere."""
    try:
        handler = RotatingFileHandler(APP_LOG_FILE, maxBytes=1_000_000, backupCount=1, encoding="utf-8")
    except OSError:
        return  # e.g. a read-only folder: carry on without a log file
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # The original hooks still run, so a console (when running from source) keeps its tracebacks.
    original_excepthook = sys.excepthook

    def excepthook(exc_type, exc_value, exc_traceback):
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        original_excepthook(exc_type, exc_value, exc_traceback)

    original_thread_excepthook = threading.excepthook

    def thread_excepthook(args):
        name = args.thread.name if args.thread else "unknown"
        logger.error("Uncaught exception in thread %s", name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        original_thread_excepthook(args)

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook


def log_tk_errors(root):
    """Exceptions in Tk callbacks (button commands, after() jobs, ...) bypass
    sys.excepthook, so route them to the log too."""
    original = root.report_callback_exception

    def report(exc_type, exc_value, exc_traceback):
        logger.error("Uncaught exception in Tk callback", exc_info=(exc_type, exc_value, exc_traceback))
        original(exc_type, exc_value, exc_traceback)

    root.report_callback_exception = report
