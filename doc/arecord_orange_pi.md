## Orange Pi Lite

To record audio on **Orange Pi Lite**:
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
  
## Orange Pi PC2

```
#!/bin/bash

for v in unmute cap; do
  /usr/bin/amixer set "Line In" $v
  /usr/bin/amixer set "Mic1" $v
  /usr/bin/amixer set "Mic2" $v
done

for k in "Mic1 Boost" "Line In" "Mic1" "Mic2 Boost" "Mic2"; do
  /usr/bin/amixer set "$k" "86%"
done
```