
# -*- coding: utf-8 -*-
__version__ = "0.1"

#-----------------------------------------------------------------------------------------------------------------------
# tunables

PYMAILCLOUD_PATH = '../PyMailCloud/'
CONFIG_PATH = '/.config/Mail.Ru/Mail.Ru_Cloud-NautilusExtension.conf'
MAILRU_CONFIG_PATH = '/.config/Mail.Ru/Mail.Ru_Cloud.conf'

NOTIFY_ICON = '/usr/share/icons/hicolor/256x256/apps/mail.ru-cloud.png'
EMBLEM_ACTUAL  = 'stock_calc-accept'
EMBLEM_SHARED  = 'applications-roleplaying'
EMBLEM_SYNCING = 'stock_refresh'

#-----------------------------------------------------------------------------------------------------------------------
# imports

from gi.repository import Nautilus, GObject, Gtk, Notify
import os.path as os_path

import sys
import subprocess
import ConfigParser
import urllib
import json

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
        self._folder_info_cache = {}

        Notify.init("nautilus-mail-cloud")
        self._load_mailru_config()
        self._load_config()


    def _load_mailru_config(self):
        try:
            config = ConfigParser.ConfigParser()
            config.read(os_path.expanduser("~") + MAILRU_CONFIG_PATH)
        except (ConfigParser.ParsingError, IOError):
            raise MailCloudClientError.CloudNotInstalledError()

        self._mailru_user = MailCloudClient.User()
        try:
            self._mailru_user.email = config.get('General', 'email')
            self._cloud_local_dir   = config.get('General', 'folder')
        except ConfigParser.Error as err:
            raise MailCloudClientError.UnconfiguredError('invalid config format: ' + err.message)


    def _load_config(self):
        try:
            config = ConfigParser.ConfigParser()
            config.read(os_path.expanduser("~") + CONFIG_PATH)
            self._mailru_user.password = config.get('User', 'password')
            self.is_configured = True

        except (IOError, ConfigParser.Error) as err:
            print(err)
            self.is_configured = False


    def _save_config(self):
        config = ConfigParser.ConfigParser()
        config.add_section('User')
        config.set('User', 'password', self._mailru_user.password)

        with open(os_path.expanduser("~") + CONFIG_PATH, 'wb') as config_file:
            config.write(config_file)

        self.is_configured = True


    def configure_with_gui(self):
        dlg = PasswordEntryDialog()
        password_str = dlg.run()
        dlg.destroy()
        if password_str is None: return False  # configuration cancelled by user

        self._mailru_user.password = password_str

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
            self.py_mail_cloud = PyMailCloud(self._mailru_user.email, self._mailru_user.password)


    def _decode_uri(self, path_uri):
        uri_prefix = 'file://'
        return urllib.unquote(path_uri[len(uri_prefix):]).decode('utf8')


    def local_path_is_in_cloud(self, path_uri):
        local_path = self._decode_uri(path_uri)
        return local_path.startswith(self._cloud_local_dir) and len(local_path) > len(self._cloud_local_dir)


    def to_relative_path(self, path_uri):
        local_path = self._decode_uri(path_uri)
        return local_path[len(self._cloud_local_dir):]


    def get_public_link(self, path_uri):
        self._ensure_pymalicloud_initialized()
        return self.py_mail_cloud.get_public_link(self.to_relative_path(path_uri))


    def _load_folder_info(self, path):
        if path in self._folder_info_cache: return self._folder_info_cache[path]

        self._ensure_pymalicloud_initialized()
        folder_info_raw = self.py_mail_cloud.get_folder_contents(path)
        folder_info = { 'files':{}, 'folders':[] }
        folder_info_files = folder_info['files']

        for entry in folder_info_raw['body']['list']:
            if entry['kind'] == 'file':
                file_entry = { 'mtime': int(entry['mtime']) }
                if 'weblink' in entry:
                    file_entry['weblink'] = entry['weblink']
                folder_info_files[entry['home']] = file_entry

        self._folder_info_cache[path] = folder_info
        return folder_info


    FILE_STATE_INSYNC  = 1
    FILE_STATE_ACTUAL  = 2
    FILE_STATE_SHARED  = 3
    FILE_STATE_UNKNOWN = 4

    def local_file_state(self, path_uri):
        local_file_path = self._decode_uri(path_uri)
        if os_path.isdir(local_file_path): return self.FILE_STATE_UNKNOWN

        rel_file_path = self.to_relative_path(path_uri)
        rel_dir_name = os_path.dirname(rel_file_path)
        folder_info = self._load_folder_info(rel_dir_name)

        if not rel_file_path in folder_info['files']: return self.FILE_STATE_INSYNC
        file_info = folder_info['files'][rel_file_path]
        if file_info['mtime'] == int(os_path.getmtime(local_file_path)):
            if 'weblink' in file_info: return self.FILE_STATE_SHARED
            else:                      return self.FILE_STATE_ACTUAL
        else: return self.FILE_STATE_INSYNC


    def invalidate_folder_info(self, path_uri):
        local_file_path = self._decode_uri(path_uri)
        if not os_path.isdir(local_file_path): return

        rel_file_path = self.to_relative_path(path_uri)
        rel_dir_name = os_path.dirname(rel_file_path)
        del self._folder_info_cache[rel_dir_name]


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
        public_link_item.connect('activate', self._on_menu_get_public_link, file)
        mailru_submenu.append_item(public_link_item)

        return [top_mailru_item]


    def update_file_info(self, file):
        try: self.mailru_client
        except AttributeError: return # extensions is unitialized

        if file.get_uri_scheme() != 'file':
            return

        if not self.mailru_client.local_path_is_in_cloud(file.get_uri()):
            return  # no emblems outside cloud dir

        GObject.timeout_add_seconds(0, self._update_file_info_async, file, False)

    #--------------------------------------------------- handlers ------------------------------------------------------

    def _update_file_info_async(self, file, reload):
        emblemes = { self.mailru_client.FILE_STATE_ACTUAL  : EMBLEM_ACTUAL,
                     self.mailru_client.FILE_STATE_INSYNC  : EMBLEM_SYNCING,
                     self.mailru_client.FILE_STATE_SHARED  : EMBLEM_SHARED,
                     self.mailru_client.FILE_STATE_UNKNOWN : ''}

        self.mailru_client
        file.add_emblem(emblemes[self.mailru_client.local_file_state(file.get_uri())])

        if reload: self.mailru_client.invalidate_folder_info(file.get_uri())
        GObject.timeout_add_seconds(5, self._update_file_info_async, file, True)
        return False


    def _on_menu_get_public_link(self, menu, file):
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
