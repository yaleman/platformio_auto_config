#!/usr/bin/env python3

""" easy re-configure for platformio_overrides when
    you're using a lot of devices

    config file for *this* script can go in two places:
    - platformio_auto_config.cfg
    - $HOME/.config/platformio_auto_config.cfg

    Options:
        'platformio_file' : 'platformio.ini',
        'config_file' : 'platformio_override.ini',
        'section' : 'common'

"""

import configparser
import os
import sys

try:
    import click
    from loguru import logger
except ImportError as error_message:
    sys.exit(error_message)



IGNORE_DEVICES_BY_DEFAULT = [
    '/dev/tty.Bluetooth-Incoming-Port',
    '/dev/tty.wlan-debug',
    '/dev/tty.debug-console',
]

def setup_logging(debug: bool, logger_object):
    """ sets up logging """
    if os.environ.get('LOGURU_LEVEL'):
        return True
    if not debug:
        logger_object.remove()
        logger_object.add(sys.stdout,
                          level="INFO",
                          format='<level>{message}</level>' #pylint: disable=line-too-long,
                          )
    return True

def get_tty_from_list(tty_list_object, indexof):
    """ .get for lists """
    if isinstance(indexof, str):
        if indexof.strip() == "":
            return False
    if not isinstance(indexof, int):
        logger.debug("converting {} type {} to int", indexof, type(indexof))
        try:
            indexof = int(indexof)
        except ValueError as error_message:
            logger.error("Failed to convert user input '{}' to int, bailing.", indexof)
            logger.debug(error_message)
            return False
    logger.debug("Pulling {} from {}", indexof, tty_list_object)
    try:
        retval = tty_list_object[indexof]
    except IndexError as error_message:
        logger.debug("Couldn't pull {} from {}, error: {}", indexof, tty_list_object, error_message)
        retval = False
    logger.debug("Returning {}", retval)
    return retval

def get_device_list(debug: bool):
    """ makes a device list """
    if os.uname().sysname in ('Darwin',):
        if not os.path.exists('/dev/'):
            logger.error("Couldn't find /dev/, what?")
            return False
        tty_list = [ os.path.join('/dev/', filename) for filename in os.listdir('/dev/') if filename.startswith('tty.') ] #pylint: disable=line-too-long
        if not debug:
            tty_list = [ entry for entry in tty_list if entry not in IGNORE_DEVICES_BY_DEFAULT ]
    else:
        logger.error("Sorry I don't support {} yet", os.uname().sysname)
        return False
    return tty_list

def show_device_list(debug: bool):
    """ shows a list of devices """
    default = -1
    seen_ttys = []
    tty_list = get_device_list(debug)
    if not tty_list:
        logger.error("Couldn't find any devices, quitting.")
        sys.exit(1)
    for indexof, tty in enumerate(tty_list):
        if 'usbserial' in tty:
            logger.info("{}\t{}", indexof, tty)
            default = indexof
            seen_ttys.append(tty)
    for indexof, tty in enumerate(tty_list):
        if tty not in seen_ttys:
            logger.info("{}\t{}", indexof, tty)

    return default, tty_list

def load_config(script_config):
    """ config loady things """
    section = script_config.get('settings', 'section')
    config = configparser.ConfigParser()

    if not os.path.exists(script_config.get('settings', 'config_file')):
        if not os.path.exists(script_config.get('settings', 'platformio_file')):
            sys.exit("You're not in a platformio dir, quitting")
        user_response = input(f"Config file {script_config.get('settings', 'config_file')} doesn't exist, do you want to create one? (y|yes) ").strip() #pylint: disable=line-too-long
        if user_response.lower() in ('yes','y'):
            config = configparser.ConfigParser()
            config[section] = {}
        else:
            sys.exit("User didn't confirm, bailing")

    else:
        config.read(script_config.get('settings', 'config_file'))

    if section not in config:
        config[section] = {}
    return config

def load_script_config(section: str=None, defaults: dict={}): #pylint: disable=dangerous-default-value
    """ loads config for *this* script """

    script_config = configparser.ConfigParser()
    script_config.read_dict(defaults)
    config_read = script_config.read([
        'platformio_auto_config.cfg',
        os.path.expanduser("~/.config/platformio_auto_config.cfg"),
        ])
    logger.debug("Read config from: {}", config_read)

    # override defaults
    if section:
        script_config['settings']['section'] = section
    return script_config

@click.command()
@click.option('--debug', '-d',
              is_flag=True,
              default=False,
              help="Debug mode, output more information",
              )
@click.option('--test', '-t',
              is_flag=True,
              default=False,
              help="Test mode - don't make changes",
              )
@click.option('--section','-s',
              default="common",
              help="Which section to edit - default is common",
              )
def cli(debug: bool, test: bool, section: str=None):
    """ cli command """
    setup_logging(debug, logger)

    script_config = load_script_config(section=section,defaults={
        'settings' : {
            'platformio_file' : 'platformio.ini',
            'config_file' : 'platformio_override.ini',
            'section' : 'common'
        }
    })

    config = load_config(script_config)
    logger.info("Editing config file: {}", script_config.get('settings', 'config_file') )

    logger.info("Editing section: {}", script_config.get('settings', 'section'))
    upload_port = False
    if config.has_option(section, 'upload_port'):
        upload_port = config.get(section, 'upload_port')
        logger.info("Upload port is currently set to: {}", upload_port)

    new_device = ""
    WHICH_QUESTION="Which input do you want to use?" #pylint: disable=invalid-name
    while True:
        default, tty_list = show_device_list(debug)
        selected = False
        if default >=0:
            user_response = input(f"{WHICH_QUESTION} Hit enter to select {tty_list[default]}: ").strip() #pylint: disable=line-too-long
            print("")
            if user_response == "":
                logger.debug("Selecting default option {}", default)
                new_device = get_tty_from_list(tty_list, default)
                selected = True
        else:
            if upload_port:
                input_msg = f"{WHICH_QUESTION} default is {upload_port}: "
            else:
                input_msg = f"No default currently set. {WHICH_QUESTION} "
            user_response = input(input_msg).strip()
            if isinstance(user_response, (bytes, str)) and user_response == "" and upload_port:
                new_device = upload_port
                selected = True
        if not selected and get_tty_from_list(tty_list, user_response):
            new_device = get_tty_from_list(tty_list, user_response)
        if new_device:
            break
        logger.error("I'm not sure what you selected ({}), but it wasn't right!", user_response)

    logger.info("Selected {}", new_device)
    config[section]['upload_port'] = new_device
    logger.debug("config[section]['upload_port'] = new_device")
    logger.debug("config[{}]['upload_port'] = {}", section, new_device)

    if test:
        logger.warning("Nothing changed, running in test mode.")
    else:
        with open(script_config.get('settings', 'config_file'), 'w') as file_handle:
            config.write(file_handle)

if __name__ == '__main__':
    cli() # pylint: disable=no-value-for-parameter
