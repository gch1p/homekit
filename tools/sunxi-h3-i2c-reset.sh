#!/bin/sh

devices="1c2ac00.i2c 1c2b000.i2c"
pins="8 9 28 30"
driver_path="/sys/bus/platform/drivers/mv64xxx_i2c"

driver_unbind() {
	echo -n "$1" > "$driver_path/unbind"
}

driver_bind() {
	echo -n "$1" > "$driver_path/bind"
}

for dev in $devices; do driver_unbind "$dev"; done
echo "unbind done"

for pin in pins; do
	gpio mode $pin out
	gpio write $pin 0
done
echo "gpio reset done"

for dev in $devices; do driver_bind "$dev"; done
echo "bind done"