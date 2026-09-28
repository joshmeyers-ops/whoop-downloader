"""journal_dl — parse WHOOP's manual-export journal_entries.csv.

The WHOOP developer API does NOT expose journal/behavior data (alcohol, caffeine,
etc.). That data only exists in WHOOP's manual account export
(Settings -> Account -> Export My Data), which includes journal_entries.csv.

This tool reads that manually-downloaded file and writes:
  - alcohol.csv     (date, drank y/n, # drinks, raw journal detail)
  - journal_all.csv (every journal question/answer, long format)

It is NOT an automated pull -- point it at a file you downloaded from WHOOP.
"""

__version__ = "0.1.0"
