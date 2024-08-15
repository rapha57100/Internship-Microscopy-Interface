# FINALE AND DEFINITIVE VERSION
# RAphael TOSCANO


import nidaqmx  
import numpy as np  
from nidaqmx.stream_writers import AnalogSingleChannelWriter
from nidaqmx.constants import Edge, AcquisitionType  
import sys  
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                              QHBoxLayout, QGroupBox, QFileDialog, QLabel, 
                              QSlider, QLineEdit ,QTabWidget,QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt  

# Galvo DATASHEET
max_scan_angle = 12.5  # Max degrees (±12.5°)
voltage_range = 10     # Max voltage output (±10 V)
sample_rate = 10000    # Hz, same as nidaq

ExposureTime = 10  # Default value

class GalvoWorker_initPhase(QObject): 

    """
    Worker class for handling the initialization phase of the Galvo.

    Attributes:
        finished (pyqtSignal): Signal emitted when the task is finished.
        voltage_control_widget (VoltageControlWidget()): Reference to the voltage control widget.
        _is_running_init (bool): Flag to control the running state.

    Methods:
        run_initialisation(): Runs the Galvo initialization.
        stop(): Stops the task.
    """

    finished = pyqtSignal()  # Signal to emit when the task is finished

    def __init__(self, voltage_control_widget): 
        super().__init__()
        self.voltage_control_widget = voltage_control_widget  # Store the voltage control widget instance
        self._is_running_init = True  # Flag to control the running state

    def run_initialisation(self):  # Method to run the galvo 
        """
        Method to run the Galvo initialization.
        Continuously gets min and max voltage, galvo value, and factor to control the Galvo.

        Runs until the _is_running_init flag is set to False.
        Emits finished signal when done.
        """
        while self._is_running_init:  # Continue running while the flag is True
            min_voltage = self.voltage_control_widget.get_min_voltage()  # Get the minimum voltage
            max_voltage = self.voltage_control_widget.get_max_voltage()  # Get the maximum voltage
            galvo1_Value = self.voltage_control_widget.get_galvo1_Value()

            if min_voltage is not None and max_voltage is not None : # Check if min, max voltages and factor are set
                duration_ms = ExposureTime + 22.937  # Calculate the duration in milliseconds
                num_samples = int(sample_rate * (duration_ms / 1000))  # Convert duration to number of samples

                voltages_sequence =  [galvo1_Value] * (num_samples+1)
                data = np.vstack(voltages_sequence)

                try:
                    with nidaqmx.Task() as task:
                        task.ao_channels.add_ao_voltage_chan('Dev1/ao17')
                        task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI1", trigger_edge=Edge.RISING)  # Configure a digital edge start trigger
                        task.timing.cfg_samp_clk_timing(rate=sample_rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=num_samples)  # Configure sample clock timing

                        writer = AnalogSingleChannelWriter(task.out_stream)  # Create a writer for the task output stream
                        writer.write_many_sample(data)  # Write the voltage sequence to the output stream
                        task.start()  # Start the task
                        task.wait_until_done(timeout=0.5)  # Wait until the task is done

                except nidaqmx.errors.DaqError as e:  # Handle DAQ errors
                    pass
        self.finished.emit()  # Emit the finished signal

    def stop(self):
        """
        Method to stop the task.
        Sets the _is_running_init flag to False.
        """
        self._is_running_init = False  # Set the running flag to False

