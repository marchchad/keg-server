import RPi.GPIO as GPIO
from time import sleep

FAN_PIN = 21
PLATE_PIN = 23

GPIO.cleanup()

while True:

    GPIO.setmode(GPIO.BCM)

    GPIO.setup(FAN_PIN, GPIO.OUT)
    GPIO.setup(PLATE_PIN, GPIO.OUT)

    relays_on = raw_input('Enter `On` or `Off` to toggle the relays:')

    if relays_on == 'On':
        # Turn on the Relay (this works - it clicks gives 3.3v)
        GPIO.output(FAN_PIN, GPIO.LOW)
        GPIO.output(PLATE_PIN, GPIO.LOW)

    else:

        # Turn off the Relay (this does nothing but goes back to 0v)
        GPIO.output(FAN_PIN, GPIO.HIGH)
        GPIO.output(PLATE_PIN, GPIO.HIGH)
        #sleep(1)

        # if I add GPIO.cleanup(), the relay then closes,
        # but I dont want to cleanup at this point

        GPIO.cleanup()

    sleep(5)