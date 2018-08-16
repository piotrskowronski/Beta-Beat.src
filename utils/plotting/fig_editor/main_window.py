import logging
import os
import sys
from PyQt5 import QtGui, QtWidgets, QtCore

import matplotlib
import numpy as np
import six
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

import options_artists
from gui_utils import get_icon
import io_utils as io
from main_window_widgets import NavigationToolbar, LogDialog, LogStatusBar, ICON_SIZE_NAVTOOLBAR


LOG = logging.getLogger(__name__)

# TODO: set title position higher
# On picker: check if line is in errorbarcontainer
# use formlayout.fedit to edit lines/title/text/etc
#


CONFIG = {
    "zoomscale": 1.5,   # scaling of scrollzoom
    "autozoom": 0.05,   # percentage of points to cut
    "bordertol": 0.05,  # after autozoom add this to limits
    "picktol": 5,       # picker tolerance in pixels
}


_VERSION = "0.0_prealpha"
_AUTHOR = "Joschua"


class MainWindow(QtWidgets.QMainWindow):
    dpi = 100
    figure_size = (8.0, 4.0)
    status_bar_height = 16
    nav_toolbar_height = ICON_SIZE_NAVTOOLBAR + 8

    def __init__(self, fig=None, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setWindowTitle('TFS-Plotter')
        self.setWindowIcon(get_icon("photo"))

        self._create_logger()
        self._create_menu()

        self._create_main_frame(fig)

    # Creators ###############################################################

    def _create_logger(self):
        """ Create a logging dialog window and a status bar """
        root_logger = logging.getLogger("")

        root_logger.setLevel(logging.DEBUG)
        fmt = "%(asctime)s %(levelname)s %(message)s"
        datefmt = '%d/%m/%Y %H:%M:%S'

        formatter = logging.Formatter(fmt, datefmt)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)

        self._log_dialog = LogDialog(
            fmt=fmt,
            datefmt=datefmt,
            parent=self
        )
        root_logger.addHandler(self._log_dialog)

        self._status_bar = LogStatusBar(
            fmt="%(asctime)s %(message)s",
            datefmt='%H:%M:%S',
            parent=self
        )
        self._status_bar.setFixedHeight(self.status_bar_height)
        root_logger.addHandler(self._status_bar)
        self.setStatusBar(self._status_bar)

    def _create_menu(self):
        """ Add a menu """
        self.file_menu = self.menuBar().addMenu("&File")

        load_action = self._create_action("&Load Data", slot=self._load_data,
                                            shortcut="Ctrl+O", tip="Load Data")
        save_action = self._create_action("&Save plot", slot=self._save_figure,
                                            shortcut="Ctrl+S", tip="Save the plot")
        import_action = self._create_action("&Import plot", slot=self._import_dly,
                                            shortcut="Ctrl+Shift+O", tip="Import the plot")
        export_action = self._create_action("&Export plot", slot=self._export_dly,
                                            shortcut="Ctrl+Shift+S", tip="Export the plot")
        quit_action = self._create_action("&Quit", slot=self.close,
                                          shortcut="Ctrl+Q", tip="Close the application")

        self._add_actions(self.file_menu, (load_action, save_action, import_action, export_action,
                                           None, quit_action))

        self.help_menu = self.menuBar().addMenu("&Help")
        about_action = self._create_action("&About", slot=self.on_about,
                                           shortcut='F1', tip='About the demo')
        log_action = self._create_action("&Show Log", slot=self.show_log,
                                           shortcut='F2', tip='Show the log.')

        self._add_actions(self.help_menu, (about_action, log_action))

    def _create_main_frame(self, fig):
        """ Sets up the main frame of the window """
        self.main_frame = QtWidgets.QWidget(self)
        self.axes = None
        if fig is None:
            self.figure = matplotlib.figure.Figure()
            # self.figure.add_subplot(111)
        else:
            self.figure = fig
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self.main_frame)
        # Connect events and save them to list
        self.cids = []   # save events for disconnecting later
        self._connect_events()
        # Create the navigation toolbar, tied to the canvas
        #
        self.mpl_toolbar = NavigationToolbar(self.canvas,
                                             save_fun=self._save_figure,
                                             load_fun=self._load_data,
                                             import_fun=self._import_dly,
                                             export_fun=self._export_dly,
                                             parent=self
                                             )
        self.mpl_toolbar.setFixedHeight(self.nav_toolbar_height)

        # create a placeholder for the zoomstack:
        self.scrolling = False
        self.zoom_stack = []
        #
        # Layout with box sizers
        #
        hbox = QtWidgets.QHBoxLayout()

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.canvas)
        vbox.addWidget(self.mpl_toolbar)
        vbox.addLayout(hbox)

        self.main_frame.setLayout(vbox)
        self.setCentralWidget(self.main_frame)

        # Update and draw
        self.update_figure(new=True)

    # Creator Helpers ########################################################

    @staticmethod
    def _add_actions(target, actions):
        for action in actions:
            if action is None:
                target.addSeparator()
            else:
                target.addAction(action)

    def _create_action(self, text, slot=None, shortcut=None,
                       icon=None, tip=None, checkable=False,
                       ):
        """ QAction wrapper """
        action = QtWidgets.QAction(text, self)
        if icon is not None:
            action.setIcon(QtGui.QIcon(":/%s.png" % icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            action.triggered.connect(slot)
        if checkable:
            action.setCheckable(True)
        return action

    def _connect_events(self):
        # Bind the clicking events to our handlers
        #
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)  # needed for key events to regisiter
        self.canvas.setFocus()                            # sets focus without clicking on it
        self.cids.append(self.canvas.mpl_connect('pick_event', self.on_pick))
        self.cids.append(self.canvas.mpl_connect('draw_event', self.on_draw))
        self.cids.append(self.canvas.mpl_connect('key_press_event', self.on_key_press))
        self.cids.append(self.canvas.mpl_connect('key_release_event', self.on_key_release))
        self.cids.append(self.canvas.mpl_connect('button_press_event', self.on_mouse_click))
        self.cids.append(self.canvas.mpl_connect('scroll_event', self.on_scroll))

    def _disconnect_events(self):
        for cid in self.cids:
            self.canvas.mpl_disconnect(cid)
        self.cids = []


    # Listeners ###############################################################

    def on_about(self):
        msg = "A small gui to plot tfs files easily and adapt matplotlib plots on the fly.\n"
        msg += "\n"
        msg += "Version: {:s}\n".format(_VERSION)
        msg += "Author: {:s}\n".format(_AUTHOR)

        QtWidgets.QMessageBox.about(self, "About the tfs plotter.", msg)

    def on_pick(self, event):
        # The event received here is of the type
        # matplotlib.backend_bases.PickEvent
        #
        if event.mouseevent.button == 1 and event.mouseevent.dblclick:
            LOG.debug("You've dblclicked on : {:s}".format(event.artist))
            options_artists.change_properties(event.artist, self)

    def on_draw(self, event):
        pass

    def on_mouse_click(self, event):
        """ Single mouse click into window """
        ax = event.canvas.figure.gca()
        if event.button == 2:
            # middle button -> zoom in to 90% of visible data
            if self.mpl_toolbar._nav_stack() is None:
                self.mpl_toolbar.push_current()  # set current view as home

            xlim = ax.get_xlim()
            ylim = ax.get_ylim()

            all_data = np.array([])
            for line in ax.lines:
                data = line.get_data()

                # filter
                xmask = (xlim[0] < data[0]) & (data[0] < xlim[1])
                ymask = (ylim[0] < data[1]) & (data[1] < ylim[1])

                all_data = np.append(all_data, np.array(data[1])[xmask & ymask])
            if len(all_data):
                drop_idx = int(round(len(all_data) * CONFIG["autozoom"]))
                all_data = sorted(all_data)[drop_idx:-drop_idx]

                ymin = min(all_data)
                ymax = max(all_data)
                d = (ymax - ymin) * CONFIG["bordertol"]

                ax.set_ylim((ymin-d, ymax+d))
                self.update_figure()
                self.mpl_toolbar.push_current()

        if event.button == 3:
            # right button -> return in history
            self.mpl_toolbar.back()

    def on_scroll(self, event):
        """ Zoom with respect to mouse-position or center of axes. """
        if self.mpl_toolbar._nav_stack() is None:
            self.mpl_toolbar.push_current()  # set current view as home

        ax = event.canvas.figure.gca()

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        if event.inaxes:
            origin_x = event.xdata
            origin_y = event.ydata
        else:
            origin_x = (xlim[0] + xlim[1]) / 2.
            origin_y = (ylim[0] + ylim[1]) / 2.

        scale = CONFIG["zoomscale"] ** event.step
        new_xlim = [None, None]
        new_ylim = [None, None]
        new_xlim[0] = origin_x + (xlim[0] - origin_x) * scale
        new_xlim[1] = origin_x + (xlim[1] - origin_x) * scale
        new_ylim[0] = origin_y + (ylim[0] - origin_y) * scale
        new_ylim[1] = origin_y + (ylim[1] - origin_y) * scale

        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)
        self.update_figure()

    def on_key_press(self, event):
        # LOG.info("Key press '{}' has been registered".format(event.key))
        if "ctrl+c" == event.key:
                self._copy_selection()
        elif "ctrl+v" == event.key:
            self._paste_from_clipboard()
        elif "ctrl+x" == event.key:
            self._copy_selection()
            self._delete_selection()
        elif "delete" == event.key:
            self._delete_selection()

    def on_key_release(self, event):
        # LOG.info("Key release '{}' has been registered".format(event.key))
        pass

    # Main Frame functions ###########################################################

    def update_figure(self, new=False):
        if new:
            self.figure.set_dpi(self.dpi)
            self.figure.set_size_inches(self.figure_size)
            self.figure.canvas = self.canvas
            self.axes = self.figure.get_axes()
            self._set_pickers()
            self.canvas.figure = self.figure
            self.figure.tight_layout()
        self.canvas.draw()

    def _set_pickers(self):
        """ Set all artists to send pick events when they are clicked """
        tol = CONFIG["picktol"]
        for ax in self.axes:
            for l in ax.lines:
                width = max(1.1*l.get_markersize(), 1.5*l.get_linewidth())
                l.set_picker(width)

            for a in [ax.xaxis, ax.yaxis]:
                a.set_picker(tol)
                for c in a.get_children():
                    c.set_picker(True)

            for t in ax.texts:
                t.set_picker(True)

            legend = ax.get_legend()
            if legend is not None:
                legend.draggable()
                legend.set_picker(True)

            ax.title.set_picker(True)
            ax.set_picker(True)

    def _unset_pickers(self):
        for c in self.figure.get_children():
            try:
                c.set_picker(False)
                c.set_draggable(False)
            except AttributeError:
                pass


    # Copy/Pase ######################################

    def _copy_selection(self):
        LOG.debug("Copy selection has been triggered.")
        pass  # TODO  https://stackoverflow.com/questions/40225270/copy-paste-multiple-items-from-qtableview-in-pyqt4

    def _delete_selection(self):
        LOG.debug("Delete selection has been triggered.")
        pass  # TODO

    def _paste_from_clipboard(self):
        LOG.debug("Paste has been triggered.")
        pass  # TODO

    # Import/Export ##################################

    def _import_dly(self):
        fig = io.load_dly()
        if fig:
            self.figure = fig
            self.update_figure(new=True)

    def _export_dly(self):
        io.save_dly(self.figure)

    def _load_data(self):
        fig = io.load_tfs()
        if fig:
            self.figure = fig
            self.update_figure(new=True)

    def _save_figure(self):
        """ Save figure

        From backend_qt5.NavigationToolbar2QT
        """
        filetypes = self.canvas.get_supported_filetypes_grouped()
        sorted_filetypes = sorted(six.iteritems(filetypes))
        default_filetype = self.canvas.get_default_filetype()

        startpath = os.path.expanduser(
            matplotlib.rcParams['savefig.directory'])
        start = os.path.join(startpath, self.canvas.get_default_filename())
        filters = []
        selected_filter = None

        for name, exts in sorted_filetypes:
            exts_list = " ".join(['*.%s' % ext for ext in exts])
            filter = '%s (%s)' % (name, exts_list)
            if default_filetype in exts:
                selected_filter = filter
            filters.append(filter)
        filters = ';;'.join(filters)

        fname, filter = QtWidgets.QFileDialog.getSaveFileName(
            caption="Choose a filename to save to",
            directory=start,
            filter=filters,
            initialFilter=selected_filter,
        )

        if fname:
            # Save dir for next time, unless empty str (i.e., use cwd).
            if startpath != "":
                matplotlib.rcParams['savefig.directory'] = (
                    os.path.dirname(six.text_type(fname)))
            try:
                self.canvas.figure.savefig(six.text_type(fname))
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    None, "Error saving file", six.text_type(e),
                    QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.NoButton)

    # Public Functions #######################################################

    def show_log(self):
        self._log_dialog.show()


