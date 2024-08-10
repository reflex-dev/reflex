"""Functions to communicate to the user via console."""

import logging
from termcolor import colored
import inquirer
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from reflex.constants import LogLevel

# Set up logging
logging.basicConfig(level=logging.INFO)

# The current log level.
_LOG_LEVEL = LogLevel.INFO

# Deprecated features who's warning has been printed.
_EMITTED_DEPRECATION_WARNINGS = set()

# Info messages which have been printed.
_EMITTED_INFO = set()


def set_log_level(log_level: LogLevel):
    """Set the log level.

    Args:
        log_level: The log level to set.
    """
    global _LOG_LEVEL
    _LOG_LEVEL = log_level


def is_debug() -> bool:
    """Check if the log level is debug.

    Returns:
        True if the log level is debug.
    """
    return _LOG_LEVEL <= LogLevel.DEBUG


def debug(msg: str, **kwargs):
    """Print a debug message.

    Args:
        msg: The debug message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if is_debug():
        msg_ = colored(f"Debug: {msg}", "blue")
        logging.debug(msg_, **kwargs)


def info(msg: str, dedupe: bool = False, **kwargs):
    """Print an info message.

    Args:
        msg: The info message.
        dedupe: If True, suppress multiple console logs of info message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.INFO:
        if dedupe:
            if msg in _EMITTED_INFO:
                return
            else:
                _EMITTED_INFO.add(msg)
        logging.info(colored(f"Info: {msg}", "cyan"), **kwargs)


def success(msg: str, **kwargs):
    """Print a success message.

    Args:
        msg: The success message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.INFO:
        logging.info(colored(f"Success: {msg}", "green"), **kwargs)


def log(msg: str, **kwargs):
    """Takes a string and logs it to the console.

    Args:
        msg: The message to log.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.INFO:
        logging.info(msg, **kwargs)


def rule(title: str, **kwargs):
    """Prints a horizontal rule with a title.

    Args:
        title: The title of the rule.
        kwargs: Keyword arguments to pass to the print function.
    """
    logging.info(f"--- {title} ---", **kwargs)


def error(msg: str, **kwargs):
    """Print an error message.

    Args:
        msg: The error message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.ERROR:
        logging.error(colored(msg, "red"), **kwargs)


def ask(question: str, choices: list[str] = None, default: str = None) -> str:
    """Takes a prompt question and optionally a list of choices and returns the user input.

    Args:
        question: The question to ask the user.
        choices: A list of choices to select from.
        default: The default option selected.

    Returns:
        A string with the user input.
    """
    questions = [
        inquirer.List(
            'choice',
            message=question,
            choices=choices,
            default=default,
        ),
    ]
    answers = inquirer.prompt(questions)
    return answers['choice']


def progress(total: int, desc: str = ""):
    """Create a new progress bar.

    Args:
        total: The total number of iterations.
        desc: The description of the progress bar.

    Returns:
        A new progress bar.
    """
    with logging_redirect_tqdm():
        return tqdm(total=total, desc=desc)