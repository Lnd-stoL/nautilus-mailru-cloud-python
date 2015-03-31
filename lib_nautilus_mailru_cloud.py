# -*- coding: utf-8 -*-

from gi.repository import Notify
import sys
import subprocess
import ConfigParser
from os.path import expanduser, isfile

# TODO: move to /usr/lib
sys.path.append('../PyMailCloud/')
from PyMailCloud import PyMailCloud


mail_icon = "/usr/share/icons/hicolor/256x256/apps/mail.ru-cloud.png"
Notify.init("nautilus-mail-cloud")

__mailru_cloud_path = ""
def get_mailru_cloud_path():
    global __mailru_cloud_path
    if __mailru_cloud_path == "":
        configParser = ConfigParser.RawConfigParser()
        configParser.read(expanduser("~") + "/.config/Mail.Ru/Mail.Ru_Cloud.conf")
        __mailru_cloud_path = configParser.get('General', 'folder')
    return __mailru_cloud_path

__email = ""
def get_mailru_cloud_email():
    global __email
    if __email == "":
        configParser = ConfigParser.RawConfigParser()
        configParser.read(expanduser("~") + "/.config/Mail.Ru/Mail.Ru_Cloud.conf")
        __email = configParser.get('General', 'email')
    return __email

__password = ""
def get_mailru_cloud_password():
    global __password
    if __password == "":
        config_filename = expanduser("~") + "/.config/Mail.Ru/Mail.Ru_Cloud-Nautilus.conf"
        if isfile(config_filename):
            configParser = ConfigParser.RawConfigParser()
            configParser.read(config_filename)
            __password = configParser.get('General', 'password')
    return __password


mail_cloud = None
def init():
    global mail_cloud
    if get_mailru_cloud_email() != "" and get_mailru_cloud_password() != "":
        mail_cloud = PyMailCloud(get_mailru_cloud_email(), get_mailru_cloud_password())


def save_config(password):
    config_filename = expanduser("~") + "/.config/Mail.Ru/Mail.Ru_Cloud-Nautilus.conf"
    configParser = ConfigParser.RawConfigParser()
    configParser.add_section('General')
    configParser.set('General', 'password', password)

    with open(config_filename, 'wb') as configfile:
        configParser.write(configfile)


def to_clipboard(string):
    p = subprocess.Popen(['xclip', '-selection', 'c'], stdin=subprocess.PIPE)
    p.communicate(input=string.encode("utf-8"))


def copy_public_link(filename):

    if filename.startswith(get_mailru_cloud_path()):
        filename = filename[len(get_mailru_cloud_path()):]

    try:
        url = mail_cloud.get_public_link(filename)
        to_clipboard(url)
        notification = Notify.Notification.new(
            "Cloud@Mail.ru",
            "Public link copied to clipboard",
            mail_icon
        )
    except Exception as e:
        print e
        notification = Notify.Notification.new(
            "Cloud@Mail.ru",
            "Could not create public link",
            mail_icon
        )
    notification.show()