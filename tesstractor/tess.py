#
# Copyright 2018-2019 Universidad Complutense de Madrid
#
# This file is part of tesstractor
#
# SPDX-License-Identifier: GPL-3.0+
# License-Filename: LICENSE.txt
#


import logging
import time
import re
import math
import datetime

from .device import Device, PhotometerConf


MEASURE_RE = re.compile(br"""
    ^(<f(?P<freq_pref>[mH])((?P<freq_u>(?<=m)-.{5})|(?P<freq_o>(?<=H)-.{5})|(?P<freq>\ \d{5}))>
    (<tA\ (?P<temp_ambient>[+-]\d{4})>)? # white space is ignored, so "\ "
    (<tO\ (?P<temp_sky>[+-]\d{4})>)?
    (<aX\ (?P<acc_x>[+-]\d{4})>)?
    (<aY\ (?P<acc_y>[+-]\d{4})>)?
    (<aZ\ (?P<acc_z>[+-]\d{4})>)?
    (<mX\ (?P<mag_x>[+-]\d{4})>)?
    (<mY\ (?P<mag_y>[+-]\d{4})>)?
    (<mZ\ (?P<mag_z>[+-]\d{4})>)?
    (?P<counter>\d+)?)?
    \r\n
    """, re.VERBOSE)


_logger = logging.getLogger(__name__)


class TESSConf(PhotometerConf):
    pass


class Tess(Device):
    def __init__(self, name="unknown", model='unknown'):
        super().__init__()
        # Get Photometer identification codes

        self.name = name
        self.model = model
        self.protocol_number = 0
        self.model_number = 0
        self.feature_number = 0
        self.serial_number = self.name
        self.calibration = 20.5
        self.mac = "01:23:45:67:89:AB"
        self.cmd_wait = 0
        self.counts = 1

    def static_conf(self):
        conf = TESSConf()
        conf.name = self.serial_number
        conf.model = self.model
        conf.serial_number = self.serial_number
        conf.firmware = self.feature_number
        conf.zero_point = self.calibration
        conf.mac_address = self.mac
        return conf

    def process_metadata(self, match):
        if match:
            return {'cmd': 'i', 'protocol_number': self.protocol_number,
                    'model_number': self.model_number,
                    'feature_number': self.feature_number,
                    'serial_number': self.serial_number}
        else:
            raise ValueError('process_metadata')

    def process_data(self, match):
        re_m = match.groupdict()
        # temps
        result = {}
        result['cmd'] = 'r'
        result['freq'] = 0.0
        result['magnitude'] = 99.0
        result['name'] = self.name
        result['model'] = 'TESS'
        result['freq_sensor'] = 0.0

        if re_m['freq_pref'] is None:
            return result
        else:
            if re_m['freq_o'] is not None:
                # overflow
                return result
            if re_m['freq_u'] is not None:
                # underflow
                return result

            if re_m['freq_pref'] == b'm':
                result['freq'] = int(re_m['freq']) / 1000.0
            elif re_m['freq_pref'] == b'H':
                result['freq'] = int(re_m['freq']) / 1.0
            else:
                raise ValueError('freq_pref')
            result['freq_sensor'] = result['freq'] * 1000.0
            result['magnitude'] = self.calibration - 2.5 * math.log10(result['freq'])
        acc_keys = ['temp_ambient', 'temp_sky']
        for key in acc_keys:
            if re_m[key] is not None:
                result[key] = int(re_m[key]) / 100.0

        acc_keys = ['acc_x', 'acc_y', 'acc_z']

        for key in acc_keys:
            if re_m[key] is not None:
                result[key] = int(re_m[key])

        acc_keys = ['mag_x', 'mag_y', 'mag_z']

        for key in acc_keys:
            if re_m[key] is not None:
                result[key] = int(re_m[key])
        return result


    def check_capabilities(self, match):

        key_f = 'freq_pref'
        # flux_keys = ['freq_pref', 'freq_o', 'freq_u', 'freq']
        temp_keys = ['temp_ambient', 'temp_sky']
        acc_keys = ['acc_x', 'acc_y', 'acc_z']
        mag_keys = ['mag_x', 'mag_y', 'mag_z']

        capabilities = dict(
            has_flux=False,
            has_acc=False,
            has_mag=False,
        )

        for key in temp_keys:
            capabilities['has_{}'.format(key)] = False

        re_m = match.groupdict()

        if re_m.get(key_f, None) is not None:
            capabilities['has_flux'] = True

        for key in temp_keys:
            if re_m.get(key, None) is not None:
                capabilities['has_{}'.format(key)] = True
        capabilities['has_acc'] = all(re_m.get(k, None) is not None for k in acc_keys)
        capabilities['has_mag'] = all(re_m.get(k, None) is not None for k in mag_keys)

        return capabilities

    def filter_buffer(self, payloads):
        npayloads = len(payloads)
        result = dict(payloads[0])
        # we have to average
        # tstamp, freq, freq_sensor, magnitude
        # magnitude corresponds to the mag of the average freq
        if any([p['freq'] <= 0 for p in payloads]):
            # FIXME: over/underflow
            result['freq'] = result['freq_sensor'] = 0
            result['magnitude'] = 99
        else:
            for key in ['freq_sensor']:
                result[key] = sum(p[key] for p in payloads) / npayloads
            # print(result['freq'])
            # print([p['freq'] <= 0 for p in payloads])
            # print(any([p['freq'] <= 0 for p in payloads]))
            result['freq'] = result['freq_sensor'] / 1000.0
            result['magnitude'] = self.calibration - 2.5 * math.log10(result['freq'])

        # average times
        ts0 = payloads[0]['tstamp']
        ts = [(p['tstamp'] - ts0) for p in payloads]
        result['tstamp'] = ts0 + sum(ts, datetime.timedelta(0)) / npayloads
        return result

    @classmethod
    def filter_buffer2(cls, payloads):
        npayloads = len(payloads)
        result = dict(payloads[0])
        # we have to average
        # tstamp, freq, freq_sensor, magnitude
        # magnitude corresponds to the mag of the average freq
        for key in ['freq_sensor']:
            result[key] = sum(p[key] for p in payloads) / npayloads

        result['freq'] = result['freq_sensor'] / 1000.0
        mags = [p['magnitude'] for p in payloads]
        result['magnitude'] = average_mags(mags)

        # average times
        ts0 = payloads[0]['tstamp']
        ts = [(p['tstamp'] - ts0) for p in payloads]
        result['tstamp'] = ts0 + sum(ts, datetime.timedelta(0)) / npayloads
        return result


    def process_calibration(self, match):
        if match:
            return {'cmd': 'c', 'calibration': self.calibration}
        else:
            raise ValueError('process_calibration')

    def start_connection(self):
        pass

    def close_connection(self):
        pass

    def reset_device(self):
        """Restart connection"""
        _logger.debug('reset device')
        self.close_connection()
        self.start_connection()
        _logger.debug('reset done')

    def read_metadata(self, tries=1):
        """Read the serial number, firmware version."""

        logger = logging.getLogger(__name__)
        # Read data to check capabilities

        this_try = 0
        while this_try < tries:
            msg = self.read_msg()
            logger.debug("metadata msg is %s", msg)
            match = MEASURE_RE.match(msg)
            if match:
                # check capabilities
                logger.debug('metadata is %s', msg)
                self.check_capabilities(match)
                return msg
            else:
                logger.warning('malformed data, ignoring %s', msg)
                logger.debug('data is %s', msg)
                this_try += 1

        msg = 'reading data after {} tries'.format(tries)
        logger.error(msg)
        raise ValueError(msg)


    def read_calibration(self, tries=1):
        """Read the calibration parameters"""

        pmsg = {}
        return pmsg

    def read_data(self, tries=1):
        """Read the calibration parameters"""

        logger = logging.getLogger(__name__)

        this_try = 0
        while this_try < tries:
            msg = self.read_msg()
            logger.debug("msg is %s", msg)
            match = MEASURE_RE.match(msg)
            if match:
                #logger.debug('process data')
                pmsg = self.process_data(match)
                logger.debug('data is %s', pmsg)
                return pmsg
            else:
                logger.warning('malformed data, ignoring %s', msg)
                # logger.debug('data is %s', msg)
                this_try += 1
                time.sleep(self.cmd_wait)
                self.reset_device()
                time.sleep(self.cmd_wait)
                return None

        msg = 'reading data after {} tries'.format(tries)
        logger.error(msg)
        raise ValueError(msg)

    def pass_command(self, cmd):
        pass

    def read_msg(self):
        return b''


