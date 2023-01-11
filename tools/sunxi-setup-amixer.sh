#!/bin/bash

amixer() {
    /usr/bin/amixer "$@"
}

setup_opi_pc2() {
	for v in unmute cap; do
		amixer set "Line In" $v
		amixer set "Mic1" $v
		amixer set "Mic2" $v
	done

	for k in "Mic1 Boost" "Line In" "Mic1" "Mic2 Boost" "Mic2"; do
		amixer set "$k" "86%"
	done
}

setup_opi_one() {
	for v in unmute cap; do
		amixer set "Line In" $v
		amixer set "Mic1" $v
  	done

  	for k in "Mic1 Boost" "Line In" "Mic1"; do
		amixer set "$k" "86%"
  	done
}

setup_opi3lts() {
	switches=(
		"Left DAC Mixer ADCL"
		"Left DAC Mixer I2SDACL"
		"Left I2S Mixer ADCL"
		"Left I2S Mixer I2SDACL"
		"Left Input Mixer LINEINL"
		"Left Input Mixer MIC1"
		"Left Input Mixer MIC2"
		"Left Input Mixer OMixerL"
		"Left Input Mixer OMixerR"
		"Left Input Mixer PhoneN"
		"Left Input Mixer PhonePN"
		"Left Output Mixer DACL"
		"Left Output Mixer DACR"
		"Left Output Mixer LINEINL"
		"Left Output Mixer MIC1"
		"Left Output Mixer MIC2"
		"Left Output Mixer PhoneN"
		"Left Output Mixer PhonePN"
		"Right DAC Mixer ADCR"
		"Right DAC Mixer I2SDACR"
		"Right I2S Mixer ADCR"
		"Right I2S Mixer I2SDACR"
		"Right Input Mixer LINEINR"
		"Right Input Mixer MIC1"
		"Right Input Mixer MIC2"
		"Right Input Mixer OMixerL"
		"Right Input Mixer OMixerR"
		"Right Input Mixer PhoneP"
		"Right Input Mixer PhonePN"
		"Right Output Mixer DACL"
		"Right Output Mixer DACR"
		"Right Output Mixer LINEINR"
		"Right Output Mixer MIC1"
		"Right Output Mixer MIC2"
		"Right Output Mixer PhoneP"
		"Right Output Mixer PhonePN"
	)
	for v in "${switches[@]}"; do
		value=on
		case "$v" in
			*Input*)
				value=on
				;;
			*Output*)
				value=off
				;;
		esac
		amixer set "$v" $value
	done

	to_mute=(
		"I2S Mixer ADC"
		"I2S Mixer DAC"
		"ADC Input"
		"DAC Mixer ADC"
		"DAC Mxier DAC" # this is not a typo
	)
	for v in "${to_mute[@]}"; do
		amixer set "$v" "0%"
	done

	amixer set "Master" "100%"
	amixer set "MIC1 Boost" "100%"
	amixer set "MIC2 Boost" "100%"
	amixer set "Line Out Mixer" "86%"
	amixer set "MIC Out Mixer" "71%"
}

device="$(tr -d '\0' < /sys/firmware/devicetree/base/model)"
case "$device" in
	*"Orange Pi PC 2")
		setup_opi_pc2
		;;
	*"Orange Pi One")
		setup_opi_one
		;;
	*"OrangePi 3 LTS")
		setup_opi3lts
		;;
	*)
		>&2 echo "error: unidentified device: $device"
		;;
esac
