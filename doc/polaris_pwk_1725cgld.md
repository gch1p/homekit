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

### Random notes

All commands, from `com/polaris/iot/api/comments`:
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

See also `com/syncleoiot/**/commands`.