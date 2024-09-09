import os
from reflex import constants
from reflex.utils import console

def check_first_error() -> bool:
    """Check if it's the first error and create a file if it doesn't exist.
    
    Returns:
        True if it's the first error, False otherwise.
    """
    first_error_file = os.path.join(constants.Reflex.DIR, "first_error")
    if not os.path.exists(first_error_file):
        with open(first_error_file, "w") as f:
            f.write("1")
        return True
    return False

def get_support_message() -> str:
    #if check_first_error():
    console.info("You can the command 'reflex support' to get help from the team or ask questions in our forum: forum.reflex.dev")