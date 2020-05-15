
import logging
import logging.handlers
import os
import sys

def build_logger(handler=None, level='WARNING', name=None):
    """Instantiate a logger with an optional handler."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if handler:
        logger.addHandler(handler)
    return logger

def get_rotating_handler(logfile, **kwargs):
    """Validate logfile path and return a RotatingFileHandler.
    
    Arguments:
        logfile: Path to file
        kwargs: As specified for RotatingFileHandler.

    Returns: A file handler
    """
    logdir = os.path.dirname(logfile)
    if not os.path.exists(logdir):
        os.mkdir(logdir)
    handler = logging.handlers.RotatingFileHandler(logfile, **kwargs)
    handler.setFormatter(
            logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s'))
    return handler

def get_stream_handler(stream=sys.stderr):
    return logging.StreamHandler(stream)
        
def signal_handler(*args):
    print('KeyboardInterrupt: Writing logs before exiting...')
    logging.shutdown()
    os._exit(0)
