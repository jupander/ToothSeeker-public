"""
This is the main file for the toothseeker program. It contains the main window and the main function.
"""

import sys
import platform
from PyQt5.QtWidgets import QAction, QHBoxLayout, QApplication, QMainWindow, QWidget, QMenu, QTabWidget
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5 import QtGui

# own modules:
import databasemenu
from imagedropwidget_simple_v2 import ImageDropWidgetSimple
from stackview import StackView
import helper_functions

class MainWindow(QMainWindow):

    new_tab_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setGeometry(60, 100, 900, 900)
        self.setWindowIcon(QtGui.QIcon('icon.png'))


        # ------------------ Menus for opening new tabs/windows ------------------
        
        #new_tab_menu = menu_bar.addMenu('Add tab')
        #new_view_tab_action = new_tab_menu.addAction('New StackView')
        #new_view_window_action = new_view_menu.addAction('New window')

        new_view_tab_action = self.menuBar().addAction('New tab')
        
        # Connect menu items to functions
        new_view_tab_action.triggered.connect(self.open_new_view_tab)
        #new_view_window_action.triggered.connect(self.open_new_view_window)

        # ------------------ Close tabs menu ------------------

        # Create the "Close Tabs" menu
        self.close_tabs_menu = QMenu("Close Tabs", self.menuBar())

        # Add the "Close Tabs" menu to the menu bar
        self.menuBar().addMenu(self.close_tabs_menu)

        # Alternatively: Make tabs closable (with close button on the tab)
        #self.tab_widget.setTabsClosable(True)
        #self.tab_widget.tabCloseRequested.connect(self.tab_widget.removeTab)

        # ------------------ Create tabs widget ------------------

        # Create the tab widget with initial tab
        self.tab_widget = QTabWidget()

        self.tab_widget.setStyleSheet("""
            QTabBar::tab {
                height: 40px;    /* Adjust the height to fit the 2-line text */
                padding: 5px;
            }
            """)

        # ------------------ Database menu ------------------

        # initialize database name variable
        self.db_path = None

        # add database menu to menu bar (NOTE: now it also updates the class variable self.db_path in this class when the database is changed!)
        # NOTE: this also creates the initial image drop widget
        self.database_menu = databasemenu.DatabaseMenu(self)
        
        # redundant, self.db_path is already set when the DatabaseMenu class is created
        #self.db_path = self.database_menu.db_path

        # ------------------ Connect to database ------------------

        self.conn, self.c = helper_functions.connect_to_database(self.db_path)

        # ------------------ Central widget: tabs ------------------

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        main_layout.addWidget(self.tab_widget)

        # ------------------ Status bar ------------------

        # TODO something more useful with status bar?
        self.statusBar().showMessage('Ready')

        # ------------------ windows ------------------

        # Keep track of the windows that have been opened
        #self.windows = []

        # ------------------ macOS fix ------------------

        if platform.system() == 'Darwin':
            # is running on macOS...
            # prevent the menu bar from being hidden by macOS
            self.menuBar().setNativeMenuBar(False)
            # prevent the tabs being fucked up by macOS
            self.tab_widget.setStyleSheet("QTabWidget::tab-bar { left: 0; }")


    # ------------------ functions for opening new views ------------------

    def open_new_view_tab(self, id_row = None, chosen_param = None, old_chosen_param = None):
        """Opens a new tab with the given widget."""
        # Create a new tab and add it to the list of tabs
        new_tab_index = self.tab_widget.count() + 1
        #self.tab_widget.addTab(ImageDropWidget(self.db_path), f'ImageDrop {new_tab_index}')

        if not id_row:
            id_row = helper_functions.ask_row_id(self.db_path, self)
 
        #view_widget = StackView(self.db_path, id_row, chosen_param, old_chosen_param, parent=self)
        view_widget = StackView(self.db_path, int(id_row), chosen_param, old_chosen_param, parent=self)

        # Connect the 'new view using this image' signal from the new imageview to the function that opens a new tab
        view_widget.new_view_tab_signal.connect(self.open_new_view_tab)

        self.tab_widget.addTab(view_widget, f'{view_widget.chosen_param}\n id {view_widget.row_id} ')
        # focus on the newly created tab
        self.tab_widget.setCurrentIndex(new_tab_index - 1)
        # focus on the ImageView of the view_widget on the newly created tab (so that the arrow keys work without clicking on the view first)
        view_widget.view.setFocus(Qt.OtherFocusReason)

        # Emit the signal to refresh the Close Tabs menu
        self.new_tab_signal.emit()
        # Update the "Close Tabs" menu
        self.update_close_tabs_menu()

    def close_tabs_or_alter_name(self, tab_widget):
        for i in reversed(range(tab_widget.count())):
            tab = tab_widget.widget(i)
            tab_name = tab_widget.tabText(i)
            # if the tab is an ImageDropWidget, close it
            if 'ImageDrop' in tab_name:
                tab_widget.removeTab(i)
                tab.deleteLater()
            # if the tab is a StackView, rename it to indicate that the database has changed
            else:
                tab_name_one_line = tab_name.replace('\n','')
                new_tab_name = f"{tab_name_one_line}\n( database changed! \n next steps unreliable! )"
                tab_widget.setTabText(i, new_tab_name)

    def open_new_imagedrop_tab(self):
        """Opens a new imagedrop tab with the new database, closes all existing image drop tabs, and renames all view tabs to indicate that the database has changed"""
        # close all existing image drop widget tabs, and rename all view tabs to indicate that the database has changed
        self.close_tabs_or_alter_name(self.tab_widget)
        # Create a new tab and add it to the list of tabs
        new_tab_index = self.tab_widget.count() + 1
        # create the ImageDropWidgetSimple
        image_drop_widget = ImageDropWidgetSimple(self.db_path)
        # connect the signal from the ImageDropWidget to the function that opens a new tab
        image_drop_widget.new_view_tab_signal.connect(self.open_new_view_tab)
        # add the ImageDropWidget to the tab widget
        self.tab_widget.addTab(image_drop_widget, f'ImageDrop')
        # focus on the newly created tab
        self.tab_widget.setCurrentIndex(new_tab_index - 1)
        # Emit the signal to refresh the Close Tabs menu
        self.new_tab_signal.emit()
        # Update the "Close Tabs" menu
        self.update_close_tabs_menu()

    # ------------------ functions for closing tabs ------------------

    def update_close_tabs_menu(self):
        # Remove all actions from the "Close Tabs" menu
        self.close_tabs_menu.clear()

        # Add actions for each tab in the tab widget
        for i in range(self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(i)
            close_action = QAction(f'{tab_name}', self)
            close_action.triggered.connect(lambda checked, idx=i: self.close_tab(idx))
            self.close_tabs_menu.addAction(close_action)

    def close_tab(self, index):
        # Remove the tab and update the "Close Tabs" menu
        self.tab_widget.removeTab(index)
        self.update_close_tabs_menu()

    # ------------------ functions for opening new windows ------------------

    """
    def open_new_view_window(self, id_row = None, chosen_param = None):
        # Create a new window and add it to the list of windows
        window = QWidget()
        self.windows.append(window)

        # Add a widget to the window
        if not id_row:
            id_row = ImageDropWidget.ask_row_id(self)
        if not chosen_param:
            #chosen_param = stacker.show_pick_axis_param_option_window(self.c, id_row)
            chosen_param = stacker_by_gpt.StackView.show_pick_axis_param_option_window(self.c, id_row)
        #view_widget = stacker.the_whole_shebang(self.db_path, id_row, chosen_param)
        view_widget = stacker_by_gpt.StackView(self.db_path, id_row, chosen_param, parent=self)
        layout = QVBoxLayout()
        layout.addWidget(view_widget)
        window.setLayout(layout)

        self.setWindowTitle(f'{chosen_param}, id {id_row}')

        # Show the window
        window.show()
    """

if __name__ == '__main__':
    print('\nStarting up ToothSeeker...\n')
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()
    # make sure the main window is activated (in case it was hidden behind other windows)
    main_window.activateWindow()

    sys.exit(app.exec_())
