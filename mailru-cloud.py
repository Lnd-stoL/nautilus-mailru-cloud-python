
# -*- coding: utf-8 -*-
__version__ = "0.1"

#-----------------------------------------------------------------------------------------------------------------------
# tunables

PYMAILCLOUD_PATH = '../PyMailCloud/'
NOTIFY_ICON = '/usr/share/icons/hicolor/256x256/apps/mail.ru-cloud.png'
CONFIG_PATH = '/.config/Mail.Ru/Mail.Ru_Cloud-NautilusExtension.conf'
MAILRU_CONFIG_PATH = '/.config/Mail.Ru/Mail.Ru_Cloud.conf'

#-----------------------------------------------------------------------------------------------------------------------
# imports

from gi.repository import Nautilus, GObject, Gtk, Notify
from os.path import expanduser, isfile

import sys
import subprocess
import ConfigParser
import urllib

sys.path.append(PYMAILCLOUD_PATH)
from PyMailCloud import PyMailCloud, PyMailCloudError

#-----------------------------------------------------------------------------------------------------------------------
# error handling

class MailCloudClientError(Exception):
    pass

    class CloudNotInstalledError(Exception):
        def __init__(self, details='', message="Official Mail.Ru cloud client is probably not installed (can't find configs)"):
            super(MailCloudClientError.CloudNotInstalledError, self).__init__(message + ' [' + details + ']')

    class UnconfiguredError(Exception):
        def __init__(self, details='', message="Can't do this without valid configuration (password is needed)"):
            super(PyMailCloudError.NetworkError, self).__init__(message + ' [' + details + ']')

#-----------------------------------------------------------------------------------------------------------------------
# GUI components

class PasswordEntryDialog(Gtk.Dialog):

    def __init__(self, *args, **kwargs):
        if 'default_value' in kwargs:
            default_value = kwargs['default_value']
            del kwargs['default_value']
        else:
            default_value = ''

        dlg_buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        super(PasswordEntryDialog, self).__init__(title='Cloud@Mail.Ru Password', flags=0, buttons=dlg_buttons, *args, **kwargs)
        self.set_default_size(200, 150)

        label = Gtk.Label()
        label.set_markup("<b>Enter your cloud@mail.ru password: </b>")
        self.vbox.pack_start(label, True, True, 5)

        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_text(str(default_value))
        entry.connect("activate",
                      lambda ent, dlg, resp: dlg.response(resp),
                      self, Gtk.ResponseType.OK)
        self.vbox.pack_end(entry, True, True, 10)
        self.vbox.show_all()
        self.entry = entry

    def set_value(self, text):
        self.entry.set_text(text)

    def run(self):
        result = super(PasswordEntryDialog, self).run()
        if result == Gtk.ResponseType.OK:
            text = self.entry.get_text()
        else:
            text = None
        return text


class ErrorDialog(Gtk.MessageDialog):
     def __init__(self, message):
        super(ErrorDialog, self).__init__(None, 0, Gtk.MESSAGE_INFO, Gtk.BUTTONS_CLOSE, message)
        self.set_default_size(200, 150)

     def show(self):
         self.run()
         self.destroy()

#-----------------------------------------------------------------------------------------------------------------------

