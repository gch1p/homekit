## Bot configuration

```
[bot]
token = "bot token"
users = [ id1, id2 ]
#notify_users = [ 1, 2 ]

[mqtt]
host = "192.168.88.49"
port = 1883
client_id = "kettle_bot"

[logging]
verbose = true
default_fmt = true

[kettle]
mac = 'kettle mac'
token = 'kettle token'
temp_max = 100
temp_min = 30
temp_step = 5
read_timeout = 1
```


## Random research notes

### Device features

From `devices.json`:
```
    "id": "cec1f5ed-be5e-4545-9ce9-e2d843032587",
    "vendor": "polaris",
    "type": 6,
    "class": "kettle",
    "name": "PWK 1725CGLD",
    "connectivity": [
      "wifi",
      "hotspot"
    ],

    ... 

    "features": [
      "program",
      "temperature",
      "current_temperature",
      "schedule",
      "child_lock",
      "semi_recipe",
      "demo"
    ],
    "temperature_units": "celsius",
    "limits": {
      "temperature": {
        "min": 30,
        "max": 100,
        "default": 40,
        "step": 5
      },
      "child_lock": {
        "min": 0,
        "max": 1,
        "default": 0,
        "step": 1
      }
    },
```

### Protocol commands

From `com/polaris/iot/api/commands`:
```
$ grep -A1 -r "public byte getType()" .
./CmdAccessControl.java:   public byte getType() {
./CmdAccessControl.java-      return -123;
--
./CmdBattery.java:   public byte getType() {
./CmdBattery.java-      return 27;
--
./CmdCurrentHumidity.java:   public byte getType() {
./CmdCurrentHumidity.java-      return 19;
--
./CmdMultiStepCurrent.java:   public byte getType() {
./CmdMultiStepCurrent.java-      return 21;
--
./CmdSmartMode.java:   public byte getType() {
./CmdSmartMode.java-      return 40;
--
./CmdTimeStart.java:   public byte getType() {
./CmdTimeStart.java-      return 0;
--
./CmdProgramData.java:   public byte getType() {
./CmdProgramData.java-      return 66;
--
./CmdTank.java:   public byte getType() {
./CmdTank.java-      return 31;
--
./CmdSpeed.java:   public byte getType() {
./CmdSpeed.java-      return 15;
--
./CmdTargetHumidity.java:   public byte getType() {
./CmdTargetHumidity.java-      return 18;
--
./CmdTargetTime.java:   public byte getType() {
./CmdTargetTime.java-      return 3;
--
./CmdRecipeStep.java:   public byte getType() {
./CmdRecipeStep.java-      return 5;
--
./CmdWarmStream.java:   public byte getType() {
./CmdWarmStream.java-      return 25;
--
./CmdMapData.java:   public byte getType() {
./CmdMapData.java-      return 10;
--
./CmdRecipeId.java:   public byte getType() {
./CmdRecipeId.java-      return 4;
--
./CmdBacklight.java:   public byte getType() {
./CmdBacklight.java-      return 28;
--
./CmdCurrentTemperature.java:   public byte getType() {
./CmdCurrentTemperature.java-      return 20;
--
./CmdIonization.java:   public byte getType() {
./CmdIonization.java-      return 24;
--
./CmdMapTarget.java:   public byte getType() {
./CmdMapTarget.java-      return 67;
--
./CmdKeepWarm.java:   public byte getType() {
./CmdKeepWarm.java-      return 16;
--
./CmdMultiStep.java:   public byte getType() {
./CmdMultiStep.java-      return 14;
--
./CmdCleanArea.java:   public byte getType() {
./CmdCleanArea.java-      return 36;
--
./CmdVolume.java:   public byte getType() {
./CmdVolume.java-      return 9;
--
./CmdTargetTemperature.java:   public byte getType() {
./CmdTargetTemperature.java-      return 2;
--
./CmdError.java:   public byte getType() {
./CmdError.java-      return 7;
--
./CmdCleanTime.java:   public byte getType() {
./CmdCleanTime.java-      return 35;
--
./CmdScheduleRemove.java:   public byte getType() {
./CmdScheduleRemove.java-      return 65;
--
./CmdBatteryState.java:   public byte getType() {
./CmdBatteryState.java-      return 29;
--
./CmdExpendables.java:   public byte getType() {
./CmdExpendables.java-      return 34;
--
./CmdContour.java:   public byte getType() {
./CmdContour.java-      return 68;
--
./CmdJoystick.java:   public byte getType() {
./CmdJoystick.java-      return 8;
--
./CmdMode.java:   public byte getType() {
./CmdMode.java-      return 1;
--
./CmdDelayStart.java:   public byte getType() {
./CmdDelayStart.java-      return 13;
--
./CmdTargetId.java:   public byte getType() {
./CmdTargetId.java-      return -112;
--
./CmdInternalLogs.java:   public byte getType() {
./CmdInternalLogs.java-      return -16;
--
./CmdFindMe.java:   public byte getType() {
./CmdFindMe.java-      return 69;
--
./CmdCustomCommand.java:   public byte getType() {
./CmdCustomCommand.java-      return 0;
--
./CmdScheduleSet.java:   public byte getType() {
./CmdScheduleSet.java-      return 64;
--
./CmdTotalTime.java:   public byte getType() {
./CmdTotalTime.java-      return 26;
--
./CmdChildLock.java:   public byte getType() {
./CmdChildLock.java-      return 30;
```

From `com/syncleoiot/iottransport/udp/commands`:
```
$ grep -A1 -r "public byte getType()" .
./CmdDeviceDiagnostics.java:   public byte getType() {
./CmdDeviceDiagnostics.java-      return -111;
--
./CmdHandshake.java:   public byte getType() {
./CmdHandshake.java-      return 0;
--
./CmdUdpFirmware.java:   public byte getType() {
./CmdUdpFirmware.java-      return -3;
--
./CmdTimeSync.java:   public byte getType() {
./CmdTimeSync.java-      return -128;
--
./CmdPing.java:   public byte getType() {
./CmdPing.java-      return -1;
```

From `com/syncleoiot/iottransport/commands`:
```
$ grep -A1 -r "public byte getType()" .
./CmdCrossConfig.java:   public byte getType() {
./CmdCrossConfig.java-      return -125;
--
./CmdWifiConfiguration.java:   public byte getType() {
./CmdWifiConfiguration.java-      return -126;
--
./CmdDiagnostics.java:   public byte getType() {
./CmdDiagnostics.java-      return -115;
--
./CmdWifiStatus.java:   public byte getType() {
./CmdWifiStatus.java-      return -126;
--
./CmdHardware.java:   public byte getType() {
./CmdHardware.java-      return 0;
--
./CmdWifiList.java:   public byte getType() {
./CmdWifiList.java-      return -127;
```

See also class `com/syncleiot/iottransport/commands/CmdHardware`.