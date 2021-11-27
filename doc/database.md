# Databases

## Inverter database

ClickHouse tables:
```sql
CREATE TABLE status (
	ClientTime DateTime,
	ReceivedTime DateTime,
	HomeID UInt16,
	GridVoltage UInt16,
	GridFrequency UInt16,
	ACOutputVoltage UInt16,
	ACOutputFrequency UInt16,
	ACOutputApparentPower UInt16,
	ACOutputActivePower UInt16,
	OutputLoadPercent UInt8,
	BatteryVoltage UInt16,
	BatteryVoltageSCC UInt16,
	BatteryVoltageSCC2 UInt16,
	BatteryDischargingCurrent UInt16,
	BatteryChargingCurrent UInt16,
	BatteryCapacity UInt8,
	HeatSinkTemp UInt16,
	MPPT1ChargerTemp UInt16,
	MPPT2ChargerTemp UInt16,
	PV1InputPower UInt16,
	PV2InputPower UInt16,
	PV1InputVoltage UInt16,
	PV2InputVoltage UInt16,
	MPPT1ChargerStatus Enum8('Abnormal' = 0, 'NotCharging' = 1, 'Charging' = 2),
	MPPT2ChargerStatus Enum8('Abnormal' = 0, 'NotCharging' = 1, 'Charging' = 2),
	BatteryPowerDirection Enum8('DoNothing' = 0, 'Charge' = 1, 'Discharge' = 2),
	DCACPowerDirection Enum8('DoNothing' = 0, 'AC/DC' = 1, 'DC/AC' = 2),
	LinePowerDirection Enum8('DoNothing' = 0, 'Input' = 1, 'Output' = 2),
	LoadConnected Enum8('Disconnected' = 0, 'Connected' = 1)
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ReceivedTime)
ORDER BY (HomeID, ReceivedTime);

CREATE TABLE generation (
	ClientTime DateTime,
	ReceivedTime DateTime,
	HomeID UInt16,
	Watts UInt16
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ReceivedTime)
ORDER BY (HomeID, ReceivedTime);
```


## Sensors database

ClickHouse tables:
```sql
CREATE TABLE temp_table_name (
    ClientTime DateTime,
    ReceivedTime DateTime,
    HomeID UInt16,
    Temperature Int16,
    RelativeHumidity UInt16
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ReceivedTime)
ORDER BY (HomeID, ReceivedTime);
```