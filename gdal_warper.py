#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Listen to Posttroll messages and use gdalwarp to resample the images."""

import datetime as dt
import logging
import logging.config
import os
import signal
import subprocess
import sys
import time
from multiprocessing import Pool

import yaml
from posttroll.subscriber import Subscribe
from posttroll.publisher import Publish
from posttroll.message import Message


def read_config(fname):
    """Read configuration file."""
    with open(fname, 'r') as fid:
        config = yaml.load(fid, yaml.SafeLoader)
    return config


def _get_warp_command(config, fname_in, fname_out):
    """Parse gdalwarp arguments."""
    cmd = ['gdalwarp']
    for opt in config:
        if isinstance(config[opt], list):
            opts = []
            for itm in config[opt]:
                opts += ['-' + opt, itm]
            cmd += opts
        else:
            cmd += ['-' + opt] + config[opt].split()
    cmd += [fname_in, fname_out]

    return cmd


def _run_cmd(cmd):
    """Run a command."""
    tic = time.time()
    try:
        process = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
    except FileNotFoundError:
        return (False, "Command '%s' not found" % cmd[0])
    elapsed = time.time() - tic
    if process.returncode != 0:
        return (False, process.stderr.decode('utf-8'))
    return (True,
            "File reprojected in %.1f seconds." % elapsed)


def warp(fname_in, target_dir, config):
    """Warp the image using gdalwarp."""
    logger = logging.getLogger("warp")

    fname = os.path.basename(fname_in)
    fname_out = os.path.join(target_dir, fname)

    cmd = _get_warp_command(config, fname_in, fname_out)

    logger.debug("Running gdalwarp for '%s'", fname)
    success, msg = _run_cmd(cmd)

    if success:
        logger.debug(msg)
        return fname_out
    logger.error(msg)
    return None


def add_overviews(fname, overviews):
    """Add overviews to a geotiff file."""
    logger = logging.getLogger("overviews")
    if not overviews:
        logger.debug("No overviews configured")
        return True

    cmd = ['gdaladdo', fname] + [str(x) for x in overviews]
    success, msg = _run_cmd(cmd)

    if success:
        logger.info(msg)
        return True
    else:
        logger.error(msg)
        return False


def _warper_loop(config, pub, pub_topic, pool):
    """Run warper loop."""
    logger = logging.getLogger("warper_loop")
    restart_timeout = config.get("restart_timeout")

    sub_config = config.get("subscriber", {})
    if "addr_listener" not in sub_config:
        sub_config["addr_listener"] = True

    keep_looping = True

    def _signal_handler(signum, frame):
        nonlocal keep_looping
        logger.info("Caught SIGTERM, stop receiving new messages.")
        keep_looping = False

    signal.signal(signal.SIGTERM, _signal_handler)

    latest_message_time = dt.datetime.utcnow()
    results = []
    queued_images = 0
    with Subscribe(**sub_config) as sub:
        for msg in sub.recv(1):
            while results:
                msg_data, pub_msg = results.pop(0)
                _publish_message(pub, msg_data, pub_msg)
                queued_images -= 1
            if restart_timeout:
                time_since_last_msg = dt.datetime.utcnow() - latest_message_time
                time_since_last_msg = time_since_last_msg.total_seconds() / 60.
            if queued_images == 0:
                if not keep_looping:
                    return signal.SIGTERM
                if time_since_last_msg > restart_timeout:
                    logger.debug("%.0f minutes since last message",
                                 time_since_last_msg)
                    return
            if msg is None:
                continue
            logger.debug("New message received: %s", str(msg))
            latest_message_time = dt.datetime.utcnow()

            pool.apply_async(
                _process_message_worker,
                args=(config, msg.data.copy(), pub_topic),
                callback=results.append)
            queued_images += 1


def _process_message_worker(config, msg_data, pub_topic):
    pub_msg = _process_message(config, msg_data, pub_topic)
    return (msg_data, pub_msg)


def _publish_message(pub, msg_data, pub_msg):
    if pub_msg is not None:
        logger = logging.getLogger("warp_process_message")
        logger.debug("Publishing %s", str(pub_msg))
        pub.send(str(pub_msg))
        logger.info("Warped %s to %s", msg_data['uri'],
                    pub_msg.data['uri'])


def _process_message(config, msg_data, pub_topic):
    """Process the message."""
    overviews = config.get("overviews")
    meta = msg_data.copy()
    new_uri = warp(meta['uri'], config["target_dir"],
                   config[config["target_projection"]])
    if new_uri is None:
        return
    if not add_overviews(new_uri, overviews):
        return
    meta['uri'] = new_uri
    meta['uid'] = os.path.basename(new_uri)
    return Message(pub_topic, "file", meta)


def main():
    """Main()"""
    config = read_config(sys.argv[1])
    if "target_projection" not in config:
        config["target_projection"] = sys.argv[2]

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])
    logger = logging.getLogger("gdal_warper")
    logger.info("GDAL warper started.")

    pub_config = config["publisher"]
    pub_topic = pub_config.pop("pub_topic")

    num_workers = config.get("num_workers", 1)
    with Pool(processes=num_workers) as pool:
        with Publish("gdal_warper", **pub_config) as pub:
            while True:
                logger.debug("Starting warper loop.")
                ret = _warper_loop(config, pub, pub_topic, pool)
                if ret == signal.SIGTERM:
                    break
    logger.info("GDAL warper stopped.")


if __name__ == "__main__":
    main()
