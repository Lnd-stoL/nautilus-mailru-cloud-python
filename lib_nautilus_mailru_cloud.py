# -*- coding: utf-8 -*-

from gi.repository import Notify
import pyperclip
import sys
import subprocess

# TODO: move to /usr/lib
sys.path.append('../PyMailCloud/')
from pymailcloud import PyMailCloud


mail_icon = "/usr/share/icons/hicolor/256x256/apps/mail.ru-cloud.png"
Notify.init ("nautilus-mail-cloud")

mail_cloud = PyMailCloud("test-cloud-api@mail.ru", "test-cloud-api123")

def get_mailru_cloud_path():
	return "~/Cloud-Mail.Ru"

def to_clipboard(string):
    p = subprocess.Popen(['xclip', '-selection', 'c'], stdin=subprocess.PIPE)
    p.communicate(input=string.encode("utf-8"))


def copy_public_link(filename):

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
