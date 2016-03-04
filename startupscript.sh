#! /bin/sh

### BEGIN INIT INFO
# Provides:          flowmeter
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Simple script to start the python flowmeter program and outputs all logging info to a log at /home/pi/keg-server/flowmeter.log
# Description:       Flowmeter program monitors a gpio pin of a raspberry pi to receive input information from a hall effect sensor.
#                    The information is then converted into fluid ounces and emitted over a socket connection and posted via http to an API to log the information.
### END INIT INFO

if [ ! -f /home/pi/keg-server/flowmeter.log ];
then
    touch /home/pi/keg-server/flowmeter.log
fi

python /home/pi/keg-server/flowmeter.py >> /home/pi/keg-server/flowmeter.log 2>&1
