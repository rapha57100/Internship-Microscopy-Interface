from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import (
    QMainWindow,
    QApplication,
    QHBoxLayout, QVBoxLayout, QGridLayout,
    QGroupBox,
    QFormLayout,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QSlider

)

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap,QIcon
import numpy as np
import cv2

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import math

from pathlib import Path
import numpy as np
import nidaqmx
from nidaqmx.stream_writers import AnalogSingleChannelWriter
from pymmcore_widgets import (
    ShuttersWidget, DeviceWidget, StageWidget,
    ConfigurationWidget, 
    ExposureWidget,
    ImagePreview,
    LiveButton,
    SnapButton,
    PropertyWidget,

)
ICONS = Path(__file__).parent.parent / "icons"


class ConfigurationManager(QWidget):
    def __init__(self):
        self.app = QApplication([])

    def run(self):
        mmc = CMMCorePlus().instance()
        mmc.loadSystemConfiguration()
        wiz = ConfigurationWidget()
        wiz.show()
        self.app.exec_()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Main Window")   # Title of the window

        # Widgets creation
        self.camera_widget = CameraView()
        self.CoherentObisController_widget = CoherentObisController()
        self.FISBAController_widget = FISBAController()
        self.galvo1_widget = Galvo1Control()
        self.galvo2_widget = Galvo2Control()
        self.filter_wheel_widget = FilterWheelConnexion() 
        self.stage_control_widget = StageControlWidget()
        self.image_and_hist_widget = ImageAndHistogramWidget()  

        # Add widgets to the main window
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        # Add widgets in a grid
        grid_layout = QGridLayout()
        grid_layout.addWidget(self.camera_widget, 0, 0,10,15)
        grid_layout.addWidget(self.image_and_hist_widget, 11, 0,10,15) 
        grid_layout.addWidget(self.filter_wheel_widget, 0, 18,8,8)
        grid_layout.addWidget(self.CoherentObisController_widget, 9, 16,5,15)
        grid_layout.addWidget(self.FISBAController_widget, 15, 20,5,5)
        grid_layout.addWidget(self.stage_control_widget, 0, 31,15,20)
        grid_layout.addWidget(self.galvo1_widget, 16, 35,3,6)
        grid_layout.addWidget(self.galvo2_widget, 16, 42,3,6)

        layout.addLayout(grid_layout)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

