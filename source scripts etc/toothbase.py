"""
Scans a folder (by default 'exports') 
for ToothMaker output folders (e.g., 'scan_parameters_run_1', 'scan_parameters_run_2'...) 
and combines them into a database file with the data.

When run (and given a name as input), creates a new database file and fills it with data. 
Also creates a csv-file with the same data.

Note, as of now: 
- only works on tribosphenic teeth, triconodont ones break it
- the database is not very flexible, it is hard-coded to the current parameters
- the output folder should include screenshots, as the program expects them
- the output should not include multiple views of the same tooth 
(i.e., option 'Store all orientations' in the ToothMaker scan settings should be off)
(because "KeyError: '00_Anterior'" ('00' expected))
(could perhaps be fixed by tweaking the "image_id_str_list = [re.findall('ToothMaker_(.*)_', path)[0] for path in image_path_list]" to have something else than 'findall')
"""

# TODO: read database column names from a file/list - or make otherwise more flexible

import os
import sqlite3 as db
import re
import pandas as pd
import sys
from datetime import datetime
import csv
import platform

import helper_functions


def construct_database(source_directory_name: str = r'exports', db_path: str = 'tooth_database', table_name: str = 'images', csv_separator: str = ' '):
    """Create a new database file and fill it with data. Also create a csv-file with the same data. 
    Return the database name and table name."""

    # initialize database
    conn, c = init_db(db_path, table_name)

    # process all folders and insert data into table
    process_all_folders(source_directory_name, c, table_name)

    # create csv file
    create_csv(conn, db_path, table_name, csv_separator)
    
    # close connection
    conn.commit()
    conn.close()

    # remove duplicate images (if any)
    remove_duplicate_images(db_path, table_name)

    return db_path, table_name


def init_db(db_name: str = 'tooth_database', table_name: str = 'images'):
    """create a new database file and a table in it."""

    db_path = helper_functions.get_absolute_path(db_name)

    # Create a new SQLite database
    if not os.path.exists(db_path):
        conn = db.connect(db_path)
        print(f"\nDatabase '{db_name}' created at '{db_path}'\n")
    else:
        sys.exit(f"ERROR: Database by the name '{db_name}' already exists at {db_path}! Please use another name for the database to be created.\n")

    #create cursor
    c = conn.cursor()

    # Create a new table to store the image data
    # NOTE: 'Set'-parameter needs single quotes
    c.execute(f'''CREATE TABLE {table_name}
                (id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                model TEXT,
                viewthresh REAL,
                viewmode INTEGER,
                iter INTEGER,
                Egr REAL,
                Mgr REAL,
                Rep REAL,
                Swi REAL,
                Adh REAL,
                Act REAL,
                Inh REAL,
                Sec REAL,
                Da REAL,
                Di REAL,
                Ds REAL,
                Int REAL,
                'Set' REAL,
                Boy REAL,
                Dff REAL,
                Bgr REAL,
                Abi REAL,
                Pbi REAL,
                Lbi REAL,
                Bbi REAL,
                Rad REAL,
                Deg REAL,
                Dgr REAL,
                Ntr REAL,
                Bwi REAL,
                Ina REAL,
                uMgr REAL,
                faulty BOOL);''')
    return conn, c


def read_base_param(folder_path):
    """
    Return a dictionary of the base parameters (key: parameter name, value: parameter value)
    """
    params = []
    #param_file = r'exports/export_1/parameters_base.txt'
    with open(os.path.join(folder_path, 'parameters_base.txt'),'r') as f:
        for i,line in enumerate(f):
            if i in (0,1,2,3,4,9,10): #skip the lines without parameters
                pass
            else:
                params.append(line.strip().split('=='))
    base_param_dict = {param:value for (param, value) in params}
    return base_param_dict


