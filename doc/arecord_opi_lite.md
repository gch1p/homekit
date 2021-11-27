In order to use microphone on **Orange Pi Lite**:
- enable audio codec in `armbian-config`
- put this to `/etc/rc.local` (and make it executable):
  ```
  for v in unmute cap; do
      /usr/bin/amixer set "Line In" $v
      /usr/bin/amixer set "Mic1" $v
  done
  
  for k in "Mic1 Boost" "Line In" "Mic1"; do
      /usr/bin/amixer set "$k" "86%"
  done
  ```