class CameraView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.camera_thread = None
        self.current_frame = None
        self.frame_for_saving = None
        self.preview = ImagePreview() 
        self.snap_button = SnapButton()
        self.live_button = LiveButton()
        self.exposure = ExposureWidget()
        self.exposure._mmc.events.exposureChanged.connect(self.update_exposure)
        self.actual_exposure = None

        self.mmc = CMMCorePlus.instance()

        # Create Main layout
        main_layout = QHBoxLayout(self)

        # Add Preview window to the left side
        main_layout.addWidget(self.preview)

        # Create layout for buttons and exposure controls
        buttons_and_exposure_layout = QVBoxLayout()

        # Add exposure group to the layout
        exposure_group = QGroupBox("Exposure")
        exposure_layout = QVBoxLayout(exposure_group)
        exposure_layout.addWidget(self.exposure)
        exposure_group.setLayout(exposure_layout)
        buttons_and_exposure_layout.addWidget(exposure_group)

        # Create and add Snap and Save group-buttons 
        buttons_group = QGroupBox("Snap & Save")
        buttons_layout = QVBoxLayout(buttons_group)

        snap_button = QPushButton("Snap")
        snap_button.pressed.connect(self.snap_blocking)

        # Create Save button with icon
        save_button = QPushButton()
        icon = QIcon.fromTheme("document-save")  # Utilise un icône prédéfini pour "Save"
        save_button.setIcon(icon)
        save_button.setToolTip("Save")
        save_button.pressed.connect(self.save_photo)

        buttons_layout.addWidget(snap_button)
        buttons_layout.addWidget(save_button)
        buttons_group.setLayout(buttons_layout)

        # Add buttons group to the layout
        buttons_and_exposure_layout.addWidget(buttons_group)

        # Add Live button below the Snap & Save buttons
        buttons_and_exposure_layout.addWidget(self.live_button)

        # Add the buttons and exposure layout to the main layout
        main_layout.addLayout(buttons_and_exposure_layout)

    def update_exposure(self, camera: str, exposure: float):
        if camera == self.exposure._camera:
            self.exposure.spinBox.setValue(exposure)
            self.actual_exposure = exposure

    def snap_blocking(self):
        self.mmc.snapImage()  # Capturer l'image
        self.mmc.popNextImage()
        img = self.mmc.popNextImage()
        self.mmc.fixImage(img)
        self.frame_for_saving = self.mmc.fixImage(img)  # Sauvegarde l'image capturée dans frame_for_saving
        
        # Définir le chemin de sauvegarde prédéfini
        save_folder = r"C:\Users\ratos9288\OneDrive - UiT Office 365\Documents\.venv\pictures_test"

        
       # Save the temporary image in the predefined folder
        temp_image_path = os.path.join(save_folder, "temp_image.tiff")
        cv2.imwrite(temp_image_path, self.frame_for_saving)

        # Pass the image path to ImageAndHistogramWidget
        self.image_and_hist_widget = ImageAndHistogramWidget(temp_image_path)

    def save_photo(self):
        if not hasattr(self, 'frame_for_saving') or self.frame_for_saving is None or self.frame_for_saving.size == 0:
            self.error_label.setText("No frame to save.")
            return  # No frame to save

        # Convert the frame to a format suitable for saving if needed
        if not isinstance(self.frame_for_saving, np.ndarray):
            self.error_label.setText("Captured frame is not a valid image format.")
            return

        # Open file dialog to choose save location
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "TIFF Files (*.tiff *.tif)")

        if file_path:
            try:
                # Save current frame as TIFF
                cv2.imwrite(file_path, self.frame_for_saving)
                self.error_label.setText("Image saved successfully.")
            except cv2.error as e:
                self.error_label.setText(f"Error saving image: {e}")


