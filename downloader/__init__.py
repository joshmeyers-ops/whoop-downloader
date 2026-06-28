"""Combined runner: pull WHOOP + Wyze data into one output folder.

Thin wrapper over whoop_dl and wyze_dl. Each source runs independently; a
failure in one (e.g. WHOOP not authenticated) does not stop the other.
"""

__version__ = "0.1.0"
