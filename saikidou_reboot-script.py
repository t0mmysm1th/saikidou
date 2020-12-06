# !/bin/python
# Saikidou (Reboot Script) - Clean shutdown/reboot Dojo with physical button.
import RPi.GPIO as GPIO
import time
import os
import logging
from subprocess import Popen, PIPE
import argparse
import time

#Set which GPIO pin to use (based on the Broadcom SOC Pin numbers)
use_gpio_pin = 21

SCRIPT_DESCRIPTION = """
Saikidou - Clean shutdown/reboot Dojo with physical button.

Requirements:
  * Created for and tested with a Raspberry Pi 4
  1. Check which GPIO pins you want to use on your raspi to connect a basic PC reset button (or similar) 
     This script is currently expecting the button to be connected to pins 39 (Ground) and 40 (GPIO 21)

  2. Install required Python libraries
    sudo pacman -Syy
    sudo pacman -S python-raspberry-gpio

  3. Install and enable cron
    sudo pacman -S cronie
    sudo systemctl enable --now cronie.service

  4. Create temp file (used to send contents to crontab file), then install root's crontab
     * Change as needed:
    echo -e '#Start Saikidou\\n@reboot /usr/bin/python /PATH_TO_SCRIPT/saikidou_reboot-script.py --user YOUR_USER --safemode --type reboot' > root_crontab.txt
    sudo crontab -u root root_crontab.txt
"""
#parser = argparse.ArgumentParser(description='Saikidou - Clean shutdown/reboot RoninDojo with physical button (NOTE! Must add to root cron with: @reboot python SCRIPT_PATH)', formatter_class=argparse.RawTextHelpFormatter)
parser = argparse.ArgumentParser(description=SCRIPT_DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('-u', '--user', type=str, help='REQUIRED: User running docker images (ie. user acount used for RoninDojo)', required=True)
parser.add_argument('-t', '--type', type=str, help='stop = Only stop Dojo, otherwise shutdown/reboot system afterwards. Default is reboot', choices=['stop','shutdown','reboot'], default='reboot')
parser.add_argument('-s', '--safemode', action='store_true', help='Unless {--forced} is used, avoid system shutdown/reboot on error (example: if docker returned error)')
parser.add_argument('-d', '--debug', action='store_true', help='To test button without stopping Dojo or doing system shutdown/reboot')
parser.add_argument('--forced', action='store_true', help='Force system shutdown/reboot (based on {--forced_type|-t|--type}) if a second button event is triggered after {--forced_delay} seconds. Default = reboot')
parser.add_argument('--forced_delay', type=int, help='Time in seconds between initial and secondary button event (example: press, hold X seconds, release = 2 events)', default=10)
parser.add_argument('--forced_type', type=str, help='Overwrites {-t|--type} for forced shutdown/reboot', choices=['shutdown','reboot'])
args = parser.parse_args()

#Create log file if it doesn't exist
log_file = "/var/log/saikidou_reboot-script.log"
if not os.path.exists(log_file):
    os.mknod(log_file)

#Define logging file
logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s - %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.info('...Saikidou initialized...')

# Setup the pin with internal pullups enabled and pin in reading mode.
GPIO.setmode(GPIO.BCM)
GPIO.setup(use_gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Our function on what to do when the button is pressed
event_count = 0
first_event_start_time = 0
event_start_time = 0
forced_started = False
timeUntilNextCheck = 5
def Shutdown(channel):
    global args, event_count, first_event_start_time, event_start_time, forced_started, timeUntilNextCheck
    
    event_start_time = time.time()

    # Dirty hack to ensure we trigger this only once
    event_count += 1

    logging.debug('Button event count=%d' % event_count)

    if event_count == 1:
        # Tracking time of initial button press event
        first_event_start_time = time.time()

        #os.system("clear")
        if not args.debug:
            logging.info('Attempting Dojo shutdown')
            dojo_stop_command = f"/home/%s/dojo/docker/my-dojo/dojo.sh stop" % args.user
            os.system(dojo_stop_command)
        else:
            logging.debug('Skipping Dojo shutdown due to "debug" argument')

        dojo_status = 'running'
        while dojo_status == 'running':
            # Sleep for timeUntilNextCheck seconds at a time, while we wait for Dojo to complete shutdown
            GPIO.remove_event_detect(use_gpio_pin)
            time.sleep(timeUntilNextCheck)
            GPIO.add_event_detect(use_gpio_pin, GPIO.FALLING, callback=Shutdown, bouncetime=3000)

            if not args.debug:
                p = Popen('docker inspect --format="{{.State.Running}}" db', shell=True, stdout=PIPE, stderr=PIPE, universal_newlines=True)
            else:
                # Fake output, for testing button
                p = Popen('echo true', shell=True, stdout=PIPE, stderr=PIPE, universal_newlines=True)
            output, error = p.communicate()
            if p.returncode == 1:
                dojo_status = 'invalid'
                logging.error('Docker inspect command failed. Unable to check if Dojo is running.')
            elif p.returncode != 0:
                if output.split()[0] in ("true"):
                    dojo_status = 'running'
                    logging.debug('Dojo shutting down')
                else:
                    dojo_status = 'unknown'
                    logging.error('Unknown Dojo shutdown status (returncode=1). output=%s' % (output))
            elif p.returncode == 0:
                if output.split()[0] in ("false"):
                    dojo_status = 'stopped'
                    logging.info('Dojo shutdown confirmed')
                else:
                    dojo_status = 'unknown'
                    logging.error('Unknown Dojo shutdown status (returncode=0). output=%s' % (output))
            elif error != '':
                dojo_status = 'error'
                logging.error('Dojo shutdown fail. error=%s' % (error))
            else:
                dojo_status = 'dead'
                logging.error('Dojo might already be stopped. output=%s error=%s' % (output, error))

        if args.safemode and dojo_status != 'stopped':
            logging.warning('Shutdown/Reboot canceled due to -s/--safemode argument')
        else:
            if args.type == 'shutdown':
                logging.info('Shutting down system')
                if not args.debug:
                    os.system("shutdown -s -t 0")
                else:
                    logging.debug('Skipping System shutdown due to "debug" argument')
            elif args.type == 'reboot':
                logging.info('Rebooting system')
                if not args.debug:
                    os.system("reboot")
                else:
                    logging.debug('Skipping System reboot due to "debug" argument')
            else:
                logging.info('System shutdown/reboot ignored')
    else:
        # Check time since the first event
        time_since_event = (time.time() - first_event_start_time)
        if not forced_started:
            logging.debug("--- %s seconds since first event ---" % time_since_event)
        if not forced_started and args.forced:
            if args.forced_delay <= timeUntilNextCheck:
                forced_delay = args.forced_delay + timeUntilNextCheck
            else:
                forced_delay = args.forced_delay
            # Do a forced System shutdown if {forced_delay} seconds passed since first event (but not more than {forced_delay} * 2
            if time_since_event >= forced_delay and time_since_event < (forced_delay * 2):
                forced_started = True
                logging.debug("First button event was %s seconds ago" % time_since_event)
                logging.info("Proceeding with Forced System shutdown")
                if args.type == 'shutdown' or args.forced_type == 'shutdown':
                    logging.info('FORCED: Shutting down system')
                    if not args.debug:
                        os.system("shutdown now")
                    else:
                        logging.debug('FORCED: Skipping System shutdown due to "debug" argument')
                else:
                    logging.info('FORCED: Rebooting system')
                    if not args.debug:
                        os.system("reboot")
                    else:
                        logging.debug('FORCED: Skipping System reboot due to "debug" argument')
            else:
                #Reset first event counter if too much time has passed
                if time_since_event > args.forced_delay * 2:
                    first_event_start_time = time.time()
                    logging.debug('FORCED: Setting new time for initial button event')

# Add our function to execute when the button pressed event happens
GPIO.add_event_detect(use_gpio_pin, GPIO.FALLING, callback=Shutdown, bouncetime=3000)

# Wait for button press event
while 1:
    time.sleep(1)
