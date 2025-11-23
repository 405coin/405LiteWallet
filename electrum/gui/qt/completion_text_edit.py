
























from PyQt6.QtGui import QTextCursor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCompleter, QPlainTextEdit, QApplication

from .util import ButtonsTextEdit


class CompletionTextEdit(ButtonsTextEdit):

    def __init__(self):
        ButtonsTextEdit.__init__(self)
        self.completer = None
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.disable_suggestions()

    def set_completer(self, completer):
        self.completer = completer
        self.initialize_completer()

    def initialize_completer(self):
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.activated.connect(self.insert_completion)
        self.enable_suggestions()

    def insert_completion(self, completion):
        if self.completer.widget() != self:
            return
        text_cursor = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        text_cursor.movePosition(QTextCursor.MoveOperation.Left)
        text_cursor.movePosition(QTextCursor.MoveOperation.EndOfWord)
        if extra == 0:
            text_cursor.insertText(" ")
        else:
            text_cursor.insertText(completion[-extra:] + " ")
        self.setTextCursor(text_cursor)

    def text_under_cursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        return tc.selectedText()

    def enable_suggestions(self):
        self.suggestions_enabled = True

    def disable_suggestions(self):
        self.suggestions_enabled = False

    def keyPressEvent(self, e):
        if self.isReadOnly():
            return

        if self.is_special_key(e):
            e.ignore()
            return

        QPlainTextEdit.keyPressEvent(self, e)
        if self.isReadOnly():
            return

        ctrlOrShift = ((Qt.KeyboardModifier.ControlModifier in e.modifiers())
                       or (Qt.KeyboardModifier.ShiftModifier in e.modifiers()))
        if self.completer is None or (ctrlOrShift and not e.text()):
            return

        if not self.suggestions_enabled:
            return

        eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
        hasModifier = (e.modifiers() != Qt.KeyboardModifier.NoModifier) and not ctrlOrShift
        completionPrefix = self.text_under_cursor()

        if hasModifier or not e.text() or len(completionPrefix) < 1 or eow.find(e.text()[-1]) >= 0:
            self.completer.popup().hide()
            return

        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def is_special_key(self, e):
        if self.completer and self.completer.popup().isVisible():
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                return True
        if e.key() == Qt.Key.Key_Tab:
            return True
        return False


if __name__ == "__main__":
    app = QApplication([])
    completer = QCompleter(["alabama", "arkansas", "avocado", "breakfast", "sausage"])
    te = CompletionTextEdit()
    te.set_completer(completer)
    te.show()
    app.exec()
