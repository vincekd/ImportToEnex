import email, os, sys, argparse, re, operator, codecs
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from mako.template import Template

class Note:
    def __init__(self, title, dtime, contents):
        self.title = title or args.defaultTitle
        self.contents = contents
        self.labels = [] if not args.addLabel else [args.addLabel]
        self.datetime = dtime
        self.datestamp = dtime.strftime("%Y%m%dT%H%M%SZ")
        self.author = args.author

    def __str__(self):
        return "%s - %s" % (self.title, self.datestamp)

    def __repr__(self):
        return "%s - %s" % (self.title, self.datestamp)

    def to_enex(self):
        enexXML = Template("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export application="Evernote" version="Evernote">
    <note>
        <title>${note.title}</title>
        <created>${note.datestamp}</created>
        <updated>${note.datestamp}</updated>
        <note-attributes>
            <author>${note.author}</author>
        </note-attributes>
        % for label in note.labels:
        <tag>${label}</tag>
        % endfor
        <content>
            <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
            <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
            <en-note>
                <div>${note.contents}</div>
            </en-note>
            ]]>
        </content>
    </note>
</en-export>
""")
        return enexXML.render(note=self)

def strip_attrs(node):
    global args
    if node and node.name is not None:
        style = node.attrs.get("style")
        node.attrs = {}
        if args.keepStyle and style:
            style = whitespace(style)
            new_style = []
            if "bold" in style:
                new_style.append("font-weight: bold")
            if "italic" in style:
                new_style.append("font-style: italic")
            if "underline" in style:
                new_style.append("text-decoration: underline")

            if len(new_style) > 0:
                node.attrs["style"] = ";".join(new_style)

        for n in node.findAll():
            strip_attrs(n)

def whitespace(text):
    wreg = r'[\n\r ]+'
    return re.sub(wreg, " ", (text or "").strip())

def htmlToNotes(html):

    soup = BeautifulSoup(html, "html.parser")
    notes = []
    index = 0

    #soup.html.body.find_all("div", recursive=False)
    for child in soup.html.body.children:
        if child.name == "div":
            base = [c for c in child.children if c.name is not None][0]
            [title_node, date_node, *contents] = [c for c in base.contents if c.name is not None]
            title = whitespace(title_node.get_text())
            date = whitespace(date_node.get_text().strip())
            dtime = datetime.strptime(date, '%A, %B %d, %Y %I:%M %p').astimezone(timezone.utc)
            html = ""
            
            if len(contents) > 0:
                for node in contents:
                    strip_attrs(node)
                html = whitespace("".join([str(n) for n in contents]))
            else:
                print("no contents: %s" % title)

            note = Note(title, dtime, html)
            notes.append(note)

            index += 1
    notes.sort(key=operator.attrgetter('datetime'))
    
    print("total: #%s" % str(index))
    return notes

def mhtToHtml(mht_file_path):
    name = os.path.splitext(os.path.basename(mht_file_path))[0]
    dir_path = os.path.dirname(mht_file_path)
    html_file_path = os.path.join(dir_path, name + ".html")
    
    print(name)
    print(dir_path)
    print(html_file_path)
    
    with open(mht_file_path, "rb") as mht_file:
        msg = email.message_from_bytes(mht_file.read())
        if msg.is_multipart():
            print("multipart!!!!!")
        else:
            notes = htmlToNotes(msg.get_payload(decode=True))

    outpath = os.path.join(dir_path, "Evernote_Files")
    print(outpath)
    try:
        #os.mkdir(args.output_path)
        os.mkdir(outpath)
    except Exception as e:
        print(e)

    for i, note in enumerate(notes):
        outfname = os.path.join(outpath, str(i + 1) + ".enex")
        # print(outfname, i)
        xml = note.to_enex()
        with codecs.open(outfname, 'w', 'utf-8') as outfile:
            outfile.write(xml)
    print("Done!!!!!")

def getArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("mht_file_path")
    #parser.add_argument("output_path")
    parser.add_argument("--encoding", default=sys.stdin.encoding or "utf-8")
    parser.add_argument("--author", default="Anonymous")
    parser.add_argument("--defaultTitle", default="")
    parser.add_argument("--addLabel", default=None)
    parser.add_argument("--keepStyle", default=False)
    return parser.parse_args()

def main():
    global args
    args = getArgs()

    print(vars(args))

    try:
        mhtToHtml(args.mht_file_path)
    except Exception as ex:
        print("error!")
        sys.exit(ex)

if __name__ == "__main__":
    main()
