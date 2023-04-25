"""
Create a DatabaseMenu that can be added to a menubar.

also keep track of the name of current database (by default 'tooth_database.db'), and update the name of the current database to the parent. (i.e. the main window at toothseeker.py)

based on database_menu_v4.py, with styling from database_menu_standalone.py. main added from database_menu_main_test_v4.py
"""

import os
import sys
import platform
from pathlib import Path
from PyQt5.QtWidgets import QAction, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog, QDialog, QApplication, QMainWindow
from PyQt5 import QtGui
import configparser

# own modules:
import toothbase
import helper_functions

class DatabaseMenu:

    def __init__(self, parent):
        self.parent = parent
        self.database_menu = parent.menuBar().addMenu("Database")

        self.new_database_option = QAction("New database", parent)
        self.new_database_option.triggered.connect(self.create_new_database)
        self.database_menu.addAction(self.new_database_option)

        self.select_existing_database_option = QAction("Select existing database", parent)
        self.select_existing_database_option.triggered.connect(self.select_existing_database)
        self.database_menu.addAction(self.select_existing_database_option)

        # initialize the name of the current database
        self.db_path = None
        self.table_name = None
        # Read the config file to get the name of the current database
        self.db_path, self.table_name = self.read_config_file()
        self.update_database_name_at_parent(self.db_path)

    def get_config_file_path(self):
        """Get the path to the config.ini file."""

        """
        # Get the directory of the main script or executable
        if getattr(sys, 'frozen', False):
            # The application is bundled with PyInstaller
            app_dir = os.path.dirname(sys.executable)
        else:
            # The application is running as a script
            app_dir = os.path.dirname(os.path.abspath(__file__))
        """
        app_dir = helper_functions.get_project_root()

        config_file_path = os.path.join(app_dir, 'config.ini')
        print(f"Reading config file from: {config_file_path}")
        return config_file_path

    def read_config_file(self):
        """Read the config file to get the name of the current database"""
        config = configparser.ConfigParser()
        #config.read('config.ini')
        config_file_path = self.get_config_file_path()
        config.read(config_file_path)
        try:
            db_path = config['database']['db_path']
            table_name = config['database']['table_name']
        except KeyError as e:
            raise KeyError(f"Missing section or key in config file: {e}")
        
        return db_path, table_name

    def update_database_name_at_parent(self, db_name):
        """Update the name of the current database to the parent. (i.e. the main window at toothseeker.py)"""

        # get the absolute path of the database (to make sure it works on all platforms)
        db_path = helper_functions.get_absolute_path(db_name)

        self.parent.db_path = db_path

        if os.path.isfile(db_path):
            self.parent.setWindowTitle(f"ToothSeeker   -   {db_name}")
            # open a new tab with the image drop widget for the new database
            self.parent.open_new_imagedrop_tab()
        else:
            self.database_not_found_warning(db_path)
            self.parent.setWindowTitle(f"ToothSeeker   -   {db_name}   <-- (Not found in current folder - please select an existing database or create a new one)")
        print(f"Database selected: {db_path}")

    def database_not_found_warning(self, db_path, parent=None):
        """Show a warning message if the database is not found"""
        print(f"NOTE: Configured database '{db_path}' does not exist in the current folder. Please select an existing database or create a new one.")
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowIcon(QtGui.QIcon('icon.png'))
        msg.setWindowTitle("Configured Database Not Found")
        #msg.setInformativeText(f"The configured database '{db_path}' does not exist in the current folder.\n\nPlease select an existing database, or create a new one.")
        msg.setText(f"The configured database '{db_path}' used previously does not exist in the current folder.\n\nPlease select an existing database, or create a new one.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def update_config_file(self, new_db_path):
        """used to update the new chosen database into the config file"""
        config = configparser.ConfigParser()
        #config.read('config.ini') # Read the existing config file
        config_file_path = self.get_config_file_path()
        config.read(config_file_path)
        config.set('database', 'db_path', new_db_path) # Update an existing key's value
        #with open('config.ini', 'w') as f: # Write the updated config object to the file
        #    config.write(f)
        with open(config_file_path, 'w') as f: # Write the updated config object to the file
            config.write(f)
        print(f"Updated config file '{config_file_path}' with newly selected database: '{new_db_path}'")

    def create_new_database(self):
        # Create a new dialog window
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("New Database")
        
        # Create labels and line edits for input fields
        source_directory_label = QLabel("Folder containing ToothMaker export folders:")
        source_directory_edit = QLineEdit()
        db_path_label = QLabel("Database name:")
        db_path_edit = QLineEdit("tooth_database.db")
        table_name_label = QLabel("Table name:")
        table_name_edit = QLineEdit("images")

        # disable the line edit for the table name, since there is really no need to change it
        table_name_edit.setEnabled(False)
        
        # Create a button to open file explorer
        select_directory_button = QPushButton("Select folder")
        select_directory_button.clicked.connect(lambda: self.open_directory_dialog(source_directory_edit))
        
        # Create layouts for the dialog window
        input_layout = QVBoxLayout()
        input_layout.addWidget(source_directory_label)
        #input_layout.addWidget(source_directory_edit)
        #input_layout.addWidget(select_directory_button)
        # - - - instead of the above: set up a horizontal layout for the line edit and the button
        select_directory_layout = QHBoxLayout()
        select_directory_layout.addWidget(source_directory_edit)
        select_directory_layout.addWidget(select_directory_button)
        input_layout.addLayout(select_directory_layout)
        # - - -
        input_layout.addWidget(db_path_label)
        input_layout.addWidget(db_path_edit)
        input_layout.addWidget(table_name_label)
        input_layout.addWidget(table_name_edit)
        
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        #ok_button.clicked.connect(lambda: self.check_db_inputs(source_directory_edit.text(), db_path_edit.text(), table_name_edit.text(), dialog))
        # instead of the above: use os.path.relpath to get the relative path of the source directory (to ensure that the database can be created and used in any computer)
        #ok_button.clicked.connect(lambda: self.check_db_inputs(os.path.relpath(source_directory_edit.text()), db_path_edit.text(), table_name_edit.text(), dialog))
        # instead of the above: use os.path.basename to get the name of the source directory (to actually ensure that the database can be created and used in any computer)
        ok_button.clicked.connect(lambda: self.check_db_inputs(os.path.basename(source_directory_edit.text()), db_path_edit.text(), table_name_edit.text(), dialog))
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.close)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(input_layout)
        main_layout.addLayout(button_layout)
        
        dialog.setLayout(main_layout)
        
        # Show the dialog window
        dialog.exec_()

    def select_existing_database(self):
        # Open file explorer to choose a file
        file_path, _ = QFileDialog.getOpenFileName(self.parent, "Select database file", "", "Database Files (*.db)")
        
        if file_path:
            #absolute_path = os.path.abspath(file_path)
            #print(f"Absolute path: {absolute_path}")
            #start_directory = os.path.abspath(os.path.dirname(__file__))
            #relative_path = os.path.relpath(absolute_path, start_directory)
            #print(f"Relative path: {relative_path}")
            #print("Selected database file:", relative_path)
            # instead of the above:
            base_name = os.path.basename(file_path)
            print("Selected database file:", base_name)
            # Update the filename into a the class variable
            self.db_path = base_name
            # Update the database name also to the parent class
            self.update_database_name_at_parent(base_name)
            self.update_config_file(base_name)

    def open_directory_dialog(self, edit):
        directory = QFileDialog.getExistingDirectory(self.parent, "Select directory")
        if directory:
            edit.setText(directory)

    def get_relative_path(self, source_directory_name):
        """ get the relative path of the source directory (guick and dirty fix just because macOS sucks)"""
        current_directory = os.getcwd()
        common_prefix = os.path.commonprefix([current_directory, source_directory_name])
        relative_path = source_directory_name[len(common_prefix):]
        
        # Remove leading slash or backslash
        if relative_path.startswith("/") or relative_path.startswith("\\"):
            relative_path = relative_path[1:]

        return relative_path

    def check_db_inputs(self, source_directory_name, db_path, table_name, dialog):
        """
        make sure all inputs are valid, then save them to class variables
        """
        # Check if any variables are missing
        if not source_directory_name or not db_path or not table_name:
            # Show a message box with the missing variable name
            if not source_directory_name:
                message = "Missing source directory name"
            elif not db_path:
                message = "Missing database name"
            else:
                message = "Missing table name"
            QMessageBox.warning(self.parent, "Missing input", message)
        else:
            # Check if the database file already exists
            #db_file_path = os.path.join(source_directory_name, f"{db_path}.db")
            if os.path.isfile(f"{db_path}.db"):
                # Show a message box if the file already exists
                message = f"A database file with the name '{db_path}' already exists in the folder '{os.getcwd()}'"
                QMessageBox.warning(self.parent, "File already exists", message)
            else:
                # Do something with the variables
                print("Source directory name:", source_directory_name)
                print("Database name:", db_path)
                print("Table name:", table_name)
                # Close the dialog window
                dialog.accept()

                # Create the database using toothbase, and save the name of the database to a class variable
                self.db_path, self.table_name = toothbase.construct_database(source_directory_name=source_directory_name, db_path=db_path, table_name=table_name)
                print(f"Database created: {self.db_path}")
                # Update the database name and table name to the parent class
                self.update_database_name_at_parent(self.db_path)
                # Update the config file
                self.update_config_file(self.db_path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Demo window for DatabaseMenu")
        self.setGeometry(100, 100, 400, 100)
        self.database_menu = DatabaseMenu(self)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
