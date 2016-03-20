# Raspberry Pi Keg Server

This repo contains a single python script used to monitor a GPIO pin on a raspberry pi.

To determine what GPIO pin you wish to use, review the [GPIO pin layout diagram](https://www.raspberrypi.org/documentation/usage/gpio-plus-and-raspi2/).

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
