INSTALL       = /usr/bin/env install
GLOBAL_PREFIX = /usr/local

ifeq ($(shell id -u), 0)
	USER_PREFIX = /usr/local
else
	USER_PREFIX = $(HOME)/.local
endif

# TODO drop or rewrite
PROGRAMS = admin_bot inverter_bot pump_bot sensors_bot
PROGRAMS += inverter_mqtt_receiver inverter_mqtt_sender
PROGRAMS += sensors_mqtt_receiver sensors_mqtt_sender
PROGRAMS += temphumd
PROGRAMS += gpiorelayd
PROGRAMS += gpiosensord
#PROGRAMS += web_api

all:
	@echo "Supported commands:"
	@echo
	@echo "    \033[1mmake install\033[0m        symlink all programs to $(USER_PREFIX)"
	@echo "    \033[1mmake install-tools\033[0m  copy admin scripts to /usr/local/bin"
	@echo "    \033[1mmake venv\033[0m           create virtualenv and install dependencies"
	@echo "    \033[1mmake web-api-dev\033[0m    launch web api development server"
	@echo

venv:
	python3 -m venv venv
	. ./venv/bin/activate && pip3 install -r requirements.txt

web-api-dev:
	. ./venv/bin/activate && HK_MODE=dev python3 src/web_api.py

install: check-root
	for name in @(PROGRAMS); do ln -s src/${name}.py $(USER_PREFIX)/bin/$name; done

install-tools: check-root
	$(INSTALL) tools/clickhouse-backup.sh $(GLOBAL_PREFIX)/bin
	chmod +x $(GLOBAL_PREFIX)/bin/clickhouse-backup.sh

check-root:
	ifneq ($(shell id -u), 0)
		$(error "You must be root.")
	endif

.PHONY: all install install-local install-tools venv web-api-dev check-root