# FINALE AND DEFINITIVE VERSION
# RAphael TOSCANO


import nidaqmx  
import numpy as np  
from nidaqmx.stream_writers import  AnalogMultiChannelWriter
from nidaqmx.constants import Edge, AcquisitionType  
import sys  
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox, QTextEdit, QFileDialog, QLabel, QSlider, QLineEdit ,QTabWidget,QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt  
import json

# Galvo DATASHEET
max_scan_angle = 12.5  # Max degrees (±12.5°)
voltage_range = 10     # Max voltage output (±10 V)
sample_rate = 10000    # Hz, same as nidaq


ExposureTime = 10  # Default value

class GalvoWorker_initPhase(QObject): 
    """
    Worker class for initializing the Galvo.
    
    Attributes:
        finished (pyqtSignal): Signal emitted when the task is finished.
        voltage_control_widget (VoltageControlWidget): Reference to the voltage control widget.
        _is_running_init (bool): Flag to control the running state.
        
    Methods:
        run_initialisation(): Runs the initialization process.
        stop(): Stops the initialization process.
    """
    finished = pyqtSignal()  # Signal to emit when the task is finished

    def __init__(self, voltage_control_widget): 
        super().__init__()
        self.voltage_control_widget = voltage_control_widget  # Store the voltage control widget instance
        self._is_running_init = True  # Flag to control the running state

    def run_initialisation(self):
        """
        Method to run the Galvo initialization process.
        Generates and writes voltage sequences to the Galvo.
        """
        while self._is_running_init:  # Continue running while the flag is True
            min_voltage = self.voltage_control_widget.get_min_voltage()  # Get the minimum voltage
            max_voltage = self.voltage_control_widget.get_max_voltage()  # Get the maximum voltage
            Galvo2_Enable = self.voltage_control_widget.get_Galvo2_Enable()
            galvo2_Value = self.voltage_control_widget.get_galvo2_Value()
            factor = self.voltage_control_widget.get_factor()  # Get the factor

            if min_voltage is not None and max_voltage is not None and factor is not None:  # Check if min, max voltages and factor are set
                initial_voltage = min_voltage  # Set initial voltage
                final_voltage = max_voltage  # Set final voltage
                duration_ms = ExposureTime + 22.937  # Calculate the duration in milliseconds
                num_samples = int(sample_rate * (duration_ms / 1000))  # Convert duration to number of samples

                voltages_sequence = np.linspace(initial_voltage, final_voltage, num_samples)  # Generate ramp sequence
                voltages_sequence = np.append(voltages_sequence, initial_voltage)  # Append the initial voltage as the last value

                if (Galvo2_Enable== True) :
                    voltages_sequence2 = np.linspace(initial_voltage * factor, final_voltage * factor, num_samples)  # Generate ramp sequence with factor
                    voltages_sequence2 = np.append(voltages_sequence2, initial_voltage * factor)  # Append the initial voltage as the last value
                else :
                    voltages_sequence2 = [galvo2_Value] * (num_samples+1)

                data = np.vstack((voltages_sequence, voltages_sequence2)).astype(np.float64)  # Stack arrays in sequence vertically

                try:
                    with nidaqmx.Task() as task:
                        task.ao_channels.add_ao_voltage_chan('Dev1/ao17')
                        task.ao_channels.add_ao_voltage_chan('Dev1/ao18')
                        task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI1", trigger_edge=Edge.RISING)  # Configure a digital edge start trigger
                        task.timing.cfg_samp_clk_timing(rate=sample_rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=num_samples)  # Configure sample clock timing

                        writer = AnalogMultiChannelWriter(task.out_stream)  # Create a writer for the task output stream
                        writer.write_many_sample(data)  # Write the voltage sequence to the output stream
                        task.start()  # Start the task
                        task.wait_until_done(timeout=0.5)  # Wait until the task is done

                except nidaqmx.errors.DaqError as e:  # Handle DAQ errors
                    pass
        self.finished.emit()  # Emit the finished signal

    def stop(self):  
        """
        Method to stop the Galvo initialization process.
        """
        self._is_running_init = False  # Set the running flag to False


