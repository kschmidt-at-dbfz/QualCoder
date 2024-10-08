# -*- coding: utf-8 -*-

"""
Copyright (c) 2023 Colin Curtain

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

Author: Colin Curtain (ccbogel)
https://github.com/ccbogel/QualCoder
"""

import os
from rispy import TAG_KEY_MAPPING
import sys
import logging
import traceback

from PyQt6 import QtWidgets, QtCore, QtGui

from .GUI.base64_helper import *
from .GUI.ui_reference_editor import Ui_DialogReferenceEditor
from .GUI.ui_manage_references import Ui_Dialog_manage_references
from .confirm_delete import DialogConfirmDelete
from .ris import Ris, RisImport

path = os.path.abspath(os.path.dirname(__file__))
logger = logging.getLogger(__name__)

REF_ID = 0
REF_DETAIL = 1
REF_TYPE = 2
REF_YEAR = 3
REF_AUTHORS = 4
REF_JOURNAL = 5
REF_VOLUME = 6
REF_ISSUE = 7
REF_KEYWORDS = 8


class DialogReferenceManager(QtWidgets.QDialog):
    """ Dialog to manipulate files for a case.
    Add files to case, add all text or text portions from a text file.
    Remove file from a case. View file.
    """

    app = None
    parent_textEdit = None
    files = []
    refs = []

    def __init__(self, app_, parent_text_edit):

        self.app = app_
        self.parent_textEdit = parent_text_edit
        self.files = []
        self.refs = []
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_Dialog_manage_references()
        self.ui.setupUi(self)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)
        font = 'font: ' + str(self.app.settings['fontsize']) + 'pt '
        font += '"' + self.app.settings['font'] + '";'
        self.setStyleSheet(font)
        font2 = 'font: ' + str(self.app.settings['treefontsize']) + 'pt '
        font2 += '"' + self.app.settings['font'] + '";'
        self.ui.tableWidget_files.setStyleSheet(font2)
        self.ui.tableWidget_files.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ui.tableWidget_files.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.tableWidget_files.customContextMenuRequested.connect(self.table_files_menu)
        self.ui.tableWidget_files.horizontalHeader().setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.tableWidget_files.horizontalHeader().customContextMenuRequested.connect(self.table_files_header_menu)
        self.ui.tableWidget_refs.setStyleSheet(font2)
        self.ui.tableWidget_refs.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ui.tableWidget_refs.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.ui.tableWidget_refs.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.tableWidget_refs.customContextMenuRequested.connect(self.table_refs_menu)
        self.ui.tableWidget_refs.horizontalHeader().setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.tableWidget_refs.horizontalHeader().customContextMenuRequested.connect(self.table_refs_header_menu)

        pm = QtGui.QPixmap()
        pm.loadFromData(QtCore.QByteArray.fromBase64(doc_import_icon), "png")
        self.ui.pushButton_import.setIcon(QtGui.QIcon(pm))
        self.ui.pushButton_import.pressed.connect(self.import_references)
        pm = QtGui.QPixmap()
        pm.loadFromData(QtCore.QByteArray.fromBase64(link_icon), "png")
        self.ui.pushButton_link.setIcon(QtGui.QIcon(pm))
        self.ui.pushButton_link.pressed.connect(self.link_files_to_reference)
        pm = QtGui.QPixmap()
        pm.loadFromData(QtCore.QByteArray.fromBase64(undo_icon), "png")
        self.ui.pushButton_unlink_files.setIcon(QtGui.QIcon(pm))
        self.ui.pushButton_unlink_files.pressed.connect(self.unlink_files)
        pm = QtGui.QPixmap()
        pm.loadFromData(QtCore.QByteArray.fromBase64(pencil_icon), "png")
        self.ui.pushButton_edit_ref.setIcon(QtGui.QIcon(pm))
        self.ui.pushButton_edit_ref.pressed.connect(self.edit_reference)
        pm = QtGui.QPixmap()
        pm.loadFromData(QtCore.QByteArray.fromBase64(delete_icon), "png")
        self.ui.pushButton_delete_ref.setIcon(QtGui.QIcon(pm))
        self.ui.pushButton_delete_ref.pressed.connect(self.delete_reference)
        pm = QtGui.QPixmap()
        pm.loadFromData(QtCore.QByteArray.fromBase64(doc_delete_icon), "png")
        self.ui.pushButton_delete_unused_refs.setIcon(QtGui.QIcon(pm))
        self.ui.pushButton_delete_unused_refs.setEnabled(False)
        self.ui.pushButton_delete_unused_refs.hide()
        self.get_data()
        self.ui.tableWidget_refs.setTabKeyNavigation(False)
        self.ui.tableWidget_refs.installEventFilter(self)
        self.ui.tableWidget_files.setTabKeyNavigation(False)
        self.ui.tableWidget_files.installEventFilter(self)
        self.ui.checkBox_hide_files.toggled.connect(self.fill_table_files)
        self.ui.checkBox_hide_refs.toggled.connect(self.fill_table_refs)
        self.ui.splitter.setSizes([500, 200])
        self.table_files_rows_hidden = False
        self.table_refs_rows_hidden = False

    def get_data(self):
        """ Get data for files and references. """

        cur = self.app.conn.cursor()
        cur.execute("select id, name, risid, memo, date from source order by lower(name)")
        result = cur.fetchall()
        self.files = []
        keys = 'id', 'name', 'risid', 'memo', 'date'
        for row in result:
            self.files.append(dict(zip(keys, row)))
        self.fill_table_files()
        r = Ris(self.app)
        r.get_references()
        self.refs = r.refs
        sorted_list = sorted(self.refs, key=lambda x: x['details'])
        self.refs = sorted_list
        self.fill_table_refs()

    def fill_table_files(self):
        """ Fill widget with file details. """

        rows = self.ui.tableWidget_files.rowCount()
        for c in range(0, rows):
            self.ui.tableWidget_files.removeRow(0)
        header_labels = ["id", "File name", "Ref Id"]
        self.ui.tableWidget_files.setColumnCount(len(header_labels))
        self.ui.tableWidget_files.setHorizontalHeaderLabels(header_labels)
        for row, f in enumerate(self.files):
            self.ui.tableWidget_files.insertRow(row)
            item = QtWidgets.QTableWidgetItem(str(f['id']))
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_files.setItem(row, 0, item)
            item = QtWidgets.QTableWidgetItem(f['name'])
            memo = f['memo']
            if not memo:
                memo = ""
            item.setToolTip(memo)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_files.setItem(row, 1, item)
            risid = ""
            if f['risid'] is not None:
                risid = str(f['risid'])
                if self.ui.checkBox_hide_files.isChecked():
                    self.ui.tableWidget_files.setRowHidden(row, True)
                else:
                    self.ui.tableWidget_files.setRowHidden(row, False)
            item = QtWidgets.QTableWidgetItem(risid)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_files.setItem(row, 2, item)
        self.ui.tableWidget_files.hideColumn(0)
        if self.app.settings['showids']:
            self.ui.tableWidget_files.showColumn(0)
        self.ui.tableWidget_files.resizeColumnsToContents()
        if self.ui.tableWidget_files.columnWidth(1) > 600:
            self.ui.tableWidget_files.setColumnWidth(1, 600)
        self.ui.tableWidget_files.resizeRowsToContents()

    def table_files_header_menu(self, position):
        """ Sort ascending or descending. """

        if not self.files:
            return
        index_at = self.ui.tableWidget_refs.indexAt(position)
        col = int(index_at.column())
        menu = QtWidgets.QMenu(self)
        action_files_asc = menu.addAction(_("Ascending"))
        action_files_desc = menu.addAction(_("Descending"))
        action = menu.exec(self.ui.tableWidget_files.mapToGlobal(position))
        if action == action_files_asc:
            sorted_list = sorted(self.files, key=lambda x: x['name'])
            self.files = sorted_list
            self.fill_table_files()
            return
        if action == action_files_desc:
            sorted_list = sorted(self.files, key=lambda x: x['name'], reverse=True)
            self.files = sorted_list
            self.fill_table_files()
            return

    def table_files_menu(self, position):
        """ Context menu for showing specific rows.
        """

        #row = self.ui.tableWidget_files.currentRow()
        menu = QtWidgets.QMenu()
        action_show_value_like = menu.addAction(_("Show value like"))
        action_show_all_rows = None
        if self.table_files_rows_hidden:
            action_show_all_rows = menu.addAction(_("Show all rows"))
        action = menu.exec(self.ui.tableWidget_files.mapToGlobal(position))
        if action == action_show_all_rows:
            for r in range(0, self.ui.tableWidget_files.rowCount()):
                self.ui.tableWidget_files.setRowHidden(r, False)
            self.table_files_rows_hidden = False
            return
        if action == action_show_value_like:
            text_value, ok = QtWidgets.QInputDialog.getText(self, _("Text filter"), _("Show value like:"),
                                                            QtWidgets.QLineEdit.EchoMode.Normal)
            if not ok or text_value == '':
                return
            for r in range(0, self.ui.tableWidget_files.rowCount()):
                if self.ui.tableWidget_files.item(r, 1).text().find(text_value) == -1:
                    self.ui.tableWidget_files.setRowHidden(r, True)
            self.table_files_rows_hidden = True
            return

    def fill_table_refs(self):
        """ Fill widget with ref details. """

        rows = self.ui.tableWidget_refs.rowCount()
        for c in range(0, rows):
            self.ui.tableWidget_refs.removeRow(0)
        header_labels = ["Ref id", _("Reference"), _("Type"), _("Year"), _("Authors"), _("Journal or Publication Title"),
                         _("Volume"), _("Issue"), _("Keywords")]
        self.ui.tableWidget_refs.setColumnCount(len(header_labels))
        self.ui.tableWidget_refs.setHorizontalHeaderLabels(header_labels)
        for row, ref in enumerate(self.refs):
            self.ui.tableWidget_refs.insertRow(row)
            item = QtWidgets.QTableWidgetItem(str(ref['risid']))
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_ID, item)
            item = QtWidgets.QTableWidgetItem(ref['vancouver'])
            item.setToolTip(ref['details'])
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_DETAIL, item)
            type_of_ref = ""
            if 'TY' in ref:
                type_of_ref = ref['TY']
            item = QtWidgets.QTableWidgetItem(type_of_ref)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_TYPE, item)
            year_of_ref = ""
            if 'PY' in ref:
                year_of_ref = ''.join(ch for ch in ref['PY'] if ch.isdigit())  # Digits only
            item = QtWidgets.QTableWidgetItem(year_of_ref)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_YEAR, item)
            authors = ""
            if 'authors' in ref:
                authors = ref['authors']
            item = QtWidgets.QTableWidgetItem(authors)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_AUTHORS, item)
            journal_or_secondary = ""
            if 'journal_or_secondary' in ref:
                journal_or_secondary = ref['journal_or_secondary']
            item = QtWidgets.QTableWidgetItem(journal_or_secondary)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_JOURNAL, item)
            volume = ""
            if 'volume' in ref:
                volume = ref['volume']
            item = QtWidgets.QTableWidgetItem(volume)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_VOLUME, item)
            issue = ""
            if 'issue' in ref:
                issue = ref['issue']
            item = QtWidgets.QTableWidgetItem(issue)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_ISSUE, item)
            keywords = ""
            if 'KW' in ref:
                keywords = ref['KW']
            item = QtWidgets.QTableWidgetItem(keywords)
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.ui.tableWidget_refs.setItem(row, REF_KEYWORDS, item)

            # Check if files assigned to this ref
            files_assigned = False
            for f in self.files:
                if f['risid'] == ref['risid']:
                    files_assigned = True
                    break
            if self.ui.checkBox_hide_refs.isChecked() and files_assigned:
                self.ui.tableWidget_refs.setRowHidden(row, True)
            else:
                self.ui.tableWidget_refs.setRowHidden(row, False)
        if self.app.settings['showids']:
            self.ui.tableWidget_refs.showColumn(REF_ID)
        self.ui.tableWidget_refs.resizeColumnsToContents()
        if self.ui.tableWidget_refs.columnWidth(REF_DETAIL) > 500:
            self.ui.tableWidget_refs.setColumnWidth(REF_DETAIL, 500)
        if self.ui.tableWidget_refs.columnWidth(REF_AUTHORS) > 400:
            self.ui.tableWidget_refs.setColumnWidth(REF_AUTHORS, 400)
        if self.ui.tableWidget_refs.columnWidth(REF_JOURNAL) > 350:
            self.ui.tableWidget_refs.setColumnWidth(REF_JOURNAL, 350)
        self.ui.tableWidget_refs.resizeRowsToContents()

    def table_refs_header_menu(self, position):
        """ Sort ascending or descending. """

        if not self.refs:
            return
        index_at = self.ui.tableWidget_refs.indexAt(position)
        col = int(index_at.column())
        menu = QtWidgets.QMenu(self)
        action_id_asc = None
        action_id_desc = None
        if col == REF_ID:
            action_id_asc = menu.addAction(_("Ascending"))
            action_id_desc = menu.addAction(_("Descending"))
        action_detail_asc = None
        action_detail_desc = None
        if col == REF_DETAIL:
            action_detail_asc = menu.addAction(_("Ascending"))
            action_detail_desc = menu.addAction(_("Descending"))
        action_type_ascending = None
        action_type_descending = None
        if col == REF_TYPE:
            action_type_ascending = menu.addAction(_("Ascending"))
            action_type_descending = menu.addAction(_("Descending"))
        action_year_ascending = None
        action_year_descending = None
        if col == REF_YEAR:
            action_year_ascending = menu.addAction(_("Ascending"))
            action_year_descending = menu.addAction(_("Descending"))
        action_authors_ascending = None
        action_authors_descending = None
        if col == REF_AUTHORS:
            action_authors_ascending = menu.addAction(_("Ascending"))
            action_authors_descending = menu.addAction(_("Descending"))
        action_journal_ascending = None
        action_journal_descending = None
        if col == REF_JOURNAL:
            action_journal_ascending = menu.addAction(_("Ascending"))
            action_journal_descending = menu.addAction(_("Descending"))
        action_volume_ascending = None
        action_volume_descending = None
        if col == REF_VOLUME:
            action_volume_ascending = menu.addAction(_("Ascending"))
            action_volume_descending = menu.addAction(_("Descending"))
        action_keywords_ascending = None
        action_keywords_descending = None
        if col == REF_KEYWORDS:
            action_keywords_ascending = menu.addAction(_("Ascending"))
            action_keywords_descending = menu.addAction(_("Descending"))

        action = menu.exec(self.ui.tableWidget_refs.mapToGlobal(position))
        if action == action_id_asc:
            sorted_list = sorted(self.refs, key=lambda x: x['risid'])
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_id_desc:
            sorted_list = sorted(self.refs, key=lambda x: x['risid'], reverse=True)
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_detail_asc:
            sorted_list = sorted(self.refs, key=lambda x: x['details'])
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_detail_desc:
            sorted_list = sorted(self.refs, key=lambda x: x['details'], reverse=True)
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_type_ascending:
            sorted_list = sorted(self.refs, key=lambda x: x['TY'])
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_type_descending:
            sorted_list = sorted(self.refs, key=lambda x: x['TY'], reverse=True)
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_year_ascending:
            sorted_list = sorted(self.refs, key=lambda x: x['PY'])
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_year_descending:
            sorted_list = sorted(self.refs, key=lambda x: x['PY'], reverse=True)
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_authors_ascending:
            sorted_list = sorted(self.refs, key=lambda x: x['authors'])
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_authors_descending:
            sorted_list = sorted(self.refs, key=lambda x: x['authors'], reverse=True)
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_journal_ascending:
            sorted_list = sorted(self.refs, key=lambda x: x['journal_or_secondary'])
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_journal_descending:
            sorted_list = sorted(self.refs, key=lambda x: x['journal_or_secondary'], reverse=True)
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_volume_ascending:
            sorted_list = sorted(self.refs, key=lambda x: x['volume'])
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_volume_descending:
            sorted_list = sorted(self.refs, key=lambda x: x['volume'], reverse=True)
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_keywords_ascending:
            sorted_list = sorted(self.refs, key=lambda x: x['keywords'])
            self.refs = sorted_list
            self.fill_table_refs()
            return
        if action == action_keywords_descending:
            sorted_list = sorted(self.refs, key=lambda x: x['keywords'], reverse=True)
            self.refs = sorted_list
            self.fill_table_refs()
            return

    def table_refs_menu(self, position):
        """ Context menu for displaying table rows in differing order,
            Showing specific rows.
        """

        row = self.ui.tableWidget_refs.currentRow()
        col = self.ui.tableWidget_refs.currentColumn()
        item = self.ui.tableWidget_refs.item(row, col)
        item_text = ""
        if item is not None:
            item_text = item.text()
        menu = QtWidgets.QMenu()
        menu.setStyleSheet("QMenu {font-size:" + str(self.app.settings['fontsize']) + "pt} ")
        action_show_this_value = menu.addAction(_("Show this value"))
        action_show_value_like = menu.addAction(_("Show value like"))
        action_show_all_rows = None
        if self.table_refs_rows_hidden:
            action_show_all_rows = menu.addAction(_("Show all rows"))
        action_copy_to_clipboard = menu.addAction(_("Copy to clipboard"))
        action_copy_apa_to_clipboard = menu.addAction(_("Copy to clipboard.  APA style"))
        action = menu.exec(self.ui.tableWidget_refs.mapToGlobal(position))
        if action == action_show_all_rows:
            for r in range(0, self.ui.tableWidget_refs.rowCount()):
                self.ui.tableWidget_refs.setRowHidden(r, False)
            self.table_refs_rows_hidden = False
            return
        if action == action_show_this_value:
            for r in range(0, self.ui.tableWidget_refs.rowCount()):
                if self.ui.tableWidget_refs.item(r, col).text() != item_text:
                    self.ui.tableWidget_refs.setRowHidden(r, True)
            self.table_refs_rows_hidden = True
            return
        if action == action_show_value_like:
            text_value, ok = QtWidgets.QInputDialog.getText(self, _("Text filter"), _("Show value like:"),
                                                            QtWidgets.QLineEdit.EchoMode.Normal)
            if not ok or text_value == '':
                return
            for r in range(0, self.ui.tableWidget_refs.rowCount()):
                if self.ui.tableWidget_refs.item(r, col).text().find(text_value) == -1:
                    self.ui.tableWidget_refs.setRowHidden(r, True)
            self.table_refs_rows_hidden = True
            return
        if action == action_copy_to_clipboard:
            reference_text = self.ui.tableWidget_refs.item(row, 1).text()
            cb = QtWidgets.QApplication.clipboard()
            cb.setText(reference_text.replace("\n", " "))
        if action == action_copy_apa_to_clipboard:
            #reference_text = self.ui.tableWidget_refs.item(row, 1).text()
            ref_id = self.ui.tableWidget_refs.item(row, REF_ID).text()
            for ref in self.refs:
                if int(ref_id) == ref['risid']:
                    cb = QtWidgets.QApplication.clipboard()
                    cb.setText(ref['apa'].replace("\n", " "))

    def import_references(self):
        """ Import RIS formatted references from .ris or .txt files """

        RisImport(self.app, self.parent_textEdit)
        self.get_data()

    def keyPressEvent(self, event):
        """ Used to activate buttons.
        Ctrl 2 to 5
        """
        key = event.key()
        mods = QtWidgets.QApplication.keyboardModifiers()
        # Ctrl 2 to 5
        if mods & QtCore.Qt.KeyboardModifier.ControlModifier:
            if key == QtCore.Qt.Key.Key_2:
                self.unlink_files()
                return
            if key == QtCore.Qt.Key.Key_3:
                self.edit_reference()
                return
            if key == QtCore.Qt.Key.Key_4:
                self.import_references()
                return
            if key == QtCore.Qt.Key.Key_5:
                self.delete_reference()
                return
            '''if key == QtCore.Qt.Key.Key_0:
                self.help()
                return'''

    def eventFilter(self, object_, event):
        """ L Link files to reference.
        U to unlink selected files
        Note. Fires multiple times very quickly.
        """

        if type(event) == QtGui.QKeyEvent:
            key = event.key()
            #mod = event.modifiers()
            if key == QtCore.Qt.Key.Key_L and (self.ui.tableWidget_refs.hasFocus() or self.ui.tableWidget_files.hasFocus()):
                self.link_files_to_reference()
                return True
            if key == QtCore.Qt.Key.Key_U and (self.ui.tableWidget_refs.hasFocus() or self.ui.tableWidget_files.hasFocus()):
                self.unlink_files()
                return True
        return False

    def unlink_files(self):
        """ Remove linked reference from selected files. """

        file_row_objs = self.ui.tableWidget_files.selectionModel().selectedRows()
        if not file_row_objs:
            return
        cur = self.app.conn.cursor()
        for index in file_row_objs:
            fid = int(index.data())  # Column 0 data
            cur.execute("update source set risid=null where id=?", [fid])
            self.app.conn.commit()
            self.ui.tableWidget_files.item(index.row(), 2).setText("")
        self.get_data()

    def link_files_to_reference(self):
        """ Link the selected files to the selected reference.
         """

        ref_row_obj = self.ui.tableWidget_refs.selectionModel().selectedRows()
        if not ref_row_obj:
            return
        ris_id = int(ref_row_obj[0].data())  # Only One index returned. Column 0 data
        file_row_objs = self.ui.tableWidget_files.selectionModel().selectedRows()
        if not file_row_objs:
            return
        ref = None
        attr_values = {"Ref_Authors": "", "Ref_Title": "", "Ref_Type": "", "Ref_Year": "", "Ref_Journal": ""}
        for r in self.refs:
            if r['risid'] == ris_id:
                ref = r
        if 'TY' in ref:
            attr_values['Ref_Type'] = ref['TY']
        if 'AU' in ref:
            attr_values['Ref_Authors'] = ref['AU']
        if 'A1' in ref:
            attr_values['Ref_Authors'] += " " + ref['A1']
        if 'A2' in ref:
            attr_values['Ref_Authors'] += " " + ref['A2']
        if 'A3' in ref:
            attr_values['Ref_Authors'] += " " + ref['A3']
        if 'A4' in ref:
            attr_values['Ref_Authors'] += " " + ref['A4']
        attr_values['Ref_Title'] = ""
        # Get the first title based on this order from several tags
        attr_values['Ref_Title'] = ""
        for tag in ("TI", "T1", "ST", "TT"):
            try:
                attr_values['Ref_Title'] = ref[tag]
                break
            except KeyError:
                pass
        # Get ref year from several tags
        attr_values['Ref_Year'] = ""
        if 'PY' in ref:
            attr_values['Ref_Year'] = ref['PY']
        if attr_values['Ref_Year'] == "" and 'Y1' in ref:
            attr_values['Ref_Year'] = ref['Y1']
        attr_values['Ref_Journal'] = ref['journal_vol_issue']

        cur = self.app.conn.cursor()
        for index in file_row_objs:
            fid = int(index.data())  # Column 0 data
            cur.execute("update source set risid=? where id=?", [ris_id, fid])
            self.app.conn.commit()
            self.ui.tableWidget_files.item(index.row(), 2).setText(str(ris_id))
            sql = "update attribute set value=? where id=? and name=?"
            for attribute in attr_values:
                cur.execute(sql, [attr_values[attribute], fid, attribute])
                self.app.conn.commit()
        self.get_data()

    def edit_reference(self):
        """ Edit selected reference. """

        ref_row_obj = self.ui.tableWidget_refs.selectionModel().selectedRows()
        if not ref_row_obj:
            return
        ris_id = int(ref_row_obj[0].data())  # Only One index returned. Column 0 data
        ref_data = None
        for r in self.refs:
            if r['risid'] == ris_id:
                ref_data = r
        short_dict = {}
        for k in ref_data:
            if len(k) == 2:
                short_dict[k] = ref_data[k]
        reference_editor = QtWidgets.QDialog()
        ui_re = Ui_DialogReferenceEditor()
        ui_re.setupUi(reference_editor)
        ui_re.tableWidget.setColumnCount(2)
        ui_re.tableWidget.setHorizontalHeaderLabels(["RIS", "Data"])
        for row, key in enumerate(short_dict):
            ui_re.tableWidget.insertRow(row)
            ris_item = QtWidgets.QTableWidgetItem(key)
            ris_item.setFlags(ris_item.flags() ^ QtCore.Qt.ItemFlag.ItemIsEditable)
            for tagkey in TAG_KEY_MAPPING:
                #print(tk, TAG_KEY_MAPPING[tk])
                if key == tagkey:
                    ris_item.setToolTip(TAG_KEY_MAPPING[tagkey])
            ui_re.tableWidget.setItem(row, 0, ris_item)
            value_item = QtWidgets.QTableWidgetItem(short_dict[key])
            ui_re.tableWidget.setItem(row, 1, value_item)
        ui_re.tableWidget.resizeColumnsToContents()
        if ui_re.tableWidget.columnWidth(1) > 600:
            ui_re.tableWidget.setColumnWidth(1, 600)
        ui_re.tableWidget.resizeRowsToContents()
        ok = reference_editor.exec()
        if not ok:
            return
        #rows = ui_re.tableWidget.rowCount()
        cur = self.app.conn.cursor()
        ref_edited = False
        for row, key in enumerate(short_dict):
            if ui_re.tableWidget.item(row, 1).text() != short_dict[key]:
                cur.execute("update ris set value=? where risid=? and tag=?",
                            [ui_re.tableWidget.item(row, 1).text(), ris_id, key])
                self.app.conn.commit()
                ref_edited = True
        if ref_edited:
            self.parent_textEdit.append(_("Reference edited."))
        self.get_data()
        self.fill_table_refs()

    def delete_reference(self):
        """ Delete the selected reference.
        Remove reference risid from files.
        """

        ref_row_obj = self.ui.tableWidget_refs.selectionModel().selectedRows()
        if not ref_row_obj:
            return
        ris_id = int(ref_row_obj[0].data())  # Only One index returned. Column 0 data
        note = _("Delete this reference.") + " Ref id {" + str(ris_id) + "}  \n"
        for r in self.refs:
            if r['risid'] == ris_id:
                note += r['vancouver']
        ui = DialogConfirmDelete(self.app, note)
        ok = ui.exec()
        if not ok:
            return
        cur = self.app.conn.cursor()
        cur.execute("update source set risid=null where risid=?", [ris_id])
        cur.execute("delete from ris where risid=?", [ris_id])
        self.app.conn.commit()
        self.get_data()
        self.fill_table_refs()
        self.fill_table_files()
        self.parent_textEdit.append(_("Reference deleted."))

