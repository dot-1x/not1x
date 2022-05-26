from datetime import datetime
import logging


class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;1m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    green = "\x1b[32;1m"
    format = "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


console_hndl = logging.StreamHandler()
console_hndl.setLevel(logging.DEBUG)
console_hndl.setFormatter(CustomFormatter())

file_hndl = logging.FileHandler("logs/not1x.log", "a")
file_hndl.setLevel(logging.DEBUG)
file_hndl.setFormatter(logging.Formatter("%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"))


class setlog(logging.Logger):
    def __init__(self, name: str) -> None:
        super().__init__(name, logging.DEBUG)
        super().addHandler(console_hndl)
        super().addHandler(file_hndl)


# _logger = logging.getLogger("not1x")
# _logger.setLevel(logging.DEBUG)
# create console handler with a higher log level

# _logger.addHandler(console_hndl)
# _logger.addHandler(file_hndl)
