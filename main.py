import sys
import os
import json
import shutil
import re
import resources_rc


from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QPlainTextEdit, QTextEdit,
    QWidget, QVBoxLayout, QSplitter, QToolBar, QAction, QComboBox,
    QLineEdit, QListWidget, QPushButton, QDialog, QFormLayout,
    QDialogButtonBox, QMessageBox, QLabel, QStyle, QMenu, QSizePolicy,
    QHBoxLayout, QFrame, QListView, QScrollBar, QToolButton
)
from PyQt5.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QPainter,
    QTextCursor, QTextFormat, QIcon, QKeySequence, QDesktopServices
)
from PyQt5.QtCore import (
    Qt, QSize, QRegExp, QIODevice, QFile, QTextStream, QUrl
)


if getattr(sys, 'frozen', False):
    # PyInstaller onedir: resources live next to the exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # running “python main.py”
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROFILES_DIR = os.path.join(BASE_DIR, 'profiles')


class Palette:
    COMMENT      = QColor("#A0A0A0")
    G_COMMAND    = QColor("#003366")
    M_COMMAND    = QColor("#800040")
    F_COMMAND    = QColor("#800000")
    S_COMMAND    = QColor("#4B0082")
    T_COMMAND    = QColor("#FF8C00")
    X_AXIS       = QColor("#006666")
    Y_AXIS       = QColor("#008080")
    Z_AXIS       = QColor("#009999")
    OFFSETS      = QColor("#666600")    # I, J, K
    OTHERS       = QColor("#556B2F")    # R, Q, N
    ERROR        = QColor("#FF0000")    # Unrecognized entries
    CHAMFER      = QColor("#8B4513")    # C-commands (brown)
    DWELL        = QColor("#228B22")    # P-commands (forest green)


class GCodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        def make_format(color: QColor, bold=False):
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            if bold:
                fmt.setFontWeight(QFont.Normal)
            return fmt
            
        # G-commands
        self._rules.append((
            QRegExp(r"\bG\d+(\.\d+)?\b"),
            make_format(Palette.G_COMMAND, bold=True)
        ))
        # M-commands
        self._rules.append((
            QRegExp(r"\bM\d+\b"),
            make_format(Palette.M_COMMAND, bold=True)
        ))
        # F-commands
        self._rules.append((
            QRegExp(r"\bF\d+(\.\d+)?\b"),
            make_format(Palette.F_COMMAND)
        ))
        # S-commands
        self._rules.append((
            QRegExp(r"\bS\d+\b"),
            make_format(Palette.S_COMMAND)
        ))
        # T-commands
        self._rules.append((
            QRegExp(r"\bT\d+\b"),
            make_format(Palette.T_COMMAND)
        ))
        # X-axis: allow “X10”, “X10.5”, “X.25”, “X-.75”
        self._rules.append((
            QRegExp(r"\bX-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.X_AXIS)
        ))
        # Y-axis: allow “Y20”, “Y20.0”, “Y.5”, “Y-.25”
        self._rules.append((
            QRegExp(r"\bY-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.Y_AXIS)
        ))
        # Z-axis: allow “Z0”, “Z0.0”, “Z.1”, “Z-.1”
        self._rules.append((
            QRegExp(r"\bZ-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.Z_AXIS)
        ))
        # I, J, K offsets
        self._rules.append((
            QRegExp(r"\b[IJK]-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.OFFSETS)
        ))
        # R, Q, N etc.
        self._rules.append((
            QRegExp(r"\b[RQN]-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.OTHERS)
        ))

        # C = Chamfer
        self._rules.append((
            QRegExp(r"\bC-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.CHAMFER)
        ))

        # F = Feedrate
        self._rules.append((
            QRegExp(r"\bF-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.F_COMMAND)
        ))

        # P = Dwell time
        self._rules.append((
            QRegExp(r"\bP-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.DWELL)
        ))

        # S = Spindle speed
        self._rules.append((
            QRegExp(r"\bS-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.S_COMMAND)
        ))

        # T = Tool selection (integer only, but we’ll allow decimal just in case)
        self._rules.append((
            QRegExp(r"\bT-?(?:\d+(\.\d*)?|\.\d+)\b"),
            make_format(Palette.T_COMMAND)
        ))

        # comment / % — match “;…” comments, “%…” full-line markers, and “(…)” groups
        self._rules.append((
            QRegExp(r";[^\n]*|%[^\n]*|\([^)]*\)"),
            make_format(Palette.COMMENT)
        ))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            i = pattern.indexIn(text, 0)
            while i >= 0:
                length = pattern.matchedLength()
                self.setFormat(i, length, fmt)
                i = pattern.indexIn(text, i + length)


class NumberedTextEdit(QPlainTextEdit):
    """A QPlainTextEdit with a line-number gutter on the left."""
    def __init__(self, parent=None, read_only=False, font_family='Courier', font_size=11):
        super().__init__(parent)
        self.setFont(QFont(font_family, font_size))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setReadOnly(read_only)

        # Gutter setup
        self.lineNumberArea = QWidget(self)
        self.lineNumberArea.paintEvent = self._paintLineNumbers

        self.blockCountChanged.connect(self._updateGutterWidth)
        self.updateRequest    .connect(self._updateGutterArea)
        self._updateGutterWidth(0)

    def _gutterWidth(self):
        lines  = max(1, self.blockCount())
        digits = max(3, len(str(lines)))
        return self.fontMetrics().horizontalAdvance('9') * digits + 10

    def _updateGutterWidth(self, _):
        self.setViewportMargins(self._gutterWidth(), 0, 0, 0)

    def _updateGutterArea(self, rect, dy):
        # always repaint the full gutter so no stale bits remain
        self.lineNumberArea.update(0, 0,
                                   self._gutterWidth(),
                                   self.height())
        if rect.contains(self.viewport().rect()):
            self._updateGutterWidth(0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(cr.left(), cr.top(),
                                        self._gutterWidth(), cr.height())

    def _paintLineNumbers(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor(230,230,230))

        block    = self.firstVisibleBlock()
        blockNum = block.blockNumber()
        top      = int(self.blockBoundingGeometry(block)
                       .translated(self.contentOffset()).top())
        bottom   = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(100,100,100))
                painter.drawText(
                    0, top,
                    self._gutterWidth() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    str(blockNum+1)
                )
            block    = block.next()
            top      = bottom
            bottom   = top + int(self.blockBoundingRect(block).height())
            blockNum += 1


class CodeEditor(NumberedTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent, read_only=False)
        self.setFont(QFont('Courier', 11))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)


class AnnotationPane(NumberedTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent, read_only=True)
        self.setFont(QFont('Courier', 11))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setReadOnly(True)


class DictionaryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ── MACHINE PROFILE FRAME ──
        profile_frame = QFrame(self)
        profile_frame.setObjectName("profileFrame")
        profile_frame.setFrameShape(QFrame.StyledPanel)
        profile_frame.setFrameShadow(QFrame.Raised)
        
        frm_layout = QHBoxLayout(profile_frame)
        frm_layout.setContentsMargins(8, 4, 8, 4)   # tighter inside padding
        frm_layout.setSpacing(6)

        # label
        profile_label = QLabel("Profile:", profile_frame)
        profile_label.setObjectName("profileLabel")
        frm_layout.addWidget(profile_label, 0)

        view = QListView(self)
        view.setObjectName("profileComboView")
        view.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        view.setAutoFillBackground(False)
        view.setAttribute(Qt.WA_OpaquePaintEvent, False)
        view.setAttribute(Qt.WA_TranslucentBackground, False)
        view.setAutoFillBackground(True)      # fill with the white from QSS

        # 2) Hook it up to the combo:
        combo = parent.profile_combo
        combo.setObjectName("profileCombo")
        combo.setView(view)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 3) Add into frame layout:
        frm_layout.addWidget(combo, 1)
        layout.addWidget(profile_frame)

        # 4) Separator below:
        line = QFrame(self)
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # ── SEARCH DICTIONARY ──
        self.filter_box = QLineEdit(self)
        self.filter_box.setObjectName("filterBox")
        self.filter_box.setPlaceholderText("Search dictionary…")
        layout.addWidget(self.filter_box)

        self.list_widget = QListWidget(self)
        # allow custom right-click menus
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.open_context_menu)
        self.list_widget.setObjectName("dictList")
        self.list_widget.setAttribute(Qt.WA_StyledBackground, True)
        layout.addWidget(self.list_widget)

        self.add_button = QPushButton('+ Add Entry', self)
        self.add_button.setObjectName("addEntryButton")
        layout.addWidget(self.add_button)

        self.filter_box.textChanged.connect(self.filter_items)
        self.list_widget.itemDoubleClicked.connect(self.insert_snippet)
        self.add_button.clicked.connect(self.add_entry)

        self.profile = None
        self.entries = {}

    def load_entries(self, profile):
        self.profile = profile
        self.entries = {}
        path = os.path.join(PROFILES_DIR, f"{profile}-dictionary.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                self.entries = json.load(f)
        self.refresh_list()

    def save_entries(self):
        if not os.path.exists(PROFILES_DIR):
            os.makedirs(PROFILES_DIR)
        path = os.path.join(PROFILES_DIR, f"{self.profile}-dictionary.json")
        with open(path, 'w') as f:
            json.dump(self.entries, f, indent=2)

    def refresh_list(self):
        self.list_widget.clear()
        for name in sorted(self.entries.keys()):
            self.list_widget.addItem(name)

    def filter_items(self, text):
       text_lower = text.lower()
       for i in range(self.list_widget.count()):
           item = self.list_widget.item(i)
           name = item.text()
           snippet = self.entries.get(name, '')
           # hide unless text appears in name OR in snippet
           should_hide = (text_lower not in name.lower()
                          and text_lower not in snippet.lower())
           item.setHidden(should_hide)

    def insert_snippet(self, item):
        # 1. Look up the snippet; bail if empty
        snippet = self.entries.get(item.text(), '')
        if not snippet:
            return

        # 2. Grab the MainWindow and its editor
        main_win = self.window()
        editor   = main_win.editor

        # 3. Prepare the text: ensure exactly one newline at the end
        text_to_insert = snippet
        if not text_to_insert.endswith('\n'):
            text_to_insert += '\n'

        # 4. Insert as one edit, then reposition
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.insertText(text_to_insert)
        cursor.endEditBlock()

        # 5. Move the editor’s cursor to here and restore focus
        editor.setTextCursor(cursor)
        editor.setFocus()

    def add_entry(self):
        dlg = DictionaryDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            name, snippet = dlg.get_data()
            self.entries[name] = snippet
            self.save_entries()
            self.refresh_list()

    def open_context_menu(self, pos):
        menu = QMenu(self)
        item = self.list_widget.itemAt(pos)
        # Edit/Delete only if an item was clicked
        if item:
            edit_act = QAction("Edit Entry", self)
            edit_act.triggered.connect(lambda: self.edit_entry(item))
            menu.addAction(edit_act)

            del_act = QAction("Delete Entry", self)
            del_act.triggered.connect(lambda: self.delete_entry(item))
            menu.addAction(del_act)

        # Always allow adding
        add_act = QAction("Add Entry", self)
        add_act.triggered.connect(self.add_entry)
        menu.addAction(add_act)

        menu.exec_(self.list_widget.mapToGlobal(pos))

    def edit_entry(self, item):
        old_name = item.text()
        old_snip = self.entries[old_name]
        dlg = DictionaryDialog(self)
        dlg.name_input.setText(old_name)
        dlg.snippet_input.setPlainText(old_snip)
        if dlg.exec_() == QDialog.Accepted:
            new_name, new_snip = dlg.get_data()
            # prevent duplicates
            if new_name != old_name and new_name in self.entries:
                QMessageBox.warning(self, "Duplicate Entry",
                                    f"An entry named '{new_name}' already exists.")
                return
            # update dict
            self.entries.pop(old_name)
            self.entries[new_name] = new_snip
            self.save_entries()
            self.refresh_list()

    def delete_entry(self, item):
        name = item.text()
        resp = QMessageBox.question(
            self, "Delete Entry",
            f"Delete dictionary entry '{name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if resp == QMessageBox.Yes:
            self.entries.pop(name, None)
            self.save_entries()
            self.refresh_list()


class RoundedPopupListView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("profileComboView")
        # 1) no native frame
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        # 2) allow true transparency
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_StyledBackground)
        # don’t auto-fill—QSS will paint the rounded box
        self.setAutoFillBackground(False)

    def showEvent(self, ev):
        super().showEvent(ev)
        # once know our real size, clip to a rounded rect
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, 6, 6)   # match your QSS radius
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)
        

class DictionaryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        # ── allow QSS to paint our border/background
        self.setObjectName("dictionaryDialog")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle('Dictionary Entry')
        layout = QFormLayout(self)
        self.name_input = QLineEdit(self)
        self.name_input.setObjectName("dialogNameInput")
        self.name_input.setAttribute(Qt.WA_StyledBackground, True)
  
        self.snippet_input = QPlainTextEdit(self)
        self.snippet_input.setObjectName("dialogSnippetInput")
        self.snippet_input.setAttribute(Qt.WA_StyledBackground, True)
        layout.addRow('Name:', self.name_input)
        layout.addRow('Code:', self.snippet_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return self.name_input.text(), self.snippet_input.toPlainText()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('GCodeMaker v1.2 | shopfloor.works')
        self.setWindowIcon(QIcon(':/images/green_g_icon.png'))
        self.resize(1200, 805)
        self.current_file = None
        self.annotation_dict = {}
        self.profiles = []
        self.current_profile = None
        self._syncing = False
        self.init_ui()

    def open_profiles_folder(self):
        # ensure the directory exists
        if not os.path.exists(PROFILES_DIR):
            os.makedirs(PROFILES_DIR)
        # open it in the OS file browser
        QDesktopServices.openUrl(QUrl.fromLocalFile(PROFILES_DIR))


    def init_ui(self):
        self.setup_toolbar()
        self.setup_central()
        self.editor.setFocus()
        self.setup_statusbar()
        self.load_profiles()
        if self.profiles:
            self.set_profile(self.profiles[0])

    def setup_toolbar(self):
        toolbar = QToolBar('Main Toolbar', self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)    # user can’t drag it
        toolbar.setFloatable(False)  # user can’t undock it

        self.addToolBar(toolbar)
        # ── create the profile combo for DictionaryWidget ──
        self.profile_combo = QComboBox(self)
        self.profile_combo.setObjectName("profileCombo")
        self.profile_combo.currentTextChanged.connect(self.set_profile)

        # File actions
        new_act = QAction('New', self)
        new_act.triggered.connect(self.file_new)
        toolbar.addAction(new_act)

        open_act = QAction('Open', self)
        open_act.triggered.connect(self.file_open)
        toolbar.addAction(open_act)

        save_act = QAction('Save', self)
        # give it the standard “Save” shortcut (Ctrl+S)
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self.file_save)
        toolbar.addAction(save_act)

        save_as_act = QAction('Save As', self)
        save_as_act.triggered.connect(self.file_save_as)
        toolbar.addAction(save_as_act)

        toolbar.addSeparator()
        
        # ── Profiles text button ─────────────────────────────────────────────
        profiles_btn = QToolButton(self)
        profiles_btn.setText("Profiles")
        # only show text (no icon placeholder)
        profiles_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        # make it flat/“auto-raise” so it looks like the other toolbar buttons
        profiles_btn.setAutoRaise(True)
        profiles_btn.setToolTip("Open profiles directory")
        profiles_btn.clicked.connect(self.open_profiles_folder)
        toolbar.addWidget(profiles_btn)

    def rename_profile(self):
        # 1. Grab the old name
        old = self.current_profile
        if not old:
            return

        # 2. Prompt for the new name
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Profile",
            f"Enter new name for profile '{old}':",
            text=old
        )
        if not ok:
            return
        new_name = new_name.strip()

        # 3. Validate
        if not new_name:
            QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")
            return
        if new_name in self.profiles and new_name != old:
            QMessageBox.warning(self, "Duplicate Profile",
                                f"A profile named '{new_name}' already exists.")
            return

        # 4. Rename on disk
        prof_dir = PROFILES_DIR
        old_ann = os.path.join(prof_dir, f"{old}-annotations.json")
        old_dict = os.path.join(prof_dir, f"{old}-dictionary.json")
        new_ann = os.path.join(prof_dir, f"{new_name}-annotations.json")
        new_dict = os.path.join(prof_dir, f"{new_name}-dictionary.json")

        try:
            if os.path.exists(old_ann):
                os.rename(old_ann, new_ann)
            if os.path.exists(old_dict):
                os.rename(old_dict, new_dict)
        except OSError as e:
            QMessageBox.critical(self, "Rename Failed",
                                 f"Could not rename files:\n{e}")
            return

        # 5. Update in-memory list and save
        idx = self.profiles.index(old)
        self.profiles[idx] = new_name
        self.save_profiles()

        # 6. Refresh combo and re-select
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profiles)
        self.profile_combo.setCurrentText(new_name)
        self.set_profile(new_name)

    def delete_profile(self):
        prof = self.current_profile
        if not prof:
            return

        # 1. Confirm deletion
        resp = QMessageBox.question(
            self,
            "Delete Profile",
            f"Are you sure you want to delete profile '{prof}'?\n"
            "This will remove its annotations and dictionary files.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        # 2. Remove files
        prof_dir = PROFILES_DIR
        for suffix in ('-annotations.json', '-dictionary.json'):
            path = os.path.join(prof_dir, prof + suffix)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as e:
                QMessageBox.warning(self, "Delete Failed",
                                    f"Could not remove {path}:\n{e}")

        # 3. Remove from list and save
        self.profiles.remove(prof)
        self.save_profiles()

        # 4. Refresh combo
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profiles)

        # 5. Pick a fallback (first in list, or None)
        if self.profiles:
            self.profile_combo.setCurrentText(self.profiles[0])
            self.set_profile(self.profiles[0])
        else:
            self.current_profile = None
            self.annotation_dict = {}
            self.dictionary.load_entries(None)
            self.annotation.clear()

    def setup_central(self):
        splitter = QSplitter(Qt.Horizontal, self)

        # ── Editor pane ─────────────────────────────────────────────────────────
        self.editor = CodeEditor(self)
        self.editor.textChanged.connect(self.on_editor_text_changed)
        self.highlighter = GCodeHighlighter(self.editor.document())
        splitter.addWidget(self.editor)

        # ── Annotation pane ─────────────────────────────────────────────────────
        self.annotation = AnnotationPane(self)
        splitter.addWidget(self.annotation)

        # ── Dictionary pane ─────────────────────────────────────────────────────
        self.dictionary = DictionaryWidget(self)
        splitter.addWidget(self.dictionary)

        # ── Keep horizontal scrollbars visible ──────────────────────────────────
        self.editor   .setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.annotation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # ── Hook up the vertical scrollbars ────────────────────────────────────
        ed_vsb  = self.editor.verticalScrollBar()
        ann_vsb = self.annotation.verticalScrollBar()

        # whenever the *bar itself* moves, drive its partner
        ed_vsb.valueChanged.connect(lambda v: ann_vsb.setValue(v))
        ann_vsb.valueChanged.connect(lambda v: ed_vsb.setValue(v))

        # **and** whenever the *content* scrolls (PageUp/PageDown, wheel, programmatic),
        # update the other pane’s scrollbar to match
        self.editor   .updateRequest.connect(lambda _rect, dy: ann_vsb.setValue(ed_vsb.value()))
        self.annotation.updateRequest.connect(lambda _rect, dy: ed_vsb.setValue(ann_vsb.value()))

        # ── Sync cursor positions & highlights ──────────────────────────────────
        self.editor    .cursorPositionChanged.connect(self._on_editor_cursor_changed)
        self.annotation.cursorPositionChanged.connect(self._on_annotation_cursor_changed)

        # ── Final layout ────────────────────────────────────────────────────────
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

    def _sync_scroll(self, bar: QScrollBar, value: int):
        """
        Set `bar` to `value` without re-emitting valueChanged,
        so that editor and annotation stay locked but don’t loop.
        """
        bar.blockSignals(True)
        bar.setValue(value)
        bar.blockSignals(False)

    def setup_statusbar(self):
        self.statusBar().showMessage('Ready')

    def load_profiles(self):
        # ensure the profiles/ folder exists
        os.makedirs(PROFILES_DIR, exist_ok=True)

        # path to the master list
        json_path = os.path.join(PROFILES_DIR, 'profiles.json')

        if os.path.exists(json_path):
            # load existing profiles
            with open(json_path, 'r') as f:
                self.profiles = json.load(f)
        else:
            # first‐time run → initialize with default
            self.profiles = ['default']
            # write it out via our helper
            self.save_profiles()

        # populate the combo box
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profiles)

    def add_profile(self):
        # 1. Prompt for a new profile name
        name, ok = QInputDialog.getText(
            self,
            "Add Profile",
            "Enter new profile name:"
        )
        if not ok:
            return                        # user cancelled
        name = name.strip()
        
        # 2. Validate
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")
            return
        if name in self.profiles:
            QMessageBox.warning(
                self,
                "Duplicate Profile",
                f"A profile named '{name}' already exists."
            )
            return

        # 3. Append to in-memory list and save to profiles/profiles.json
        self.profiles.append(name)
        self.save_profiles()               # writes profiles/profiles.json

        # 4. Create the two JSON files under profiles/
        profiles_dir = PROFILES_DIR
        # 4a. Annotations – copy default if it exists, else start empty
        src_ann = os.path.join(profiles_dir, f"{self.current_profile}-annotations.json")
        dst_ann = os.path.join(profiles_dir, f"{name}-annotations.json")
        if os.path.exists(src_ann):
            shutil.copyfile(src_ann, dst_ann)
        else:
            with open(dst_ann, 'w') as f:
                json.dump({}, f, indent=2)

        # 4b. Dictionary – start with an empty dict
        dst_dict = os.path.join(profiles_dir, f"{name}-dictionary.json")
        with open(dst_dict, 'w') as f:
            json.dump({}, f, indent=2)

        # 5. Refresh the combo box and select the new profile
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profiles)
        self.profile_combo.setCurrentText(name)
        # Ensure everything reloads for the new profile
        self.set_profile(name)

    def save_profiles(self):
        profiles_json = os.path.join(PROFILES_DIR, 'profiles.json')
        with open(profiles_json, 'w') as f:
            json.dump(self.profiles, f, indent=2)

    def set_profile(self, profile):
        self.current_profile = profile
        # Load annotations
        ann_path = os.path.join(PROFILES_DIR, f"{profile}-annotations.json")
        if os.path.exists(ann_path):
            with open(ann_path, 'r') as f:
                self.annotation_dict = json.load(f)
        else:
            self.annotation_dict = {}

        # after loading self.annotation_dict…
        self.reverse_annotation_map = {}
        for cmd, entry in self.annotation_dict.items():
            # _unwrap(entry) → (desc_text, sub_map)
            desc_text, _ = self._unwrap(entry)
            if desc_text:
                self.reverse_annotation_map[desc_text] = cmd


        # Load dictionary
        self.dictionary.load_entries(profile)
        self.on_editor_text_changed()

    def _unwrap(self, entry):
        """
        entry may be either a str or a dict {desc: str, sub: {...}}.
        Returns (desc: str, sub_map: dict or None).
        """
        if isinstance(entry, dict):
            return entry.get("desc"), entry.get("sub", {})
        else:
            return entry, None


    def describe_line(self, line):
        # 1) Blank or pure-comment lines
        text = line.rstrip('\n')
        stripped = text.strip()
        if not stripped:
            return ''
        if stripped.startswith('(') and stripped.endswith(')'):
            # e.g. "( this is a comment )"
            return f"Comment - {stripped[1:-1]}"
        if stripped.startswith(';'):
            # e.g. "; this is a comment"
            return f"Comment - {stripped[1:].strip()}"
        # —– Program start/stop marker
        if stripped == '%':
           # Look up in the annotations dict, unwrap if needed
           entry = self.annotation_dict.get('%')
           if entry:
               desc, _ = self._unwrap(entry)
               return desc
        if stripped == '/':
            return "Block skip"

        # 2) Extract any inline comments (semicolon **and** parentheses)
        comment = None
        code_part = text

        # –– Semicolon comments
        if ';' in code_part:
            code_part, sem_comment = code_part.split(';', 1)
            comment = sem_comment.strip()

        # –– Parenthesis comments
        paren_comments = re.findall(r'\((.*?)\)', code_part)
        if paren_comments:
            # join multiple (...) if present
            paren_text = ' '.join(paren_comments).strip()
            if comment:
                comment = f"{comment} {paren_text}"
            else:
                comment = paren_text

        # –– Now strip them out of the code
        code_part = re.sub(r'\(.*?\)', '', code_part)

        # —– Extract trailing *nn checksum
        checksum_val = None
        m_chk = re.search(r'\*(\d+)$', code_part)
        if m_chk:
            checksum_val = m_chk.group(1)
            # remove it so tokenization won’t choke
            code_part = code_part[:m_chk.start()]

        # Pure-comment lines (no tokens left)?
        if not code_part.strip():
            return f"Comment - {comment}" if comment else ''

        # 3) Tokenize: grab every letter+number or ,letter+number pair,
        #    even if they're stuck together with no spaces
        raw_code = code_part.strip().upper()
        tokens = re.findall(
            r'(?:,[A-Za-z]+[-+]?(?:\d*\.\d+|\d+))'   # comma-prefixed
          r'|(?:[A-Za-z]+[-+]?(?:\d*\.\d+|\d+))'    # X5.0, G43, etc.
          r'|(?:\#[0-9]+)',                         # macro-vars like #100
            raw_code
        )
        annotations = []
        num_re    = re.compile(r'^([A-Za-z]+)([-+]?(?:[0-9]*\.[0-9]+|[0-9]+))$')
        comma_re  = re.compile(r'^,([A-Za-z]+)([-+]?(?:\d+\.?\d*|\.\d+))$')
        sub_map   = None

        # —– ensure we consumed every character as a valid token —
        #    if not, bail out with Unrecognized command
        raw_nospace = re.sub(r'\s+', '', raw_code)
        if ''.join(tokens) != raw_nospace:
            return "Unrecognized command"

        # 4) Process each token in turn
        for i, tok in enumerate(tokens):
            raw   = tok.strip()
            clean = raw.rstrip('.').upper()

            # —– Macro-variable: “#100”
            if clean.startswith('#'):
                # value is everything after the “#”
                var_num = clean[1:]
                annotations.append(f"Macro variable {clean} = {var_num}")
                continue

            entry = None
            desc  = None
            value = None

            # 4a) comma-prefixed codes (,R1, ,C1, etc.)
            m_c = comma_re.fullmatch(clean)
            if m_c:
                letter, value = m_c.group(1).upper(), m_c.group(2)
                cmd = f",{letter}"
                if i > 0 and sub_map and cmd in sub_map:
                    desc = sub_map[cmd]
                else:
                    entry = self.annotation_dict.get(cmd)

            # 4b) full-token lookup (G80, G00, M06, T1…)
            elif clean in self.annotation_dict:
                cmd, value = clean, None
                entry = self.annotation_dict[cmd]

            # 4c) letter+number fallback (X5.0, Z-1.2, F100…)
            else:
                m = num_re.fullmatch(clean)
                if not m:
                    return "Unrecognized command"
                cmd, value = m.group(1).upper(), m.group(2)
                if i > 0 and sub_map and cmd in sub_map:
                    desc = sub_map[cmd]
                else:
                    entry = self.annotation_dict.get(cmd)

            # 5) If we got a dict entry, unwrap it (desc + new sub_map)
            if entry is not None:
                desc, new_sub = self._unwrap(entry)
                sub_map = new_sub

            # 6) If we still don’t have a description, it’s unknown
            if not desc:
                return "Unrecognized command"

            # 7) Build the annotation text
            if value is not None:
                annotations.append(f"{desc} = {value}")
            else:
                annotations.append(desc)

        # —– If we found a checksum, annotate it too
        if checksum_val is not None:
            annotations.append(f"Checksum = {checksum_val}")

        # 8) If we extracted an inline comment, tack it on
        if comment:
            annotations.append(f"Comment - {comment}")

        # 9) Join all pieces (commands first, then comment)
        result = ", ".join(annotations)
        return result or "Unrecognized command"

    def on_editor_text_changed(self):
        # Mirror every editor line (including blank ones) into the annotation pane
        editor_lines = self.editor.toPlainText().split('\n')
        annotation_lines = []
        for i, line in enumerate(editor_lines, start=1):
            if not line:
                #annotation_lines.append(f"{i}: ")
                annotation_lines.append('')
            else:
                #annotation_lines.append(f"{i}: {self.describe_line(line)}")
                annotation_lines.append(self.describe_line(line))

        self.annotation.blockSignals(True)
        
        cursor = self.annotation.textCursor()
        cursor.beginEditBlock()
        self.annotation.clear()

        for idx, line in enumerate(annotation_lines):
            stripped = line.strip()

            # 1) blank
            if not stripped:
                if idx < len(annotation_lines)-1:
                    cursor.insertBlock()
                continue

            # 2) full-line comment or marker
            if stripped.startswith("Comment") or stripped.startswith("%"):
                fmt = QTextCharFormat()
                fmt.setForeground(Palette.COMMENT)
                cursor.insertText(line, fmt)

            # 3) unrecognized
            elif stripped == "Unrecognized command":
                fmt = QTextCharFormat()
                fmt.setForeground(Palette.ERROR)
                fmt.setFontWeight(QFont.Normal)
                cursor.insertText(line, fmt)

            # 4) one or more annotation parts separated by ", "
            else:
                parts = line.split(", ")
                for i, part in enumerate(parts):
                    # grab just the desc text (before any " =")
                    desc_text = part.split(" =")[0]
                    cmd = self.reverse_annotation_map.get(desc_text)

                    # decide color + bold
                    if cmd and cmd.startswith("G"):
                        color, is_bold = Palette.G_COMMAND, True
                    elif cmd and cmd.startswith("M"):
                        color, is_bold = Palette.M_COMMAND, True
                    elif cmd and cmd.startswith("F"):
                        color, is_bold = Palette.F_COMMAND, False
                    elif cmd and cmd.startswith("S"):
                        color, is_bold = Palette.S_COMMAND, False
                    elif cmd and cmd.startswith("T"):
                        color, is_bold = Palette.T_COMMAND, False
                    elif cmd and cmd.startswith("X"):
                        color, is_bold = Palette.X_AXIS, False
                    elif cmd and cmd.startswith("Y"):
                        color, is_bold = Palette.Y_AXIS, False
                    elif cmd and cmd.startswith("Z"):
                        color, is_bold = Palette.Z_AXIS, False
                    elif cmd and cmd in ("I","J","K"):
                        color, is_bold = Palette.OFFSETS, False
                    elif cmd and cmd in ("R","Q","N"):
                        color, is_bold = Palette.OTHERS, False
                    elif cmd and cmd.startswith("C"):
                        color, is_bold = Palette.CHAMFER, False
                    elif cmd and cmd.startswith("P"):
                        color, is_bold = Palette.DWELL, False
                    else:
                        # fallback (shouldn't happen)
                        color, is_bold = Palette.COMMENT, False

                    fmt = QTextCharFormat()
                    fmt.setForeground(color)
                    if is_bold:
                        fmt.setFontWeight(QFont.Normal)
                    cursor.insertText(part, fmt)

                    # re-insert the comma+space
                    if i < len(parts)-1:
                        cursor.insertText(", ")

            # newline if needed
            if idx < len(annotation_lines)-1:
                cursor.insertBlock()

        cursor.endEditBlock()

        self.annotation.blockSignals(False)
        self.annotation._updateGutterWidth(0)
        self.annotation._updateGutterArea(self.annotation.viewport().rect(), 0)
        
        self.annotation.blockSignals(False)
        self.annotation._updateGutterWidth(0)
        self.annotation._updateGutterArea(self.annotation.viewport().rect(), 0)

        # Now that annotation has the same number of lines,
        # force a cursor/highlight sync to the editor’s current line
        self._on_editor_cursor_changed()

    def file_new(self):
        self.current_file = None
        self.editor.clear()
        self.statusBar().showMessage('New file')

    def file_open(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Open G-code', '', 'G-code Files (*.gcode *.nc);;All Files (*)')
        if fn:
            with open(fn, 'r') as f:
                self.editor.setPlainText(f.read())
            self.current_file = fn
            self.statusBar().showMessage(f'Opened {fn}')

    def file_save(self):
        if not self.current_file:
            return self.file_save_as()
        with open(self.current_file, 'w') as f:
            f.write(self.editor.toPlainText())
        self.statusBar().showMessage(f'Saved {self.current_file}')

    def file_save_as(self):
        fn, _ = QFileDialog.getSaveFileName(self, 'Save G-code', '', 'G-code Files (*.gcode *.nc);;All Files (*)')
        if fn:
            self.current_file = fn
            return self.file_save()

    def _highlight_line(self, widget, line):
        # draw a light-blue full-width selection on “line”
        extra = QTextEdit.ExtraSelection()
        extra.format.setBackground(QColor("#A8D5A2"))
        extra.format.setProperty(QTextFormat.FullWidthSelection, True)

        block = widget.document().findBlockByNumber(line)
        cursor = QTextCursor(block)
        extra.cursor = cursor
        widget.setExtraSelections([extra])

    def _on_editor_cursor_changed(self):
        if self._syncing:
            return
        self._syncing = True

        line = self.editor.textCursor().blockNumber()
        # highlight the editor
        self._highlight_line(self.editor, line)

        # highlight annotation
        self._highlight_line(self.annotation, line)

        self._syncing = False

    def _on_annotation_cursor_changed(self):
        if self._syncing: return
        self._syncing = True

        line = self.annotation.textCursor().blockNumber()
        # highlight annotation
        self._highlight_line(self.annotation, line)

        # highlight editor
        self._highlight_line(self.editor, line)

        self._syncing = False

    def createPopupMenu(self) -> QMenu:
        """
        Disable QMainWindow's default right-click toolbar/dock context menu.
        """
        return QMenu(self)  # empty menu


def main():
    app = QApplication(sys.argv)
    # load the QSS from the compiled resource (:/qss/style.qss)
    qfile = QFile(':/qss/style.qss')
    if qfile.open(QIODevice.ReadOnly | QIODevice.Text):
       stream = QTextStream(qfile)
       app.setStyleSheet(stream.readAll())
       qfile.close()
    else:
       print("WARNING: could not load :/qss/style.qss")
    app.setWindowIcon(QIcon(':/images/green_g_icon.png'))
    app.setFont(QFont('Segoe UI', 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
