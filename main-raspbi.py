import cv2
import time
import os
import RPi.GPIO as GPIO
from pynput.keyboard import Key, Controller

class TimeLapseCamera:
    """A class for creating time-lapse videos using a connected camera."""
    
    # Constants
    CAPTURE_INTERVAL = 5  # Interval between image captures in seconds
    DEFAULT_PLAYBACK_SPEED = 1  # Default playback speed when reviewing images
    LOG_PATH = "log.txt"  # Path to the log file
    PROJECTS_FOLDER = "projects"  # Folder where project images are stored
    DEFAULT_PROJECT = "default"  # Default project name
    PLAYBACK_SPEEDS = [16, 32, 64, 128, 256]  # Playback speeds for reviewing images
    WINDOW_NAME = "Zeitmaschine"  # Window name for the display
    PIXEL_LOCATION = [10,10]

    def __init__(self):
        """Initializes the TimeLapseCamera object."""
        # Camera and image tracking
        self.cap = None
        self.active_project = ""
        self.selected_project = ""
        self.selected_project_index = 0
        self.img_file_prefix = "image_"
        self.img_capture_index = 0
        self.img_max_index = 0


        # GPIO Setup
        # BCM-Nummerierung verwenden
        GPIO.setmode(GPIO.BCM)
        self.keyboard = Controller()

        # GPIO 17 (Pin 11) als Ausgang setzen
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(17, GPIO.FALLING, callback = self.interrupt, bouncetime = 200)
        
        # Playback controls
        self.img_shown_index = 1
        self.key = None
        self.playback_speed = self.DEFAULT_PLAYBACK_SPEED
        self.playback_speed_index = 0
        self.projects = []
        self.projects_dict = {}
        
        # Timing
        self.program_start_time = time.time()
        self.last_picture_time = self.program_start_time - self.CAPTURE_INTERVAL
    
    def interrupt(self, other):
        print("Button!", other)
        self.keyboard.press('f')
        self.keyboard.release('f')

    def initialize(self):
        """Initializes the camera and project settings."""
        if not self.initialize_camera():
            print("Failed to initialize camera. Exiting.")
            exit(1)
        self.setup_project()
        self.prepare_display()

    def initialize_camera(self):
        """Attempts to initialize the camera."""
        self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        # check current usb camera settings in terminal
        # v4l2-ctl -V 
        # check available usb camera settings in terminal
        # v4l2-ctl --list-formats-ext
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) #cv2.VideoWriter_fourcc(*"MJPG")
        return self.cap.isOpened()

    def setup_project(self):
        """Sets up the project directory and reads the last state from the log file."""
        self.read_log_file()
        self.ensure_directory_exists(self.PROJECTS_FOLDER)
        self.get_projects()
        self.select_project()
        self.selected_project = self.active_project
        self.selected_project_index = self.projects.index(self.selected_project)
        print(f"Project: {self.active_project} | Current Image Index: {self.img_capture_index}")
        print(self.selected_project_index)

    def prepare_display(self):
        """Prepares the display window for showing images."""
        cv2.namedWindow(self.WINDOW_NAME, cv2.WINDOW_GUI_NORMAL)
        #cv2.setWindowProperty(self.WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    def read_log_file(self):
        """Reads the log file to resume the last session's state."""
        try:
            with open(self.LOG_PATH, "r") as log_file:
                self.active_project = log_file.readline().strip()
                self.img_capture_index = int(log_file.readline().strip())
                self.program_start_time = float(log_file.readline().strip())
        except FileNotFoundError:
            print("Log file not found. Starting with default values.")

    def write_log_file(self):
        """Writes the current state to the log file."""
        with open(self.LOG_PATH, "w") as log_file:
            log_file.write(f"{self.active_project}\n{self.img_capture_index}\n{self.program_start_time}")

    def ensure_directory_exists(self, path):
        """Ensures that a directory exists at the given path."""
        os.makedirs(path, exist_ok=True)

    def get_projects(self):
        """Returns a list of projects sorted by creation time."""
        projects_list = [d for d in os.listdir(self.PROJECTS_FOLDER) if os.path.isdir(os.path.join(self.PROJECTS_FOLDER, d))]
        #projects_list.sort(key=lambda d: -os.path.getctime(os.path.join(self.PROJECTS_FOLDER, d)))
        if not projects_list:
            projects_list.append(self.DEFAULT_PROJECT)
            self.ensure_directory_exists(os.path.join(self.PROJECTS_FOLDER, self.DEFAULT_PROJECT))
        for project in projects_list:
            dir_path = os.path.join(self.PROJECTS_FOLDER, project)
            number_of_files = len([entry for entry in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, entry))])
            self.projects_dict[project] = number_of_files
        self.projects = projects_list
        print("Projects Dict:", self.projects_dict)

    def select_project(self):
        """Selects the current project from the available projects."""
        for project in self.projects:
            if self.is_directory_empty(os.path.join(self.PROJECTS_FOLDER, project)):
                self.active_project = project
                self.program_start_time = time.time()
                self.img_capture_index = 0
                self.write_log_file()
                return
        if self.active_project in self.projects:
            return
        self.active_project = self.DEFAULT_PROJECT
        self.write_log_file()

    def is_directory_empty(self, path):
        """Checks if a directory is empty."""
        return next(os.scandir(path), None) is None

    def capture_image(self):
        """Captures an image from the camera and saves it with a timestamp."""
        if not self.cap:
            print("Camera not initialized.")
            return
        ret, frame = self.cap.read()
        if ret:
            img_path = os.path.join(self.PROJECTS_FOLDER, self.active_project, f"{self.img_file_prefix}{self.img_capture_index}.jpg")
            self.save_image_with_timestamp(frame, img_path)
            self.last_picture_time = time.time()
            if self.selected_project == self.active_project:
                self.img_max_index = self.img_capture_index
            self.img_capture_index += 1
            self.write_log_file()

    def save_image_with_timestamp(self, frame, filename):
        """Saves the image with a timestamp overlay."""
        frame_with_timestamp = self.add_timestamp_to_image(frame)
        cv2.imwrite(filename, frame_with_timestamp)

    def add_timestamp_to_image(self, frame):
        """Adds a timestamp overlay to the given image frame."""
        elapsed_time = int(time.time() - self.program_start_time)
        stats = self.map_time_255(elapsed_time)
        frame[self.PIXEL_LOCATION[0]-10:self.PIXEL_LOCATION[0]+10, self.PIXEL_LOCATION[1]-10:self.PIXEL_LOCATION[1]+10] = (stats[0], stats[1], stats[2]) #(elapsed_time // 3600, (elapsed_time % 3600) // 60, elapsed_time % 60)
        return frame
    

    def map_time_255(self, elapsed_time):
        #days = elapsed_time // 86400
        hours = elapsed_time % 86400 // 3600
        minutes = elapsed_time % 3600 // 60
        seconds = elapsed_time % 60
        return [hours * 10 + 4, minutes * 4 + 2 , seconds * 4 + 2] #days* 10 + 4,
    
    def map_255_time(self, stats):
        return [stats[0] // 10, stats[1] // 4, stats[2] // 4] #stats[0] // 10, 

    def update_display(self, index):
        """Updates the display with the image at the given index."""

        img_filename = os.path.join(self.PROJECTS_FOLDER, self.selected_project, f"{self.img_file_prefix}{index}.jpg")
        frame = cv2.imread(img_filename)

        if frame is not None:
            font = cv2.FONT_HERSHEY_SIMPLEX

            height = 40
            font_size = 1.2
            font_weight = 2
            font_color = (255, 255, 255)

            # draw black background for text
            cv2.rectangle(frame, (20, 0), (1280, 60), (0, 0, 0), -1)
            
            # print elapsed time on canvas
            cv2.putText(frame, str(self.map_255_time(frame[self.PIXEL_LOCATION[0], self.PIXEL_LOCATION[1]])), (40, height), font, font_size, font_color, font_weight)
            
            # print project on canvas
            cv2.putText(frame, str(self.selected_project), (500, height), font, font_size, font_color, font_weight)
            
            # print playback speed on canvas
            if self.playback_speed == 1:
                icon = "> "
            elif self.playback_speed > 1:
                icon = ">>"
            elif self.playback_speed < 1:
                icon = "<<"
            cv2.putText(frame, icon + str(abs(self.playback_speed)) + "x", (1000, height), font, font_size, font_color, font_weight)    
            
            cv2.imshow(self.WINDOW_NAME, frame)

    def play_movie(self):
        """Plays the captured images as a time-lapse movie."""
        if self.img_max_index:
            self.img_shown_index = (self.img_shown_index + (1 if self.playback_speed > 0 else -1)) % self.img_max_index
        else:
            self.img_shown_index = 0
        self.update_display(self.img_shown_index)
        self.key = cv2.waitKey(int(1000 * self.CAPTURE_INTERVAL / abs(self.playback_speed)))

    def handle_key_press(self):
        """Handles key press events for playback control."""
        if self.key in [ord('f'), ord('b')]:
            self.playback_speed = self.PLAYBACK_SPEEDS[self.playback_speed_index] * (-1 if self.key == ord('b') else 1)
            self.playback_speed_index = (self.playback_speed_index + 1) % len(self.PLAYBACK_SPEEDS)
            direction = "backward" if self.key == ord('b') else "forward"
            print(f"{direction} speed {self.playback_speed}")
        elif self.key == ord('p'):
            if self.playback_speed > 0:
                self.playback_speed = self.DEFAULT_PLAYBACK_SPEED
            else:
                self.playback_speed = -1* self.DEFAULT_PLAYBACK_SPEED
            print("Play/Pause")
        elif self.key == ord('s'):
            self.selected_project_index = (self.selected_project_index + 1) % len(self.projects)
            self.selected_project = self.projects[self.selected_project_index]
            self.img_shown_index = 1
            print("Select", self.selected_project_index, self.selected_project)
            self.img_max_index = self.projects_dict[self.selected_project]
        elif self.key == ord('a'):
            self.selected_project_index = (self.selected_project_index - 1) % len(self.projects)
            self.selected_project = self.projects[self.selected_project_index]
            self.img_shown_index = 1
            print("Select", self.selected_project_index, self.selected_project)
            self.img_max_index = self.projects_dict[self.selected_project]
        elif self.key == ord('q'):
            print("Quit")
            return False
        return True

    def main_loop(self):
        """Main loop for capturing images and handling playback."""
        while True:
            if not self.handle_key_press():
                break
            if time.time() - self.last_picture_time >= self.CAPTURE_INTERVAL:
                self.capture_image()
            self.play_movie()

    def cleanup(self):
        """Releases resources and cleans up before exiting."""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    cam = TimeLapseCamera()
    cam.initialize()
    cam.main_loop()
    cam.cleanup()