class MailCloudClient:

    class User:
        email = '<unset>'
        password = '<unset>'


    def __init__(self):
        self.is_configured = False

        Notify.init("nautilus-mail-cloud")
        self._load_mailru_config()
        self._load_config()


    def _load_mailru_config(self):
        try:
            config = ConfigParser.ConfigParser()
            config.read(expanduser("~") + MAILRU_CONFIG_PATH)
        except (ConfigParser.ParsingError, IOError):
            raise MailCloudClientError.CloudNotInstalledError()

        self.mailru_user = MailCloudClient.User()
        try:
            self.mailru_user.email = config.get('General', 'email')
            self.cloud_local_dir   = config.get('General', 'folder')
        except ConfigParser.Error as err:
            raise MailCloudClientError.UnconfiguredError('invalid config format: ' + err.message)


    def _load_config(self):
        try:
            config = ConfigParser.ConfigParser()
            config.read(expanduser("~") + CONFIG_PATH)
            self.mailru_user.password = config.get('User', 'password')
            self.is_configured = True

        except (IOError, ConfigParser.Error) as err:
            print(err)
            self.is_configured = False


    def _save_config(self):
        config = ConfigParser.ConfigParser()
        config.add_section('User')
        config.set('User', 'password', self.mailru_user.password)

        with open(expanduser("~") + CONFIG_PATH, 'wb') as config_file:
            config.write(config_file)

        self.is_configured = True


    def configure_with_gui(self):
        dlg = PasswordEntryDialog()
        password_str = dlg.run()
        dlg.destroy()
        if password_str is None: return False  # configuration cancelled by user

        self.mailru_user.password = password_str

        try:
            self._save_config()
        except (IOError, ConfigParser.Error) as err:
            print(err)
            # todo: handle error
            return False

        return True   # configured ok


    def _ensure_pymalicloud_initialized(self):
        try: self.py_mail_cloud
        except AttributeError:
            self.py_mail_cloud = PyMailCloud(self.mailru_user.email, self.mailru_user.password)


    def _decode_uri(self, path_uri):
        uri_prefix = 'file://'
        return urllib.unquote(path_uri[len(uri_prefix):]).decode('utf8')


    def local_path_is_in_cloud(self, path_uri):
        local_path = self._decode_uri(path_uri)
        return local_path.startswith(self.cloud_local_dir)


    def to_relative_path(self, path_uri):
        local_path = self._decode_uri(path_uri)
        return local_path[len(self.cloud_local_dir):]


    def get_public_link(self, path_uri):
        self._ensure_pymalicloud_initialized()
        return self.py_mail_cloud.get_public_link(self.to_relative_path(path_uri))


#-----------------------------------------------------------------------------------------------------------------------
# nautilus extension class

class MailRuCloudExtension(GObject.GObject, Nautilus.MenuProvider, Nautilus.InfoProvider):

    def __init__(self):
        try:
            self.mailru_client = MailCloudClient()
        except MailCloudClientError.CloudNotInstalledError as err:
            print(err)
            ErrorDialog('Unable to initialize Cloud@MailRu extension: ' + err.message).show()

        print 'Cloud@Mail.ru extension ver.' +  __version__ + ' initialized'


    def get_file_items(self, window, files):
        try: self.mailru_client
        except AttributeError: return  # extensions is unitialized

        if len(files) != 1 or not self.mailru_client.local_path_is_in_cloud(files[0].get_uri()):
            return    # nothing to do with multiple selected files or outside mail.ru cloud directory
        file = files[0]

        top_mailru_item = Nautilus.MenuItem(name="MailRuCloudExtension::TopMenu", label="Cloud@Mail.ru")
        mailru_submenu = Nautilus.Menu()
        top_mailru_item.set_submenu(mailru_submenu)

        public_link_item = Nautilus.MenuItem(
            name="MailRuCloudExtension::GetPublicLink",
            label="Copy public link to '%s'" % file.get_name()
        )
        public_link_item.connect('activate', self.on_menu_get_public_link, file)
        mailru_submenu.append_item(public_link_item)

        return [top_mailru_item]


    def update_file_info(self, file):
        if not self.mailru_client.local_path_is_in_cloud(file.get_uri()): return
        file.add_emblem("default")

    #------------------------------------------------- menu handlers ---------------------------------------------------

    def on_menu_get_public_link(self, menu, file):
        if not self.mailru_client.is_configured:
            if not self.mailru_client.configure_with_gui():
                return  # the user refused configuration

        notification_text = 'Could not get public link'
        try:
            public_url = self.mailru_client.get_public_link(file.get_uri())
            self._to_clipboard(public_url)
            notification_text = 'Public link copied to clipboard'

        except PyMailCloudError.AuthError:
            ErrorDialog('Mail.Ru autentification failed. Maybe password is incorrect.').show()

        except Exception as err:
            print(err)

        notification = Notify.Notification.new("Cloud@Mail.ru", notification_text, NOTIFY_ICON)
        notification.show()


    def _to_clipboard(self, data):
        p = subprocess.Popen(['xclip', '-selection', 'c'], stdin=subprocess.PIPE)
        p.communicate(input=data.encode("utf-8"))