def read_job_param(folder_path):
    """
    Return a dictionary of dictionaries of the job parameters (key: index number, value: dictionary of parameters)
    """
    job_dict = {}
    with open(os.path.join(folder_path, 'job_parameters.txt'),'r') as f:
        n_variables = 0
        param_dict = {}
        for i,line in enumerate(f):
            # if empty line
            if line == '\n':
                continue
            # if 'i:0 --- 0 0 '-line
            elif i%(n_variables+2)==0:
                if i!=0:
                    # append the previous section, initialize the dictionary
                    job_dict.update({idx_nums: param_dict})
                    param_dict = {}
                middle_line = re.findall('i:(.*) ', line)[0]
                #i_num = re.findall('(.*) ---', middle_line)[0]
                idx_nums = re.findall('--- (.*)', middle_line)[0]
                # remove spaces from the index numbers # TODO: figure out how to do inx_nums when more than 9 steps in variables (e.g. 11 1 vs 1 11 -> both '111')
                idx_nums = idx_nums.replace(" ", "")
                if i==0:
                    # study the first line of the file to get the number of variables in this scan
                    n_variables = len(idx_nums.replace("X", ""))
                    #print(f'{i_num} Number of variables: {n_variables}')
            # if parameter line
            else:
                par_name = re.findall('par: (.*),', line)[0]
                par_value = re.findall('val: (.*)', line)[0]
                param_dict.update({par_name: par_value})
        # append the last section
        job_dict.update({idx_nums: param_dict})
    return job_dict


def combine_lists(image_path_list, image_id_str_list, base_param_dict, job_param_dict):
    """
    Return a list of lists, where each list is a row in the database
    """
    master_list = []
    param_names = list(base_param_dict.keys())
    for (path, id_str) in zip(image_path_list, image_id_str_list):
        # 1. and 2. item: id (automatically assigned on insert), image path
        this_row = [path]
        # 3.-33. items: parameters 'model'-'uMgr'
        for param_name in param_names:
            #print('param:', param_name)
            #print('dict:', job_param_dict)
            if param_name in job_param_dict[id_str]:
                this_row.append(job_param_dict[id_str][param_name])
                #print('job:', param_name, job_param_dict[id_str][param_name])
            else:
                this_row.append(base_param_dict[param_name])
                #print('base:', param_name, base_param_dict[param_name])
        # other items:
        this_row.append(0)
        # finally, add row to master_list
        master_list.append(this_row)
    return master_list


def insert_data_to_table(complete_list, c, table_name):
    """
    insert the data from the list into the table
    """
    for row in complete_list:
        c.execute(f"INSERT INTO {table_name} VALUES {str(tuple(row)).replace('(', '(NULL, ')}") # the NULL is for the id
    return


def process_folder(folder_path, c, table_name):
    """
    process one folder and insert the data into the table
    """
    # example folder_path on windows: 'exports_example\example_scan_1'
    # example folder_path on macOS: 'Documents/GitHub/ToothSeeker/exports_example/example_scan_1'
    # to make this also work on macOS:
    if platform.system() == 'Darwin':
        exports_folder_name = os.path.basename(os.path.dirname(folder_path))
        one_scan_folder_name = os.path.basename(folder_path)
        folder_path_from_executable = os.path.join(exports_folder_name, one_scan_folder_name)
    else:
        folder_path_from_executable = folder_path
    # DEBUG
    #print(f"folder_path: {folder_path}")
    #print(f"os.path.basename(os.path.dirname(folder_path)): {os.path.basename(os.path.dirname(folder_path))}")
    #print(f"os.path.basename(folder_path): {os.path.basename(folder_path)}")
    #print(f"os.path.dirname(folder_path): {os.path.dirname(folder_path)}")    
    #print(f"folder_path_from_executable: {folder_path_from_executable}")

    # list of 'exports/export_1/screenshots/ToothMaker_01_0000009000.png' etc.
    #image_path_list = [os.path.join(os.path.join(folder_path, 'screenshots'), filename) for filename in os.listdir(os.path.join(folder_path, 'screenshots'))]
    image_path_list = [os.path.join(os.path.join(folder_path_from_executable, 'screenshots'), filename) for filename in os.listdir(os.path.join(folder_path, 'screenshots'))]
    # list of '01' (meaning tooth 0 1) etc.
    image_id_str_list = [re.findall('ToothMaker_(.*)_', path)[0] for path in image_path_list]
    # dict of 'Di': '0.2000000' etc.
    base_param_dict = read_base_param(folder_path)
    # dict of '01': {'Di': '0.2000000', etc.} etc.
    job_param_dict = read_job_param(folder_path)
    # list of lists, where each list is a row in the database
    complete_list = combine_lists(image_path_list, image_id_str_list, base_param_dict, job_param_dict)
    # insert data into table
    insert_data_to_table(complete_list, c, table_name)
    return