class GalvoWorker_MDA(QObject):  
    """
    Worker class for performing MDA (Multi-Dimensional Acquisition).

    Attributes:
        finished (pyqtSignal): Signal emitted when the task is finished.
        voltage_control_widget (VoltageControlWidget): Reference to the voltage control widget.
        file_explorer_widget (FileExplorerWidget): Reference to the file explorer widget.
        MDA_is_running (bool): Flag to control the running state.
        
    Methods:
        increase_range(): Increases the voltage range using the factor.
        generate_voltage_sequences(): Generates voltage sequences based on the acquisition order.
        run_MDA(): Runs the MDA process.
        stop(): Stops the MDA process.
    """
    finished = pyqtSignal()  # Signal to emit when the task is finished

    def __init__(self, voltage_control_widget, file_explorer_widget):  # Constructor
        super().__init__()
        self.voltage_control_widget = voltage_control_widget  # Store the voltage control widget instance
        self.MDA_is_running = True  # Flag to control the running state
        self.file_explorer_widget = file_explorer_widget  # Store the file explorer widget instance

    def increase_range(self,factor):
        """
        Increases the voltage range using the factor.

        Returns:
            tuple: New minimum and maximum voltages.
        """
        min_voltage = self.voltage_control_widget.get_min_voltage()  # Get the minimum voltage
        max_voltage = self.voltage_control_widget.get_max_voltage()  # Get the maximum voltage
        center = (min_voltage + max_voltage) / 2
        half_range = (max_voltage - min_voltage) / 2
        half_range_new = half_range * factor
        min_new = center - half_range_new
        max_new = center + half_range_new

        if (min_new<=-10) :
            min_new =-10 
        elif (min_new>=10) :
            min_new =10 
        else :  
            min_new = center - half_range_new
        if (max_new<=-10) :
            max_new =-10 
        elif (max_new>=10) :
            max_new =10 
        else :  
            max_new = center + half_range_new


        return min_new, max_new
    
    def generate_voltage_sequences(self):
        """
        Generates voltage sequences based on the acquisition order.

        Returns:
            tuple: All sequences, all sequences with factor, and duration list.
        """
        factor = self.voltage_control_widget.get_factor()  # Get the minimum factor value
        Acq_order = self.file_explorer_widget.Acq_order
        num_frames = self.file_explorer_widget.num_frames
        num_slices = self.file_explorer_widget.num_slices
        exposure_times = self.file_explorer_widget.exposure_values
        FW = self.file_explorer_widget.FW
        amp = self.file_explorer_widget.amp
        min_voltage = self.voltage_control_widget.get_min_voltage()  # Get the minimum voltage
        max_voltage = self.voltage_control_widget.get_max_voltage()  # Get the maximum voltage
        Galvo2_Enable = self.voltage_control_widget.get_Galvo2_Enable()
        galvo2_Value = self.voltage_control_widget.get_galvo2_Value()

        


        # Create a unique list of scale factors
        if factor<=0 :
            factor_list_unique = np.linspace(factor, -1.0, int(amp)).tolist()
        else :
            factor_list_unique = np.linspace(factor, 1.0, int(amp)).tolist()
        
        # Flatten the list by repeating factor_list_unique for each filter wheel (FW)
        factor_list = factor_list_unique * FW

        all_sequences = []
        all_sequences2 = []  # With factor
        duration_list = []

        # print(exposure_times)
        # print(factor_list)

        if Acq_order == 0:
            for frame_index in range(num_frames):
                for slice_index in range(num_slices):                    
                    for i, exposure_time in enumerate(exposure_times):  # `i` is guaranteed to be an integer
                        duration_ms = exposure_time + 22.937  # Now `exposure_time` is directly accessed
                        num_samples = int(sample_rate * (duration_ms / 1000))

                        # Original sequence
                        voltages_sequence = np.linspace(min_voltage, max_voltage, num_samples)
                        voltages_sequence = np.append(voltages_sequence, min_voltage)
                        all_sequences.append(voltages_sequence)

                        # New sequence with scale factor voltage range
                        factor = factor_list[i]  # Get the correct factor
                        min_voltage_new, max_voltage_new = self.increase_range(factor)

                        if Galvo2_Enable:
                            voltages_sequence_new = np.linspace(min_voltage_new, max_voltage_new, num_samples)
                            voltages_sequence_new = np.append(voltages_sequence_new, min_voltage_new)
                            all_sequences2.append(voltages_sequence_new)
                        else:
                            voltages_sequence_new = np.linspace(galvo2_Value, galvo2_Value, num_samples)
                            voltages_sequence_new = np.append(voltages_sequence_new, galvo2_Value)
                            all_sequences2.append(voltages_sequence_new)

                        duration_list.append(duration_ms)
        elif Acq_order == 1:
            for frame_index in range(num_frames):
                for i, exposure_time in enumerate(exposure_times):
                    for slice_index in range(num_slices):

                        duration_ms = exposure_time + 22.937
                        num_samples = int(sample_rate * (duration_ms / 1000))

                        # Original sequence
                        voltages_sequence = np.linspace(min_voltage, max_voltage, num_samples)
                        voltages_sequence = np.append(voltages_sequence, min_voltage)
                        all_sequences.append(voltages_sequence)
                        factor = factor_list[i]  # Get the correct factor
                        min_voltage_new, max_voltage_new = self.increase_range(factor)

                        # New sequence with enlarged voltage range
                        if Galvo2_Enable:
                            voltages_sequence_new = np.linspace(min_voltage_new, max_voltage_new, num_samples)
                            voltages_sequence_new = np.append(voltages_sequence_new, min_voltage_new)
                            all_sequences2.append(voltages_sequence_new)
                        else:
                            voltages_sequence_new = np.linspace(galvo2_Value, galvo2_Value, num_samples)
                            voltages_sequence_new = np.append(voltages_sequence_new, galvo2_Value)
                            all_sequences2.append(voltages_sequence_new)
                        
                        duration_list.append(duration_ms)

        return all_sequences, all_sequences2, duration_list
    
    def run_MDA(self):  
        """
        Method to run the Galvo MDA task.
        Generates and writes voltage sequences to the Galvo.
        """
        all_sequences,all_sequences2,duration_list = self.generate_voltage_sequences()  # Generate voltage sequences

        try:
            for i in range(len(all_sequences)):
                with nidaqmx.Task() as task:
                    task.ao_channels.add_ao_voltage_chan('Dev1/ao17')
                    task.ao_channels.add_ao_voltage_chan('Dev1/ao18')
                    task.timing.cfg_samp_clk_timing(rate=sample_rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=int(sample_rate * (duration_list[i] / 1000)) + 1)
                    task.triggers.start_trigger.cfg_dig_edge_start_trig("/Dev1/PFI1", trigger_edge=Edge.RISING)

                    data = np.vstack((all_sequences[i], all_sequences2[i]))   #Stack arrays in sequence vertically

                    writer = AnalogMultiChannelWriter(task.out_stream)
                    writer.write_many_sample(data)
                    task.start()
                    task.wait_until_done(timeout=10000)
                    task.stop()

                    print(f"Frame {i + 1} completed.")
                    i += 1

            print("All sequences completed.")

        except nidaqmx.errors.DaqError :
            pass
        self.finished.emit()

    def stop(self):  
        """
        Method to stop the Galvo MDA task.
        """
        self._is_running_init = False  # Set the running flag to False

