import time
import glob
# Once we get a DB set up, we'll activate this
# import mysql.connector  # To save data locally in the event we can't post or need to recover/reset data
import logging
import requests
import json
import threading
from socketIO_client import SocketIO, LoggingNamespace 	# To stream pouring data to the client page

# this holds configuration information for the services to connect to.
import settings

# When False, temp probe will connect to live site for api authentication, data posting, and web socket streaming
DEBUG = True


class TempMonitor(threading.Thread):
    """
    This class provides methods to post, stream, and log temperature data read from a GPIO pin of a raspberry pi.

    Parameters
    ----------
    device_file_id: Integer
        The id of the temperature probe is transmitting the data through.
    local<optional>: Boolean
        A boolean designating whether or not the data is emitting to local or remote web services.
    """
    def __init__(self, device_file_id, debug=True):
        """
            Some properties are declared as 0.0 so they are set to be floating point numbers instead of integers
            as they need finer precision for some calculations.
        """
        super(TempMonitor, self).__init__()
        self.debug = debug
        self.deviceId = device_file_id[-4:]
        self.device_file = device_file_id + '/w1_slave'

        self.user = settings.USER
        self.password = settings.PASSWORD
        self.token = None

        self.target_host = settings.TARGET_HOST
        self.AuthenticationUrl = '%s/api-auth-token/' % self.target_host
        self.PostTemperatureUrl = '%s/api/temperature/' % self.target_host

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
        headers = {'Authorization': 'Token: %s' % self.token}

        response = requests.post(self.PostTemperatureUrl, headers=headers, data=temp_data)
        data = json.loads(response.text)

        # No need to keep the latest pour if it posted successfully
        if data['success']:
            if data['message']:
                logging.info("\n\t%s" % data['message'])
            else:
                logging.info("\n\tSuccessfully posted temperature data!")
        else:
            if data['message']:
                logging.warning("\n\tThe post was not successful.")
                logging.warning("\n\t%s" % data['message'])
            else:
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

    def main(self):
        """
        Endless loop that parses local files written by temperature probes then posts
        the data to the API.
        """
        # We want this to constantly monitor the temperature files, so start an infinite loop
        while True:
            lines = self.read_temp_raw()
            while lines[0].strip()[-3:] != 'YES':
                time.sleep(0.2)
                lines = self.read_temp_raw()
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos + 2:]
                temp_c = float(temp_string) / 1000.0
                temp_f = temp_c * 9.0 / 5.0 + 32.0
                print self.deviceId + " is reading at " + str(temp_f) + " deg F"
                # TODO: emit, post data here.
            time.sleep(.5)


try:
    basepath = '/sys/bus/w1/devices/'

    # The concatenated string will ensure to only list the device folders
    # and exclude the `w1_bus_master` directory
    device_dirs = glob.glob(basepath + '28*')

    if len(device_dirs) == 0:
        raise Exception("No devices found")

    for device_file in device_dirs:
        tm = TempMonitor(device_file, DEBUG)
        # Since the TempMonitor class utilizes an endless loop, it's important we start each main method
        # in its own thread, otherwise only the first device will ever be setup and read.
        thread = threading.Thread(target=tm.startup)
        thread.start()

except Exception as e:
    print e