class ImageAndHistogramWidget(QMainWindow):
    def __init__(self, image_path=r"C:\Users\ratos9288\OneDrive - UiT Office 365\Documents\.venv\pictures_test\temp_image.tiff"):
        super().__init__()
        self.image_path = image_path
        self.image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        self.hist_min, self.hist_max = self.calculate_auto_contrast(self.image)  # Calculer le contraste automatiquement
        self.max_16bit_value = 65535  # Valeur maximale pour une profondeur de 16 bits

        self.setWindowTitle('Image and Histogram')
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout()

        # Horizontal layout for image and histogram
        image_and_hist_layout = QHBoxLayout()
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_and_hist_layout.addWidget(self.image_label)
        
        self.figure = Figure(figsize=(30, 20))
        self.canvas = FigureCanvas(self.figure)
        image_and_hist_layout.addWidget(self.canvas)

        layout.addLayout(image_and_hist_layout)
        
        # Vertical layout for sliders below the histogram
        sliders_layout = QVBoxLayout()
        
        self.slider_min = QSlider(Qt.Orientation.Horizontal)
        self.slider_min.setMinimum(0)
        self.slider_min.setMaximum(int(self.max_16bit_value ))
        self.slider_min.setValue(int(self.hist_min))
        self.slider_min.valueChanged.connect(self.update_display)
        sliders_layout.addWidget(self.slider_min)
        
        self.slider_max = QSlider(Qt.Orientation.Horizontal)
        self.slider_max.setMinimum(0)
        self.slider_max.setMaximum(int(self.max_16bit_value))
        self.slider_max.setValue(int(self.hist_max))
        self.slider_max.valueChanged.connect(self.update_display)
        sliders_layout.addWidget(self.slider_max)
        
        layout.addLayout(sliders_layout)

        # Add the button to reset histogram to automatic values
        reset_button = QPushButton("Reset Histogram")
        reset_button.clicked.connect(self.reset_histogram)
        layout.addWidget(reset_button)

        # Button to manually update the image
        update_button = QPushButton("Refresh Image")
        update_button.clicked.connect(self.update_image_from_file)
        layout.addWidget(update_button)

        # Group box for adjusted image stats
        adjusted_stats_box = QGroupBox("Adjusted Image Stats")
        adjusted_stats_layout = QVBoxLayout()

        self.min_label = QLabel()
        self.max_label = QLabel()
        self.mean_label = QLabel()

        adjusted_stats_layout.addWidget(self.min_label)
        adjusted_stats_layout.addWidget(self.max_label)
        adjusted_stats_layout.addWidget(self.mean_label)

        adjusted_stats_box.setLayout(adjusted_stats_layout)

        # Group box for raw image stats
        raw_stats_box = QGroupBox("Raw Image Stats")
        raw_stats_layout = QVBoxLayout()

        self.raw_min_label = QLabel()
        self.raw_max_label = QLabel()
        self.raw_mean_label = QLabel()

        raw_stats_layout.addWidget(self.raw_min_label)
        raw_stats_layout.addWidget(self.raw_max_label)
        raw_stats_layout.addWidget(self.raw_mean_label)

        raw_stats_box.setLayout(raw_stats_layout)

        # Group box for histogram slider values
        slider_values_box = QGroupBox("Histogram Slider Values")
        slider_values_layout = QVBoxLayout()

        self.slider_min_label = QLabel()
        self.slider_max_label = QLabel()

        slider_values_layout.addWidget(self.slider_min_label)
        slider_values_layout.addWidget(self.slider_max_label)

        slider_values_box.setLayout(slider_values_layout)

        # Horizontal layout to contain the three boxes
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(adjusted_stats_box)
        stats_layout.addWidget(raw_stats_box)
        stats_layout.addWidget(slider_values_box)

        layout.addLayout(stats_layout)

        self.central_widget.setLayout(layout)
        
        self.update_display()

        # Setup timer to update the image every 500 ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_image_from_file)

    def calculate_auto_contrast(self, image):
        # Calculer le contraste automatiquement
        min_val, max_val, _, _ = cv2.minMaxLoc(image)
        return min_val, max_val

    def update_image_from_file(self):
        # Read the image from the file
        self.image = cv2.imread(self.image_path, cv2.IMREAD_UNCHANGED)
        if self.image is not None:
            self.update_display()



    def update_display(self):
        if self.image is None:
            return

        self.hist_min = self.slider_min.value()
        self.hist_max = self.slider_max.value()
        
        # Normalize the image and adjust contrast
        normalized_image = (self.image - self.hist_min) / (self.hist_max - self.hist_min)
        adjusted_image = np.clip(normalized_image, 0, 1) * self.max_16bit_value
        adjusted_image = adjusted_image.astype(np.uint16)

        # Update min, max, and mean labels for adjusted image
        min_val = adjusted_image.min()
        max_val = adjusted_image.max()
        mean_val = adjusted_image.mean()
        self.min_label.setText(f"Adjusted Min: {min_val}")
        self.max_label.setText(f"Adjusted Max: {max_val}")
        self.mean_label.setText(f"Adjusted Mean: {mean_val:.2f}")

        # Update min, max, and mean labels for raw image
        raw_min_val = self.image.min()
        raw_max_val = self.image.max()
        raw_mean_val = self.image.mean()
        self.raw_min_label.setText(f"Raw Min: {raw_min_val}")
        self.raw_max_label.setText(f"Raw Max: {raw_max_val}")
        self.raw_mean_label.setText(f"Raw Mean: {raw_mean_val:.2f}")

        # Update slider values
        self.slider_min_label.setText(f"Histogram Min Slider: {self.hist_min}")
        self.slider_max_label.setText(f"Histogram Max Slider: {self.hist_max}")

        # Convert to QImage
        qimage = QImage(adjusted_image.data, adjusted_image.shape[1], adjusted_image.shape[0], adjusted_image.strides[0], QImage.Format.Format_Grayscale16)
        pixmap = QPixmap.fromImage(qimage)
        
        # Display the image
        self.image_label.setPixmap(pixmap.scaled(self.image_label.width(), self.image_label.height(), Qt.AspectRatioMode.KeepAspectRatio))
        
        # Calculate and display the histogram
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('gray')  # Définir la couleur de fond en gris
        hist = cv2.calcHist([adjusted_image], [0], None, [self.max_16bit_value + 1], [0, self.max_16bit_value])
        ax.plot(hist, color='white',alpha=0.9)
        ax.set_xlim([0, self.max_16bit_value])
        ax.set_ylim([0, hist.max()])  # Assurer que les données sont tracées dans la plage des axes y
        ax.set_xlabel('Intensity of pixels', color='black', fontsize=6)  
        ax.set_ylabel('Frequency', color='black', fontsize=6)  
        ax.xaxis.label.set_color('black') 
        ax.yaxis.label.set_color('black')
        ax.xaxis.label.set_size(6) 
        ax.yaxis.label.set_size(6)  
        # ax.spines['bottom'].set_color('black')
        # ax.spines['top'].set_color('black') 
        # ax.spines['right'].set_color('black')
        # ax.spines['left'].set_color('black')
        ax.tick_params(axis='x', colors='blue', labelsize=6) 
        ax.tick_params(axis='y', colors='black', labelsize=6) 
        ax.autoscale(enable=True, axis='both', tight=True)  # Ajuster automatiquement les échelles des axes

        # Définir les étiquettes de l'axe x
        ax.set_xticks([ self.hist_min, self.hist_max])
        ax.set_xticklabels([f'{self.hist_min}', f'{self.hist_max}'])

        # Calculer l'histogramme de l'image brute
        raw_hist = cv2.calcHist([self.image], [0], None, [self.max_16bit_value + 1], [0, self.max_16bit_value])

        # Ajouter une seconde courbe à l'histogramme
        ax.fill_between(np.arange(self.max_16bit_value + 1), raw_hist.flatten(), color='blue', alpha=0.3)  # Ajouter une courbe bleue transparente pour l'histogramme de l'image brute

        self.canvas.draw()


    def reset_histogram(self):
        self.hist_min, self.hist_max = self.calculate_auto_contrast(self.image)
        self.slider_min.setValue(int(self.hist_min))
        self.slider_max.setValue(int(self.hist_max))
        self.update_display()


class StageControlWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mmc = CMMCorePlus().instance()
        self.setLayout(QHBoxLayout())

        stage_dev_list = list(self.mmc.getLoadedDevicesOfType(DeviceType.XYStage))
        stage_dev_list.extend(self.mmc.getLoadedDevicesOfType(DeviceType.Stage))

        for stage_dev in stage_dev_list:
            if self.mmc.getDeviceType(stage_dev) is DeviceType.XYStage:
                bx = QGroupBox("XY Control")
                bx.setLayout(QHBoxLayout())
                stage_widget = StageWidget(device=stage_dev)
                bx.layout().addWidget(stage_widget)
                self.layout().addWidget(bx)
       
            if self.mmc.getDeviceType(stage_dev) is DeviceType.Stage:
                bx = QGroupBox("Z Control")
                bx.setLayout(QHBoxLayout())
                stage_widget = StageWidget(device=stage_dev)
                bx.layout().addWidget(stage_widget)
                self.layout().addWidget(bx)


class CoherentObisController(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Set the layout of the CoherentObisController widget
        self.setLayout(QVBoxLayout())

        self._mmc = CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self._on_cfg_loaded)  # Connect the event to _on_cfg_loaded method

        self._on_cfg_loaded()  # Load the configuration initially

    def _on_cfg_loaded(self) -> None:
        shutters_devs = self._mmc.getLoadedDevicesOfType(DeviceType.ShutterDevice)
        shutter = shutters_devs[-1]  # Get the last shutter device
        s = ShuttersWidget(shutter, autoshutter=True)  # Create ShuttersWidget , but COMMENT  in shutterwidget.py # main_layout.addWidget(self.autoshutter_checkbox)

        s.button_text_open = shutter  # Set button text when open
        s.button_text_closed = shutter  # Set button text when closed

        # Create a QGroupBox for the property widgets
        properties_group = QGroupBox("Properties")
        form_layout = QFormLayout()
        properties_group.setLayout(form_layout)

        # List of device-property
        devs_pros = [
            ("CoherentObis", "Minimum Laser Power"),
            ("CoherentObis", "Maximum Laser Power"),
            ("CoherentObis", "PowerSetpoint"),
            ("CoherentObis", "Wavelength"),
        ]

        # Add each property widget to the form layout
        for dev, prop in devs_pros:
            prop_wdg = PropertyWidget(dev, prop)
            form_layout.addRow(f"{prop}:", prop_wdg)

        # Create a main group box to contain both the shutter widget and property widgets
        main_group_box = QGroupBox("Coherent® OBIS™ Controller")
        main_layout = QVBoxLayout()
        main_group_box.setLayout(main_layout)

        # Add the shutter widget and properties group box to the main layout
        main_layout.addWidget(s)
        main_layout.addWidget(properties_group)

        # Add the main group box to the main layout of CoherentObisController
        self.layout().addWidget(main_group_box)


