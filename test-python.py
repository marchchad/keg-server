import time
import RPi.GPIO as gpio
import requests 	# To post the final pour data to the server
import json 		# May need this for formatting, not sure yet
import mysql.connector 	# To save data locally in the event we can't post or need to recover/reset data
import socket 		# To stream pouring data to the client page
from threading import * # So the program can continue running while streaming and posting data

# Variable to set pin to read from
pin = 26
pouring = False
lastPinState = False
pinState = 0
lastPinChange = int(time.time() * 1000)
pourStart = 0
pinChange = lastPinChange
pinDelta = 0
hertz = 0
flow = 0
litersPoured = 0
pintsPoured = 0

# Initializing GPIO ports
boardRevision = gpio.RPI_REVISION # Clearing previous gpio port settings
gpio.setmode(gpio.BCM) # Use real physical gpio port numbering
gpio.setup(pin, gpio.IN, pull_up_down=gpio.PUD_UP)

while True:
    currentTime = int(time.time() * 1000)
    if gpio.input(pin):
        pinState = True
    else:
        pinState = False
    
    if(pinState != lastPinState and pinState == True):
        if(pouring == False):
            pourStart = currentTime
            print "we're pouring!"
        pouring = True
        # get the current time
        pinChange = currentTime
        pinDelta = pinChange - lastPinChange
        #print ((((((1000.0000 / pinDelta) / (60 * 7.5)) * (pinDelta / 1100.000) )) * 2.11338) / 16), " oz"
        if (pinDelta < 1000):
            # calculate the instantaneous speed
            hertz = 1000.0000 / pinDelta
            flow = hertz / (60 * 7.5) # L/s
            litersPoured += flow * (pinDelta / 1000.0000)
            pintsPoured = litersPoured * 2.11338

    if (pouring == True and pinState == lastPinState and (currentTime - lastPinChange) > 3000):
        # set pouring back to false, tweet the current amt poured, and reset everything
        pouring = False
        if (pintsPoured > 0.1):
            pourTime = int((currentTime - pourStart) / 1000) - 3
	    print 'liters poured ', litersPoured
	    print litersPoured * 1000, ' ml poured'
            #print 'pints poured ', pintsPoured
            print 'pour time ', pourTime, ' seconds'
            #print 'oz/min ', (pintsPoured * 16) / (pourTime / 60)
            litersPoured = 0
            pintsPoured = 0
            #TODO: post final pour volume
    lastPinChange = pinChange
    lastPinState = pinState
gpio.cleanup()
