from argparse import ArgumentParser
from home.temphum import SensorType, create_sensor


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-t', '--type', choices=[item.value for item in SensorType],
                        required=True,
                        help='Sensor type')
    parser.add_argument('-b', '--bus', type=int, default=0,
                        help='I2C bus number')
    arg = parser.parse_args()

    sensor = create_sensor(SensorType(arg.type), arg.bus)
    temp = sensor.temperature()
    hum = sensor.humidity()

    print(f'temperature: {temp}')
    print(f'rel. humidity: {hum}')
