import time
import os
import glob
# Once we get a DB set up, we'll activate this
#import mysql.connector 	# To save data locally in the event we can't post or need to recover/reset data
import logging
import requests
import json
import threading
from socketIO_client import SocketIO, LoggingNamespace 	# To stream pouring data to the client page

LOCAL = True # When False, flow meter will hook up to Live site for api authentication, data posting, and web socket streaming

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

class TempMonitor(threading.Thread):
    """
    This class provides methods to post, stream, and log temperature data read from a GPIO pin of a raspberry pi.

    Parameters
    ----------
    pin: Integer
        The id of the pin the flowmeter is transmitting the data through.
    local<optional>: Boolean
        A boolean designating whether or not the data is emitting to local or remote web services.
    """
    def __init__(self, device, local=True):
        """
            Some properties are declared as 0.0 so they are set to be floating point numbers instead of integers
            as they need finer precision for some calculations.
        """
        super(TempMonitor, self).__init__()
        self.local = local
        self.deviceId = device[-4:]
        self.device_file = device + '/w1_slave'

        # TODO: move values to a config that is excluded from repo
        self.user = 'pi'
        self.password = 'raspberry'

        if self.local:
            # local debugging
            self.targetHost = 'http://10.0.0.78'
            self.targetWsPort = 3000
            self.AuthenticationUrl = '%s:%s/api/authenticate' % (self.targetHost, self.targetWsPort)
            self.PostTemperatureUrl = '%s:%s/api/temperature' % (self.targetHost, self.targetWsPort)
        else:
            # live site
            self.targetHost = 'http://www.chadmarchpdx.com'
            self.targetWsPort = 8000
            self.AuthenticationUrl = "%s/api/authenticate" % self.targetHost
            self.PostTemperatureUrl = '%s/api/temperature' % self.targetHost

    def run(self):
        self.startup()

    def GetToken(self):
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

    def GetSocketConnection(self):
        """
        Creates a web socket connection to target host

        :rtype: Socket connection
        """
        logging.info("\n\tGetting socket connection...")
        # only log if we're running against the local instance
        logging.getLogger('requests').setLevel(logging.WARNING)

        socket = SocketIO(self.targetHost, self.targetWsPort, LoggingNamespace)
        return socket


    def emitTemperature(self, tempData):
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

    def postTempData(self, tempData):
        """
        Posts the pour data to the server.

        :param tempData: Object containing the temperature data
        """
        logging.info("\n\tposturl: %s" % self.PostTemperatureUrl)

        # Must mixin the auth token in order to post the data
        tempData['token'] = self.token

        response = requests.post(self.PostTemperatureUrl, data=tempData)
        data = json.loads(response.text)

        # No need to keep the latest pour if it posted successfully
        if data['success'] == True:
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
        logging.info("\n\n\n") # pad the log a bit so we can see where the program restarted

        #self.token = self.GetToken()
        # set up connection
        #self.socketIO = self.GetSocketConnection()

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
            currentTime = time.time()
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
    for device in glob.glob(basepath + '28*'):
        tm = TempMonitor(device, LOCAL)
        tm.start()
except Exception as e:
    print e