class MainApp(QWidget):
    """
    Main application class.
    
    Attributes:
        voltage_control_widget (VoltageControlWidget): Reference to the voltage control widget.
        file_explorer_widget (FileExplorerWidget): Reference to the file explorer widget.
        btn_start_MDA (QPushButton): Button to start the MDA process.
        thread (QThread): Thread for running the Galvo MDA task.
        galvo_worker_MDA (GalvoWorker_MDA): Worker instance for running the Galvo MDA task.
        
    Methods:
        init_ui(): Initializes the UI components.
        start_MDA(): Starts the MDA process.
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """
        Initializes the UI components.
        """
        # Create the main layout
        main_layout = QHBoxLayout()
        tab_widget = QTabWidget()

        # Initialization tab
        init_tab = QWidget()
        layout_init_tab = QVBoxLayout()
        init_tab.setLayout(layout_init_tab)
        self.voltage_control_widget = VoltageControlWidget()
        layout_init_tab.addWidget(self.voltage_control_widget)
        tab_widget.addTab(init_tab, 'Initialization')

        # MDA tab
        mda_tab = QWidget()
        layout_mda_tab = QVBoxLayout()
        mda_tab.setLayout(layout_mda_tab)
        middle_panel_mda = QVBoxLayout()  # Vertical layout for right panel in MDA tab
        self.file_explorer_widget = FileExplorerWidget()
        middle_panel_mda.addWidget(self.file_explorer_widget)
        self.btn_start_MDA = QPushButton('Start MDA (tap here before MM button)')
        self.btn_start_MDA.clicked.connect(self.voltage_control_widget.stop_task)
        self.btn_start_MDA.clicked.connect(self.start_MDA)
        middle_panel_mda.addWidget(self.btn_start_MDA)
        layout_mda_tab.addLayout(middle_panel_mda)  # Add right panel to the MDA tab layout
        tab_widget.addTab(mda_tab, 'MDA projection')

        main_layout.addWidget(tab_widget)  # Add tab widget to the main layout
        self.setLayout(main_layout)

    def start_MDA(self): 
        """
        Method to start the MDA process.
        """
        self.btn_start_MDA.setEnabled(False)

        print("MDA started")  # Print a message
        self.thread = QThread()  # Create a new thread
        self.galvo_worker_MDA = GalvoWorker_MDA(self.voltage_control_widget, self.file_explorer_widget)  # Pass both widgets
        self.galvo_worker_MDA.moveToThread(self.thread)  # Move the worker to the new thread
        self.thread.started.connect(self.galvo_worker_MDA.run_MDA)  # Connect the thread start to the worker run method
        self.galvo_worker_MDA.finished.connect(self.thread.quit)  # Connect the worker finished signal to the thread quit method
        self.galvo_worker_MDA.finished.connect(self.galvo_worker_MDA.deleteLater)  # Connect the worker finished signal to the worker delete method
        self.thread.finished.connect(self.thread.deleteLater)  # Connect the thread finished signal to the thread delete method
        self.thread.start()  # Start the thread


class VoltageControlWidget(QWidget): 
    """
    Widget de contrôle de la tension pour la configuration des paramètres d'exposition et de voltage.
    
    Attributs:
        min_voltage (float or None): Tension minimale définie par l'utilisateur.
        max_voltage (float or None): Tension maximale définie par l'utilisateur.
        factor (float or None): Facteur de multiplication pour les tensions.
        setting_min (bool): Indique si la tension minimale est en cours de définition.
        Galvo2_Enable (bool): Indique si le Galvo2 est activé ou non.
        galvo2_Value (float or None): Valeur de tension pour le Galvo2.
        
    Méthodes:
        init_ui(): Initialise les composants de l'interface utilisateur.
        toggle_slider(): Active ou désactive le contrôle du Galvo2.
        get_Galvo2_Enable(): Retourne l'état d'activation du Galvo2.
        update_voltage_label(): Met à jour les étiquettes de tension et d'angle pour le Galvo principal.
        update_galvo2_position_label(): Met à jour les étiquettes de tension et d'angle pour le Galvo2.
        update_factor_label(): Met à jour l'étiquette de facteur.
        set_max_voltage(): Définit la tension maximale et l'applique.
        set_galvo2_voltage(): Définit la tension pour le Galvo2 et l'applique.
        set_min_voltage(): Définit la tension minimale et l'applique.
        get_max_voltage(): Retourne la tension maximale définie.
        get_min_voltage(): Retourne la tension minimale définie.
        get_galvo2_Value(): Retourne la valeur de la tension pour le Galvo2.
        set_factor_value(): Définit le facteur de multiplication et l'applique.
        get_factor(): Retourne le facteur de multiplication défini.
        apply_settings(): Applique les paramètres d'exposition.
        start_task(): Démarre le processus de tâche dans un nouveau thread.
        stop_task(): Arrête le processus de tâche en cours.
    """
    def __init__(self): 
        super().__init__()
        self.min_voltage = None  # Initialize minimum voltage
        self.max_voltage = None  # Initialize maximum voltage
        self.factor = None  # Initialize factor value
        self.setting_min = True  # Flag to control setting min voltage
        self.init_ui()  # Initialize the UI
        self.Galvo2_Enable = True
        self.galvo2_Value = None

    def init_ui(self):  # Method to initialize the UI
        main_layout = QVBoxLayout()  # Create the main vertical layout
        
        # Exposure Block
        exposure_group = QGroupBox('Exposure Settings')
        exposure_layout = QVBoxLayout()
        
        self.exposure_line_edit = QLineEdit()  # Create a line edit for exposure time
        self.exposure_line_edit.setPlaceholderText('Enter Exposure Time (ms) (same as MM)')  # Set placeholder text
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
        # Factor and Galvo2 Block
        factor_galvo2_group = QGroupBox('Factor and Galvo2 Settings')
        factor_galvo2_layout = QHBoxLayout()

        # Create the layout for the columns
        left_column_layout = QVBoxLayout()  # For the "No 2nd Galvo" button and labels
        right_column_layout = QVBoxLayout()  # For the sliders and buttons

        # Button to enable/disable the slider
        self.btn_toggle_slider = QPushButton('Set Galvo2 position')
        self.btn_toggle_slider.clicked.connect(self.toggle_slider)
        left_column_layout.addWidget(self.btn_toggle_slider)

        # Labels for Factor and Galvo2
        self.label_factor = QLabel('Factor : click to Set ')
        left_column_layout.addWidget(self.label_factor)

        self.label_slider3 = QLabel('Slider 3: 0.0 V')
        left_column_layout.addWidget(self.label_slider3)

        self.label_voltage_galvo2 = QLabel('Voltage: 0.0 V')
        left_column_layout.addWidget(self.label_voltage_galvo2)

        self.label_angle_galvo2 = QLabel('Angle: 0.0 °')
        left_column_layout.addWidget(self.label_angle_galvo2)

        # Factor Slider
        self.slider2 = QSlider(Qt.Orientation.Horizontal)
        self.slider2.setRange(-100, 100)
        self.slider2.setValue(10)
        self.slider2.setTickInterval(10)
        self.slider2.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider2.valueChanged.connect(self.update_factor_label)
        right_column_layout.addWidget(self.slider2)

        self.btn_set_factor = QPushButton('Set Factor')
        self.btn_set_factor.clicked.connect(self.set_factor_value)
        right_column_layout.addWidget(self.btn_set_factor)



        # Galvo2 Slider
        self.slider3 = QSlider(Qt.Orientation.Horizontal)
        self.slider3.setRange(-100, 100)
        self.slider3.setValue(0)
        self.slider3.setTickInterval(10)
        self.slider3.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider3.setEnabled(False)
        self.slider3.valueChanged.connect(self.update_galvo2_position_label)
        right_column_layout.addWidget(self.slider3)

        self.btn_set_galvo2_pos = QPushButton('Set Galvo2 position')
        self.btn_set_galvo2_pos.setEnabled(False)
        self.btn_set_galvo2_pos.clicked.connect(self.set_galvo2_voltage)
        right_column_layout.addWidget(self.btn_set_galvo2_pos)

        # Add columns to the main layout
        factor_galvo2_layout.addLayout(left_column_layout)
        factor_galvo2_layout.addLayout(right_column_layout)

        factor_galvo2_group.setLayout(factor_galvo2_layout)
        main_layout.addWidget(factor_galvo2_group)

        self.setLayout(main_layout)

    def toggle_slider(self):        
        """
        Toggles the slider and button states based on whether the second galvo is enabled.

        This method changes the state of the factor slider and galvo2 position slider
        and updates the button text to reflect the current state.
        """
        if self.slider2.isEnabled():
            self.slider2.setEnabled(False)
            self.btn_set_factor.setEnabled(False)
            self.btn_set_galvo2_pos.setEnabled(True)

            self.slider3.setEnabled(True)
            self.Galvo2_Enable = False
            self.btn_toggle_slider.setText('2nd Galvo with Ramp')
        else:
            self.slider2.setEnabled(True)
            self.btn_set_factor.setEnabled(True)
            self.btn_set_galvo2_pos.setEnabled(False)

            self.slider3.setEnabled(False)

            self.Galvo2_Enable = True
            self.btn_toggle_slider.setText(' Static 2nd Galvo')

    def get_Galvo2_Enable(self) :
        """
        Gets the current state of the second galvo enable flag.

        Returns:
            bool: The current state of the second galvo enable flag.
        """
        return self.Galvo2_Enable

    def update_voltage_label(self):  
        """
        Updates the voltage and angle labels based on the current slider value.

        This method calculates and updates the voltage and angle labels for the main
        control block and adjusts the min and max degree labels if min and max voltages are set.
        """
        voltage = self.slider.value() / 10.0  # Calculate the voltage from the slider value
        self.label_voltage.setText(f'Voltage: {voltage:.1f} V')  # Update the voltage label

        angle = voltage * (max_scan_angle / voltage_range)  # Calculate the angle from the voltage
        self.label_angle.setText(f'Angle: {angle:.1f} °')  # Update the angle label

        if self.min_voltage is not None:  # Check if min voltage is set
            min_degrees = self.min_voltage * (max_scan_angle / voltage_range)  # Calculate min degrees
            self.label_min_degrees.setText(f'Min Degrees: {min_degrees:.1f}°')  # Update min degrees label

        if self.max_voltage is not None:  # Check if max voltage is set
            max_degrees = self.max_voltage * (max_scan_angle / voltage_range)  # Calculate max degrees
            self.label_max_degrees.setText(f'Max Degrees: {max_degrees:.1f}°')  # Update max degrees label

    def update_galvo2_position_label(self):
        """
        Updates the voltage and angle labels for the galvo2 position.

        This method calculates and updates the voltage and angle labels for the galvo2
        control block based on the current slider value.
        """
        voltage = self.slider3.value() / 10.0  # Calculate the voltage from the slider3 value
        self.label_voltage_galvo2.setText(f'Voltage: {voltage:.1f} V')  # Update the voltage label
        angle = voltage * (max_scan_angle / voltage_range)  # Calculate the angle from the voltage
        self.label_angle_galvo2.setText(f'Angle: {angle:.1f} °')  # Update the angle label 

    def update_factor_label(self):  
        """
        Updates the factor label based on the current slider value.

        This method calculates and updates the factor label for the factor control block.
        """
        factor = self.slider2.value() / 100.0  # Calculate the factor from the slider value
        self.label_factor.setText(f'Factor : x {factor:.2f}')  # Update the factor label

    def set_max_voltage(self):
        """
        Sets the maximum voltage based on the current slider value.

        This method stops the current task, updates the maximum voltage, and writes the
        value to the device. It also updates the max voltage label and restarts the task.
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

    def set_galvo2_voltage(self):  
        """
        Sets the galvo2 voltage based on the current slider value.

        This method stops the current task, updates the galvo2 voltage, and writes the
        value to the device. It also updates the galvo2 voltage label and restarts the task.
        """
        self.stop_task()  # Stop the current task
        galvo2_Value = self.slider3.value() / 10.0  # Get the min voltage from the slider
        self.galvo2_Value = galvo2_Value
        self.label_voltage_galvo2.setText(f'Min Voltage: {galvo2_Value:.1f} V')  # Update the min voltage label
        self.setting_min = True  # Set the flag to indicate min voltage is being set
        self.update_galvo2_position_label()  # Update the voltage and angle labels
        print(f"Min voltage : {galvo2_Value} V ")
        # Apply min voltage to the device
        try:
            with nidaqmx.Task() as task:  # Create a new NI-DAQmx task
                task.ao_channels.add_ao_voltage_chan('Dev1/ao18')  # Add an analog output channel
                task.start()  # Start the task
                task.write(galvo2_Value)  # Write the min voltage to the channel
        except nidaqmx.errors.DaqError as e:  # Handle DAQ errors
            print(f"DAQ Error: {e}")

        self.start_task()  # Restart the task


    def set_min_voltage(self):  
        """
        Sets the minimum voltage based on the current slider value.

        This method stops the current task, updates the minimum voltage, and writes the
        value to the device. It also updates the min voltage label and restarts the task.
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
        Gets the maximum voltage.

        Returns:
            float: The maximum voltage.
        """
        return self.max_voltage

    def get_min_voltage(self):
        """
        Gets the minimum voltage.

        Returns:
            float: The minimum voltage.
        """
        return self.min_voltage

    def get_galvo2_Value(self):
        """
        Gets the galvo2 voltage.

        Returns:
            float: The galvo2 voltage.
        """
        return self.galvo2_Value



    def set_factor_value(self):  
        """
        Sets the factor value based on the current slider value.

        This method stops the current task, updates the factor value, and writes the
        value to the device based on whether the second galvo is enabled. It also updates
        the factor label and restarts the task.

        """
        self.stop_task()  # Stop the current task
        factor = self.slider2.value() / 100.0  # Get the factor from the slider
        min_voltage=self.get_min_voltage()
        max_voltage=self.get_max_voltage()
        Galvo2_Enable = self.get_Galvo2_Enable()
        galvo2_Value= self.get_galvo2_Value()
        self.factor = factor  # Set the factor
        self.label_factor.setText(f'Factor: x {factor:.1f} ')  # Update the factor label
        self.setting_factor = True  # Set the flag to indicate factor is being set
        self.update_factor_label()  # Update the factor label
        print(f"Factor : x {factor} ")

        if (Galvo2_Enable == True) :
            try:
                with nidaqmx.Task() as task:  # Create a new NI-DAQmx task
                    task.ao_channels.add_ao_voltage_chan('Dev1/ao18')  # Add an analog output channel
                    task.start()  # Start the task
                    if (factor*min_voltage<=-10) :
                        task.write(-10)  # Write the factor to the channel
                    elif (factor*min_voltage>=10) :
                        task.write(10)  # Write the factor to the channel
                    else :  
                        task.write(factor*min_voltage)  # Write the factor to the channel

                    if (factor*max_voltage<=-10) :
                        task.write(-10)  # Write the factor to the channel
                    elif (factor*max_voltage>=10) :
                        task.write(10)  # Write the factor to the channel
                    else :  
                        task.write(factor*max_voltage)  # Write the factor to the channel

                    
            except nidaqmx.errors.DaqError as e:  # Handle DAQ errors
                print(f"DAQ Error with factor value: {e}")

        else :
            try:
                with nidaqmx.Task() as task:  # Create a new NI-DAQmx task
                    task.ao_channels.add_ao_voltage_chan('Dev1/ao18')  # Add an analog output channel
                    task.start()  # Start the task
                    task.write(galvo2_Value)  # Write the factor to the channel
                
            except nidaqmx.errors.DaqError as e:  # Handle DAQ errors
                print(f"DAQ Error with factor value: {e}")            


        self.start_task()  # Restart the task

    def get_factor(self):  
        """
        Retrieves the current factor value.

        This method returns the factor value used in calculations. If the factor is not set,
        it returns a default value of 1.

        Returns:
        float: The current factor value, or 1 if the factor is not set.
        """
        if self.factor == None :
            return 1
        else :
            return self.factor  # Return the factor
        
    def set_step_factor_value(self):  
        """
        Sets the factor value based on the current the line edit.

        This method stops the current task, updates the step factor value, it also updates
        the step factor label and restarts the task.

        """
        self.stop_task()  # Stop the current task
        try:
            step_factor_value = float(self.step_factor_value_line_edit.text())  # Get the Step Factor Value from the line edit
            print(f"Step Factor Value : {step_factor_value} ms")  # Print the new Step Factor Value
        except ValueError:  # Handle invalid input
            print("Invalid Step Factor Value entered.")
        self.start_task()  # Restart the task


    def get_step_factor_value(self):  
        """
        Gets the step factor value.

        Returns:
            float: The step factor value.
        """
        return self.step_factor_value

    def apply_settings(self):  
        """
        Applies the exposure settings from the user input.

        This method retrieves the exposure time from the line edit, updates the global exposure
        time variable, and restarts the task. It handles invalid input by printing an error message.

        Raises:
        ValueError: If the text in the line edit cannot be converted to a float.
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
        Starts a new task in a separate thread.

        This method creates and starts a new thread, moves the galvo worker to the thread,
        and connects the worker's signals to the appropriate slot functions to handle task completion.

        The thread is started, and upon completion, it is cleaned up.
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
        Stops the currently running task and cleans up resources.

        This method checks if the galvo worker exists, stops it if running, and then quits
        and waits for the thread to finish.

        If the worker is not running or does not exist, this method does nothing.
        """
        if hasattr(self, 'galvo_worker') and self.galvo_worker is not None:  # Check if the worker exists
            self.galvo_worker.stop()  # Stop the worker
            self.thread.quit()  # Quit the thread
            self.thread.wait()  # Wait for the thread to finish


