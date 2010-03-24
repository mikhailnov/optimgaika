#!/usr/bin/python

import sys
import errno
from os import listdir
from os import path
from subprocess import call, PIPE
from optparse import OptionParser

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from hurry.filesize import *

from ui import Ui_trimage

VERSION = "1.0.0b"

class StartQT4(QMainWindow):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.ui = Ui_trimage()
        self.ui.setupUi(self)

        self.showapp = True
        self.verbose = True
        self.imagelist = []

        # check if apps are installed
        if self.checkapps():
            quit()

        #add quit shortcut
        if hasattr(QKeySequence, "Quit"):
            self.quit_shortcut = QShortcut(QKeySequence(QKeySequence.Quit),
                self)
        else:
            self.quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)

        # disable recompress
        self.ui.recompress.setEnabled(False)
        #self.ui.recompress.hide()

        # make a worker thread
        self.thread = Worker()

        # connect signals with slots
        QObject.connect(self.ui.addfiles, SIGNAL("clicked()"),
            self.file_dialog)
        QObject.connect(self.ui.recompress, SIGNAL("clicked()"),
            self.recompress_files)
        QObject.connect(self.quit_shortcut, SIGNAL("activated()"),
            qApp, SLOT('quit()'))
        QObject.connect(self.ui.processedfiles, SIGNAL("fileDropEvent"),
            self.file_drop)
        QObject.connect(self.thread, SIGNAL("finished()"), self.update_table)
        QObject.connect(self.thread, SIGNAL("terminated()"), self.update_table)
        QObject.connect(self.thread, SIGNAL("updateUi"), self.update_table)

        # activate command line options
        self.commandline_options()

    def commandline_options(self):
        """Set up the command line options."""
        parser = OptionParser(version="%prog " + VERSION,
            description="GUI front-end to compress png and jpg images via "
                "optipng, advpng and jpegoptim")

        parser.set_defaults(verbose=True)
        parser.add_option("-v", "--verbose", action="store_true",
            dest="verbose", help="Verbose mode (default)")
        parser.add_option("-q", "--quiet", action="store_false",
            dest="verbose", help="Quiet mode")

        parser.add_option("-f", "--file", action="store", type="string",
            dest="filename", help="compresses image and exit")
        parser.add_option("-d", "--directory", action="store", type="string",
            dest="directory", help="compresses images in directory and exit")

        options, args = parser.parse_args()

        # send to correct function
        if options.filename:
            self.file_from_cmd(options.filename)
        if options.directory:
            self.dir_from_cmd(options.directory)

        self.verbose = options.verbose

    """
    Input functions
    """

    def dir_from_cmd(self, directory):
        """
        Read the files in the directory and send all files to compress_file.
        """
        self.showapp = False
        dirpath = path.abspath(path.dirname(directory))
        imagedir = listdir(directory)
        filelist = QStringList()
        for image in imagedir:
            image = QString(path.join(dirpath, image))
            filelist.append(image)
        self.delegator(filelist)

    def file_from_cmd(self, image):
        """Get the file and send it to compress_file"""
        self.showapp = False
        image = path.abspath(image)
        filecmdlist = QStringList()
        filecmdlist.append(image)
        self.delegator(filecmdlist)

    def file_drop(self, images):
        """
        Get a file from the drag and drop handler and send it to compress_file.
        """
        self.delegator(images)

    def file_dialog(self):
        """Open a file dialog and send the selected images to compress_file."""
        fd = QFileDialog(self)
        images = fd.getOpenFileNames(self,
            "Select one or more image files to compress",
            "", # directory
            # this is a fix for file dialog differentiating between cases
            "Image files (*.png *.jpg *.jpeg *.PNG *.JPG *.JPEG)")
        self.delegator(images)

    def recompress_files(self):
        """Send each file in the current file list to compress_file again."""
        newimagelist = []
        for image in self.imagelist:
            newimagelist.append(image[4])
        self.imagelist = []
        self.delegator(newimagelist)

    """
    Compress functions
    """

    def delegator(self, images):
        """
        Recieve all images, check them and send them to the worker thread.
        """
        delegatorlist = []
        for image in images:
            if self.checkname(image):
                delegatorlist.append((image, QIcon(image)))
                self.imagelist.append(("Compressing...", "", "", "", image,
                    QIcon(QPixmap(self.ui.get_image("pixmaps/compressing.gif")))))
            else:
                sys.stderr.write("[error] %s not an image file" % image)

        self.update_table()
        self.thread.compress_file(delegatorlist, self.showapp, self.verbose,
            self.imagelist)


    """
    UI Functions
    """

    def update_table(self):
        """Update the table view with the latest file data."""
        tview = self.ui.processedfiles
        # set table model
        tmodel = TriTableModel(self, self.imagelist,
            ["Filename", "Old Size", "New Size", "Compressed"])
        tview.setModel(tmodel)

        # set minimum size of table
        vh = tview.verticalHeader()
        vh.setVisible(False)

        # set horizontal header properties
        hh = tview.horizontalHeader()
        hh.setStretchLastSection(True)

        # set all row heights
        nrows = len(self.imagelist)
        for row in range(nrows):
            tview.setRowHeight(row, 25)

        # set the second column to be longest
        tview.setColumnWidth(0, 300)

        # enable recompress button
        self.enable_recompress()

    """
    Helper functions
    """

    def checkname(self, name):
        """Check if the file is a jpg or png."""
        return path.splitext(str(name))[1].lower() in [".jpg", ".jpeg", ".png"]

    def enable_recompress(self):
        """Enable the recompress button."""
        self.ui.recompress.setEnabled(True)

    def checkapps(self):
        """Check if the required command line apps exist."""
        status = False
        retcode = self.safe_call("jpegoptim --version")
        if retcode != 0:
            status = True
            sys.stderr.write("[error] please install jpegoptim")

        retcode = self.safe_call("optipng -v")
        if retcode != 0:
            status = True
            sys.stderr.write("[error] please install optipng")

        retcode = self.save_call("advpng --version")
        if retcode != 0:
            status = True
            sys.stderr.write("[error] please install advancecomp")
        return status

    def safe_call(self, command):
        while True:
            try:
                return call(command, shell=True, stdout=PIPE)
            except OSError, e:
                if e.errno == errno.EINTR:
                    continue
                else:
                    raise

