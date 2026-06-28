"""wyze_dl — standalone Wyze Scale data downloader.

Pulls body-composition history (weight, body fat %, lean mass, etc.) from the
Wyze cloud via the unofficial wyze-sdk and writes a CSV. This is the data that
flows Wyze Scale -> Wyze cloud -> Health Connect -> WHOOP; WHOOP's own API does
not expose it, so we go to the source.
"""

__version__ = "0.1.0"
