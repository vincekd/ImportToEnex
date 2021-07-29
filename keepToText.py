from __future__ import print_function
import sys, glob, os, shutil, zipfile, time, codecs, re, argparse, json, base64, hashlib
from zipfile import ZipFile
from datetime import datetime, timezone
from PIL import Image

indexErrorCount = 0
fileCount = 0
jsonExt = re.compile(r"\.json$", re.I)

class InvalidEncoding(Exception):
    def __init__(self, inner):
        Exception.__init__(self)
        self.inner = str(inner)
        
def msg(s):
    print(s, file=sys.stderr)
    sys.stderr.flush()

def jsonFileToEnex(inputPath, outputDir, tag, attrib, attribVal, inputDir):
    basename = os.path.basename(inputPath).replace(".html", ".enex")
    global fileCount
    outfname = os.path.join(outputDir, str(fileCount)+".enex")

    fileCount += 1
    with codecs.open(inputPath, "r", "utf-8") as inf, codecs.open(outfname, "w", outputEncoding) as outf:
        try:
            note = extractNoteFromJsonFile(inputPath, inputDir)

            # enex file template
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
        <content>
            <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
            <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
            <en-note style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">${note.text}
            % for attachment in note.attachments:
            <en-media style="--en-naturalWidth:${attachment["width"]}; --en-naturalHeight:${attachment["height"]};" hash="${attachment["hash"]}" type="${attachment["mimetype"]}" />
            % endfor
            </en-note>
            ]]>
        </content>
        
        % for attachment in note.attachments:
        <resource>
            <data encoding="base64">
${attachment["data"]}
            </data>
            <mime>${attachment["mimetype"]}</mime>
            <width>${attachment["width"]}</width>
            <height>${attachment["height"]}</height>
            <resource-attributes>
                <file-name>${attachment["filename"]}</file-name>
                <source-url></source-url>
            </resource-attributes>
        </resource>
        % endfor
        
        % for label in note.labels:
        <tag>${label}</tag>
        % endfor
    </note>
