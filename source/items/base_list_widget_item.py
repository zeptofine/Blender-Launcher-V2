from __future__ import annotations

import re

from modules._platform import set_locale
from PyQt5.QtWidgets import QListWidgetItem


class BaseListWidgetItem(QListWidgetItem):
    def __init__(self, date=None):
        super().__init__()
        self.date = date

    def __lt__(self, other):
        soring_type = self.listWidget().parent.sorting_type

        if soring_type.name == "DATETIME":
            return self.compare_datetime(other)
        if soring_type.name == "VERSION":
            return self.compare_version(other)
        return False

    def compare_datetime(self, other):
        if (self.date is None) or (other.date is None):
            return False

        set_locale()

        return self.date > other.date

    def compare_version(self, other):
        list_widget = self.listWidget()

        this_widget = list_widget.itemWidget(self)
        other_widget = list_widget.itemWidget(other)

        if (
            this_widget is None
            or other_widget is None
            or this_widget.build_info is None
            or other_widget.build_info is None
        ):
            return False

        this_match = re.search(r"\d+\.\d+", this_widget.build_info.subversion)
        other_match = re.search(r"\d+\.\d+", other_widget.build_info.subversion)

        this_version = float(this_match.group(0))
        other_version = float(other_match.group(0))

        if this_version == other_version:
            return self.compare_datetime(other)

        return this_version > other_version
