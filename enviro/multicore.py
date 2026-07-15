import _thread
from time import ticks_ms, ticks_diff, time
from machine import Pin
import _thread
from math import pi
import enviro
from enviro.boards import weather
from phew import logging
from lib.ulogging import uLogger

class Multicore_Weather:
  def __init__(self) -> None:
    self.mww = Multicore_Weather_Wind()

  def init_multicore_poll_loop(self) -> None:
    # enviro.connect_to_wifi() existing enviro NTP code connects to wifi unconditionally
    enviro.pulse_activity_led()
    enviro.sync_clock_from_ntp()
    self.mww.init_wind_poll_thread()
    enviro.stop_activity_led()

    # Arm watchdog if configured
    if hasattr(enviro.config, 'pio_watchdog_time') and enviro.config.pio_watchdog_time != 0:
        enviro.arm_watchdog()

    while True:
      try:
        self.poll_rain_pin()

        if self.mww.check_pending_wind_data_length() > 0:
          enviro.activity_led(100)
          all_data = self.collect_all_data()
          # Bouncing to disk maintains compatibility with original enviro code - no need to rewrite upload logic
          enviro.cache_upload(all_data)
          enviro.upload_readings()
          enviro.activity_led(0)
          
        # Reset watchdog timer on each iteration to prevent it from firing
        if hasattr(enviro.config, 'pio_watchdog_time') and enviro.config.pio_watchdog_time != 0:
            enviro.arm_watchdog()
            
      except Exception as e:
        enviro.logging.error(f"Multicore loop error: {e}")
        enviro.activity_led(0)
        # Re-arm watchdog after error to ensure system recovers
        if hasattr(enviro.config, 'pio_watchdog_time') and enviro.config.pio_watchdog_time != 0:
            enviro.arm_watchdog()

  def poll_rain_pin(self) -> None:
    weather.check_trigger()

  def collect_all_data(self) -> dict:
    sensors_reading = enviro.get_sensor_readings()
    wind_data = self.mww.get_pending_data()[-1]
    self.mww.clear_pending_data()
    all_data = sensors_reading | wind_data
    return all_data

