from __future__ import print_function
import sys, glob, os, shutil, zipfile, time, codecs, re, argparse
from zipfile import ZipFile

titleCount = 0
inputPathCount = 0
indexErrorCount = 0
fileCount = 0

class InvalidEncoding(Exception):
    def __init__(self, inner):
        Exception.__init__(self)
        self.inner = str(inner)
        
def msg(s):
    print(s, file=sys.stderr)
    sys.stderr.flush()

def htmlFileToText(inputPath, outputDir, tag, attrib, attribVal):
    basename = os.path.basename(inputPath).replace(".html", ".txt")
    outfname = os.path.join(outputDir, basename)
    try:
        with codecs.open(inputPath, "r", "utf-8") as inf, codecs.open(outfname, "w", outputEncoding) as outf:
            html = inf.read()
            parser = MyHTMLParser(outf, tag, attrib, attribVal)
            parser.feed(html)

            parser = MyHTMLParser(outf, "span", "class", "label-name")
            parser.feed(html)
    except UnicodeEncodeError as ex:
        msg("Skipping file " + inputPath + ": " + str(ex))
    except LookupError as ex:
        raise InvalidEncoding(ex)

def htmlFileToEnex(inputPath, outputDir, tag, attrib, attribVal, inputDir):
    basename = os.path.basename(inputPath).replace(".html", ".enex")
    global fileCount
    outfname = os.path.join(outputDir, str(fileCount)+".enex")
    global titleCount
    global inputPathCount
    global indexErrorCount
    fileCount += 1
    println(args.author)
    with codecs.open(inputPath, "r", "utf-8") as inf, codecs.open(outfname, "w", outputEncoding) as outf:
        try:
            note = extractNoteFromHtmlFile(inputPath)

            # check if there is any title
            title = "No title"
            if len(note.title) != 0:
                title = note.title[0]

            try:
                # remove line breaks in title
                originalLen = len(title)
                title = title.replace('\n', '   ').replace('\r', '   ')
                afterLen = len(title)

                # remove ampersand
                title = title.replace('&', '_')

                # edit title if length too long
                if afterLen >= 250:
                    note.text = title + note.text
                    title = title[:251]
                titleCount += 1
            except:
                inputPathCount += 1
            note.title = title

            # replace line break with <br/>
            note.text = note.text.replace('\n', '<br/>').replace('\r', '<br/>').replace('&', '_')
            created = "Today"
            updated = "Today"

            # enex file template
            enexXML = Template("""
                <?xml version="1.0" encoding="UTF-8"?>
                <!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">
                <en-export application="Evernote" version="Evernote">
                    <note>
                        <title>${note.title}</title>
                        <created>${dateTime}</created>
                        <updated></updated>
                        <note-attributes>
                            <author>${args.author}</author>
                        </note-attributes>
                        <content>
                            <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
                            <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
                            <en-note style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">
                                ${note.text}
                            </en-note>
                            ]]>
                        </content>
                        % for label in note.labels:
                            <tag>${label}</tag>
                        % endfor
                    </note>
                </en-export>
            """)

            with codecs.open(outfname, 'w', 'utf-8') as outfile:
                outfile.write(enexXML.render(note=note))
        except IndexError:
            indexErrorCount += 1

    
        
def htmlDirToText(inputDir, outputDir, tag, attrib, attribVal):
    try_rmtree(outputDir)
    try_mkdir(outputDir)
    msg("Building text files in {0} ...".format(outputDir))
    
    for path in glob.glob(os.path.join(inputDir, "*.html")):
        htmlFileToEnex(path, outputDir, tag, attrib, attribVal, inputDir)
        
    msg("Done.")
    
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
    
htmlExt = re.compile(r"\.html$", re.I)
    
class Note:
    def __init__(self, title, text, labels, dtime):

        #self.ctime = parse(heading, parserinfo(dayfirst=True))
        self.title = title
        self.text = text
        self.labels = labels

    def getWsSeparatedLabelString(self):
        "Return a WS-separated label string suited for import into CintaNotes"
        labels = []
        for label in self.labels:
            label = label.replace(" ", "_")
            label = label.replace(",", "")
            labels.append(label)
        return " ".join(labels)
        
def extractNoteFromHtmlFile(inputPath):
    """
    Extracts the note heading (containing the ctime), text, and labels from
    an exported Keep HTML file
    """

    with codecs.open(inputPath, 'r', 'utf-8') as myfile:
        data = myfile.read()
    
    tree = etree.HTML(data)


    title = []
    for t in tree.xpath("//div[@class='title']/text()"):
        title.append(t)

    try:
        archiveStatus = tree.xpath("//span[@class='archived']")[0]
        archiveStatus = True
    except IndexError:
        archiveStatus = False

    text = "\n".join(tree.xpath("//div[@class='content']/text()"))
    labels = []
    for label in tree.xpath("//span[@class='label-name']/text()"):
        labels.append(label)
    if archiveStatus:
        labels.append("Archive")
        
    dtime = "Nonono"
    println(tree.xpath("//span[@class='heading']/text()"))

    return Note(title, text, labels, dtime)

def getHtmlDir(takeoutDir):
    "Returns first subdirectory beneath takeoutDir which contains .html files"
    dirs = [os.path.join(takeoutDir, s) for s in os.listdir(takeoutDir)]
    for dir in dirs:
        if not os.path.isdir(dir): continue
        htmlFiles = [f for f in os.listdir(dir) if htmlExt.search(f)]
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

    htmlDir = getHtmlDir(takeoutDir)
    if htmlDir is None: sys.exit("No Keep directory found")
    
    msg("Keep dir: " + htmlDir)

    if args.format == "Evernote":
        htmlDirToText(inputDir=htmlDir,
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
    global args
    args = parser.parse_args()    

def doImports():
    global etree
    from lxml import etree
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
    global titleCount
    global inputPathCount
    global indexErrorCount
    global fileCount

if __name__ == "__main__":
    main()