class TriTableModel(QAbstractTableModel):

    def __init__(self, parent, imagelist, header, *args):
        """
        @param parent Qt parent object.
        @param imagelist A list of tuples.
        @param header A list of strings.
        """
        QAbstractTableModel.__init__(self, parent, *args)
        self.imagelist = imagelist
        self.header = header

    def rowCount(self, parent):
        """Count the number of rows."""
        return len(self.imagelist)

    def columnCount(self, parent):
        """Count the number of columns."""
        return len(self.header)

    def data(self, index, role):
        """Fill the table with data."""
        if not index.isValid():
            return QVariant()
        elif role == Qt.DisplayRole:
            data = self.imagelist[index.row()][index.column()]
            return QVariant(data)
        elif index.column() == 0 and role == Qt.DecorationRole:
            # decorate column 0 with an icon of the image itself
            f_icon = self.imagelist[index.row()][5]
            return QVariant(f_icon)
        else:
            return QVariant()

    def headerData(self, col, orientation, role):
        """Fill the table headers."""
        if orientation == Qt.Horizontal and (role == Qt.DisplayRole or
        role == Qt.DecorationRole):
            return QVariant(self.header[col])
        return QVariant()


class Worker(QThread):

    def __init__(self, parent=None):
        QThread.__init__(self, parent)
        self.exiting = False

    def __del__(self):
        self.exiting = True
        self.wait()

    def compress_file(self, images, showapp, verbose, imagelist):
        """Start the worker thread."""
        self.images = images
        self.showapp = showapp
        self.verbose = verbose
        self.imagelist = imagelist
        self.start()

    def run(self):
        """Compress the given file, get data from it and call update_table."""
        for image in self.images:
            #gather old file data
            filename = str(image[0])
            icon = image[1]
            oldfile = QFileInfo(filename)
            name = oldfile.fileName()
            oldfilesize = oldfile.size()
            oldfilesizestr = size(oldfilesize, system=alternative)

            # get extention
            extention = path.splitext(filename)[1]
            #decide with tool to use
            if extention in [".jpg", ".jpeg"]:
                runString = "jpegoptim -f --strip-all '%(file)s'"
            elif extention in [".png"]:
                runString = ("optipng -force -o7 '%(file)s';"
                    "advpng -z4 '%(file)s'")
            else:
                sys.stderr.write("[error] %s not an image file" % filename)

            try:
                retcode = call(runString % {"file": filename}, shell=True,
                               stdout=PIPE)
                runfile = retcode
            except OSError as e:
                runfile = e

            if runfile == 0:
                #gather new file data
                newfile = QFile(filename)
                newfilesize = newfile.size()
                newfilesizestr = size(newfilesize, system=alternative)

                #calculate ratio and make a nice string
                ratio = 100 - (float(newfilesize) / float(oldfilesize) * 100)
                ratiostr = "%.1f%%" % ratio

                # append current image to list
                for i, image in enumerate(self.imagelist):
                    if image[4] == filename:
                        self.imagelist.remove(image)
                        self.imagelist.insert(i, (name, oldfilesizestr,
                            newfilesizestr, ratiostr, filename, icon))

                self.emit(SIGNAL("updateUi"))

                if not self.showapp and self.verbose:
                    # we work via the commandline
                    print("File: " + filename + ", Old Size: "
                        + oldfilesizestr + ", New Size: " + newfilesizestr
                        + ", Ratio: " + ratiostr)
            else:
                sys.stderr.write("[error] %s" % runfile)

        if not self.showapp:
            #make sure the app quits after all images are done
            quit()

class TrimageTableView(QTableView):
    """Init the table drop event."""
    def __init__(self, parent=None):
        super(TrimageTableView, self).__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("text/uri-list"):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        files = str(event.mimeData().data("text/uri-list")).strip().split()
        for i, file in enumerate(files):
            files[i] = QUrl(QString(file)).toLocalFile()
        self.emit(SIGNAL("fileDropEvent"), (files))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    myapp = StartQT4()

    if myapp.showapp:
        myapp.show()
    sys.exit(app.exec_())