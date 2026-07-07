# Enviro - wireless environmental monitoring and logging
#
# On first run Enviro will go into provisioning mode where it appears
# as a wireless access point called "Enviro <board type> Setup". Connect
# to the access point with your phone, tablet or laptop and follow the
# on screen instructions.
#
# The provisioning process will generate a `config.py` file which 
# contains settings like your wifi username/password, how often you
# want to log data, and where to upload your data once it is collected.
#
# You can use enviro out of the box with the options that we supply
# or alternatively you can create your own firmware that behaves how
# you want it to - please share your setups with us! :-)
#
# Need help? check out https://pimoroni.com/enviro-guide
#
# Happy data hoarding folks,
#
#   - the Pimoroni pirate crew

# Initialize logging early to capture all startup issues
from phew import logging
import sys
import os

# Configure phew logging - write to both console and file
logging.disable_logging_types(logging.LOG_DEBUG)

# Also initialize custom file logger for more reliable persistent logging
from lib.ulogging import uLogger
global_logger = uLogger("MAIN", log_level=4, handlers=["Console", "File"])

def log_to_file(message):
    """Direct file logging that should work even if other systems fail"""
    try:
        with open("crash.log", "a") as f:
            f.write(message + "\n")
    except:
        pass  # If we can't write to file, there's nothing we can do

# Issue #117 where neeed to sleep on startup otherwis emight not boot
from time import sleep
sleep(0.5)

# import enviro firmware, this will trigger provisioning if needed
import enviro
import config

# Add top-level exception handling to catch crashes in continuous mode too
try:
    if config.run_continuously == True:
        if enviro.model == "weather":
            from enviro.multicore import Multicore_Weather
            global_logger.info("> Creating multicore object")
            logging.info("> Creating multicore object")
            mw = Multicore_Weather()
            global_logger.info("> Starting multicore loop")
            logging.info("> Starting multicore loop")
            mw.init_multicore_poll_loop()
        else:
            enviro.halt("> multicore config is only compatible with weather boards")
    else:
        try:
            # initialise enviro
            enviro.startup()

            # if the clock isn't set...
            if not enviro.is_clock_set():
                enviro.logging.info("> clock not set, synchronise from ntp server")
                if not enviro.sync_clock_from_ntp():
                    # failed to talk to ntp server go back to sleep for another cycle
                    enviro.halt("! failed to synchronise clock")  

            # check disk space...
            if enviro.low_disk_space():
                # less than 10% of diskspace left, this probably means cached results
                # are not getting uploaded so warn the user and halt with an error
                
                # Issue #126 to try and upload if disk space is low
                # is an upload destination set?
                if enviro.config.destination:
                    enviro.logging.error("! low disk space. Attempting to upload file(s)")

                    # if we have enough cached uploads...
                    enviro.logging.info(f"> {enviro.cached_upload_count()} cache file(s) need uploading")
                    if not enviro.upload_readings():
                        enviro.halt("! reading upload failed")
                else:
                    # no destination so go to sleep
                    enviro.halt("! low disk space")

                # TODO this seems to be useful to keep around?
                filesystem_stats = os.statvfs(".")
                enviro.logging.debug(f"> {filesystem_stats[3]} blocks free out of {filesystem_stats[2]}")

                # TODO should the board auto take a reading when the timer has been set, or wait for the time?
                # take a reading from the onboard sensors
                enviro.logging.debug(f"> taking new reading")
                reading = enviro.get_sensor_readings()

                # here you can customise the sensor readings by adding extra information
                # or removing readings that you don't want, for example:
                # 
                #   del readings["temperature"]        # remove the temperature reading
                #
                #   readings["custom"] = my_reading()  # add my custom reading value

                # is an upload destination set?
                if enviro.config.destination:
                    # if so cache this reading for upload later
                    enviro.logging.debug(f"> caching reading for upload")
                    enviro.cache_upload(reading)

                    # if we have enough cached uploads...
                    if enviro.is_upload_needed():
                        enviro.logging.info(f"> {enviro.cached_upload_count()} cache file(s) need uploading")
                        if not enviro.upload_readings():
                            enviro.halt("! reading upload failed")
                    else:
                        enviro.logging.info(f"> {enviro.cached_upload_count()} cache file(s) not being uploaded. Waiting until there are {enviro.config.upload_frequency} file(s)")
                else:
                    # otherwise save reading to local csv file (look in "/readings")
                    enviro.logging.debug(f"> saving reading locally")
                    enviro.save_reading(reading)

                # go to sleep until our next scheduled reading
                enviro.sleep()

            # TODO should the board auto take a reading when the timer has been set, or wait for the time?
            # take a reading from the onboard sensors
            enviro.logging.debug(f"> taking new reading")
            
            # Take a reading from the configured boards sensors and any configured qw/st
            # modules, returns a dictionary of reading name and value pairs
            # e.g. reading = {"temperature" : 19.1, "humidity" : 64,...}
            reading = enviro.get_sensor_readings()

            # Here you can customise the returned date, adding or removing data points
            # Refer to the documentation for more information: 
            # https://github.com/pimoroni/enviro/blob/main/documentation/developer-guide.md

            # is an upload destination set?
            if enviro.config.destination:
                # if so cache this reading for upload later
                enviro.logging.debug(f"> caching reading for upload")
                enviro.cache_upload(reading)

                # if we have enough cached uploads...
                if enviro.is_upload_needed():
                    enviro.logging.info(f"> {enviro.cached_upload_count()} cache file(s) need uploading")
                    if not enviro.upload_readings():
                        enviro.halt("! reading upload failed")
                else:
                    enviro.logging.info(f"> {enviro.cached_upload_count()} cache file(s) not being uploaded. Waiting until there are {enviro.config.upload_frequency} file(s)")
            else:
                # otherwise save reading to local csv file (look in "/readings")
                enviro.logging.debug(f"> saving reading locally")
                enviro.save_reading(reading)

            # go to sleep until our next scheduled reading
            enviro.sleep()

        # handle any unexpected exception that has occurred
        except Exception as exc:
            enviro.exception(exc)

except Exception as exc:
    # Top-level exception handler - catches crashes that happen before enviro is fully initialized
    import io, time
    buf = io.StringIO()
    sys.print_exception(exc, buf)
    error_msg = f"!! TOP-LEVEL CRASH at {time.time()}: {buf.getvalue()}"
    
    # Try all possible logging methods
    try:
        global_logger.error(error_msg)
    except:
        pass
    try:
        logging.error(error_msg)
    except:
        pass
    try:
        log_to_file(error_msg)
    except:
        pass
    
    # Blink warning LED if possible
    try:
        enviro.warn_led(enviro.WARN_LED_BLINK)
    except:
        pass
    
    # Go to sleep to avoid infinite reboot loop
    try:
        enviro.sleep()
    except:
        # Last resort: hard reset
        import machine
        machine.reset()