class Multicore_Weather_Wind:
  def __init__(self) -> None:
    self.log = uLogger("Multicore_Weather_Wind")
    self.pending_wind_data_lock = _thread.allocate_lock()
    self.samples_lock = _thread.allocate_lock()
    self.wind_speed_pin = Pin(9, Pin.IN, Pin.PULL_UP)
    self.monitoring_window_s = 60
    self.sample_hz = 4
    self.sample_ms = 1000 / self.sample_hz
    self.samples = [[]] * (self.monitoring_window_s * self.sample_hz)
    self.samples_max_list_id = len(self.samples) - 1
    self.WIND_CM_RADIUS = 7.0
    self.WIND_FACTOR = 0.0218
    self.pending_wind_data = []
    self.debug = False
    self.processing_overhead_poll_count = 0
    self.last_loop_overhead_ms = 0
    self.remaining_loop_overhead_ms = 0
    self.gust_rolling_average_duration_s = 3
    self.previous_loop_time_ms = 0
    self.cached_samples = []

  def init_wind_poll_thread(self) -> None:
    self.wind_poll_thread = _thread.start_new_thread(self.constant_poll_wind_speed, ())

  def discard_overhead_compensation_poll(self) -> None:
    if self.remaining_loop_overhead_ms >= self.sample_ms:
      self.remaining_loop_overhead_ms -= self.sample_ms
    else:
      start = ticks_ms()
      while ticks_diff(ticks_ms(), start) <= (self.sample_ms - self.last_loop_overhead_ms):
        pass
      self.remaining_loop_overhead_ms = 0

    self.processing_overhead_poll_count += 1

  def sample_wind_poll(self) -> list:
    previous_wind_pin_state = self.wind_speed_pin.value()
    ticks = []
    start = ticks_ms()
    while ticks_diff(ticks_ms(), start) <= self.sample_ms:
      current_wind_pin_state = self.wind_speed_pin.value()
      if current_wind_pin_state != previous_wind_pin_state:
        ticks.append(ticks_ms())
        previous_wind_pin_state = current_wind_pin_state

    return ticks

  def record_sample_datapoint(self, sample_id) -> None:
    ticks = self.sample_wind_poll()
    with self.samples_lock:
      self.samples[sample_id] = ticks

    if self.debug:
      print("sample {} has value: {}".format(sample_id, self.samples[sample_id]))

  def append_pending_wind_data(self, wind_data) -> None:
    with self.pending_wind_data_lock:
      self.pending_wind_data.append(wind_data)

  def calculate_processing_overhead(self) -> None:
    time_now_ms = ticks_ms()
    processing_time_ms = time_now_ms - self.previous_loop_time_ms
    self.previous_loop_time_ms = time_now_ms
    self.last_loop_overhead_ms = processing_time_ms - ((self.monitoring_window_s * 1000) - self.last_loop_overhead_ms)
    self.remaining_loop_overhead_ms = self.last_loop_overhead_ms
    self.processing_overhead_poll_count = 0
    if self.debug:
      print("Processing overhead: {}".format(self.last_loop_overhead_ms))

  def constant_poll_wind_speed(self) -> None:
    self.previous_loop_time_ms = ticks_ms()
    sample_id = 0

    while (True):
      if self.remaining_loop_overhead_ms > 0:
        self.discard_overhead_compensation_poll()
      else:
        self.record_sample_datapoint(sample_id)

      if sample_id < self.samples_max_list_id:
        sample_id += 1
      else:
        sample_id = 0
        self.append_pending_wind_data(self.process_wind_data())
        self.calculate_processing_overhead()


  def calculate_wind_speed_m_s(self, average_tick_ms: float) -> float:
    if average_tick_ms == 0:
      wind_m_s = 0
    else:
      rotation_hz = (1000 / average_tick_ms) / 2
      circumference = self.WIND_CM_RADIUS * 2.0 * pi
      wind_m_s = rotation_hz * circumference * self.WIND_FACTOR

    return wind_m_s

  def calculate_average_wind(self, samples) -> float:
    average_tick_ms = self.calculate_sample_set_average_duration_ms(samples)
    average_wind_speed = self.calculate_wind_speed_m_s(average_tick_ms)

    return average_wind_speed

  def calculate_sample_set_average_duration_ms(self, sample_set) -> float:
    ticks = []
    for sample in sample_set:
      for tick in sample:
        ticks.append(tick)

    total_sample_set_ticks = len(ticks)

    if total_sample_set_ticks > 1:
      total_sample_set_time = ticks[-1] - ticks[0]
      average_sample_set_tick_duration_ms = total_sample_set_time / total_sample_set_ticks
    else:
      average_sample_set_tick_duration_ms = 0

    return average_sample_set_tick_duration_ms

  def determine_gust_wind(self, samples) -> float:
    gust_wind_speed = 0

    for start_sample in range(len(samples) - (self.gust_rolling_average_duration_s * self.sample_hz)):
      current_average_duration = self.calculate_sample_set_average_duration_ms(samples[start_sample:start_sample + (self.gust_rolling_average_duration_s * self.sample_hz)])
      current_speed = self.calculate_wind_speed_m_s(current_average_duration)
      if current_speed > gust_wind_speed:
        gust_wind_speed = current_speed

    return gust_wind_speed

  def cache_samples(self) -> None:
    with self.samples_lock:
      self.cached_samples = self.samples

  def remove_processing_overhead_data_polls(self, samples) -> list:
    adjusted_samples = self.cached_samples[0 + self.processing_overhead_poll_count : -1]
    return adjusted_samples

  def process_wind_data(self): # -> dict[str, float]:
    self.cache_samples()
    samples = self.remove_processing_overhead_data_polls(self.cached_samples)

    gust_wind_error = 0
    gust_wind = self.determine_gust_wind(samples)
    if gust_wind > 50:
      self.log.error(f"Wind speed is too high: {gust_wind}, data used to calculate gust wind speed: {samples}")
      gust_wind_error = gust_wind
      gust_wind = 0
    logging.info(f"> gust wind speed is: {gust_wind}")
    average_wind = self.calculate_average_wind(samples)
    logging.info(f"> average wind speed is: {average_wind}")

    if gust_wind_error > 0:
      return {"timestamp": time(), "avg_wind_speed": average_wind, "gust_wind_speed": gust_wind, "gust_wind_error": gust_wind_error, "samples": samples}

    return {"timestamp": time(), "avg_wind_speed": average_wind, "gust_wind_speed": gust_wind, "gust_wind_error": gust_wind_error}

  def get_pending_data(self) -> list:
    """
    Returns a list of dictionaries {"timestamp" : unixtimestamp, "avg_wind_speed" : float, "gust_wind_speed" : float}
    """
    with self.pending_wind_data_lock:
      pending_data = self.pending_wind_data

    return pending_data

  def clear_pending_data(self) -> None:
    with self.pending_wind_data_lock:
      self.pending_wind_data = []

  def check_pending_wind_data_length(self) -> int:
    with self.pending_wind_data_lock:
      length = len(self.pending_wind_data)

    return length
