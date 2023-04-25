"""
stacker.py refactored as a class StackView
"""

import os
import sys
import platform
import numpy as np
import pyqtgraph as pg
from PIL import Image
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMenu, QGridLayout, QVBoxLayout, QDialog, QMainWindow, QRadioButton, QButtonGroup
from PyQt5.QtGui import QFont

# own modules:
import helper_functions
#import n_hotkey

class StackView(QWidget):
    """A widget that displays a stack of images, each of which is a row in the database table 'images'."""

    # signal to be sent to MainWindow, with the variable types (row_id, chosen_param, old_chosen_param)
    new_view_tab_signal = pyqtSignal(int, str, str)

    def __init__(self, db_path, row_id, chosen_param=None, old_chosen_param=None, parent=None):
        super(StackView, self).__init__(parent)

        if not row_id:
            raise ValueError("The row_id argument must be given.")

        self.db_path = db_path
        self.conn, self.c = helper_functions.connect_to_database(self.db_path)
        
        self.row_id = row_id

        if not chosen_param:
            self.chosen_param = self.show_pick_axis_param_option_window(self.c, self.row_id, old_chosen_param)
        else:
            self.chosen_param = chosen_param

        self.init_ui(self.c, self.row_id, self.chosen_param)


    # -------- ... (all other methods remain the same, just change their names to be methods of the class): -----------

    def check_if_row_id_exists(self, c, row_id):
        '''Checks if `row_id` exists in the images table using the given cursor object `c`.
        Returns `True` if the row exists, `False` otherwise.'''

        c.execute("SELECT * FROM images WHERE id=?", (int(row_id),))
        return bool(c.fetchone())

    def check_if_chosen_param_exists(self, c, chosen_param):
        '''Checks if `chosen_param` exists in the images table using the given cursor object `c`.
        Returns `True` if the column exists, `False` otherwise.'''

        all_column_names = [description[0] for description in c.description]
        return chosen_param in all_column_names and chosen_param not in ['id', 'path']

    def find_rows_differing_by_param(self, c, row_id: int, chosen_param: str):
        '''Finds rows in the 'images' table that differ from the row with id `row_id` _only_ by the chosen parameter.
        Returns the base_row and a list of tuples (representing the rows satisfying the properties).'''

        # Fetch the base row
        c.execute("SELECT * FROM images WHERE id=?", (int(row_id),))
        base_row = c.fetchone()

        all_column_names = [description[0] for description in c.description]
        column_indices = [i for i in range(len(all_column_names)) if all_column_names[i] not in ['id', 'path', chosen_param]]
        column_values = [base_row[i] for i in column_indices]
        query_params = tuple([int(row_id), base_row[all_column_names.index(chosen_param)]] + column_values)
        query_string = F"SELECT * FROM images WHERE id != ? AND `{chosen_param}` != ? AND " + " AND ".join([f"`{all_column_names[i]}` = ?" for i in column_indices])
        #print(f"query_string: {query_string}")
        #print(f"query_params: {query_params}")
        c.execute(query_string, query_params)
        rows = c.fetchall()

        return base_row, rows

    def stack_images(self, c, base_row, rows, chosen_param):
        '''Stacks PNG images into a 3D numpy array.
        Returns the 3D numpy array, array of the image ids, and array of chosen_param column values in sorted order.'''

        # to make this work also on macOS:
        app_dir = helper_functions.get_project_root()

        images = []
        all_column_names = [description[0] for description in c.description]
        #print(all_column_names)
        for row in [base_row] + rows:
            #img_path = os.path.join(row[1])
            img_path = os.path.join(app_dir, row[1])
            #print(row)
            #print(img_path)
            img = np.array(Image.open(img_path))
            img = img.transpose((1, 0, 2))  # Transpose the images 90 degrees clockwise to get them straight
            img_id = row[all_column_names.index('id')]
            chosen_param_value = row[all_column_names.index(chosen_param)]
            #images.append((img, chosen_param_value))
            images.append((img, img_id, chosen_param_value))
        images.sort(key=lambda x: x[2])
        arr = np.stack([img for img, _, _ in images], axis=0)

        # Get values of chosen_param in sorted order
        chosen_param_values = np.array([val for _, _, val in images])
        # Get image ids in sorted order
        img_ids = np.array([val for _, val, _ in images])

        return arr, img_ids, chosen_param_values

    def create_image_view(self, arr, chosen_param_values, show_histogram=False):
        '''Creates an instance of the ImageView class using the given 3D numpy array `arr` and an array of chosen_param column values.
        Returns the ImageView object.'''

        # Create an instance of the ImageView class
        view = pg.ImageView()

        # hide the histogram and ROI buttons
        if show_histogram: view.ui.histogram.show();view.ui.roiBtn.show();view.ui.menuBtn.show()
        else: view.ui.histogram.hide();view.ui.roiBtn.hide();view.ui.menuBtn.hide()

        # Display the 3D image using the ImageView
        view.setImage(arr, xvals=chosen_param_values)

        return view

    def create_info_labels(self, c, view, img_ids, chosen_param_values, chosen_param,  my_font = QFont('Courier', 10)):
        """Creates labels for showing the current image id and chosen_param value, and the values and counts of neighbors for each parameter.
        Returns the position_label, param_value_labels, and param_count_labels."""
        # ------------------ Create label for showing the current image id and chosen_param value ------------------

        # Create a label showing information about the current image, or slider position
        position_label = QLabel("Use arrow keys to move the slider")
        position_label.setFont(my_font)

        # Create a dictionary mapping chosen_param column name to their full name
        param_name_dict = helper_functions.create_param_name_dict()
        # change in slider position updates the bottom info label
        view.sigTimeChanged.connect(lambda index = view.currentIndex: position_label.setText(f"{int(view.currentIndex)+1:>4}/{str(view.nframes()):<4}     id: {img_ids[index]:<6}    {param_name_dict[chosen_param]} ({chosen_param}): {chosen_param_values[index]:<12}"))


        # ------------------ Create labels for showing the values and counts of neighbors for each parameter ------------------

        # Create lists of labels for showing values and counts of neighbors for each parameter (these will be updated to match the current image when the slider is moved)
        param_value_labels = [QLabel(f" ") for _ in range(5,33)]
        nb_count_labels = [QLabel(f" ") for _ in range(5,33)]
        
        # create lists of strings for the side labels, len(list) = len(img_ids)
        param_value_strings_per_img, nb_count_strings_per_img = self.create_param_info_per_slider_index(c, img_ids, chosen_param)

        # for updating the label columns
        def update_labels(index, param_value_strings_per_img, nb_count_strings_per_img, param_value_labels, nb_count_labels):
            [label.setText(f"{param_value_strings_per_img[index][i]}") for i, label in enumerate(param_value_labels)]
            [label.setText(f"{nb_count_strings_per_img[index][i]}") for i, label in enumerate(nb_count_labels)]
            #[label.show() if label.text() != '(0)' else label.hide() for label in nb_count_labels]
            #[label.setFont(my_font) if label.text() != '(0)' else label.setStyleSheet("color: grey;") for label in nb_count_labels]
            [label.setStyleSheet("color: grey;") if label.text() != '(0)' else label.setStyleSheet("color: white;") for label in nb_count_labels]
            return
        
        # update the label columns once at the beginning
        update_labels(view.currentIndex, param_value_strings_per_img, nb_count_strings_per_img, param_value_labels, nb_count_labels)

        # slider position change triggers updating the label columns
        view.sigTimeChanged.connect(lambda index = view.currentIndex: update_labels(index, param_value_strings_per_img, nb_count_strings_per_img, param_value_labels, nb_count_labels))


        # ------------------ Style the labels ------------------
        # Style the labels
        for label_1, label_2 in zip(param_value_labels, nb_count_labels):
            # TODO: font size, different colors!
            label_1.setFont(my_font)
            #label_1.mousePressEvent = lambda event, name=label_1.text() : print(f"clicked {re.sub(':.*', '', f'{name}')}") # TODO: new parameter
            # TODO: font size, different colors!
            label_2.setFont(my_font)
            #label_2.mousePressEvent = lambda event: print(f"clicked {re.sub(':.*', '', f'{label_1.text()}')}")

        return position_label, param_value_labels, nb_count_labels


    def show_pick_axis_param_option_window(self, c, row_id, old_chosen_param=None, my_font=QFont('Courier', 10)):
        '''Creates a window with a list of parameters to choose from. The window is closed when the user selects a radio button.
        Returns the name of the chosen parameter.'''

        def create_param_button(param_name, key, nb_count, my_font, radio_button_group, param_id):
            param_button = QRadioButton(f"{key:>4} - {param_name:<51} {nb_count}")
            param_button.setFont(my_font)
            radio_button_group.addButton(param_button)
            radio_button_group.setId(param_button, param_id)
            return param_button

        picked_param = None

        # Create a QDialog for the window
        pick_axis_param_option_window = QDialog()
        pick_axis_param_option_window.setWindowTitle("Pick axis parameter")

        # Create a QVBoxLayout to hold the labels
        param_buttons_layout = QVBoxLayout()

        _, nb_count_strings_per_img = self.create_param_info_per_slider_index(c, img_ids=row_id)

        # Create a QButtonGroup to group radio buttons
        radio_button_group = QButtonGroup()

        # Create a radio button for each parameter
        param_name_dict = helper_functions.create_param_name_dict()
        button_count = 0
        #print(nb_count_strings_per_img)
        for i, (key, nb_count) in enumerate(zip(param_name_dict.keys(), nb_count_strings_per_img[0])):
            if nb_count != '(0)' and key != old_chosen_param:
                param_name = param_name_dict[key]
                param_button = create_param_button(param_name, key, nb_count, my_font, radio_button_group, i)
                param_buttons_layout.addWidget(param_button)
                button_count += 1

        if button_count == 0:
            # No radio buttons to show
            print("No axis parameter options to show.")
            return None

        # Connect radio_button_group's buttonClicked signal to close the window and set the picked_param
        radio_button_group.buttonClicked[int].connect(lambda param_id: pick_axis_param_option_window.done(param_id))

        # Create a QVBoxLayout to hold the radio buttons
        vbox_layout = QVBoxLayout()
        vbox_layout.addLayout(param_buttons_layout)

        pick_axis_param_option_window.setLayout(vbox_layout)

        # Show the window and wait for it to close
        result = pick_axis_param_option_window.exec_()
        if result == QDialog.Rejected:
            # The QDialog was closed without selecting a parameter
            print("Window closed without selecting a parameter.")
            return None
        elif result >= 0 and result < len(param_name_dict):
            picked_param = list(param_name_dict.keys())[result]
            print(f"Base image id: {row_id}\nChosen axis parameter: {picked_param}\n")

        return picked_param


    def create_context_menu(self, view, img_ids, chosen_param):
        """Creates a context menu that opens when the given ImageView is clicked.
        Returns the context menu."""

        # initialize id of the image that was clicked (filled by the mousePressEvent function)
        row_id = None

        # Create a context menu
        context_menu = QMenu(view)
        action_new_base_img = context_menu.addAction("Choose as new base image")
        action_export_parameters = context_menu.addAction("Export parameters to txt")
        context_menu.addAction("Cancel")

        def mousePressEvent(event):
            if event.button() == 2:  # Left mouse button
                # store the id of the image that was clicked
                nonlocal row_id
                row_id = img_ids[view.currentIndex]
                # Convert the position of the mouse click to global coordinates
                global_pos = view.mapToGlobal(event.pos())
                # Show the context menu at the global position
                context_menu.exec_(global_pos)

        view.mousePressEvent = mousePressEvent

        # Connect the context menu actions to functions
        action_new_base_img.triggered.connect(lambda event: self.emit_new_view_tab_signal(row_id, new_chosen_param=None, old_chosen_param=chosen_param))
        action_export_parameters.triggered.connect(lambda event: helper_functions.export_row_to_file(db_path=self.db_path, row_id=row_id))

        return
    
    ''' # TODO: N-key press event, not working yet
    def connect_n_key_to_new_tab(self, view, img_ids, chosen_param):
        """Connects the N-key press event on the given ImageView to emit a signal for a new view tab.
        Does not change the widget's reaction to any other events."""

        key_press_filter = n_hotkey.KeyPressFilter(view, img_ids, chosen_param)
        view.installEventFilter(key_press_filter)
    '''
    
    def emit_new_view_tab_signal(self, row_id, new_chosen_param=None, old_chosen_param=None):
        self.new_view_tab_signal.emit(row_id, new_chosen_param, old_chosen_param)


    def create_view_widget_and_layouts(self, view, position_label, param_value_labels, nb_count_labels):
        '''Creates a QWidget and sets the layouts for the given ImageView `view` and surrounding labels.
        Returns the QWidget object 'view_widget.'''

        # ------------------ Create a QWidget for the ImageView ------------------
        
        # Create a QWidget for the ImageView
        view_widget = QWidget()
        view_widget.adjustSize()

        # Add the ImageView to the QWidget
        param_value_layout = QVBoxLayout()
        nb_count_layout = QVBoxLayout()
        view_layout = QVBoxLayout()

        view_layout.addWidget(view)
        view_layout.addWidget(position_label, alignment=Qt.AlignLeft)
        for label in param_value_labels:
            param_value_layout.addWidget(label)
        for label in nb_count_labels:
            nb_count_layout.addWidget(label)
        
        outer_layout = QGridLayout()
        outer_layout.addLayout(param_value_layout, 0, 0, 3, 1)
        outer_layout.addLayout(nb_count_layout, 0, 1, 3, 1)
        outer_layout.addLayout(view_layout, 0, 2, 30, 30, alignment=Qt.AlignTop)

        view_widget.setLayout(outer_layout)

        view_widget.setFixedSize(1200, 800)

        return view_widget


    def create_param_info_per_slider_index(self, c, img_ids, chosen_param = None):
        '''Creates strings containing static parameter values and neighbor counts for each image in img_ids.
        Returns a list of strings to be stacked into label.'''

        all_param_names = ['iter', 'Egr', 'Mgr', 'Rep', 'Swi', 'Adh', 'Act', 'Inh', 'Sec', 'Da', 'Di', 'Ds', 'Int', 'Set', 'Boy', 'Dff', 'Bgr', 'Abi', 'Pbi', 'Lbi', 'Bbi', 'Rad', 'Deg', 'Dgr', 'Ntr', 'Bwi', 'Ina', 'uMgr']
        
        # DEBUG
        #print(f"img_ids: {img_ids}")
        #print(f"type(img_ids): {type(img_ids)}")

        # Get the parameter values for each image
        param_value_strings_per_img = []
        nb_count_strings_per_img = []
        # initialize base_row outside the loop so that it can be checked later (as any base_row should do the trick, it doesn't matter which one is held here)
        base_row = None
        if isinstance(img_ids, str): # in case img_ids is a string (i.e., counts as a list, but messes things up) (e.g., '28' becomes ['2', '8'])
            img_ids = int(img_ids)
        try: # in case img_ids is not a list/array (i.e. if only one image is selected)
            iter(img_ids)
        except TypeError:
            img_ids = [img_ids]    
        for row_id in img_ids:
            neighbor_count_per_param = [0] * len(all_param_names) # by default no neighbors (only change if rows found)
            for j, param_name in enumerate(all_param_names):
                if param_name is chosen_param:
                    continue
                else:
                    base_row, rows = self.find_rows_differing_by_param(c, row_id, param_name)
                    if rows:
                        # neighbors found
                        neighbor_count_per_param[j] = len(rows)
            # create string for this image
            param_value_strings_per_img.append([f"{param_name:>4s} {base_row[base_row_value_idx]:<10}" for param_name, base_row_value_idx in zip(all_param_names, range(5,33))])
            nb_count_strings_per_img.append([f"({nb_count})" for nb_count in neighbor_count_per_param])

        return param_value_strings_per_img, nb_count_strings_per_img


    def init_ui(self, c, row_id, chosen_param):
        """ (A.k.a. the_whole_shebang) Given a row id and a chosen parameter creates a widget with ImageView + informative labels.
        """

        if not self.check_if_row_id_exists(c, row_id):
            print(f"Error: Row with id {row_id} does not exist in the database")
            return
        if not self.check_if_chosen_param_exists(c, chosen_param):
            print(f"Error: Column {chosen_param} does not exist in the table")
            return
        base_row, rows = self.find_rows_differing_by_param(c, row_id, chosen_param)
        if not rows:
            print("No neighboring tooth images found for the given parameter")
            return
        # Load PNG images into a 3D numpy array
        arr, img_ids, chosen_param_values = self.stack_images(c, base_row, rows, chosen_param)
        # Create an instance of the ImageView class
        self.view = self.create_image_view(arr, chosen_param_values)
        # Set the ImageView's slider at the base image
        base_row_index = int(np.where(img_ids == int(row_id))[0])
        base_row_value = chosen_param_values[base_row_index]
        self.view.timeLine.setValue(base_row_value)
        # Create a context menu for the ImageView (right-click) and connect it to creating a new tab
        self.create_context_menu(self.view, img_ids, chosen_param)
        # Connect N-key to creating a new tab # TODO: this is not working yet
        #self.connect_n_key_to_new_tab(self.view, img_ids, chosen_param)
        # Create labels around the ImageView
        position_label, param_value_labels, nb_count_labels = self.create_info_labels(c, self.view, img_ids, chosen_param_values, chosen_param)
        # Create a QWidget for the ImageView
        view_widget = self.create_view_widget_and_layouts(self.view, position_label, param_value_labels, nb_count_labels)
        self.setLayout(view_widget.layout())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = QMainWindow()
    main_window.resize(800, 600)
    main_window.setWindowTitle("stacker demo")
    default_db_path = 'tooth_database.db'
    row_id = input("Enter a row id: ")
    chosen_param = input("Enter chosen parameter: ")
    stack_view = StackView(default_db_path, row_id, chosen_param)
    main_window.setCentralWidget(stack_view)
    main_window.show()
    sys.exit(app.exec_())