class MainApp(QWidget):
    """
    Main application class for the Galvo control GUI.

    Methods:
        __init__(): Constructor to initialize the UI.
        init_ui(): Method to initialize the UI components.
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """
        Method to initialize the UI components.
        Creates the main layout, tabs, and group boxes for configuration and control.
        """
        # Create the main layout
        main_layout = QHBoxLayout()
        tab_widget = QTabWidget()

        # Combined tab with two group boxes
        combined_tab = QWidget()
        layout_combined_tab = QVBoxLayout()
        combined_tab.setLayout(layout_combined_tab)

        # Initialization group box
        init_group_box = QGroupBox('Initialization')
        layout_init_group_box = QVBoxLayout()
        init_group_box.setLayout(layout_init_group_box)
        self.voltage_control_widget = VoltageControlWidget()
        layout_init_group_box.addWidget(self.voltage_control_widget)

        # OPM group box
        opm_group_box = QGroupBox('OPM')
        layout_opm_group_box = QVBoxLayout()
        opm_group_box.setLayout(layout_opm_group_box)
        self.voltage_intervalle_editor_widget = VoltageIntervalEditor(self.voltage_control_widget)
        layout_opm_group_box.addWidget(self.voltage_intervalle_editor_widget)

        # Add group boxes to the combined tab layout
        layout_combined_tab.addWidget(init_group_box)
        layout_combined_tab.addWidget(opm_group_box)

        # Add the combined tab to the tab widget
        tab_widget.addTab(combined_tab, 'Configuration')

        # Add tab widget to the main layout
        main_layout.addWidget(tab_widget)
        self.setLayout(main_layout)

class VoltageControlWidget(QWidget): 
    """
    Widget for controlling voltage settings.

    Attributes:
        min_voltage (float): Minimum voltage value.
        max_voltage (float): Maximum voltage value.
        factor (float): Factor value.
        galvo1_Value (float): Galvo value.

    Methods:
        init_ui(): Initializes the UI components.
        update_voltage_label(): Updates the voltage and angle labels.
        set_max_voltage(): Sets the maximum voltage.
        set_min_voltage(): Sets the minimum voltage.
        get_max_voltage(): Returns the maximum voltage.
        get_min_voltage(): Returns the minimum voltage.
        get_galvo1_Value(): Returns the Galvo value.
        apply_settings(): Applies exposure settings.
        start_task(): Starts the Galvo task.
        stop_task(): Stops the Galvo task.
    """
    def __init__(self): 
        super().__init__()
        self.min_voltage = None  # Initialize minimum voltage
        self.max_voltage = None  # Initialize maximum voltage
        self.setting_min = True  # Flag to control setting min voltage
        self.galvo1_Value = None
        self.init_ui()  # Initialize the UI

    def init_ui(self):  
        """
        Initializes the UI components for the voltage control.
        Creates sliders, buttons, and labels for controlling and displaying voltage and angle values.
        """
        main_layout = QVBoxLayout()  # Create the main vertical layout
        
        # Exposure Block
        exposure_group = QGroupBox('Exposure Settings')
        exposure_layout = QVBoxLayout()
        
        self.exposure_line_edit = QLineEdit()  # Create a line edit for exposure time
        self.exposure_line_edit.setPlaceholderText('Enter Exposure Time (ms)')  # Set placeholder text
        exposure_layout.addWidget(self.exposure_line_edit)  # Add the line edit to the layout

        self.btn_apply = QPushButton('Set Exposure')  # Create a button to set exposure
        self.btn_apply.clicked.connect(self.apply_settings)  # Connect the button click to the apply settings method
        exposure_layout.addWidget(self.btn_apply)  # Add the button to the layout

        exposure_group.setLayout(exposure_layout)  # Set the layout for the group box
        main_layout.addWidget(exposure_group)  # Add the exposure group to the main layout

        # Min and Max Block
        min_max_group = QGroupBox('Voltage and Degrees Range')
        min_max_layout = QVBoxLayout()

        self.slider = QSlider(Qt.Orientation.Horizontal)  # Create a horizontal slider
        self.slider.setRange(-100, 100)  # Set the range of the slider
        self.slider.setValue(0)  # Set the initial value of the slider
        self.slider.setTickInterval(10)  # Set the tick interval for the slider
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)  # Set the tick position
        self.slider.valueChanged.connect(self.update_voltage_label)  # Connect the value change to the update method
        min_max_layout.addWidget(self.slider)  # Add the slider to the layout

        self.label_voltage = QLabel('Voltage: 0.0 V')  # Create a label for voltage
        min_max_layout.addWidget(self.label_voltage)  # Add the label to the layout

        self.label_angle = QLabel('Angle: 0.0 °')  # Create a label for angle
        min_max_layout.addWidget(self.label_angle)  # Add the label to the layout

        hbox_ranges = QHBoxLayout()  # Create a horizontal layout for ranges

        self.btn_set_min = QPushButton('Set Min Voltage')  # Create a button to set min voltage
        self.btn_set_min.clicked.connect(self.set_min_voltage)  # Connect the button click to the set min voltage method
        min_max_layout.addWidget(self.btn_set_min)  # Add the button to the layout

        self.btn_set_max = QPushButton('Set Max Voltage')  # Create a button to set max voltage
        self.btn_set_max.clicked.connect(self.set_max_voltage)  # Connect the button click to the set max voltage method
        min_max_layout.addWidget(self.btn_set_max)  # Add the button to the layout

        vbox_min_max_voltage = QVBoxLayout()  # Create a vertical layout for voltage range
        self.group_box_min_max_voltage = QGroupBox('Voltage Range')  # Create a group box for voltage range
        self.group_box_min_max_voltage.setLayout(vbox_min_max_voltage)  # Set the layout for the group box

        self.label_min_voltage = QLabel('Min Voltage: Not Set')  # Create a label for min voltage
        self.label_max_voltage = QLabel('Max Voltage: Not Set')  # Create a label for max voltage
        vbox_min_max_voltage.addWidget(self.label_min_voltage)  # Add the min voltage label to the layout
        vbox_min_max_voltage.addWidget(self.label_max_voltage)  # Add the max voltage label to the layout
        hbox_ranges.addWidget(self.group_box_min_max_voltage)  # Add the group box to the ranges layout

        vbox_min_max_degrees = QVBoxLayout()  # Create a vertical layout for degrees range
        self.group_box_min_max_degrees = QGroupBox('Degrees Range')  # Create a group box for degrees range
        self.group_box_min_max_degrees.setLayout(vbox_min_max_degrees)  # Set the layout for the group box

        self.label_min_degrees = QLabel('Min Degrees: Not Set')  # Create a label for min degrees
        self.label_max_degrees = QLabel('Max Degrees: Not Set')  # Create a label for max degrees
        vbox_min_max_degrees.addWidget(self.label_min_degrees)  # Add the min degrees label to the layout
        vbox_min_max_degrees.addWidget(self.label_max_degrees)  # Add the max degrees label to the layout
        hbox_ranges.addWidget(self.group_box_min_max_degrees)  # Add the group box to the ranges layout

        min_max_layout.addLayout(hbox_ranges)  # Add the ranges layout to the min_max_layout
        min_max_group.setLayout(min_max_layout)  # Set the layout for the group box
        main_layout.addWidget(min_max_group)  # Add the min_max group to the main layout

        self.setLayout(main_layout)

    def update_voltage_label(self):  
        """
        Updates the voltage and angle labels based on the slider value.
        Converts the slider value to voltage and angle.
        """
        voltage = self.slider.value() / 10.0  # Calculate the voltage from the slider value
        self.galvo1_Value = voltage
        self.label_voltage.setText(f'Voltage: {voltage:.1f} V')  # Update the voltage label

        angle = voltage * (max_scan_angle / voltage_range)  # Calculate the angle from the voltage
        self.label_angle.setText(f'Angle: {angle:.1f} °')  # Update the angle label

        if self.min_voltage is not None:  # Check if min voltage is set
            min_degrees = self.min_voltage * (max_scan_angle / voltage_range)  # Calculate min degrees
            self.label_min_degrees.setText(f'Min Degrees: {min_degrees:.1f}°')  # Update min degrees label

        if self.max_voltage is not None:  # Check if max voltage is set
            max_degrees = self.max_voltage * (max_scan_angle / voltage_range)  # Calculate max degrees
            self.label_max_degrees.setText(f'Max Degrees: {max_degrees:.1f}°')  # Update max degrees label

    def set_max_voltage(self):     
        """
        Sets the maximum voltage based on the slider value.
        Updates the max_voltage attribute and label.
        """
        self.stop_task()  # Stop the current task

        max_voltage = self.slider.value() / 10.0  # Get the max voltage from the slider
        self.max_voltage = max_voltage  # Set the max voltage
        self.label_max_voltage.setText(f'Max Voltage: {max_voltage:.1f} V')  # Update the max voltage label
        self.setting_min = False  # Set the flag to indicate max voltage is being set
        self.update_voltage_label()  # Update the voltage and angle labels
        print(f"Max voltage : {max_voltage} V ")
        # Apply max voltage to the device
        try:
            with nidaqmx.Task() as task:  # Create a new NI-DAQmx task
                task.ao_channels.add_ao_voltage_chan('Dev1/ao17')  # Add an analog output channel
                task.start()  # Start the task
                task.write(max_voltage)  # Write the max voltage to the channel
        except nidaqmx.errors.DaqError as e:  # Handle DAQ errors
            print(f"DAQ Error: {e}")

        self.start_task()  # Restart the task

    def set_min_voltage(self):  
        """
        Sets the minimum voltage based on the slider value.
        Updates the min_voltage attribute and label.
        """
        self.stop_task()  # Stop the current task
        min_voltage = self.slider.value() / 10.0  # Get the min voltage from the slider
        self.min_voltage = min_voltage  # Set the min voltage
        self.label_min_voltage.setText(f'Min Voltage: {min_voltage:.1f} V')  # Update the min voltage label
        self.setting_min = True  # Set the flag to indicate min voltage is being set
        self.update_voltage_label()  # Update the voltage and angle labels
        print(f"Min voltage : {min_voltage} V ")
        # Apply min voltage to the device
        try:
            with nidaqmx.Task() as task:  # Create a new NI-DAQmx task
                task.ao_channels.add_ao_voltage_chan('Dev1/ao17')  # Add an analog output channel
                task.start()  # Start the task
                task.write(min_voltage)  # Write the min voltage to the channel
        except nidaqmx.errors.DaqError as e:  # Handle DAQ errors
            print(f"DAQ Error: {e}")

        self.start_task()  # Restart the task

    def get_max_voltage(self):
        """
        Returns the maximum voltage value.
        """
        return self.max_voltage  # Return the max voltage

    def get_min_voltage(self):
        """
        Returns the minimum voltage value.
        """
        return self.min_voltage  # Return the min voltage

    def get_galvo1_Value(self):
        """
        Returns the Galvo value.
        """
        return self.galvo1_Value  # Return the galvo value

    def apply_settings(self):  
        """
        Applies the exposure settings based on the input value.
        Updates the ExposureTime variable.
        """
        self.stop_task()  # Stop the current task
        try:
            exposure_value = float(self.exposure_line_edit.text())  # Get the exposure time from the line edit
            global ExposureTime  # Access the global variable
            ExposureTime = exposure_value  # Set the exposure time
            print(f"Exposure Time : {ExposureTime} ms")  # Print the new exposure time
        except ValueError:  # Handle invalid input
            print("Invalid exposure time entered.")
        self.start_task()  # Restart the task

    def start_task(self):  
        """
        Starts the Galvo task in a separate thread.
        Initializes and starts the GalvoWorker_initPhase.
        """
        self.thread = QThread()  # Create a new thread
        self.galvo_worker = GalvoWorker_initPhase(self)  # Create a new galvo worker
        self.galvo_worker.moveToThread(self.thread)  # Move the worker to the new thread
        self.thread.started.connect(self.galvo_worker.run_initialisation)  # Connect the thread start to the worker run method
        self.galvo_worker.finished.connect(self.thread.quit)  # Connect the worker finished signal to the thread quit method
        self.galvo_worker.finished.connect(self.galvo_worker.deleteLater)  # Connect the worker finished signal to the worker delete method
        self.thread.finished.connect(self.thread.deleteLater)  # Connect the thread finished signal to the thread delete method
        self.thread.start()  # Start the thread

    def stop_task(self):  
        """
        Stops the Galvo task.
        """
        if hasattr(self, 'galvo_worker') and self.galvo_worker is not None:  # Check if the worker exists
            self.galvo_worker.stop()  # Stop the worker
            self.thread.quit()  # Quit the thread
            self.thread.wait()  # Wait for the thread to finish


class VoltageIntervalEditor(QWidget):
    """
    Widget for editing voltage intervals.

    Attributes:
        voltage_control_widget (VoltageControlWidget): Reference to the voltage control widget.
        file_path (str): Path to the selected .cfg file.
        original_content (str): Original content of the .cfg file.
        mode (str): Current mode for interval editing ('N' for number mode, 'I' for interval mode).

    Methods:
        init_ui(): Initializes the UI components.
        load_voltage_value(): Loads the minimum and maximum voltage values.
        select_file(): Opens a file dialog to select a .cfg file.
        load_original_content(): Loads the original content of the selected .cfg file.
        switch_mode(): Switches between number mode and interval mode.
        handle_write_voltage_intervals(): Handles writing voltage intervals to the .cfg file.
        write_voltage_intervals_by_number(): Writes voltage intervals based on the number of positions.
        write_voltage_intervals_by_interval(): Writes voltage intervals based on the interval angle.
        write_voltage_intervals(): Writes voltage intervals to the .cfg file.
        erase_voltage_intervals(): Erases the voltage intervals from the .cfg file and restores the original content.
    """

    def __init__(self, voltage_control_widget): 
        """
        Initializes the UI components for the voltage interval editor.
        Creates buttons, line edits, and layout for selecting files and entering voltage interval settings.
        """
        super().__init__()
        self.voltage_control_widget = voltage_control_widget  # Store the voltage control widget instance
        self.initUI()
        self.original_content = None  # To store the original file content
        self.mode = 'N'  # 'N' for number of positions, 'I' for interval value

    def initUI(self):
        """
        Initializes the UI components for the voltage interval editor.
        Creates a text edit for displaying and editing voltage intervals.
        """
        layout = QVBoxLayout()

        self.btn_select_file = QPushButton('Select .cfg File')
        self.btn_select_file.clicked.connect(self.select_file)
        layout.addWidget(self.btn_select_file)

        self.mode_btn = QPushButton('Switch to Interval Mode')
        self.mode_btn.clicked.connect(self.switch_mode)
        layout.addWidget(self.mode_btn)

        self.N_input = QLineEdit(self)
        self.N_input.setPlaceholderText('Enter desired Number of galvo positions')
        layout.addWidget(self.N_input)

        self.interval_input = QLineEdit(self)
        self.interval_input.setPlaceholderText('Enter desired interval angle (°) between positions')
        self.interval_input.setVisible(False)  # Hide interval input by default
        layout.addWidget(self.interval_input)

        self.add_lines_btn = QPushButton('Write voltage config')
        self.add_lines_btn.clicked.connect(self.handle_write_voltage_intervals)
        layout.addWidget(self.add_lines_btn)

        self.erase_lines_btn = QPushButton('Erase voltage config')
        self.erase_lines_btn.clicked.connect(self.erase_voltage_intervals)
        layout.addWidget(self.erase_lines_btn)

        self.setLayout(layout)

    def load_voltage_value(self):
        """
        Loads the minimum and maximum voltage values from the voltage control widget.

        Returns:
            tuple: A tuple containing the minimum and maximum voltage values.
        """
        min_voltage = self.voltage_control_widget.get_min_voltage()  # Get the minimum voltage
        max_voltage = self.voltage_control_widget.get_max_voltage()  # Get the maximum voltage
        print(min_voltage)
        print(max_voltage)

        return min_voltage, max_voltage

    def select_file(self):
        """
        Opens a file dialog to select a .cfg file and loads its original content.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Select .cfg file", "", "Config Files (*.cfg);;All Files (*)")
        if file_path:
            self.file_path = file_path
            self.load_original_content()
        else:
            QMessageBox.warning(self, 'Error', 'No file selected')

    def load_original_content(self):
        """
        Loads the original content of the selected .cfg file.
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                self.original_content = file.read()
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to read the file: {str(e)}')

    def switch_mode(self):
        """
        Switches between number mode and interval mode for voltage interval editing.
        """
        if self.mode == 'N':
            self.mode = 'I'
            self.N_input.setVisible(False)
            self.interval_input.setVisible(True)
            self.mode_btn.setText('Switch to Position Mode')
        else:
            self.mode = 'N'
            self.N_input.setVisible(True)
            self.interval_input.setVisible(False)
            self.mode_btn.setText('Switch to Interval Mode')

    def handle_write_voltage_intervals(self):
        """
        Handles writing voltage intervals to the .cfg file based on the selected mode.
        """
        if not hasattr(self, 'file_path'):
            QMessageBox.warning(self, 'Error', 'No file selected')
            return

        try:
            min_voltage, max_voltage = self.load_voltage_value()
            if self.mode == 'N':
                N = int(self.N_input.text())
                self.write_voltage_intervals_by_number(N, min_voltage, max_voltage)
            else:
                interval_degrees = float(self.interval_input.text())
                interval_Voltage = interval_degrees/(max_scan_angle / voltage_range) 
                self.write_voltage_intervals_by_interval(interval_Voltage, min_voltage, max_voltage)
            QMessageBox.information(self, 'Success', 'Voltage intervals added successfully')
        except Exception as e:
            QMessageBox.warning(self, 'Error', str(e))

    def write_voltage_intervals_by_number(self, N, min_voltage, max_voltage):
        """
        Writes voltage intervals based on the number of positions.

        Args:
            N (int): Number of galvo positions.
            min_voltage (float): Minimum voltage value.
            max_voltage (float): Maximum voltage value.
        """
        interval = (max_voltage - min_voltage) / (N - 1)
        self.write_voltage_intervals(N, interval, min_voltage, max_voltage)

    def write_voltage_intervals_by_interval(self, interval, min_voltage, max_voltage):
        """
        Writes voltage intervals based on the interval angle.

        Args:
            interval (float): Interval voltage between positions.
            min_voltage (float): Minimum voltage value.
            max_voltage (float): Maximum voltage value.
        """
        N = int((max_voltage - min_voltage) / interval) + 1
        self.write_voltage_intervals(N, interval, min_voltage, max_voltage)

    def write_voltage_intervals(self, N, interval, min_voltage, max_voltage):
        """
        Writes voltage intervals to the .cfg file.

        Args:
            N (int): Number of galvo positions.
            interval (float): Interval voltage between positions.
            min_voltage (float): Minimum voltage value.
            max_voltage (float): Maximum voltage value.
        """
        # Read the file content
        with open(self.file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        # Find the position to insert new lines
        insert_pos = -1
        for i, line in enumerate(lines):
            if "# Group: NiAO18_Galvo2" in line:
                insert_pos = i + 3  # Insert after this line
                break

        if insert_pos == -1:
            raise ValueError("The specified group was not found in the file.")

        # Generate the new lines with comments
        voltage_intervals = [round(min_voltage + i * interval, 4) for i in range(N)]
        new_lines = []
        for i, v in enumerate(voltage_intervals):
            new_lines.append(f"# Preset: Position {i+1}\n")
            new_lines.append(f"ConfigGroup,NiAO18_Galvo2,position{i+1},NIDAQAO-Dev1/ao18,Voltage,{v:.4f}\n")

        # Insert the new lines
        lines[insert_pos:insert_pos] = new_lines

        # Write the updated content back to the file
        with open(self.file_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)

    def erase_voltage_intervals(self):
        """
        Erases the voltage intervals from the .cfg file and restores the original content.
        """
        if not hasattr(self, 'file_path') or self.original_content is None:
            QMessageBox.warning(self, 'Error', 'No file selected or original content not loaded')
            return

        try:
            with open(self.file_path, 'w', encoding='utf-8') as file:
                file.write(self.original_content)
            QMessageBox.information(self, 'Success', 'Voltage intervals erased successfully')
        except Exception as e:
            QMessageBox.warning(self, 'Error', str(e))





if __name__ == '__main__':  
    app = QApplication(sys.argv)  # Create the application
    window = MainApp()  # Create an instance of the main application window
    window.setWindowTitle('Main Application')  
    window.show() 
    sys.exit(app.exec()) 