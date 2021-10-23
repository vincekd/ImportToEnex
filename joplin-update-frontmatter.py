#!/usr/bin/python3

##
# joplin-update-frontmatter.py
#
# When Joplin exports files as MD (for use in Obsidian) it does not include Tags
# Obsidian stores Tags in a block at the front of the MD files called FrontMatter (https://help.obsidian.md/Advanced+topics/YAML+front+matter)
# This script is designed to create a YAML FrontMatter block, within each Joplin note, so that on export Obsidian notes will have Tags
# Additional fields can be added to the FrontMatter, but Obsidian only recognizes "aliases", "tags", and "cssclass"
#

## Joplin API Documentation (https://joplinapp.org/api/references/rest_api/):
# curl http://localhost:41184/notes?token=YOURBIGTOKEN
# Get a specific note body, created times, updated times:
#   curl "http://localhost:41184/notes/NOTEID/?fields=body,created_time,user_created_time,updated_time,user_updated_time&token=YOURBIGTOKEN"
# Get a specific notes tags:
#   curl "http://localhost:41184/notes/NOTEID/tags?token=YOURBIGTOKEN"

# Program creates YAML FrontMatter in the following format:
# ---
# created: 2012-11-10T09:25:49-0800
# updated: 2012-11-10T09:29:35-0800
# tags: [Note, Multi-Word-Tag, lower-case-tag]
# ---

import sys, re, json, random, requests
from datetime import datetime, timezone

# CHANGE THE SETTING BELOW TO YOUR BIG TOKEN (See Joplin API documentation)
TOKEN = sys.argv[1]
NOTES_ENDPOINT = "http://localhost:41184/notes"
TITLE_CHARS = 55
TITLE_LEEWAY = 10

def get_note_metadata(noteid):
    return requests.get('{}/{}/?fields=body,title,user_created_time,user_updated_time&token={}'.format(NOTES_ENDPOINT, noteid, TOKEN))

def get_note_tags(noteid):
    note_tags = []
    res = requests.get('{}/{}/tags?token={}'.format(NOTES_ENDPOINT, noteid, TOKEN)).json()["items"]
    return [re.sub(r'[^a-zA-Z_-]', '', tag.get("title").replace(" ", "-")) for tag in res]

def get_note_ids(page=0):
    res = requests.get('{}?order_by=user_updated_time&order_dir=DESC&limit=100&page={}&token={}'.format(NOTES_ENDPOINT, page, TOKEN))
    return res

def fuzzy_title_length(title):
    if len(title) > TITLE_CHARS:
        ind = title.find(" ", TITLE_CHARS - TITLE_LEEWAY)
        #if ind < TITLE_CHARS + TITLE_LEEWAY:
        return title[0: ind].strip()
    return title.strip()

def process_notes(page=0):
    res = get_note_ids(page)
    for note in res.json()["items"]:
        note_metadata = get_note_metadata(note["id"]).json()
        body = note_metadata["body"]
        title = note_metadata["title"].strip()

        tags = get_note_tags(note["id"])
        created = datetime.fromtimestamp(round(note_metadata["user_created_time"] / 1000), timezone.utc).astimezone()
        updated = datetime.fromtimestamp(round(note_metadata["user_updated_time"] / 1000), timezone.utc).astimezone()
        tags = ", ".join(tags)

        print("original title: %s " % title)
        if title.startswith("Keep Note"):
            title = body.replace('\n', ' ')

        title = re.sub(r'[^a-zA-Z0-9\s\.,\&\)\(\]\[_-]', '', fuzzy_title_length(title))

        front_matter = ""
        if body.startswith("---"):
            print("Note <%s> already has frontmatter: %s" % (title, body))
        else:
            front_matter = f"""---
created: {created}
updated: {updated}
"""
            if tags:
                front_matter += "tags: [" + tags + "]\n"
            front_matter += "---\n\n"

            # front_matter += "# " + title + "\n"

        body = front_matter + body

        print("id:", note["id"])
        print("filename", title)
        print("body", body)

        if body and title and (body != note_metadata["body"] or title != note_metadata["title"]):
            # Only update if the new body is not empty (just a safeguard)
            requests.put(
                '{}/{}?token={}'.format(NOTES_ENDPOINT, note["id"], TOKEN),
                data='{{ "body" : {}, "title": {} }}'.format(json.dumps(body), json.dumps(title))
            )

    if res.json()["has_more"]:
        process_notes(page+1)

if __name__ == "__main__":
    process_notes()
