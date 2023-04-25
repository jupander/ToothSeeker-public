"""
A widget that accepts just drag-and-drop events and then opens new tab in MainWindow

based on imagedropwidget.py
"""

import os
import sys
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal

# own modules:
import helper_functions


class ImageDropWidgetSimple(QWidget):
    """A widget that accepts just drag-and-drop events and then opens new tab in MainWindow"""

    # signal to be sent to MainWindow, with the variable types (row_id, chosen_param, old_chosen_param)
    new_view_tab_signal = pyqtSignal(int, str, str)

    def __init__(self, db_path):
        super().__init__()

        # name/path of the database
        self.db_path = db_path

        # will store the id of the dropped or selected image file, or id given by user input
        self.given_row_id = None

        # get path of the first image in the database, to be used as example
        conn, c = helper_functions.connect_to_database(db_path)
        example_path = self.get_example_path(conn)
        conn.close()

        # Create a QLabel widget to display the image
        self.image_label = QLabel(self)
        self.image_label.setGeometry(0, 0, self.width(), self.height())
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText(f"Create a new view tab\nfrom the menu above\n\n\n- - -  or  - - -\n\n\nDrag and drop here\nany ToothMaker output screenshot\nthat was included in the creation\nof the currently selected database\n'{db_path}'\n\n(i.e. screenshot inside the folder '{os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(example_path))))}')\n\nExample screenshot from the database:\n'{example_path}'")

        self.image_label.setFont(QFont('Courier', 10))

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        self.setLayout(layout)

        # Enable drag-and-drop events for the widget
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        # Check if the dropped item is a PNG image file
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().endswith('.png'):
                    event.accept()
                    return
        print("Not a .png image file.\n")
        #self.image_label.setText("Not a .png image file.")
        event.ignore()

    def dropEvent(self, event):
        # Get the path of the dropped PNG image file
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().endswith('.png'):
                image_path = url.toLocalFile()
                self.process_image(image_path)
                event.accept()
                return
        event.ignore()

    def get_example_path(self, conn):
        '''Return the first path in the database.'''
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM images LIMIT 1")
        row = cursor.fetchone()
        if row:
            example_path = row[0]
        else:
            print("No rows found in table")
            example_path = 'None found'
        return example_path

    def get_rowid_from_path(self, db_path, image_path):
        '''Connects to the SQLite database located at `db_path`. 
        Returns the rowid of the image located at `image_path`.'''
        conn, c = helper_functions.connect_to_database(db_path)
        print(f"Looking for image path: {image_path} in database '{db_path}'.")
        c.execute('SELECT id FROM images WHERE path = ?', (image_path,))
        try:
            rowid = c.fetchone()[0]
            print(f"\nImage path '{image_path}' found in database '{db_path}'.\nRow id: {rowid}\n")
        except TypeError:
            print(f"\nImage path '{image_path}' not found in database '{db_path}'.\n")
            example_path = self.get_example_path(conn)
            print(f"Example path of an image from the database '{db_path}':\n'{example_path}'\n(^ ^ ^ Note the folder containing the export folders at the start of the path!)\n")
            print(f"It's also possible the image was removed as a duplicate (see '{db_path}___removed_duplicates___<datetime>.csv').\n")
            rowid = None
        conn.close()
        return rowid

    def process_image(self, image_path):
        '''Processes the image located at `image_path`.'''

        print(f"\nReceived PNG image path: {image_path}\n")
        absolute_path = os.path.abspath(image_path)
        #print(f"Absolute path: {absolute_path}")

        if getattr(sys, 'frozen', False):
            # If the script is bundled into an executable using PyInstaller - get relative path to the .exe file (ToothSeeker_v1.exe)
            exe_directory = os.path.dirname(sys.executable)
            print(f".exe directory: {exe_directory}")
            # Calculate the relative path of the image to the .exe file
            relative_path = os.path.relpath(absolute_path, exe_directory)
            print(f"Relative path (to .exe): {relative_path}\n")
        else:
            # If the script is run directly - get relative path to the script
            start_directory = os.path.abspath(os.path.dirname(__file__))
            print(f"Script directory: {start_directory}")
            relative_path = os.path.relpath(absolute_path, start_directory) # TODO - this caused some problems earlier when called by the exe on a university computer, in style of "ValueError: path is on mount '<some network stuff I dunno>', start on mount 'C:'"
            print(f"Relative path (to __file__): {relative_path}\n")

        # Replace the backslashes with double backslashes (to match the format in the database)
        relative_path_with_double_backslashes = r"{}".format(relative_path).replace('\\', '\\\\')
        #print(f"Relative path with double backslashes: {relative_path_with_double_backslashes}")
        #print(r"(path-values in the database are in style of: exports\\export_1\\screenshots\\ToothMaker_0780_0000009000.png)")

        # Get the rowid of the image from the database and save it in self.given_row_id
        self.given_row_id = self.get_rowid_from_path(db_path = self.db_path, image_path = relative_path_with_double_backslashes)
        # TODO: Remove the double backslashes from the databases (?) and then replace the line above with the line below (maybe? what would be the most os-independent solution?)
        #self.given_row_id = self.get_rowid_from_path(db_path = self.db_path, image_path = relative_path)

        # Emit a signal to the main window to create a new tab
        #print(f"typeof(self.given_row_id): {type(self.given_row_id)}")
        if self.given_row_id:
            self.new_view_tab_signal.emit(self.given_row_id, None, None)
        else:
            print("No row id for image with path: '{relative_path_with_double_backslashes}' found in database '{self.db_path}'.")