</en-export>
""")

            with codecs.open(outfname, 'w', 'utf-8') as outfile:
                outfile.write(enexXML.render(note=note))
        except IndexError:
            msg("index error: " + inputPath)
            indexErrorCount += 1

    
        
def jsonDirToEnex(inputDir, outputDir, tag, attrib, attribVal):
    try_rmtree(outputDir)
    try_mkdir(outputDir)
    msg("Building enex files in {0} ...".format(outputDir))
    
    for path in glob.glob(os.path.join(inputDir, "*.json")):
        jsonFileToEnex(path, outputDir, tag, attrib, attribVal, inputDir)

    global fileCount
    msg("Done. Imported %s json files." % fileCount)
    
def tryUntilDone(action, check):
    ex = None
    i = 1
    while True:
        try:
            if check(): return
        except Exception as e:
            ex = e
                
        if i == 20: break
        
        try:
            action()
        except Exception as e:
            ex = e
            
        time.sleep(1)
        i += 1
        
    sys.exit(ex if ex != None else "Failed")          
        
def try_rmtree(dir):
    if os.path.isdir(dir): msg("Removing {0}".format(dir))

    def act(): shutil.rmtree(dir)        
    def check(): return not os.path.isdir(dir)        
    tryUntilDone(act, check)
        
def try_mkdir(dir):
    def act(): os.mkdir(dir)
    def check(): return os.path.isdir(dir)
    tryUntilDone(act, check)
    
class Note:
    def __init__(self, title, text, labels, dtime, attachments):

        #self.ctime = parse(heading, parserinfo(dayfirst=True))
        self.title = title or args.defaultTitle
        self.text = text
        self.labels = labels
        self.datetime = dtime
        self.datestamp = dtime.strftime("%Y%m%dT%H%M%SZ")
        self.author = args.author
        self.attachments = attachments
        
def extractNoteFromJsonFile(inputPath, inputDir):
    """
    Extracts the note heading (containing the ctime), text, and labels from
    an exported Keep HTML file
    """
    global fileCount

    with codecs.open(inputPath, 'r', 'utf-8') as myfile:
        data = myfile.read()
    note = json.loads(data)
    title = note.get("title", "").strip()
    # edit title if length too long
    if len(title) >= 250:
        note.text = "title: " + title + "\n\n" + note.text
        title = title[:251]
    #print("title: " + title)

    if not title:
        title = (args.defaultTitle + " #" + str(fileCount)).strip()
    
    text = ""
    if "listContent" in note:
        for li in note.get("listContent"):
            text += "<li>" + li.get("text") + "</li>"
        text = "<ul>" + text + "</ul>"
    else:
        text = note.get("textContent", "")

    text = text.strip().replace('\n', '<br/>').replace('\r', '<br/>').replace('&', '&amp;')
    
    labels = [t["name"].strip() for t in note.get("labels", [])]
    if note["isArchived"]:
        labels.append("archived")
    if note["isTrashed"]:
        labels.append("keep:trash")
    if note["isPinned"]:
        labels.append("keep:pinned")

    #labels.append("keep")
    
    dtime = note.get("userEditedTimestampUsec") / 1000 / 1000
    stime = datetime.utcfromtimestamp(dtime)

    attachments = []
    for attachment in note.get("attachments", []):
        path = os.path.join(inputDir, attachment["filePath"].replace(".jpeg", ".jpg"))
        #print(path, attachment["filePath"])
        with codecs.open(path, "rb") as image_file:
            data = image_file.read()
            attachment["data"] = base64.b64encode(data).decode("utf-8")
            attachment["filename"] = attachment["filePath"]
            attachment["hash"] = hashlib.md5(data).hexdigest()
            attachment["path"] = path

            try:
                img = Image.open(path)
                attachment["width"] = img.width
                attachment["height"] = img.height
            except Exception as e:
                attachment["width"] = ""
                attachment["height"] = ""
                print(e)
                print("file: %s" % str(fileCount - 1))
        
        #print(attachment)    
        attachments.append(attachment)

    return Note(title, text, labels, stime, attachments)

def getJsonDir(takeoutDir):
    "Returns first subdirectory beneath takeoutDir which contains .json files"
    dirs = [os.path.join(takeoutDir, s) for s in os.listdir(takeoutDir)]
    for dir in dirs:
        if not os.path.isdir(dir): continue
        htmlFiles = [f for f in os.listdir(dir) if jsonExt.search(f)]
        if len(htmlFiles) > 0: return dir

def keepZipToOutput(zipFileName):
    zipFileDir = os.path.dirname(zipFileName)
    takeoutDir = os.path.join(zipFileDir, "Takeout")
    
    try_rmtree(takeoutDir)
    
    if os.path.isfile(zipFileName):
        msg("Extracting {0} ...".format(zipFileName))

    try:
        with ZipFile(zipFileName) as zipFile:
            zipFile.extractall(zipFileDir)
    except (IOError, zipfile.BadZipfile) as e:
        sys.exit(e)

    jsonDir = getJsonDir(takeoutDir)
    if jsonDir is None: sys.exit("No Keep directory found")
    
    msg("Keep dir: " + jsonDir)

    if args.format == "Evernote":
        jsonDirToEnex(inputDir=jsonDir,
            outputDir=os.path.join(zipFileDir, "Text"),
            tag="div", attrib="class", attribVal="content")
        
def setOutputEncoding():
    global outputEncoding
    outputEncoding = args.encoding
    if outputEncoding is not None: return
    if args.system_encoding: outputEncoding = sys.stdin.encoding
    if outputEncoding is not None: return    
    outputEncoding = "utf-8"

def getArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("zipFile")
    parser.add_argument("--encoding",
        help="character encoding of output")
    parser.add_argument("--system-encoding", action="store_true",
        help="use the system encoding for the output")
    parser.add_argument("--format", choices=["Evernote"],
        default='Evernote', help="Output Format")
    parser.add_argument("--author", default="Anonymous")
    parser.add_argument("--defaultTitle", default="")
    global args
    args = parser.parse_args()    

def doImports():
##    global etree
##    from lxml import etree
    global Template
    from mako.template import Template
    global parse, parserinfo
    from dateutil.parser import parse, parserinfo

def main():
    getArgs()
    doImports()
    setOutputEncoding()
        
    msg("Output encoding: " + outputEncoding)
    
    try:
        keepZipToOutput(args.zipFile)
    except WindowsError as ex:
        sys.exit(ex)
    except InvalidEncoding as ex:
        sys.exit(ex.inner)
    global indexErrorCount
    global fileCount

if __name__ == "__main__":
    main()

