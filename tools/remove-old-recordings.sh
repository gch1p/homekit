#!/bin/bash

# to be launched by cron on remote server

find /var/recordings -type f -mtime +14 -delete