class FileExplorerWidget(QWidget):
    """
    A widget for selecting and displaying information from MDA sequence files.

    This widget allows users to select a file, read and parse its content, and display
    relevant information including exposure values, number of slices, and acquisition order.

    Attributes:
        exposure_values (list of float): List to store exposure values for each channel.
        num_slices (int): Number of slices extracted from the file.
        num_frames (int): Number of frames extracted from the file.
        Acq_order (int): Acquisition order mode extracted from the file.
    """
    def __init__(self):
        super().__init__()
        self.exposure_values = []  # List to store exposure values for each channel
        self.num_slices = 0
        self.num_frames = 0
        self.init_ui()
        self.list_of_channels = []
        self.FW = 0
        self.amp = 0
        self.list_of_channels = 0

    def init_ui(self):
        """
        Initializes the user interface for the widget.

        Sets up the layout, buttons, labels, and text edit widgets.
        Connects the file selection button to the appropriate slot.
        """
        layout = QVBoxLayout()

        self.btn_select_file = QPushButton('Select MDA Sequence File')
        self.btn_select_file.clicked.connect(self.select_file)
        layout.addWidget(self.btn_select_file)

        self.label_file_path = QLabel('Selected MDA Sequence File: ')
        layout.addWidget(self.label_file_path)

        self.text_edit_content = QTextEdit()
        self.text_edit_content.setReadOnly(True)
        layout.addWidget(self.text_edit_content)

        self.setLayout(layout)

    def select_file(self):
        """
        Opens a file dialog to select an MDA sequence file.

        Upon selecting a file, updates the file path label and reads and parses the file's content.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "",
                                                   "Text Files (*.txt);;All Files (*)")
        if file_path:
            self.label_file_path.setText(f'Selected File: {file_path}')
            self.read_and_parse_file(file_path)

    def read_and_parse_file(self, file_path):
        """
        Reads and parses the selected file's content.

        Opens the file, loads its JSON content, and extracts relevant data.

        Args:
            file_path (str): Path to the file to be read and parsed.

        Raises:
            IOError: If there is an issue reading the file.
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                self.extract_data(data)
        except IOError as e:
            print(f"Error reading file: {e}")

    def extract_data(self, data):
        """
        Extracts and processes data from the parsed JSON content.

        Updates the attributes with exposure values, number of slices, number of frames,
        and acquisition order from the provided data.

        Args:
            data (dict): Parsed JSON data containing exposure values, slices, frames, and acquisition order.
        """
        # Extract the list of channels from the data
        channels = data.get('channels', [])
        
        # Extract exposure values for each channel
        self.exposure_values = [channel.get('exposure', 0.0) for channel in channels]

        # Extract the number of slices from the data
        self.num_slices = len(data.get('slices', []))
        
        # Extract the number of frames from the data
        self.num_frames = data.get('numFrames', 0)
        
        # Extract the acquisition order mode from the data
        self.Acq_order = data.get('acqOrderMode', 0)

        # Dictionary to store exposure values grouped by filter wheel ID
        filter_wheel_exposures = {}

        # Populate the dictionary with exposure values grouped by filter wheel configuration
        for channel in channels:
            config = channel.get('config', '')
            exposure = channel.get('exposure', 0.0)
            if config.startswith('fw'):
                filter_wheel_id = config.split()[0]  # Extract 'fw1', 'fw2', etc.
                
                if filter_wheel_id not in filter_wheel_exposures:
                    filter_wheel_exposures[filter_wheel_id] = []
                    
                filter_wheel_exposures[filter_wheel_id].append(exposure)

        # Convert dictionary to a list of lists
        self.channels_by_filter_wheel = [filter_wheel_exposures[fw_id] for fw_id in sorted(filter_wheel_exposures)]

        # Calculate the number of unique filter wheel configurations
        self.FW = len(filter_wheel_exposures)
        
        # Calculate the total number of amplifiers
        self.amp = sum(len(exposures) for exposures in filter_wheel_exposures.values()) / max(len(filter_wheel_exposures), 1)

        # Display extracted information (method assumed to be implemented elsewhere)
        self.display_extracted_info()

    def display_extracted_info(self):
        """
        Displays the extracted information in the text edit widget.

        Clears the text edit widget and appends information about acquisition order,
        number of frames, number of slices, and exposure values.
        """
        # Clear the text edit widget
        self.text_edit_content.clear()

        # Append acquisition order information
        self.text_edit_content.append(f"Acquisition Order : {self.Acq_order}")
        if self.Acq_order == 0:
            self.text_edit_content.append("         Time Slice Channel")
        elif self.Acq_order == 1:
            self.text_edit_content.append("         Time Channel Slice")

        # Append number of frames and slices
        self.text_edit_content.append(f"Number of Frames :  {self.num_frames}")
        self.text_edit_content.append(f"Number of Slices :  {self.num_slices}")

        # Append exposure values for each channel
        self.text_edit_content.append("Exposure Values:")
        for idx, exposure in enumerate(self.exposure_values, start=1):
            self.text_edit_content.append(f"        Channel {idx}: {exposure}")

        # Append list of channels (exposure values grouped by filter wheel)
        self.text_edit_content.append("Channels by Filter Wheel (Exposure Values):")
        for idx, exposures in enumerate(self.channels_by_filter_wheel, start=1):
            self.text_edit_content.append(f"    FW Group {idx}: {exposures}")
if __name__ == '__main__':  
    app = QApplication(sys.argv)  # Create the application
    window = MainApp()  # Create an instance of the main application window
    window.setWindowTitle('Projection Imaging')  
    window.show() 
    sys.exit(app.exec()) 
