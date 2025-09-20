

import functools
import time
import traceback


from qgis.core import Qgis, QgsMessageLog


PLUGIN = 'Lizmap'
PROFILE = False


def info(message: str):
    QgsMessageLog.logMessage(str(message), PLUGIN, Qgis.MessageLevel.Info)


def warning(message: str):
    QgsMessageLog.logMessage(str(message), PLUGIN, Qgis.MessageLevel.Warning)


def critical(message: str):
    QgsMessageLog.logMessage(str(message), PLUGIN, Qgis.MessageLevel.Critical)


def log_exception(e: BaseException):
    """ Log a Python exception. """
    critical(
        "Critical exception:\n{e}\n{traceback}".format(
            e=e,
            traceback=traceback.format_exc(),
        ),
    )


def profiling(func):
    """ Decorator to make some profiling. """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if PROFILE:
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            info(f"{func.__name__} ran in {round(end - start, 2)}s")
            return result
        else:
            return func(*args, **kwargs)

    return wrapper