def process_all_folders(source_directory_name, c, table_name):
    """
    process all folders in the source_directory_name and insert the data into the table
    """
    # to make this work also in macOS...
    #source_directory_path = helper_functions.get_absolute_path(source_directory_name)
    if platform.system() == 'Darwin':
        app_dir = os.path.dirname(os.path.relpath(sys.argv[0]))
        source_directory_rel_path = os.path.join(app_dir, source_directory_name)
        source_directory_path = source_directory_rel_path
    else:
        source_directory_path = source_directory_name

    #print(f"source_directory_rel_path: '{source_directory_rel_path}'")
    #for item in os.listdir(source_directory_rel_path):
    #    print(f"item in os.listdir(source_directory_rel_path): '{item}'")
    
    #for item in os.listdir(source_directory_name):
    for export_folder_of_one_scan in os.listdir(source_directory_path):
        #item_path = os.path.join(source_directory_name, export_folder_of_one_scan)
        folder_path = os.path.join(source_directory_path, export_folder_of_one_scan)
        #print(f"source_directory_path: '{source_directory_path}'")
        #print(f"export_folder_of_one_scan: '{export_folder_of_one_scan}'")
        #print(f"folder_path: '{folder_path}'")
        if os.path.isdir(folder_path):  # Check if the item is a directory
            process_folder(folder_path, c, table_name)
            print(f"Processed folder '{export_folder_of_one_scan}'")
    print(f"Processed all folders in '{source_directory_name}'\n")
    return

def create_csv(conn, db_path: str, table_name: str, csv_separator: str = ' '):
    """
    also copy the database data into a .csv file
    """
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    #df.to_csv(f"{db_path.replace('db', 'csv')}", index=None, sep=csv_separator, mode='a')
    output_file_path = helper_functions.get_absolute_path(f"{db_path.replace('db', 'csv')}")
    df.to_csv(output_file_path, index=None, sep=csv_separator, mode='a')

    print(f"Processed data also exported into '{db_path.replace('db', 'csv')}'\n")


