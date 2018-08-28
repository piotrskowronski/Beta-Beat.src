"""
Launcher for the advanced qt-gui for matpoltlib.
"""
import sys
from PyQt5 import QtWidgets
from main_window import MainWindow


# Main #######################################################################


def main():
    fig = quick_figure()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("fusion")
    form = MainWindow(fig)
    form.show()
    app.exec_()

def quick_figure():
    import matplotlib.pyplot as plt
    fig = plt.figure()
    plt.text(.5,.5, "Hallo")
    plt.errorbar(range(3), range(3), yerr=range(3), xerr=range(3), capsize=3)
    return fig


# Script Mode #################################################################


if __name__ == "__main__":
    main()
