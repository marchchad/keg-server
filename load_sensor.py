import RPi.GPIO as gpio
import time
import sys

# from hx711 import HX711

# Hx711 signal pins
DT = 24
SCK = 23

print "Starting up"


# def cleanAndExit():
#     print "Cleaning..."
#     GPIO.cleanup()
#     print "Bye!"
#     sys.exit()


#
# print "Initializing hx711"
#
# hx = HX711(DT, SCK)
#
# print "Set reading format"
# # I've found out that, for some reason, the order of the bytes is not always the same between versions of python,
# # numpy and the hx711 itself.
# # Still need to figure out why does it change.
# # If you're experiencing super random values, change these values to MSB or LSB until to get more stable values.
# # There is some code below to debug and log the order of the bits and the bytes.
# # The first parameter is the order in which the bytes are used to build the "long" value.
# # The second parameter is the order of the bits inside each byte.
# # According to the HX711 Datasheet, the second parameter is MSB so you shouldn't need to modify it.
# hx.set_reading_format("LSB", "MSB")
#
# print "Set ref unit"
# # HOW TO CALCULATE THE REFERENCE UNIT
# # To set the reference unit to 1. Put 1kg on your sensor or anything you have and know exactly how much it weights.
# # In this case, 92 is 1 gram because, with 1 as a reference unit I got numbers near 0 without any weight
# # and I got numbers around 184000 when I added 2kg. So, according to the rule of thirds:
# # If 2000 grams is 184000 then 1000 grams is 184000 / 2000 = 92.
# # hx.set_reference_unit(113)
# hx.set_reference_unit(92)
#
# print "Resetting hx711"
# hx.reset()
# print "Taring hx711"
# hx.tare()
#
#
# while True:
#     try:
#         print "reading"
#         # These three lines are useful to debug whether to use MSB or LSB in the reading formats
#         # for the first parameter of "hx.set_reading_format("LSB", "MSB")".
#         # Comment the two lines "val = hx.get_weight(5)" and "print val" and uncomment the three lines to see what it prints.
#         np_arr8_string = hx.get_np_arr8_string()
#         binary_string = hx.get_binary_string()
#         print binary_string + " " + np_arr8_string
#
#         # Prints the weight. Comment if you're debugging the MSB and LSB issue.
#         val = hx.get_weight(5)
#         print val
#
#         hx.power_down()
#         hx.power_up()
#         time.sleep(0.5)
#     except (KeyboardInterrupt, SystemExit):
#         cleanAndExit()


HIGH = 1
LOW = 0
val = 0
gpio.setwarnings(False)
gpio.setmode(gpio.BCM)
gpio.setup(SCK, gpio.OUT)


def readCount():

    Count = 0
    # print Count
    # time.sleep(0.001)
    gpio.setup(DT, gpio.OUT)
    gpio.output(DT, 1)
    gpio.output(SCK, 0)
    gpio.setup(DT, gpio.IN)
    waiting_time = 0
    while gpio.input(DT) == 1:
        print "waiting {0} secs".format(waiting_time)
        i = 0
        waiting_time += 1
        time.sleep(1)
    for i in range(24):
        gpio.output(SCK, 1)
        Count = Count << 1
        gpio.output(SCK, 0)
        # time.sleep(0.001)
        if gpio.input(DT) == 0:
            Count = Count + 1
            # print Count

    gpio.output(SCK, 1)
    Count = Count ^ 0x800000
    # time.sleep(0.001)
    gpio.output(SCK, 0)
    return Count


time.sleep(3)
sample = readCount()
flag = 0

while 1:
    count = readCount()
    w = (count - sample) / 106  # is this the calibration value?
    w = w / 453.592  # grams to lbs
    print w, "lbs"
    time.sleep(0.175)
