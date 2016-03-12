import time
from datetime import datetime
import pytz
import RPi.GPIO as gpio
# Once we get a DB set up, we'll activate this
#import mysql.connector 	# To save data locally in the event we can't post or need to recover/reset data
import logging
import requests
import json
from socketIO_client import SocketIO, LoggingNamespace 	# To stream pouring data to the client page

LOCAL = True # When False, flow meter will hook up to Live site for api authentication, data posting, and web socket streaming


class FlowMeter():

    def __init__(self, kegId, pin, local=True):
        self.pin = pin
        self.kegId = kegId
        self.local = local

        self.pouring = False
        self.lastPinState = False
        self.pinState = 0
        self.lastPinChange = int(time.time() * 1000)
        self.pourStart = 0
        self.pinChange = self.lastPinChange
        self.pinDelta = 0
        self.hertz = 0
        self.flow = 0
        self.litersPoured = 0
        self.ouncesPoured = 0

        self.convFactor = (7.5 * 60)
        self.scaleFactor = 1000.0000

        # TODO: move values to a config that is excluded from repo 
        self.user = 'pi'
        self.password = 'raspberry'

        if local:
            # local debugging
            self.targetHost = 'http://10.0.0.78'
            self.targetWsPort = 3000
            self.AuthenticationUrl = '%s:%s/api/authenticate' % (self.targetHost, self.targetWsPort)
            self.PostPourUrl = '%s:%s/api/pour' % (self.targetHost, self.targetWsPort)
        else:
            # live site
            self.targetHost = 'http://www.chadmarchpdx.com'
            self.targetWsPort = 8000
            self.AuthenticationUrl = "%s/api/authenticate" % self.targetHost
            self.PostPourUrl = '%s/api/pour' % self.targetHost

        self.lastFivePours = []

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

    def emitPourStart(self):
        try:
            logging.info("\n\tEmitting pour start...")
            self.socketIO.emit('pourStart', self.kegId)
            logging.info("\n\tDone emitting pour start...")
        except Exception as e:
            logging.error("\n\tAn error occurred when emitting the pour data")
            logging.error(e)

    def emitTotalPour(self, pourData):
        """
        Emits the pour data to the `emitTotalPourData event

        :param pourData: Object containing the keg id, volume, and pour duration
        """
        try:
            logging.info("\n\tEmitting data...")
            self.socketIO.emit('emitTotalPourData', pourData)
            logging.info("\n\tDone emitting data...")
            # save latest pour
            if len(self.lastFivePours) == 5:
                del self.lastFivePours[-1]

            # append new pour data to beginning of list
            self.lastFivePours = [pourData] + self.lastFivePours
        except Exception as e:
            logging.error("\n\tAn error occurred when emitting the pour data")
            logging.error(e)

    def postPourData(self, pourData):
        """
        Posts the pour data to the server.

        :param pourData: Object containing the keg id, volume, and pour duration
        """
        logging.info("\n\tposturl: %s" % self.PostPourUrl)

        # Must mixin the auth token in order to post the data
        pourData['token'] = self.token

        response = requests.post(self.PostPourUrl, data=pourData)
        data = json.loads(response.text)

        # No need to keep the latest pour if it posted successfully
        if data['success'] == True:
            if data['message']:
                logging.info("\n\t%s" % data['message'])
            else:
                logging.info("\n\tSuccessfully posted pour data!")
            del self.lastFivePours[-1]
        else:
            if data['message']:
                logging.warning("\n\tThe post was not successful.")
                logging.warning("\n\t%s" % data['message'])
            else:
                logging.error("\n\tSomething went wrong.")
            #TODO: log pour data to local database
            pass

    def tryAgainInaMinute(self):
        """
        Keeps trying to emit the pour data every minute until all the pours are emitted.
        """
        failedTime = time.time()
        while (self.currentTime - failedTime) > 60:
            # Try getting a new connection every minute
            self.socketIO = self.GetSocketConnection()
            # TODO: find a way to check to see if we got a new connection
            # If we do, only emit the latest one, but post the others.
            for idx, pour in enumerate(self.lastFivePours):
                if idx == 0:
                    self.emitTotalPour(pour)
                del self.lastFivePours[idx]
            break

    def startup(self):
        """
        Sets up the web socket connection, the raspberry pi board and pins, and starts the `main` method
        """
        logging.basicConfig(level=logging.DEBUG)
        logging.info("\n\n\n") # pad the log a bit so we can see where the program restarted

        self.token = self.GetToken()
        # set up connection
        self.socketIO = self.GetSocketConnection()

        # Initializing GPIO ports
        boardRevision = gpio.RPI_REVISION # Clearing previous gpio port settings
        gpio.setmode(gpio.BCM) # Use real physical gpio port numbering
        gpio.setup(self.pin, gpio.IN, pull_up_down = gpio.PUD_UP)

        logging.info("\n\twe're ready to pour!")
        # start up main loop
        self.main()

    def main(self):
        """
        Endless loop that listens to specific pins for input data. Once data is detected, logic
        is set to calculate the pulses into pour data then emit the data on a socket connection
        and post it to the API.
        """
        # We want this to constantly monitor to gpio pins so start an infinite loop
        while True:
            # this is multiplied by 1000 and converted to an int to maintain enough precision
            # but not enough that the comparison later to determine if pouring is finished
            # is too precise
            currentTime = int(time.time() * 1000)
            if gpio.input(self.pin):
                self.pinState = True
            else:
                self.pinState = False

            if self.pinState != self.lastPinState and self.pinState == True:
                if self.pouring == False:
                    self.startTime = currentTime
                    self.pourStart = datetime.now(pytz.timezone('America/Los_Angeles'))
                    self.emitPourStart()

                self.pouring = True
                # get the current time
                self.pinChange = currentTime
                self.pinDelta = self.pinChange - self.lastPinChange

                if self.pinDelta > 0 and self.pinDelta < 1000:
                    # calculate the instantaneous speed
                    self.hertz = self.scaleFactor / self.pinDelta
                    #logging.info('\n\tpindelta: %s, hertz: %s' % (self.pinDelta, self.hertz))

                    self.flow = self.hertz / self.convFactor # L/s, This assumes a 1 liter per minute flow by the kegerator
                    #logging.info('\n\tflow: %s, conv. factor: %s' % (self.flow, self.convFactor))

                    self.litersPoured += self.flow * (self.pinDelta / self.scaleFactor)
                    #logging.info('\n\tlitersPoured: %s' % self.litersPoured)

                    #TODO: emit data at a configured interval of poured beer
                    # such as every 2-3 oz.

            # if pouring was set to true, and the pin hasn't changed state and there hasn't been a change in
            # the pin in over 3 seconds, we can assume pouring has ceased so we'll post the data and reset
            # the variables
            if self.pouring == True and self.pinState == self.lastPinState and (currentTime - self.lastPinChange) > 3000:
                # set pouring back to false to set up for the next pour capture
                self.pouring = False
                logging.info('\n\tliters poured: %s' % self.litersPoured)
                # Until i can figure out the algorithm, we're going to scale the value by a factor of
                # 55% since that is what it seems to be off by.
                self.litersPoured = (self.litersPoured * 1.55)
                logging.info('\n\tscaled liters poured: %s' % self.litersPoured)

                self.ouncesPoured = self.litersPoured * 33.814 # we want to return ounces and this value is the constant to do so
                # the 0.2 value is a bit arbitrary. when the flow meter gets jostled, the impeller can sometimes
                # trip the pin state, creating a 'false positive' read. This value helps to capture what are
                # only what are perceived to be legit pours.
                if self.ouncesPoured > 0.2:
                    # derive pour time in seconds by subtracting the current time from the start time
                    # and unraveling the precision we added earlier
                    pourTime = float(currentTime - self.startTime) / 1000

                    socketPourData = {
                        'kegid': self.kegId,
                        'volume': self.ouncesPoured,
                        'duration': pourTime
                    }

                    postPourData = {
                        'kegid': self.kegId,
                        'volume': self.ouncesPoured,
                        'pourstart': self.pourStart,
                        'pourend': datetime.now(pytz.timezone('America/Los_Angeles'))
                    }

                    logging.info('\n volume: %s oz\n duration: %s secs' % (socketPourData['volume'], socketPourData['duration']))

                    # Zero out the pour amount now that we've created an object to emit/post
                    self.litersPoured = 0
                    self.ouncesPoured = 0
                    self.pourTime = 0

                    try:
                        # Sends data through socket connect to the server to pass through to
                        # any connected users
                        self.emitTotalPour(socketPourData)
                        self.postPourData(postPourData)

                    except Exception as e:
                        #TODO: log error to database
                        logging.error(e)
                        #self.tryAgainInaMinute()

            self.lastPinChange = self.pinChange
            self.lastPinState = self.pinState

fm1 = FlowMeter(1, 4, LOCAL)
fm1.startup()