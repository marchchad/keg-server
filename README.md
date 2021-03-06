# Raspberry Pi Keg Server

This repo contains a single python script used to monitor a GPIO pin on a raspberry pi.

To determine what GPIO pin you wish to use, review the [GPIO pin layout diagram](https://www.raspberrypi.org/documentation/usage/gpio-plus-and-raspi2/).
This server script interfaces with an API provided by [chadmarchpdx](https://github.com/marchchad/chadmarchpdx) where the data is stored and visualized.


A startup script is included that can be installed to start the flowmeter when the pi starts up.
To do so, place the script at /etc/init.d/ and run the following commands:


* **Make it executable**
```
    sudo chmod 755 /etc/init.d/startupscript.sh
```
* **Test run the script**
```
    sudo /etc/init.d/startupscript.sh
```
* **Register script for startup**
```
    sudo update-rc.d startupscript.sh defaults
```
* **To remove the script from startup**
```
    sudo update-rc.d -f  startupscript.sh remove
```

### Temperature Monitor

The `w1-gpio` module assumes that the probes are connected to the GPIO 4 pin along with a 4.7k or 10k ohm resistor
between the `3.3v` and GPIO 4 pin.

The limit on the number of probes that can be run in parallel on the single GPIO pin is rather high, some reporting
upwards of 70, however your mileage may vary.

Note: Not sure why, but I cannot get any POSTs to work from the raspberry pi to a server on the LAN.