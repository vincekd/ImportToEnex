# KeepToEnex
Convert a Google Takeout zip file containing Google Keep notes in json format to a directory of Evernote Export (ENEX) XML files, suitable for import into Evernote.



# How to use

Install Python, then, run the script through the command prompt by `python keepToText.py [ZIP_FILE] --defaultTitle "Imported from Keep" --author "anonymous"`.

Checklists become bullet point lists.

Attachment files are imported, but mileage may vary. Attached image files work just fine.
