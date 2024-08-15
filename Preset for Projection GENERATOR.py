# FINALE AND DEFINITIVE VERSION
# RAphael TOSCANO

import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QSpinBox, QPushButton, QTextEdit, QLabel, QMessageBox, QFileDialog
)

class PresetGenerator(QWidget):
    """
    A QWidget-based class that provides a GUI for generating and managing presets.
    
    This class allows users to:
    - Select filters from a list.
    - Specify the number of amplitude presets.
    - Generate presets based on selected filters.
    - Write generated presets to a .cfg file.
    - Remove the generated presets and restore the original content of the .cfg file.
    """

    def __init__(self):
        """
        Initializes the PresetGenerator instance and sets up the user interface.
        """
        super().__init__()
        self.init_ui()
        self.file_path = None  # Path to the selected .cfg file
        self.original_content = None  # Original content of the .cfg file for restoration

    def init_ui(self):
        """
        Sets up the user interface elements and layout.
        """
        # Main layout
        main_layout = QVBoxLayout()

        # Title
        title = QLabel('Select used filter:')
        main_layout.addWidget(title)

        # Create checkboxes for filters
        self.filters = {}
        filter_layout = QVBoxLayout()
        for i in range(1, 7):
            checkbox = QCheckBox(f'fw{i}')
            filter_layout.addWidget(checkbox)
            self.filters[f'fw{i}'] = checkbox
        main_layout.addLayout(filter_layout)

        # Selector for the number of "ao" (amp) presets
        self.amp_spinbox = QSpinBox()
        self.amp_spinbox.setValue(10)
        amp_layout = QHBoxLayout()
        amp_label = QLabel('Number of amplitude for each filter:')
        amp_layout.addWidget(amp_label)
        amp_layout.addWidget(self.amp_spinbox)
        main_layout.addLayout(amp_layout)

        # Button to generate the text
        generate_button = QPushButton('Generate presets')
        generate_button.clicked.connect(self.generate_presets)
        main_layout.addWidget(generate_button)

        # Button to select the .cfg file
        select_file_button = QPushButton('Select .cfg File')
        select_file_button.clicked.connect(self.select_file)
        main_layout.addWidget(select_file_button)

        # Button to write the generated presets to the selected file
        write_button = QPushButton('Write Presets to .cfg File')
        write_button.clicked.connect(self.write_presets)
        main_layout.addWidget(write_button)

        # Text area to display the result
        self.result_text = QTextEdit()
        main_layout.addWidget(self.result_text)

        # Button to remove the written presets
        remove_button = QPushButton('Remove Presets from .cfg File')
        remove_button.clicked.connect(self.remove_presets)
        main_layout.addWidget(remove_button)

        # Window configuration
        self.setLayout(main_layout)
        self.setWindowTitle('Presets "fw amp" Generator')
        self.resize(600, 400)

    def select_file(self):
        """
        Opens a file dialog to select a .cfg file and stores its path.
        Reads and stores the original content of the file for restoration purposes.
        """
        file_name, _ = QFileDialog.getOpenFileName(self, "Select .cfg File", "", "Configuration Files (*.cfg);;All Files (*)")
        if file_name:
            self.file_path = file_name
            # Read and store the original content of the file
            with open(self.file_path, 'r', encoding='utf-8') as file:
                self.original_content = file.read()
            QMessageBox.information(self, 'File Selected', f'Selected file: {file_name}')
        else:
            self.file_path = None
            self.original_content = None

    def generate_presets(self):
        """
        Generates the preset configurations based on selected filters and amplitude values.
        Updates the text area with the generated presets.
        """
        selected_filters = [fw for fw, checkbox in self.filters.items() if checkbox.isChecked()]
        num_amp = self.amp_spinbox.value()

        if not selected_filters:
            QMessageBox.warning(self, 'Error', 'Please select at least 1 filter.')
            return

        result = f"# Group: FW AMP\n"
        for fw in selected_filters:
            for amp in range(num_amp, 0, -1):
                result += f"# Preset: {fw} amp{amp}\n"
                result += f"ConfigGroup,FW AMP,{fw} amp{amp},Filter wheel 1,Label,Filter-{fw[-1]}\n"
                result += f"ConfigGroup,FW AMP,{fw} amp{amp},NIDAQAO-Dev1/ao1,Voltage,0.000{amp}\n\n"

        self.result_text.setText(result)

    def write_presets(self):
        """
        Writes the generated presets to the selected .cfg file.
        Inserts the presets after the line containing "# Configuration presets".
        """
        if not self.file_path:
            QMessageBox.warning(self, 'Error', 'No .cfg file selected.')
            return

        # Generate the presets text if it hasn't been generated yet
        if not self.result_text.toPlainText():
            self.generate_presets()

        try:
            with open(self.file_path, 'r+', encoding='utf-8') as file:
                lines = file.readlines()

                # Find the position to insert new lines
                insert_pos = -1
                for i, line in enumerate(lines):
                    if "# Configuration presets" in line:
                        insert_pos = i + 1  # Insert 1 line after finding the group
                        break

                if insert_pos == -1:
                    raise ValueError("The specified group was not found in the file.")

                # Get the generated presets
                new_lines = self.result_text.toPlainText().splitlines(True)

                # Insert the new presets into the file content
                lines[insert_pos:insert_pos] = new_lines

                # Write the updated content back to the file
                file.seek(0)
                file.writelines(lines)

            QMessageBox.information(self, 'Success', 'Presets written to the file successfully.')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to write to the file: {e}')

    def remove_presets(self):
        """
        Removes the generated presets from the .cfg file and restores the original content.
        """
        if not self.file_path or not self.original_content:
            QMessageBox.warning(self, 'Error', 'No .cfg file selected or no original content to restore.')
            return

        try:
            with open(self.file_path, 'w', encoding='utf-8') as file:
                # Write the original content back to the file
                file.write(self.original_content)
            QMessageBox.information(self, 'Success', 'Presets removed and original content restored successfully.')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to restore the file: {e}')

def main():
    """
    Entry point of the application.
    Initializes the QApplication and displays the PresetGenerator widget.
    """
    app = QApplication(sys.argv)
    generator = PresetGenerator()
    generator.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