class FISBAController(QMainWindow):
    def __init__(self):
        super().__init__()

        # Group box to contain the laser controls
        self.laser_box = QGroupBox("FISBA READYBeam™ Controller")
        self.laser_layout = QVBoxLayout()
        self.laser_box.setLayout(self.laser_layout)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.layout.addWidget(self.laser_box)

        self.initUI()

        # # Create a task to manage the DAQ channels
        # self.task = nidaqmx.Task()

        # # Add analog output channels to control laser pin voltages
        # self.task.ao_channels.add_ao_voltage_chan("Dev1/ao2")  # Analog output channel for red laser
        # self.task.ao_channels.add_ao_voltage_chan("Dev1/ao4")  # Analog output channel for green laser
        # self.task.ao_channels.add_ao_voltage_chan("Dev1/ao6")  # Analog output channel for blue laser

        # # Add digital output channels to enable/disable the laser
        # self.task.do_channels.add_do_chan("Dev1/port0/line8")  # Digital output channel for red laser
        # self.task.do_channels.add_do_chan("Dev1/port0/line9")  # Digital output channel for green laser
        # self.task.do_channels.add_do_chan("Dev1/port0/line10")  # Digital output channel for blue laser

    def initUI(self):
        self.laser_controls = {}

        # Create UI elements for each laser
        for idx, (color, wavelength, max_power_mW) in enumerate([('Red', '638 nm', 40), ('Blue', '488 nm', 30), ('UV', '405 nm', 40)]):
            laser_widget = QWidget()
            laser_layout = QVBoxLayout()
            laser_widget.setLayout(laser_layout)

            # Add label for laser description
            label = QLabel(f"{wavelength} ({color}) Laser:")
            laser_layout.addWidget(label)

            # Add button to turn laser on/off
            on_off_button = QPushButton("Turn On")
            on_off_button.setCheckable(True)
            on_off_button.clicked.connect(lambda checked, idx=idx: self.toggle_laser(idx))
            laser_layout.addWidget(on_off_button)

            # Add slider to control laser power
            power_layout = QHBoxLayout()
            laser_layout.addLayout(power_layout)

            power_slider = QSlider(Qt.Orientation.Horizontal)
            power_slider.setMinimum(10)  # Set minimum to 10%
            power_slider.setMaximum(100)
            power_slider.setTickInterval(10)
            power_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            power_slider.valueChanged.connect(lambda val, idx=idx: self.set_laser_power(val, idx))
            power_layout.addWidget(power_slider)

            # Add labels to display power percentage and mW
            percent_label = QLabel("10 %")
            power_layout.addWidget(percent_label)

            mw_label = QLabel("0 mW")
            power_layout.addWidget(mw_label)

            # Store references to UI elements for later use
            self.laser_controls[idx] = {'on_off_button': on_off_button, 'power_slider': power_slider, 'percent_label': percent_label, 'mw_label': mw_label, 'max_power_mW': max_power_mW}

            self.laser_layout.addWidget(laser_widget)

    # Callback function to toggle laser on/off
    def toggle_laser(self, idx):
        button = self.laser_controls[idx]['on_off_button']
        if button.isChecked():
            button.setText("Turn Off")
            # Activate the laser
            # self.task.write(True, auto_start=True)
        else:
            button.setText("Turn On")
            # Deactivate the laser
            # self.task.write(False, auto_start=True)

    # Callback function to set laser power
    def set_laser_power(self, value, idx):
        # Update power labels
        self.update_mW_value(value, idx)
        # Calculate corresponding voltage in volts (from 0 to 3.3V)
        voltage = value / 100 * 3.3
        # Send voltage to the corresponding analog output channel
        # self.task.write_voltage(voltage, auto_start=True)

    # Update power labels with percentage and mW values
    def update_mW_value(self, value, idx):
        max_power_mW = self.laser_controls[idx]['max_power_mW']
        power_mW = value * max_power_mW / 100
        self.laser_controls[idx]['percent_label'].setText(f"{value} %")
        self.laser_controls[idx]['mw_label'].setText(f"{power_mW} mW")

    # Override closeEvent to stop and close the task when the window is closed
    def closeEvent(self, event):
        # self.task.stop()
        # self.task.close()
        event.accept()


