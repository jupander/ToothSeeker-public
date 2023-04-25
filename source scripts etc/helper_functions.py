"""
These help.
"""

import sqlite3
from numpy import random
import os
import sys
import platform
from datetime import datetime

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QDialog, QLineEdit, QHBoxLayout
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import Qt, QRegExp

def get_project_root():
    """Returns project root folder."""
    if getattr(sys, 'frozen', False):
        # The application is bundled with PyInstaller
        if platform.system() == 'Darwin':
            # Mac OS
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        else:
            # Windows
            app_dir = os.path.dirname(sys.executable)
    else:
        # The application is running as a script
        app_dir = os.path.dirname(os.path.abspath(__file__))
    #print(f"debug - app_dir by get_project_root: {app_dir}")
    return app_dir

def get_absolute_path(local_path):
    '''Returns the correct path to the given local path, depending on whether the application is running as a script or as a bundled executable.'''
    app_dir = get_project_root()
    #print(f"debug - path given as argument to get_correct_path: {local_path}")
    absolute_path = os.path.join(app_dir, local_path)
    #print(f"debug - correct_path after joining with app_dir: {correct_path}")

    return absolute_path

def connect_to_database(db_name):
    '''Connects to the database and returns the connection and cursor objects.'''

    db_path = get_absolute_path(db_name)

    if not os.path.isfile(db_path):
        print(f"Note: Configured database '{db_name}' does not exist. Please select an existing database or create a new one.\n")
        return None, None
    else:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        return conn, c

def check_database_max_row(db_path):
    conn, c = connect_to_database(db_path)
    if not conn:
        print(f"Could not connect to database '{db_path}'\n")
        return None
    c.execute('SELECT COUNT(*) FROM images')
    max_row = c.fetchone()[0]
    conn.close()
    return max_row

def row_exists_in_database(db_path, row_id):
    conn, c = connect_to_database(db_path)
    c.execute('SELECT 1 FROM images WHERE rowid=?', (row_id,))
    row_exists = c.fetchone() is not None
    conn.close()
    return row_exists

def save_input_value(value, input_window, db_path, row_id_ref):
    
    max_row = check_database_max_row(db_path)
    if not max_row:
        print(f"Error: No max row found for database '{db_path}' - does the database exist?\n")
        print(f"Closing input window...\n")
        input_window.close()
        return

    value = int(value)

    if value == 0:
        while True:
            random_id = random.randint(1, max_row)
            if row_exists_in_database(db_path, random_id):
                row_id_ref[0] = random_id
                print(f'Randomized row id (1...{max_row}): {random_id}\n')
                break
    elif value > max_row:
        print(f"Given row id {value} > {max_row} (the largest row id in the database '{db_path}'). Please try another.\n")
    elif row_exists_in_database(db_path, value):
        row_id_ref[0] = value
        print(f'Given base image row id: {row_id_ref[0]}\n')
    else:
        print(f"Image by row id {value} not found in database '{db_path}'. Please try another.\n")

    if row_id_ref[0] is not None:
        input_window.close()


def ask_row_id(db_path, parent=None):
    row_id_ref = [None]

    input_window = QDialog(parent)
    input_window.setWindowTitle('Input image id')
    input_window.setModal(True)

    input_box = QLineEdit(input_window)
    input_box.setValidator(QRegExpValidator(QRegExp('\d+'), input_box))
    input_box.textChanged.connect(lambda: ok_button.setEnabled(input_box.hasAcceptableInput()))

    button_layout = QHBoxLayout()
    ok_button = QPushButton('OK')
    ok_button.setDefault(True)
    ok_button.setEnabled(False)
    ok_button.clicked.connect(lambda: save_input_value(input_box.text(), input_window, db_path, row_id_ref))
    button_layout.addWidget(ok_button)

    layout = QVBoxLayout(input_window)
    num_label = QLabel('Enter the row id of the image\nto be fetched from the database:\n(or input 0 for a random image)')
    num_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(num_label, alignment=Qt.AlignCenter)
    layout.addWidget(input_box)
    layout.addLayout(button_layout)

    input_window.exec_()

    return row_id_ref[0]


