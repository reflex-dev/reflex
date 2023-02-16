"""Anonymous telemetry for Pynecone."""

import multiprocessing
import platform
import json
import psutil

from pynecone import constants
from pynecone.base import Base
import requests
from datetime import datetime


def get_os():
    """Get the operating system."""
    return platform.system()

def get_python_version():
    """Get the Python version."""
    return platform.python_version()

def get_pynecone_version():
    """Get the Pynecone version."""
    return constants.VERSION

def get_cpu_count():
    """Get the number of CPUs."""
    return multiprocessing.cpu_count()

def get_memory():
    """Get the total memory in MB."""
    return psutil.virtual_memory().total >> 20

class Telemetry(Base):
    """Anonymous telemetry for Pynecone."""

    user_os: str = get_os()
    cpu_count: int = get_cpu_count()
    memory: int =  get_memory()
    pynecone_version: str = get_pynecone_version()
    python_version: str = get_python_version()
    
def pynecone_telemetry(event, telemetry_enabled):
    """Post to PostHog."""
    try:
        if telemetry_enabled:
            telemetry = Telemetry()
            with open(constants.PCVERSION_APP_FILE) as f:  # type: ignore
                pynecone_json = json.load(f)
                distinct_id = pynecone_json["project_hash"] 
            post_hog  = {
                "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
                "event": event,
                "properties": {
                    "distinct_id": distinct_id,
                    "user_os": telemetry.user_os,
                    "pynecone_version": telemetry.pynecone_version,
                    "python_version": telemetry.python_version,
                    "cpu_count": telemetry.cpu_count,
                    "memory": telemetry.memory
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            requests.post('https://app.posthog.com/capture/', json = post_hog)
    except Exception:
        pass
