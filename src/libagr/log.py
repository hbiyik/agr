'''
Created on Feb 1, 2024

@author: boogie
'''
import logging
import copy
import time
import sys

MAPPING = {'DEBUG': 37,  # white
           'INFO': 36,  # cyan
           'AGR': 32,  # green
           'WARNING': 33,  # yellow
           'ERROR': 31,  # red
           'CRITICAL': 41,  # white on red bg
           }

RESULT_LEVEL = 99
logging.addLevelName(RESULT_LEVEL, "AGR")


def result(self, message, *args, **kws):
    if self.isEnabledFor(RESULT_LEVEL):
        self._log(RESULT_LEVEL, message, args, **kws)


logging.Logger.result = result


class ColoredFormatter(logging.Formatter):

    def __init__(self, patern):
        logging.Formatter.__init__(self, patern)

    def format(self, record):
        colored_record = copy.copy(record)
        levelname = colored_record.levelname
        seq = MAPPING.get(levelname, 33)  # default white
        colored_levelname = ('{0}{1}m{2}{3}') \
            .format('\033[', seq, levelname, '\033[0m')
        colored_record.levelname = colored_levelname
        return logging.Formatter.format(self, colored_record)


logger = logging.getLogger('log')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = ColoredFormatter('%(levelname)18s | %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


def setlevel(level):
    logger.setLevel(level)
    ch.setLevel(level)


class Report:
    def __init__(self):
        self.buffer = []
        self.startime = time.time()

    def log(self, msg, info=False):
        if info:
            logger.info(msg)
        self.buffer.append(msg)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        retval = False
        if exc_type == KeyboardInterrupt:
            self.log(f"User requested cancel")
            retval = True
        deltat = time.time() - self.startime
        self.log(f"Result time: {deltat:.2f} seconds")
        for msg in self.buffer:
            logger.result(msg)
        if retval:
            sys.exit()
        return retval
