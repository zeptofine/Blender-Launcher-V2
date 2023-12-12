from PyQt5 import QtCore, QtWidgets


class Ui_SettingsWindow:
    def setupUi(self, SettingsWindow):
        SettingsWindow.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        SettingsWindow.resize(480, 100)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.MinimumExpanding,
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(SettingsWindow.sizePolicy().hasHeightForWidth())
        SettingsWindow.setSizePolicy(sizePolicy)
        SettingsWindow.setMinimumSize(QtCore.QSize(480, 100))
        self.CentralWidget = QtWidgets.QWidget(SettingsWindow)
        self.CentralLayout = QtWidgets.QVBoxLayout(self.CentralWidget)
        self.CentralLayout.setContentsMargins(1, 1, 1, 1)
        SettingsWindow.setCentralWidget(self.CentralWidget)
