import time
import glob
# Once we get a DB set up, we'll activate this
# import mysql.connector  # To save data locally in the event we can't post or need to recover/reset data
import logging
import requests
import json
import threading
from socketIO_client import SocketIO, LoggingNamespace 	# To stream pouring data to the client page

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

        # TODO: move values to a config that is excluded from repo
        self.user = 'pi'
        self.password = 'raspberry'

        if self.debug:
            # local debugging
            self.targetHost = 'http://10.0.0.78'
            self.targetWsPort = 3000
            self.AuthenticationUrl = '%s:%s/api/authenticate' % (self.targetHost, self.targetWsPort)
            self.PostTemperatureUrl = '%s:%s/api/temperature' % (self.targetHost, self.targetWsPort)
        else:
            # live site
            self.targetHost = 'https://www.chadmarchpdx.com'
            self.targetWsPort = 8000
            self.AuthenticationUrl = "%s/api/authenticate" % self.targetHost
            self.PostTemperatureUrl = '%s/api/temperature' % self.targetHost

    def run(self):
        self.startup()

    def get_token(self):
        """
        Gets a JSON Web Token used to authenticate our POSTs to the API
        # TODO: reauthorize every 24 hours at 3 A.M. since the auth token only lasts that long
        """
        logging.info("\n\tauth url: %s" % self.AuthenticationUrl)
        response = requests.post(self.AuthenticationUrl, data={'username': self.user, 'password': self.password })
        data = json.loads(response.text)
        if data['success'] is True:
            logging.info("\n\tSuccessfully generated token!")
            return data['token']
        else:
            raise "Unauthorized! Please check the username and password."

    def get_socket_connection(self):
        """
        Creates a web socket connection to target host

        :rtype: Socket connection
        """
        logging.info("\n\tGetting socket connection...")
        # only log if we're running against the local instance
        logging.getLogger('requests').setLevel(logging.WARNING)

        socket = SocketIO(self.targetHost, self.targetWsPort, LoggingNamespace)
        return socket

    def emit_temperature(self, tempData):
        """
        Emits the pour data to the `emitTotalPourData` event

        :param tempData: Object containing the keg id, volume, and pour duration
        """
        try:
            logging.info("\n\tEmitting data...")
            self.socketIO.emit('emitTempData', tempData)
            logging.info("\n\tDone emitting data...")
        except Exception as e:
            logging.error("\n\tAn error occurred when emitting the temperature data")
            logging.error(e)

    def post_temperature_data(self, temp_data):
        """
        Posts the pour data to the server.

        :param temp_data: Object containing the temperature data
        """
        logging.info("\n\tposturl: %s" % self.PostTemperatureUrl)

        # Must mixin the auth token in order to post the data
        temp_data['token'] = self.token

        response = requests.post(self.PostTemperatureUrl, data=temp_data)
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
            #TODO: log temperature data to local database
            pass

    def startup(self):
        """
        Sets up the web socket connection, the raspberry pi board and pins, and starts the `main` method
        """
        logging.basicConfig(level=logging.WARNING)
        logging.info("\n\n\n")  # pad the log a bit so we can see where the program restarted

        # self.token = self.get_token()
        # set up connection
        # self.socketIO = self.get_socket_connection()

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
