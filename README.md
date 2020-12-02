# Saikidou
*Clean shutdown/reboot your Dojo with a physical button.*


### Why?
* I don't have (don't need) a dedicated display for my node.
* Was unable to ssh into my node on multiple occasions.
* Wanted a fast go-to solution for a safe/forced system shutdown/reboot.
* Why not ¯\\\_(ツ)\_/¯


## Requirements
*Created for and tested with a Raspberry Pi 4 (all I have atm)*

1. Check which [GPIO pins](https://www.raspberrypi.org/documentation/usage/gpio/) you want to use on your board to connect a basic PC reset switch (or similar) 
  *This script is currently expecting the button to be connected to pins **39** (Ground) and **40** (GPIO 21)*

2. Install required Python libraries
    ```
    sudo pacman -Syy
    sudo pacman -S python-raspberry-gpio

    #Stop Dojo via GUI, then shutdown your system
    sudo shutdown -r now
    ```

3. Carefully connect your button to the GPIO pins, then turn on your raspi

4. Install and enable cron
    ```
    sudo pacman -S cronie
    sudo systemctl enable --now cronie.service
    ```


## Setup
1. Copy the contents of the Saikidou script to your user's home folder
    ```
    curl https://raw.githubusercontent.com/t0mmysm1th/saikidou/main/saikidou_reboot-script.py -o ~/saikidou_reboot-script.py
    ```

2. Create a temp file for `root` crontab (used to send contents to crontab file)

    *Change **PATH_TO_SCRIPT**, **YOUR_USER** and arguments as needed*
    ```
    echo -e '#Start Saikidou\n@reboot /usr/bin/python /PATH_TO_SCRIPT/saikidou_reboot-script.py --user YOUR_USER --safemode --type reboot' > root_crontab.txt
    ```

3. Install root's crontab using the contents of `root_crontab.txt`
    ```
    sudo crontab -u root root_crontab.txt
    
    #Stop Dojo via GUI, then reboot system
    reboot
    
    #After reboot, you can check if the script is running:
    ps aux | grep saikidou
    ```

4. Tail the log file, then test the button
    ```
    sudo tail -f /var/log/saikidou_reboot-script.log
    
    #Check help section for details on arguments
    
    ```

## Help & Examples
* Check help section for details on arguments
  ```
  python ~/saikidou_reboot-script.py -h
  ```
  
* Shutdown the raspi even if there was a problem stopping Dojo (ie. not using safemode)
  ```
  #Edit & repeat step 2 of "Setup" instructions, or edit /var/spool/cron/root
  saikidou_reboot-script.py --user YOUR_USER --type shutdown
  ```

* Force a system shutdown after holding down reset button for 15 seconds, then releasing (event triggers after release)
  ```
  #Edit & repeat step 2 of "Setup" instructions, or edit /var/spool/cron/root
  saikidou_reboot-script.py --user YOUR_USER --safemode --type reboot --forced --forced_delay 15 --forced_type shutdown
  ```
