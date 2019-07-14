import time
import glob
import atexit
# Once we get a DB set up, we'll activate this
# import mysql.connector  # To save data locally in the event we can't post or need to recover/reset data
import logging
import requests
import json
import threading
import datetime
import RPi.GPIO as GPIO
# from socketIO_client import SocketIO, LoggingNamespace 	# To stream pouring data to the client page

# this holds configuration information for the services to connect to.
import settings

# When False, temp probe will connect to live site for api authentication, data posting, and web socket streaming
DEBUG = settings.DEBUG


class TempMonitor(threading.Thread):
    """
    This class provides methods to post, stream, and log temperature data read from a GPIO pin of a raspberry pi.

    Parameters
    ----------
    device_file_id: Integer
        The id of the temperature probe is transmitting the data through.
    read_interval<optional>: Integer
        Time in seconds in which the probe will be read and reported.
    debug<optional>: Boolean
        A boolean designating whether or not the data is emitting to local or remote web services.
    """
    def __init__(self, device_file_id, gpio_pin, read_interval=10, debug=True):
        """
            Some properties are declared as 0.0 so they are set to be floating point numbers instead of integers
            as they need finer precision for some calculations.
        """

        super(TempMonitor, self).__init__()
        self.initial_read = True
        self.debug = debug
        self.deviceId = device_file_id[-4:]
        self.device_file = device_file_id + '/w1_slave'
        self.read_interval = read_interval

        self.user = settings.USER
        self.password = settings.PASSWORD
        self.token = None

        self.target_host = settings.TARGET_HOST
        self.AuthenticationUrl = '%s/api-auth-token/' % self.target_host
        self.PostTemperatureUrl = '%s/temperatures/' % self.target_host

        self.max_temp_f = settings.MAX_TEMP_F if hasattr(settings, 'MAX_TEMP_F') else 72  # default to a max of 72 degrees F
        self.min_temp_f = settings.MIN_TEMP_F if hasattr(settings, 'MIN_TEMP_F') else 60  # default to a min of 72 degrees F

        if gpio_pin is None:
            raise Exception('You must provide a GPIO pin')

        self.fan_pin = gpio_pin
        self.plate_pin = 23
        self.fan_is_on = False
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.fan_pin, GPIO.OUT)


        #atexit.register(self.gpio_cleanup)

    def run(self):
        self.startup()

    def get_token(self):
        """
        Gets a JSON Web Token used to authenticate our POSTs to the API
        """
        logging.info("\n\tauth url: %s" % self.AuthenticationUrl)

        login_data = {"username": self.user, "password": self.password}
        response = None
        try:
            response = requests.post(self.AuthenticationUrl, json=login_data)

            data = json.loads(response.text)

            if 'token' in data:
                logging.info("\n\tSuccessfully retrieved token!")
                return data['token']
            else:

                # TODO: log to a local db instead of just erroring out.
                raise Exception("Unauthorized! Please check the username and password.")

        except requests.exceptions.ConnectionError as e:
            print "No response\n\n", e

            if response is not None:
                try:
                    response.close()
                except:
                    pass

    def post_temperature_data(self, temp_data):
        """
        Posts the pour data to the server.

        :param temp_data: Object containing the temperature data
        """
        logging.info("\n\tposturl: %s" % self.PostTemperatureUrl)

        if self.token is None:

            # TODO: log to a local db instead of just erroring out.
            raise Exception("Unauthorized! Cannot post temperature data. Please check the username and password.")

        # Must mixin the auth token in order to post the data
        headers = {'Authorization': 'Token %s' % self.token}

        response = requests.post(self.PostTemperatureUrl, headers=headers, data=temp_data)
        data = json.loads(response.text)
        success = False
        # No need to keep the latest pour if it posted successfully
        if 'id' in data:
            success = True
            logging.info("\n\tSuccessfully posted temperature data!")
        else:

            logging.warning("\n\tThe post was not successful.")

            logging.error("\n\tSomething went wrong.")
            # TODO: log temperature data to local database
            pass

    def startup(self):
        """
        Sets up the web socket connection, the raspberry pi board and pins, and starts the `main` method
        """
        logging.basicConfig(level=logging.WARNING)
        logging.info("\n\n\n")  # pad the log a bit so we can see where the program restarted

        self.token = self.get_token()

        logging.info("\n\twe're monitoring temperature!")

        self.main()

    def read_temp_raw(self):
        """
        Opens the device file and reads the lines into memory then returns the data.
        :return:
        """

        f = open(self.device_file, 'r')
        lines = f.readlines()
        f.close()
        return lines

    def toggle_fan(self, on=True):

        if on:
            # Only turn on if it is not already on
            if not self.fan_is_on:
                # Turn on the Relay
                GPIO.output(self.fan_pin, GPIO.LOW)
                self.fan_is_on = True

        else:
            # Turn off the Relay
            GPIO.output(self.fan_pin, GPIO.HIGH)
            self.fan_is_on = False

    @atexit.register
    def gpio_cleanup(self):
        GPIO.output(self.fan_pin, GPIO.HIGH)
        GPIO.cleanup()

    def main(self):
        """
        Endless loop that parses local files written by temperature probes then posts
        the data to the API.
        """
        # We want this to constantly monitor the temperature files, so start an infinite loop
        while True:
            if not self.initial_read:
                self.initial_read = False
                # This pauses the program for 5 minutes in order to reduce network traffic for data collection
                time.sleep(self.read_interval)
            lines = self.read_temp_raw()
            yes = lines[0].strip()[-3:]

            while yes != 'YES':
                time.sleep(0.2)
                lines = self.read_temp_raw()

            equals_pos = lines[1].find('t=')

            if equals_pos != -1:
                temp_string = lines[1][equals_pos + 2:]
                temp_c = float(temp_string) / 1000.0
                temp_f = temp_c * 9.0 / 5.0 + 32.0

                if temp_f > self.max_temp_f or temp_f < self.min_temp_f:
                    self.toggle_fan(on=True)
                else:
                    self.toggle_fan(on=False)

                print self.deviceId + " is reading at " + str(temp_f) + " deg F"
                #self.post_temperature_data({"name": self.deviceId, "temperature": temp_f, "created_on": str(datetime.datetime.now())})

GPIO_PIN = 21

try:
    basepath = '/sys/bus/w1/devices/'

    # The concatenated string will ensure to only list the device folders
    # and exclude the `w1_bus_master` directory
    device_dirs = glob.glob(basepath + '28*')

    if len(device_dirs) == 0:
        raise Exception("No devices found")

    GPIO_PIN = raw_input('Please enter the GPIO pin the Temp Probes are linked to: ')

    for device_file in device_dirs:
        tm = TempMonitor(device_file)
        # Since the TempMonitor class utilizes an endless loop, it's important we start each main method
        # in its own thread, otherwise only the first device will ever be setup and read.
        thread = threading.Thread(target=tm.startup)
        thread.start()

except Exception as e:
    print e

finally:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.OUT)
    GPIO.output(GPIO_PIN, GPIO.HIGH)
    GPIO.cleanup()