def remove_duplicate_images(db_path, table_name = 'images'):
    #conn = db.connect(db_path)
    #c = conn.cursor()
    # the above caused a new database being created at home folder on macOS, the below should work on all platforms:
    conn, c = helper_functions.connect_to_database(db_path)

    # Identify duplicate rows based on all columns except 'id' and 'path'
    c.execute(f'''
        SELECT 
            t1.min_id,
            t1.id,
            t1.path,
            t1.min_path
        FROM (
            SELECT
                MIN(id) OVER (PARTITION BY model, viewthresh, viewmode, iter, Egr, Mgr, Rep, Swi, Adh, Act, Inh, Sec, Da, Di, Ds, Int, "Set", Boy, Dff, Bgr, Abi, Pbi, Lbi, Bbi, Rad, Deg, Dgr, Ntr, Bwi, Ina, uMgr, faulty) AS min_id,
                MIN(path) OVER (PARTITION BY model, viewthresh, viewmode, iter, Egr, Mgr, Rep, Swi, Adh, Act, Inh, Sec, Da, Di, Ds, Int, "Set", Boy, Dff, Bgr, Abi, Pbi, Lbi, Bbi, Rad, Deg, Dgr, Ntr, Bwi, Ina, uMgr, faulty) AS min_path,
                id,
                path,
                model, viewthresh, viewmode, iter, Egr, Mgr, Rep, Swi, Adh, Act, Inh, Sec, Da, Di, Ds, Int, "Set", Boy, Dff, Bgr, Abi, Pbi, Lbi, Bbi, Rad, Deg, Dgr, Ntr, Bwi, Ina, uMgr, faulty
            FROM {table_name}
        ) AS t1
        WHERE t1.id != t1.min_id
        ORDER BY t1.min_id
    ''')

    duplicates = c.fetchall()

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    csv_file = f"{os.path.basename(db_path)}___removed_duplicates___{timestamp}.csv"
    # to make this work also in macOS...
    csv_file_abs_path = helper_functions.get_absolute_path(csv_file)
    # Export duplicate pairs and removed rows to a CSV file
    with open(csv_file_abs_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['min_id', 'id', 'path', 'status'])
        for idx, dup in enumerate(duplicates):
            if idx == 0 or dup[0] != duplicates[idx - 1][0]:
                writer.writerow([dup[0], dup[0], dup[3], 'preserved'])
            writer.writerow([dup[0], dup[1], dup[2], 'removed'])

    # Remove duplicate rows with greater id values
    c.execute(f'''
        DELETE FROM {table_name}
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id
                FROM {table_name}
                WHERE (model, viewthresh, viewmode, iter, Egr, Mgr, Rep, Swi, Adh, Act, Inh, Sec, Da, Di, Ds, Int, "Set", Boy, Dff, Bgr, Abi, Pbi, Lbi, Bbi, Rad, Deg, Dgr, Ntr, Bwi, Ina, uMgr, faulty)
                IN (
                    SELECT model, viewthresh, viewmode, iter, Egr, Mgr, Rep, Swi, Adh, Act, Inh, Sec, Da, Di, Ds, Int, "Set", Boy, Dff, Bgr, Abi, Pbi, Lbi, Bbi, Rad, Deg, Dgr, Ntr, Bwi, Ina, uMgr, faulty
                    FROM {table_name}
                    GROUP BY model, viewthresh, viewmode, iter, Egr, Mgr, Rep, Swi, Adh, Act, Inh, Sec, Da, Di, Ds, Int, "Set", Boy, Dff, Bgr, Abi, Pbi, Lbi, Bbi, Rad, Deg, Dgr, Ntr, Bwi, Ina, uMgr, faulty
                    HAVING COUNT(*) > 1
                ) AND id NOT IN (
                    SELECT MIN(id)
                    FROM {table_name}
                    GROUP BY model, viewthresh, viewmode, iter, Egr, Mgr, Rep, Swi, Adh, Act, Inh, Sec, Da, Di, Ds, Int, "Set", Boy, Dff, Bgr, Abi, Pbi, Lbi, Bbi, Rad, Deg, Dgr, Ntr, Bwi, Ina, uMgr, faulty
                    HAVING COUNT(*) > 1
                )
            )
        )
    ''')

    conn.commit()
    conn.close()
    
    print(f"Duplicate rows removed and exported to '{csv_file}' at {csv_file_abs_path}\n")


def get_names():
    """
    Ask the user for exports directory, database name, table name and return the input
    """

     # get exports directory
    default_source_directory_name=r'exports'
    source_directory_name = input(f"\nDefault input directory path or name: '{default_source_directory_name}' \nConfirm by pressing enter, or give another input directory path: ")
    if not source_directory_name:
        source_directory_name = default_source_directory_name
        print('Confirmed default input directory path.\n')

    # get database name
    default_db_path = 'tooth_database.db'
    while True:
        db_path_input = input(f"\nDefault export database name: '{default_db_path}' \nAccept by pressing enter, or give another name for the database to be created (without the .db): ")
        if not db_path_input:
            db_path = default_db_path
            print(f'Accepted default database name: {db_path}\n')
        else:
            db_path = db_path_input + '.db'
        
        # check if a database by that name already exists
        if not os.path.exists(db_path):
            break
        else:
            print(f"Database by the name '{db_path}' already exists! Please use another name for the database to be created.\n")
            
    # get table name
    default_table_name = 'images'
    table_name = input(f"\nDefault table name: '{default_table_name}' \nAccept by pressing enter, or give another name for the table to be created: ")
    if not table_name:
        table_name = default_table_name
        print(f'Table name: {table_name}\n')

    return source_directory_name, db_path, table_name


if __name__ == "__main__":

    # get the names needed
    source_directory_name, db_path, table_name = get_names()
    
    # just do it
    construct_database(source_directory_name=source_directory_name, db_path=db_path, table_name=table_name)