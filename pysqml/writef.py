#
# Copyright 2018 Universidad Complutense de Madrid
#
# This file is part of pysqm-lite
#
# SPDX-License-Identifier: GPL-3.0+
# License-Filename: LICENSE.txt
#


import logging
import pkgutil
import datetime
import glob
import os.path

import pytz
import tzlocal

_logger = logging.getLogger(__name__)

# HALF_DAY = datetime.timedelta(days=0.5)


class TimeInterval:
    def __init__(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val

    def in_co(self, dt):

        if self.min_val <= dt < self.max_val:
            return True
        else:
            return False

    def in_oc(self, dt):
        if self.min_val < dt <= self.max_val:
            return True
        else:
            return False


class TimedDailyRotator:
    def __init__(self, when):
        self.when = when
        # self.interval = interval
        self.interval = datetime.timedelta(days=1.0)

    def in_interval(self, dt):
        ctime = dt.time()
        cdate = dt.date()

        lim = datetime.datetime.combine(cdate, self.when)
        if ctime < self.when:
            b = lim
            a = lim - self.interval
        else:
            a = lim
            b = lim + self.interval
        return TimeInterval(a, b)


def startup_(dirname, ref_dt):
    rot = TimedDailyRotator(
        when=datetime.time(hour=12, minute=0, second=0)
    )

    ref_inter = rot.in_interval(ref_dt)
    # for f in glob.glob(os.path.join(dirname, '*_*_*.dat')):
    candidates = []
    for f in glob.glob(os.path.join(dirname, '????????_??????_*.dat')):
        # A RE would be more general?
        g = os.path.basename(f)
        r = g.split('_')
        rr = '_'.join(r[:2])
        mm = datetime.datetime.strptime(rr, "%Y%m%d_%H%M%S")
        candidates.append((g, mm))
    candidates.sort(reverse=True)

    # print(candidates)
    # check most recent
    for cnd in candidates:
        fname, dt = cnd
        # TODO: we are checking all files here
        # but they are sorted, so less checks
        # are required
        if ref_inter.in_oc(dt):
            create = False
            filename = fname
            break
    else:
        # No candidates
        create = True
        filename = None
    return create, filename


def startup(time_interval, dirname):

    # for f in glob.glob(os.path.join(dirname, '*_*_*.dat')):
    candidates = []
    for f in glob.glob(os.path.join(dirname, '????????_??????_*.dat')):
        # A RE would be more general?
        g = os.path.basename(f)
        r = g.split('_')
        rr = '_'.join(r[:2])
        mm = datetime.datetime.strptime(rr, "%Y%m%d_%H%M%S")
        candidates.append((g, mm))
    candidates.sort(reverse=True)

    # print(candidates)
    # check most recent
    for cnd in candidates:
        fname, dt = cnd
        # TODO: we are checking all files here
        # but they are sorted, so less checks
        # are required
        if dt > time_interval.max_val:
            # This file is in the future, weird:
            continue

        if time_interval.in_oc(dt):
            create = False
            filename = fname
            break
        else:
            # No candidates
            create = True
            filename = None
            break
    else:
        # No candidates
        create = True
        filename = None

    return create, filename


class Conf:
    pass

def consumer_write_file(q, other):
    _logger.info('starting file writer consumer')

    ref_dt = datetime.datetime.now()
    _logger.debug('current local time, %s', ref_dt)
    # directory with logs

    dirname = '/home/spr/devel/guaix/pysqm-lite/A'
    _logger.debug('directory with previous files, %s', dirname)

    _logger.debug('interval of valid logs')
    rot = TimedDailyRotator(
        when=datetime.time(hour=12, minute=0, second=0)
    )
    valid_inter = rot.in_interval(ref_dt)

    last_change = valid_inter.min_val
    next_change = valid_inter.max_val
    _logger.debug('from %s upto %s', last_change, next_change)

    create, valid_fname = startup(valid_inter, dirname)

    if create:
        valid_fname = calc_filename(ref_dt, name='somename')
        _logger.debug('valid file not found')
        _logger.debug('create %s', valid_fname)
    else:
        _logger.debug('valid file is %s', valid_fname)

    while True:
        _logger.debug('enter thread loop')
        payload = q.get()
        if payload:
            _logger.debug('got (w) payload %s', payload)
            # write_to_file_3(payload, None)
            payload = update_p(payload)
            now_local = payload['tstamp_local']
            now_local_n = now_local.replace(tzinfo=None)
            if now_local_n >= next_change:
                _logger.debug('read time is after scheduled time change')
                _logger.debug('create new file')
                _logger.debug('compute next change')
                valid_inter = rot.in_interval(now_local_n)
                next_change = valid_inter.max_val
                valid_fname = calc_filename(now_local_n, name='somename')
            _logger.debug('write to file')
            write_to_file_3(payload, dirname, valid_fname)
            q.task_done()
        else:
            _logger.info('end file writer consumer thread')
            # other.client.loop_stop()
            break


def update_p(payload):
    # try file
    now = payload['tstamp']
    local_tz = payload['localtz']
    now_utc = pytz.utc.localize(now)
    now_local = now_utc.astimezone(local_tz)
    payload['tstamp_local'] = now_local
    return payload


def write_to_file_3(payload, dirname, filename):

    payload['tstamp_str'] = payload['tstamp'].isoformat('T', timespec='milliseconds')
    payload['tstamp_local_str'] = payload['tstamp_local'].replace(tzinfo=None).isoformat('T', timespec='milliseconds')
    # m.isoformat('T', timespec='milliseconds')
    line_tpl = "{tstamp_str};{tstamp_local_str};0;{temp_sensor};{freq_sensor};{sky_brightness};0"
    with open(os.path.join(dirname, filename), 'a') as fd:
        print(payload)
        if payload['cmd'] == 'r':
            msg = line_tpl.format(**payload)
            print(msg, file=fd)
    return 0


def consumer_write_file_(q, other):
    _logger.info('starting file writer consumer')

    # initial file
    dirname = '/home/spr/devel/guaix/pysqm-lite/A'

    ref_dt = datetime.datetime.now()

    create, fname = startup(dirname, ref_dt)
    # os.remove(filename)

    insconf = InstrumentConf()
    locconf = LocationConf()

    if create:
        filename = calc_filename(ref_dt, name=insconf.name)
        init_file(os.path.join(other.dirname, filename), insconf, locconf)

    other2 = Conf()
    other2.dirname = dirname
    other2.filename = fname

    while True:
        payload = q.get()
        if payload:
            _logger.debug('got (w) payload %s', payload)
            res = write_to_file_2(payload, other2)
            _logger.debug('server says %s', res)
            q.task_done()
        else:
            _logger.info('end file writer consumer thread')
            # other.client.loop_stop()
            break


def write_to_file(payload):
    _logger.debug('write payload %s to file', payload)
    with open('dum.txt', 'a') as fd:
        fd.write('%{}'.format(payload))
    return 0


def calc_filename(now, name):
    fname_tmpl = '{date:%Y%m%d_%H%M%S}_{name}.dat'
    return fname_tmpl.format(date=now, name=name)


class InstrumentConf:
    name = 'somename'
    filter = 'b'
    azimuth = 0.0
    altitude = 0.0
    model = 'model'
    fov = 'fov'
    mac_address = 'xxx'
    firmware = 'firmware'
    cover_offset = 0
    zero_point = 29


class LocationConf:
    contact_name = 'Sergio Pascual'
    organization = 'UCM'
    location = 'location'
    province = 'province'
    country = 'ES'
    site = 'site'
    latitude = 20.000
    longitude = 45.0000
    elevation = 203.4
    timezone = 'TZ'


def write_to_file_2(payload, other, fname, dt_interval, insconf, locconf):
    # try file
    now = payload['tstamp']
    local_tz = payload['localtz']
    now_utc = pytz.utc.localize(now)
    now_local = now_utc.astimezone(local_tz)
    payload['tstamp_local'] = now_local

    if not dt_interval.in_co(now_local):
        filename = calc_filename(now_local, name=insconf.name)
        init_file(os.path.join(other.dirname, filename), insconf, locconf)
    else:
        filename = other.filename

    try:
        open(os.path.join(other.dirname, filename))
    except FileNotFoundError:
        _logger.debug('file not found, create')
        init_file(os.path.join(other.dirname, filename), insconf, locconf)

    payload['tstamp_str'] = payload['tstamp'].isoformat('T', timespec='milliseconds')
    payload['tstamp_local_str'] = payload['tstamp_local'].replace(tzinfo=None).isoformat('T', timespec='milliseconds')
    # m.isoformat('T', timespec='milliseconds')
    line_tpl = "{tstamp_str};{tstamp_local_str};0;{temp_sensor};{freq_sensor};{sky_brightness};0"
    with open(os.path.join(other.dirname, filename), 'a') as fd:
        print(payload)
        if payload['cmd'] == 'r':
            msg = line_tpl.format(**payload)
            print(msg, file=fd)
    return 0


def init_file(filename, insconf, locconf):
    tmpl_b = pkgutil.get_data('pysqml', 'IDA-template.tpl')
    template_string = tmpl_b.decode('utf-8')
    with open(filename, 'w') as fd:
        sus = template_string.format(instrument=insconf, location=locconf)
        print(sus[:-1], end='', file=fd)