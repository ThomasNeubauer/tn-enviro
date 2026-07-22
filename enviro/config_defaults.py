import config
from phew import logging

DEFAULT_USB_POWER_TEMPERATURE_OFFSET = 4.5
DEFAULT_BATTERY_POWER_TEMPERATURE_OFFSET = 0.0
DEFAULT_UTC_OFFSET = 0
DEFAULT_UK_BST = True
DEFAULT_BME688_ADDRESS = None
DEFAULT_SECONDARY_DESTINATION = None
DEFAULT_WIND_DIRECTION_OFFSET = 0
DEFAULT_PIO_WATCHDOG_TIME = 0
DEFAULT_SOFTWARE_WATCHDOG_TIME = 5
DEFAULT_SCHEDULED_RESTART_MINUTES = 0  # 0 = disabled

def add_missing_config_settings():
  try:
    # check if ca file parameter is set, if not set it to not use SSL by setting to None
    config.mqtt_broker_ca_file
  except AttributeError:
    warn_missing_config_setting("mqtt_broker_ca_file")
    config.mqtt_broker_ca_file = None

  try:
    config.usb_power_temperature_offset
  except AttributeError:
    warn_missing_config_setting("usb_power_temperature_offset")
    config.usb_power_temperature_offset = DEFAULT_USB_POWER_TEMPERATURE_OFFSET
  
  try:
    config.wifi_country
  except AttributeError:
    warn_missing_config_setting("wifi_country")
    config.wifi_country = "GB"
    
  try:
    config.battery_power_temperature_offset
  except AttributeError:
    warn_missing_config_setting("battery_power_temperature_offset")
    config.battery_power_temperature_offset = DEFAULT_BATTERY_POWER_TEMPERATURE_OFFSET

  try:
    config.secondary_destination
  except AttributeError:
    warn_missing_config_setting("secondary_destination")
    config.secondary_destination = DEFAULT_SECONDARY_DESTINATION

  try:
    config.wunderground_id
  except AttributeError:
    warn_missing_config_setting("wunderground_id")
    config.wunderground_id = None
  
  try:
    config.wunderground_key
  except AttributeError:
    warn_missing_config_setting("wunderground_key")
    config.wunderground_key = None
  
  try:
    config.sea_level_pressure
  except AttributeError:
    warn_missing_config_setting("sea_level_pressure")
    config.sea_level_pressure = False

  try:
    config.height_above_sea_level
  except AttributeError:
    warn_missing_config_setting("height_above_sea_level")
    config.height_above_sea_level = 0

  try:
    config.wind_direction_offset
  except AttributeError:
    warn_missing_config_setting("wind_direction_offset")
    config.wind_direction_offset = DEFAULT_WIND_DIRECTION_OFFSET
  
  try:
    config.uk_bst
  except AttributeError:
    warn_missing_config_setting("uk_bst")
    config.uk_bst = DEFAULT_UK_BST

  try:
    config.utc_offset
  except AttributeError:
    warn_missing_config_setting("utc_offset")
    config.utc_offset = DEFAULT_UTC_OFFSET

  try:
    config.bme688_address
  except AttributeError:
    warn_missing_config_setting("bme688_address")
    config.bme688_address = DEFAULT_BME688_ADDRESS

  try:
    config.run_continuously
  except AttributeError:
    warn_missing_config_setting("run_continuously")
    config.run_continuously = False

  try:
    config.pio_watchdog_time
  except AttributeError:
    warn_missing_config_setting("pio_watchdog_time")
    config.pio_watchdog_time = DEFAULT_PIO_WATCHDOG_TIME

  try:
    config.software_watchdog_time
  except AttributeError:
    warn_missing_config_setting("software_watchdog_time")
    config.software_watchdog_time = DEFAULT_SOFTWARE_WATCHDOG_TIME

  try:
    config.scheduled_restart_minutes
  except AttributeError:
    warn_missing_config_setting("scheduled_restart_minutes")
    config.scheduled_restart_minutes = DEFAULT_SCHEDULED_RESTART_MINUTES
  

def warn_missing_config_setting(setting):
    logging.warn(f"> config setting '{setting}' missing, please add it to config.py")