class Galvo1Control(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.galvo1_task = nidaqmx.Task()
        self.galvo1_task.ao_channels.add_ao_voltage_chan('Dev1/ao18')
        self.last_position_degrees = 0  # Last recorded position in degrees
        self.create_layout()

    def create_layout(self):
        layout = QVBoxLayout()

        # Add button to move galvo1
        self.move_button = QPushButton("Move Galvo1")
        self.move_button.clicked.connect(self.move_galvo1)
        layout.addWidget(self.move_button)

        # Widgets for user input
        self.degrees_label = QLabel("Move from : ___ degrees")
        self.degrees_lineedit = QLineEdit()
        layout.addWidget(self.degrees_label)
        layout.addWidget(self.degrees_lineedit)

        self.duration_label = QLabel("Movement Duration (milliseconds):")
        self.duration_lineedit = QLineEdit()
        layout.addWidget(self.duration_label)
        layout.addWidget(self.duration_lineedit)

        self.setLayout(layout)

    def move_galvo1(self):
        total_degrees = float(self.degrees_lineedit.text())
        duration_milliseconds = float(self.duration_lineedit.text())

        print("Moving Galvo1...")

        # DATASHEET
        max_scan_angle = 12.5  # Max degrees (±12.5°)
        voltage_range = 10     # Max voltage output (±10 V)
        voltage_ratio = 0.8    # Voltage ratio (0.5, 0.8 or 1)

        # Calculate the new position after the move
        new_position_degrees = self.last_position_degrees + total_degrees

        # Check if the new position exceeds the limits
        if new_position_degrees > max_scan_angle:
            print("maximum position reached")
            new_position_degrees = max_scan_angle
        elif new_position_degrees < -max_scan_angle:
            print("minimum position reached.")
            new_position_degrees = -max_scan_angle

        # Conversion degree to Volt
        initial_voltage = self.last_position_degrees * voltage_ratio * (voltage_range / max_scan_angle)
        final_voltage = new_position_degrees * voltage_ratio * (voltage_range / max_scan_angle)

        if duration_milliseconds == 0:  # If step
            self.galvo1_task.write(final_voltage)
        else:
            num_samples = 10000
            sample_rate = num_samples * 1000 / duration_milliseconds

            # Ensure the sample rate does not exceed the device's limit (1 MHz)
            max_sample_rate = 1e6
            if sample_rate > max_sample_rate:
                print(f"Requested sample rate {sample_rate} Hz exceeds the maximum {max_sample_rate} Hz.")
                # Adjust num_samples to stay within limits
                num_samples = int(max_sample_rate * duration_milliseconds / 1000)
                print(f"Adjusted number of samples to {num_samples} to stay within limits. or increases time ")

            # Generate linear movement sequence
            voltages_sequence = np.linspace(initial_voltage, final_voltage, num_samples)

            # Configure task to use clock
            self.galvo1_task.timing.cfg_samp_clk_timing(
                rate=min(sample_rate, max_sample_rate),
                sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                samps_per_chan=num_samples
            )

            # Write sequence to the task
            writer = AnalogSingleChannelWriter(self.galvo1_task.out_stream)
            writer.write_many_sample(voltages_sequence)

            # Start the task
            self.galvo1_task.start()
            self.galvo1_task.wait_until_done()
            self.galvo1_task.stop()

        # Update last position
        self.last_position_degrees = new_position_degrees

        print(f"Galvo1 moved to {new_position_degrees} degrees.")

class Galvo2Control(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.galvo2_task = nidaqmx.Task()
        self.galvo2_task.ao_channels.add_ao_voltage_chan('Dev1/ao18')
        self.last_position_degrees = 0  # Last recorded position in degrees
        self.create_layout()

    def create_layout(self):
        layout = QVBoxLayout()

        # Add button to move galvo2
        self.move_button = QPushButton("Move Galvo2")
        self.move_button.clicked.connect(self.move_galvo2)
        layout.addWidget(self.move_button)

        # Widgets for user input
        self.degrees_label = QLabel("Move from : ___ degrees")
        self.degrees_lineedit = QLineEdit()
        layout.addWidget(self.degrees_label)
        layout.addWidget(self.degrees_lineedit)

        self.duration_label = QLabel("Movement Duration (milliseconds):")
        self.duration_lineedit = QLineEdit()
        layout.addWidget(self.duration_label)
        layout.addWidget(self.duration_lineedit)

        self.setLayout(layout)

    def move_galvo2(self):
        total_degrees = float(self.degrees_lineedit.text())
        duration_milliseconds = float(self.duration_lineedit.text())

        print("Moving Galvo2...")

        # DATASHEET
        max_scan_angle = 12.5  # Max degrees (±12.5°)
        voltage_range = 10     # Max voltage output (±10 V)
        voltage_ratio = 0.8    # Voltage ratio (0.5, 0.8 or 1)

        # Calculate the new position after the move
        new_position_degrees = self.last_position_degrees + total_degrees

        # Check if the new position exceeds the limits
        if new_position_degrees > max_scan_angle:
            print("maximum posisition reached")
            new_position_degrees = max_scan_angle
        elif new_position_degrees < -max_scan_angle:
            print("minimum posisition reached.")
            new_position_degrees = -max_scan_angle

        # Conversion degree to Volt
        initial_voltage = self.last_position_degrees * voltage_ratio * (voltage_range / max_scan_angle)
        final_voltage = new_position_degrees * voltage_ratio * (voltage_range / max_scan_angle)

        if duration_milliseconds == 0:  # If step
            self.galvo2_task.write(final_voltage)
        else:
            num_samples = 10000
            sample_rate = num_samples * 1000 / duration_milliseconds

            # Ensure the sample rate does not exceed the device's limit (1 MHz)
            max_sample_rate = 1e6
            if sample_rate > max_sample_rate:
                print(f"Requested sample rate {sample_rate} Hz exceeds the maximum {max_sample_rate} Hz.")
                # Adjust num_samples to stay within limits
                num_samples = int(max_sample_rate * duration_milliseconds / 1000)
                print(f"Adjusted number of samples to {num_samples} to stay within limits. or increases time ")

            # Generate linear movement sequence
            voltages_sequence = np.linspace(initial_voltage, final_voltage, num_samples)

            # Configure task to use clock
            self.galvo2_task.timing.cfg_samp_clk_timing(
                rate=min(sample_rate, max_sample_rate),
                sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                samps_per_chan=num_samples
            )

            # Write sequence to the task
            writer = AnalogSingleChannelWriter(self.galvo2_task.out_stream)
            writer.write_many_sample(voltages_sequence)

            # Start the task
            self.galvo2_task.start()
            self.galvo2_task.wait_until_done()
            self.galvo2_task.stop()

        # Update last position
        self.last_position_degrees = new_position_degrees

        print(f"Galvo2 moved to {new_position_degrees} degrees.")

class FilterWheelWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedSize(300, 300)  # Set the fixed size
        self.filter_names = ["Filtre 1", "Filtre 2", "Filtre 3", "Filtre 4", "Filtre 5", "Filtre 6"]
        self.setLayout(QGridLayout())  # Set layout to a grid layout
        self.buttons = []  # Initialize an empty list to store buttons
        self.prop_wdg = None  # Initialize the property widget reference to None
        self.create_buttons()  # Call the method to create buttons
        self.arrange_buttons_in_circle()  # Call the method to arrange buttons in a circle

    def create_buttons(self):
        for i, filter_name in enumerate(self.filter_names):  # Iterate over filter names with index
            button = QPushButton(filter_name, self)  # Create a QPushButton for each filter name
            button.setFixedSize(70, 70)  # Set a fixed size for the button
            button.clicked.connect(lambda checked, b=button: self.button_clicked(b))  # Connect the button's click signal to button_clicked method
            self.set_button_style(button)  # Set the button style
            self.buttons.append(button)  # Add the button to the list of buttons

    def set_button_style(self, button):
        if button.property('selected'):  # Check if the button is selected
            button.setStyleSheet("""
                QPushButton {
                    background-color: rgb(96, 150, 186);
                    border-radius: 35px;
                    color: rgb(39, 76, 119);
                    font-weight: bold;
                }
            """)  # Set style for selected button
        else:
            button.setStyleSheet("""
                QPushButton {
                    background-color: rgb(180, 180, 180);
                    border-radius: 35px;
                    color: white;
                    font-weight: bolder;
                }
                QPushButton:hover:!pressed {
                    background: rgb(200, 200, 200); /* Slightly lighter background on hover */
                }
            """)  # Set style for unselected button

    def button_clicked(self, button):
        self.select_button(button)  # Select the clicked button
        self.move_filter(button)  # Move the filter

    def select_button(self, button):
        for btn in self.buttons:  # For each button
            btn.setProperty('selected', btn is button)  # Set the selected property for the clicked button
            self.set_button_style(btn)  # Update the style of the button

    def move_filter(self, button):
        button_index = self.buttons.index(button) + 1  # Get the index of the clicked button
        filter_name = self.filter_names[button_index - 1]  # Get the filter name corresponding to the button index
        print(f"Moving to {filter_name}")  # Print the filter name
        if self.prop_wdg:  # If the PropertyWidget reference is set
            self.prop_wdg.setValue(str(button_index))  # Convert the index to a string and set the value

    def arrange_buttons_in_circle(self):
        center_x, center_y = self.width() // 2, self.height() // 2  # Calculate the center of the widget
        radius = 75  # Set the radius for the circle

        for i, button in enumerate(self.buttons):  # Iterate over all buttons with index
            angle = 2 * math.pi * i / len(self.buttons)  # Calculate the angle for each button
            x = int(center_x + radius * math.cos(angle) - button.width() / 2)  # Calcul x position
            y = int(center_y + radius * math.sin(angle) - button.height() / 2)  # Calcul y position
            button.move(x, y)  # Move the button to the calculated position

class FilterWheelConnexion(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent) 
        self.setLayout(QVBoxLayout())  # Set the layout of the widget to QVBoxLayout
        self.filter_wheel = FilterWheelWidget()  # Create an instance of the FilterWheel class
        self.layout().addWidget(self.filter_wheel)  # Add FilterWheel widget to the layout
        self._mmc = CMMCorePlus.instance()  # Get an instance of the CMMCorePlus class
        self._mmc.events.systemConfigurationLoaded.connect(self._on_cfg_loaded)  # Connect the systemConfigurationLoaded event to _on_cfg_loaded method
        self._on_cfg_loaded()  # Call the _on_cfg_loaded method to load the configuration initially

    def _on_cfg_loaded(self) -> None:
        # Add Filter Wheel DeviceWidget
        FW_devs = self._mmc.getLoadedDevicesOfType(DeviceType.StateDevice)  # Get loaded devices of type StateDevice
        wheel = FW_devs[-1]  # Get the last state device (assuming it is the filter wheel)
        fw = DeviceWidget(wheel)  # Create a DeviceWidget for the filter wheel
        self.layout().addWidget(fw)  # Add the filter wheel widget to the layout

        devs_props = [("Optospin Controller", "Positions"),]

        form_layout = QFormLayout()  # Create a QFormLayout to organize the property widgets
        # self.layout().addLayout(form_layout)  # Add the form layout to the main layout
        for dev, prop in devs_props:  # Iterate over device properties
             prop_wdg = PropertyWidget(dev, prop)  # Create a PropertyWidget for each property
             form_layout.addRow(f"{dev} - {prop}:", prop_wdg)  # Add the property widget to the form layout with a label
             self.filter_wheel.prop_wdg = prop_wdg  # Assign the property widget to the FilterWheel's prop_wdg attribute


if __name__ == "__main__":
    app = QApplication([])

    simple_wizard = ConfigurationManager()
    simple_wizard.run()

    main_window = MainWindow()
    main_window.show()

    app.exec_()
