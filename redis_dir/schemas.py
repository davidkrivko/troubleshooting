class StreamsKeySchema:
    """
    Stores keys string formats for
    redis_dir data types
    """

    def format_serial(self, sn):
        return sn.strip("-").upper()

    def thermostat_status_key(self, sn):

        serial = self.format_serial(sn)
        return f"TRM:ONL:{serial}"

    def ioniq_status_key(self, sn):

        serial = self.format_serial(sn)
        return f"ION:ONL:{serial}"

    def thermostat_data_key(self, sn):

        serial = self.format_serial(sn)
        return f"TRM:DATA:{serial}"

    def ioniq_data_key(self, sn):

        serial = self.format_serial(sn)
        return f"ION:DATA:{serial}"

    def ioniq_vars_key(self, sn):
        serial = self.format_serial(sn)
        return f"ION:VARS:{serial}"

    def boiler_settings_key(self, sn):
        serial = self.format_serial(sn)
        return f"ION:BLR:{serial}"

    # relay-thermostat pairs
    def paired_relay_key(self, sn):
        serial = self.format_serial(sn)
        return f"ION:PAIR:REL:{serial}"

    def receiver_key(self, sn):
        serial = self.format_serial(sn)
        return f"ION:PAIR:RES:{serial}"

    def paired_thermostat_key(self, sn):
        serial = self.format_serial(sn)
        return f"ION:PAIR:TRM:{serial}"

    def ioniq_max_thermostats_hset_key(self, sn: str):
        serial = self.format_serial(sn)
        return f"ION:TRH:{serial}"

    def thermostat_setpoint_key(self, sn: str):
        serial = self.format_serial(sn)
        return f"ION:TRM:STP{serial}"

    def boiler_data_key(self, sn: str):
        serial = self.format_serial(sn)
        return f"BLR:DATA:{serial}"