def create_param_name_dict():
    '''Creates a dictionary of param_name and their full names. (e.g. 'Bbi': 'Buccal bias')
    Returns the dictionary.'''
    
    param_name_dict = {'iter': 'iterations', 'Egr': 'Epithelial proliferation rate', 'Mgr': 'Mesenchymal proliferation rate', 
                    'Rep': "Young's modulus (stiffness)", 'Swi': 'Distance from 0 where the borders are defined', 
                    'Adh': 'Traction between neighbours', 'Act': 'Activator auto-activation', 'Inh': 'Inhibition of activator', 
                    'Sec': 'Growth factor secretion rate', 'Da': 'Activator diffusion rate', 'Di': 'Inhibitor diffusion rate', 
                    'Ds': 'Growth factor diffusion rate', 'Int': 'Initial inhibitor threshold.', 'Set': 'Growth factor threshold', 
                    'Boy': 'Mesenchyme mechanic resistance', 'Dff': 'Differentiation rate', 'Bgr': 'Border growth, amount of mes. in ant.-post.', 
                    'Abi': 'Anterior bias', 'Pbi': 'Posterior bias', 'Lbi': 'Lingual bias', 'Bbi': 'Buccal bias', 'Rad': 'Radius of initial conditions', 
                    'Deg': 'Protein degradation rate', 'Dgr': 'Downward vector of growth', 'Ntr': 'Mechanical traction from the borders to the nucleus', 
                    'Bwi': 'Width of border', 'Ina': 'Initial activator concentration', 'uMgr': 'Basal mesenchymal proliferation rate'}
    
    return param_name_dict


def export_row_to_file(db_path, row_id):
    """Exports the parameters of a database row into a text file, which can be imported into ToothMaker."""

    # Connect to the database
    conn, c = connect_to_database(db_path)

    # Query the database for the row with the given ID
    c.execute(f"SELECT * FROM images WHERE id=?", (int(row_id),))
    row = c.fetchone()

    # Check if the row was found
    if row is None:
        print(f"No row with ID {row_id} found in table 'images' of database '{db_path}'.")
        return

    # Create a dictionary with parameter names and values
    params = {
        "model": row[2],
        "viewthresh": row[3],
        "viewmode": row[4],
        "iter": row[5],
        "Egr": row[6],
        "Mgr": row[7],
        "Rep": row[8],
        "Swi": row[9],
        "Adh": row[10],
        "Act": row[11],
        "Inh": row[12],
        "Sec": row[13],
        "Da": row[14],
        "Di": row[15],
        "Ds": row[16],
        "Int": row[17],
        "Set": row[18],
        "Boy": row[19],
        "Dff": row[20],
        "Bgr": row[21],
        "Abi": row[22],
        "Pbi": row[23],
        "Lbi": row[24],
        "Bbi": row[25],
        "Rad": row[26],
        "Deg": row[27],
        "Dgr": row[28],
        "Ntr": row[29],
        "Bwi": row[30],
        "Ina": row[31]
    }

    # Create the 'exported_parameters' folder if it doesn't exist
    #if not os.path.exists('exported_parameters'):
    #    os.makedirs('exported_parameters')
    # to make it work on macOS too:
    exported_parameter_folder_path = get_absolute_path('parameters_exported_to_txt')
    if not os.path.exists(exported_parameter_folder_path):
        os.makedirs(exported_parameter_folder_path)

    # Create the output file path
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_file_name = f"id-{row_id}___{os.path.basename(db_path)}___{timestamp}.txt"
    output_file_path = os.path.join(exported_parameter_folder_path, output_file_name)

    # Write the parameters to the output file
    with open(output_file_path, "w", newline='\n') as file:
        file.write("# Model parameters file generated by Toothseeker! (in style of ones created by MorphoMaker 0.6.4.)\n")
        file.write("# NOTE: Parameter names are case-sensitive, while non-parameter keywords\n")
        file.write("# (e.g. model, viewtresh) are case-insensitive!\n\n")

        file.write("# Model name, view threshold, view mode, iterations.\n")
        file.write(f"model=={params['model']}\n")
        file.write(f"viewthresh=={params['viewthresh']}\n")
        file.write(f"viewmode=={params['viewmode']}\n")
        file.write(f"iter=={params['iter']}\n\n")


        file.write("# Parameters.\n")
        for param, value in params.items():
            if param not in {'model', 'viewthresh', 'viewmode', 'iter'}:
                file.write(f"{param}=={value}\n")

    # Close the database connection
    conn.close()

    print(f"Parameters of row {row_id} from database '{db_path}' successfully exported to '{output_file_path}'.")