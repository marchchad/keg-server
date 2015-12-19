import time
import RPi.GPIO as gpio
# Once we get a DB set up, we'll activate this
#import mysql.connector 	# To save data locally in the event we can't post or need to recover/reset data
from socketIO_client import SocketIO, LoggingNamespace 	# To stream pouring data to the client page

# TODO: migrate to standalone file to be imported
class FlowMeter():

    def __init__(self, kegId, pin):
        self.pin = pin
        self.kegId = kegId

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

        self.lastFivePours = []

    def GetSocketConnection(self):
        """
        :rtype: Socket connection
        """
        return SocketIO('http://10.0.0.78', 3000, LoggingNamespace)

    def emitTotalPour(self, pourData):
        """
        :rtype: None
        """
        self.socketIO.emit('emitTotalPourData', pourData)
        # save latest pour
        if len(self.lastFivePours) == 5:
            del self.lastFivePours[-1]

        # append new pour data to beginning of list
        [pourData] + self.lastFivePours

    def tryAgainInaMinute(self):
        """
        :rtype: None
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
        # set up connection
        self.socketIO = self.GetSocketConnection()

        # Initializing GPIO ports
        boardRevision = gpio.RPI_REVISION # Clearing previous gpio port settings
        gpio.setmode(gpio.BCM) # Use real physical gpio port numbering
        gpio.setup(self.pin, gpio.IN, pull_up_down = gpio.PUD_UP)

        # start up main loop
        self.main()

    def main(self):
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

            if(self.pinState != self.lastPinState and self.pinState == True):
                if(self.pouring == False):
                    self.pourStart = currentTime
                    print "we're ready to pour!"

                self.pouring = True
                # get the current time
                self.pinChange = currentTime
                self.pinDelta = self.pinChange - self.lastPinChange

                if (self.pinDelta > 0 and self.pinDelta < 1000):
                    # calculate the instantaneous speed
                    self.hertz = 1000.0000 / self.pinDelta
                    self.flow = self.hertz / (60 * 7.5) # L/s, This assumes a 1 liter per minute flow by the kegerator
                    self.litersPoured += self.flow * (self.pinDelta / 1000.0000)

                    #TODO: emit data at a configured interval of poured beer
                    # such as ever 2-3 oz.

            # if pouring was set to true, and the pin hasn't changed state and there hasn't been a change in
            # the pin in over 3 seconds, we can assume pouring has ceased so we'll post the data and reset
            # the variables
            if (self.pouring == True and self.pinState == self.lastPinState and (currentTime - self.lastPinChange) > 3000):
                # set pouring back to false to set up for the next pour capture
                self.pouring = False
                self.ouncesPoured = self.litersPoured * 33.814 # we want to return ounces and this value is the constant to do so
                # the 0.2 value is a bit arbitrary. when the flow meter gets jostled, the impeller can sometimes
                # trip the pin state, creating a 'false positive' read. This value helps to capture what are
                # only what are perceived to be legit pours.
                if (self.ouncesPoured > 0.2):
                    # derive pour time in seconds by subtracting the current time from the start time
                    # and unraveling the precision we added earlier
                    pourTime = float(currentTime - self.pourStart) / 1000

                    pourData = {}
                    pourData['keg'] = self.kegId
                    pourData['volume'] = self.ouncesPoured
                    pourData['duration'] = pourTime

                    print pourData, '\n volume is ounces \n duration is secs'

                    # Zero out the pour amount now that we've created an object to emit/post
                    self.litersPoured = 0
                    self.ouncesPoured = 0
                    self.pourTime = 0

                    try:
                        # Sends data through socket connect to the server to pass through to
                        # any connected users
                        self.emitTotalPour(pourData)

                        #TODO: log pour data to local database

                    except Exception as e:
                        #TODO: log error to database
                        print e
                        self.tryAgainInaMinute()

            self.lastPinChange = self.pinChange
            self.lastPinState = self.pinState

fm1 = FlowMeter(1, 4)
fm1.startup()