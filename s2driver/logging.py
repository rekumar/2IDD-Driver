import epics
import logging
import os
import sys

def get_experiment_dir():
	path = "/mnt"+os.path.join(
        epics.caget("2idd:saveData_fileSystem", as_string=True).replace("micdata/data1", "micdata1"),
        epics.caget("2idd:saveData_subDir", as_string=True).split("/")[0],
)
	return path

def initialize_logbook():
    LOGBOOK_PATH = os.path.join(
        get_experiment_dir(),
        "s2driver.log",
    )
    logger = logging.Logger("s2driver Logging", level=logging.DEBUG)
    fh = logging.FileHandler(LOGBOOK_PATH)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    fh_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )
    sh_formatter = logging.Formatter(
        "%(asctime)s %(message)s",
        datefmt="%I:%M:%S",
    )
    fh.setFormatter(fh_formatter)
    sh.setFormatter(sh_formatter)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def get_logbook():
    logger = logging.Logger("s2driver Logging", level=logging.DEBUG)
    return logger