class TessR(Tess):
    def __init__(self, conn, name="tess", sleep_time=1, tries=10):
        super().__init__(name=name, model='TESS-R')
        self.serial = conn
        # Clearing buffer
        self.read_msg()

    def start_connection(self):
        """Start photometer connection"""
        _logger.debug('start connection')
        if not self.serial.is_open:
            self.serial.open()

        self.read_metadata(tries=10)
        self.read_calibration(tries=10)
        self.read_data(tries=10)

    def close_connection(self):
        """End photometer connection"""
        # Check until there is no answer from device
        _logger.debug('close connection')
        self.serial.close()

    def read_msg(self):
        """Read the data"""
        msg = self.serial.readline()
        return msg

    def pass_command(self, cmd):
        self.serial.write(cmd)


def filter_buffer(payloads):
    mags = [p['magnitude'] for p in payloads]
    avg_mag = average_mags(mags)
    # return avg payload
    avg_payload = dict(payloads[0])
    avg_payload['magnitude'] = avg_mag
    return avg_payload


def average_mags(mags):
    # to avoid overflows reference to the brightest mag
    min_mag = min(mags)
    fluxes = [10**(-0.4 * (m - min_mag)) for m in mags]
    avg_flux = sum(fluxes) / len(fluxes)
    avg_mag = min_mag - 2.5 * math.log10(avg_flux)
    # return avg payload
    return avg_mag
