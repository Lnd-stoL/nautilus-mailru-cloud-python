
# -*- coding: utf-8 -*-
__version__ = "0.1"

#-----------------------------------------------------------------------------------------------------------------------
# tunables

ENABLE_EXPERIMENTAL = False

PYMAILCLOUD_PATH   = '../PyMailCloud/'
CONFIG_PATH        = '/.config/Mail.Ru/Mail.Ru_Cloud-NautilusExtension.conf'
MAILRU_CONFIG_PATH = '/.config/Mail.Ru/Mail.Ru_Cloud.conf'

NOTIFY_ICON    = '/usr/share/icons/hicolor/256x256/apps/mail.ru-cloud.png'
EMBLEM_ACTUAL  = 'stock_calc-accept'
EMBLEM_SHARED  = 'applications-roleplaying'
EMBLEM_SYNCING = 'stock_refresh'

FOLDER_INFO_REFRESH_RATE = 1    # in seconds
FILE_INFO_REFRESH_RATE   = 800  # in ms

LOG_PREFIX = 'nautilus-mailru-cloud: '


#-----------------------------------------------------------------------------------------------------------------------
# imports

from gi.repository import Nautilus, GObject, Gtk, Notify, Gio, GLib
from threading import Thread
import os.path as os_path

import sys
import subprocess
import ConfigParser
import urllib
import time
import Queue

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


    class LocalFileInfo:
        weblink = None
        mtime = None
        was_updated = False


    class LocalFileState:
        UNKNOWN = 0,
        IN_SYNC = 1,
        SHARED  = 2,
        ACTUAL  = 3


    class LocalDirectoryInfo:
        pass


    def __init__(self):
        self.is_configured = False
        self._cur_display_dir = ''
        self._net_ops_queue = Queue.Queue()
        self._net_ops_set = set()
        self._local_file_info_cache = {}

        Notify.init("nautilus-mail-cloud")
        self._load_mailru_config()
        self._load_config()

        if ENABLE_EXPERIMENTAL:
            net_thread = Thread(target=self._net_thread_worker)
            net_thread.daemon = False
            net_thread.start()


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
            print(LOG_PREFIX + err.message)
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
        if password_str is None: return False   # configuration cancelled by user

        self._mailru_user.password = password_str

        try:
            self._save_config()
        except (IOError, ConfigParser.Error) as err:
            print(LOG_PREFIX + err.message)
            # todo: handle error here
            return False

        return True   # configured ok


    def _ensure_pymailcloud_initialized(self):
        try: self.py_mail_cloud
        except AttributeError:
            print LOG_PREFIX + 'initializing cloud@mail.ru API connection ...'
            self.py_mail_cloud = PyMailCloud(self._mailru_user.email, self._mailru_user.password)


    def _decode_uri(self, local_path_uri):
        uri_prefix = 'file://'
        return urllib.unquote(local_path_uri[len(uri_prefix):]).decode('utf8')


    def local_path_is_in_cloud(self, local_path_uri):
        local_path = self._decode_uri(local_path_uri)
        return local_path.startswith(self._cloud_local_dir) and len(local_path) > len(self._cloud_local_dir)


    def to_cloud_relative_path(self, local_path_uri):
        local_path = self._decode_uri(local_path_uri)
        return local_path[len(self._cloud_local_dir):]


    def get_public_link(self, local_path_uri):
        self._ensure_pymailcloud_initialized()
        public_link = self.py_mail_cloud.get_public_link(self.to_cloud_relative_path(local_path_uri))


        if not ENABLE_EXPERIMENTAL: return public_link

        try:
            file_info = self._get_cached_fileinfo(local_path_uri)
            file_info.weblink = public_link
            file_info.was_updated = True
        except KeyError:
            pass

        return public_link


    def _net_load_folder_info(self, local_dir_uri):
        cloud_rel_dir = self.to_cloud_relative_path(local_dir_uri + '/')

        self._ensure_pymailcloud_initialized()
        print 'net: getting folder content for ', cloud_rel_dir, '\n'
        folder_info_raw = self.py_mail_cloud.get_folder_contents(cloud_rel_dir)
        print 'net: ready', '\n'

        for entry in folder_info_raw['body']['list']:
            if entry['kind'] == 'file':

                try:
                    old_file_info = self._local_file_info_cache[entry['home']]
                except KeyError:
                    old_file_info = MailCloudClient.LocalFileInfo

                file_info = MailCloudClient.LocalFileInfo()
                file_info.mtime = int(entry['mtime'])
                if 'weblink' in entry:
                    file_info.weblink = entry['weblink']

                file_info.was_updated = old_file_info.mtime != file_info.mtime or \
                                        old_file_info.weblink != file_info.weblink
                self._local_file_info_cache[entry['home']] = file_info

        dir_info = MailCloudClient.LocalDirectoryInfo()
        print 'saving', cloud_rel_dir
        self._local_file_info_cache[cloud_rel_dir] = dir_info


    def get_local_file_state(self, path_uri):
        cloud_rel_path = self.to_cloud_relative_path(path_uri)
        local_file_path = self._decode_uri(path_uri)

        try:
            file_info = self._local_file_info_cache[cloud_rel_path]
        except KeyError:
            cloud_rel_dir = self.to_cloud_relative_path(os_path.dirname(path_uri) + '/')
            print 'asking', cloud_rel_dir
            if cloud_rel_dir in self._local_file_info_cache:
                return MailCloudClient.LocalFileState.IN_SYNC    # it seems cloud knows nothing about this file yet
            else:
                print "unknown"
                return MailCloudClient.LocalFileState.UNKNOWN    # no info about this file

        try:
            if file_info.mtime == int(os_path.getmtime(local_file_path)):                         # test if outdated copy
                if not file_info.weblink is None: return MailCloudClient.LocalFileState.SHARED    # has public link or not
                else:                             return MailCloudClient.LocalFileState.ACTUAL
            else: return MailCloudClient.LocalFileState.IN_SYNC

        except OSError:                                                        # strange issue with deleted files
            return MailCloudClient.LocalFileState.UNKNOWN                      # being asked for even after removing


    def _net_thread_worker(self):
        while True:
            item = self._net_ops_queue.get()
            self._net_load_folder_info(item)
            self._net_ops_set.remove(item)
            self._net_ops_queue.task_done()


    def change_display_dir(self, local_path_uri):
        local_path = self._decode_uri(local_path_uri)
        if self._cur_display_dir != local_path:
            self._cur_display_dir = local_path
            self.shedule_folder_info_update(local_path_uri)


    def shedule_folder_info_update(self, local_dir_uri):
        if local_dir_uri in self._net_ops_set: return
        self._net_ops_set.add(local_dir_uri)
        self._net_ops_queue.put(local_dir_uri)


    def _get_cached_fileinfo(self, local_path_uri):
        return self._local_file_info_cache[self.to_cloud_relative_path(local_path_uri)]


    def was_file_info_updated(self, local_path_uri):
        try:
            file_info = self._get_cached_fileinfo(local_path_uri)
            if file_info.was_updated:
                file_info.was_updated = False
                return True
            return False

        except KeyError:
            rel_dir_path = self.to_cloud_relative_path(os_path.dirname(local_path_uri) + '/')
            if rel_dir_path in self._local_file_info_cache: return True
            return False


    def file_has_public_link(self, local_path_uri):
        try:
            file_info = self._get_cached_fileinfo(local_path_uri)
            return file_info.weblink is not None

        except KeyError:
            return False


    def get_file_weblink(self, local_path_uri):
        try:
            file_info = self._get_cached_fileinfo(local_path_uri)
            return file_info.weblink

        except KeyError:
            return None


    def remove_file_public_link(self, local_path_uri):
        try:
            file_info = self._get_cached_fileinfo(local_path_uri)
            weblink = file_info.weblink

            self._ensure_pymailcloud_initialized()
            self.py_mail_cloud.remove_public_link(weblink)

            file_info.weblink = None
            file_info.was_updated = True

        except KeyError:
            pass


#-----------------------------------------------------------------------------------------------------------------------
# nautilus extension class

class MailRuCloudExtension(GObject.GObject, Nautilus.MenuProvider, Nautilus.InfoProvider):

    def __init__(self):
        self.emblems = { MailCloudClient.LocalFileState.ACTUAL  : EMBLEM_ACTUAL,
                         MailCloudClient.LocalFileState.IN_SYNC : EMBLEM_SYNCING,
                         MailCloudClient.LocalFileState.SHARED  : EMBLEM_SHARED,
                         MailCloudClient.LocalFileState.UNKNOWN : ''}
        try:
            self.mailru_client = MailCloudClient()
        except MailCloudClientError.CloudNotInstalledError as err:
            print(LOG_PREFIX + err)
            ErrorDialog('Unable to initialize Cloud@MailRu extension: ' + err.message).show()

        print LOG_PREFIX + 'Cloud@Mail.ru extension ver.' +  __version__ + ' initialized'

    #--------------------------------------------- extensions interface ------------------------------------------------

    def get_background_items(self, window, files):
        return []


    def get_file_items(self, window, files):
        try: self.mailru_client
        except AttributeError: return []  # extensions was not correctly itialized

        if len(files) != 1 or not self.mailru_client.local_path_is_in_cloud(files[0].get_uri()):
            return []    # nothing to do with multiple selected files or outside mail.ru cloud directory
        file = files[0]

        if file.get_uri_scheme() != 'file':
            return []    # unsupported uri scheme

        top_mailru_item = Nautilus.MenuItem(name="MailRuCloudExtension::TopMenu", label="Cloud@Mail.ru")
        mailru_submenu = Nautilus.Menu()
        top_mailru_item.set_submenu(mailru_submenu)

        get_public_link_item = Nautilus.MenuItem(
            name="MailRuCloudExtension::GetPublicLink",
            label="Copy public link to '%s'" % file.get_name()
        )
        get_public_link_item.connect('activate', self._on_menu_get_public_link, file)
        mailru_submenu.append_item(get_public_link_item)

        if ENABLE_EXPERIMENTAL:    # also experimental
            if self.mailru_client.file_has_public_link(file.get_uri()):
                remove_public_link_item = Nautilus.MenuItem(
                    name="MailRuCloudExtension::RemovePublicLink",
                    label="Remove public link to '%s'" % file.get_name()
                )
                remove_public_link_item.connect('activate', self._on_menu_remove_public_link, file)
                mailru_submenu.append_item(remove_public_link_item)

        return [top_mailru_item]


    def update_file_info(self, file):
        if not ENABLE_EXPERIMENTAL: return    # file status icons are not stable right now

        try: self.mailru_client
        except AttributeError: return  # extensions was not correctly itialized

        if file.get_uri_scheme() != 'file':
            return    # unsupported uri scheme

        if not self.mailru_client.local_path_is_in_cloud(file.get_uri()):
            return    # no emblems outside cloud dir

        if not file.is_directory():
            # print 'getting ', file.get_uri()    # debug printing
            self.mailru_client.change_display_dir(os_path.dirname(file.get_uri()))
            emblem = self.emblems[self.mailru_client.get_local_file_state(file.get_uri())]
            file.add_emblem(emblem)
            GObject.timeout_add(FILE_INFO_REFRESH_RATE, self._invalidate_info_async, file)

    #--------------------------------------------------- handlers ------------------------------------------------------

    def _invalidate_info_async(self, file):
        self.mailru_client.shedule_folder_info_update(os_path.dirname(file.get_uri()))
        if self.mailru_client.was_file_info_updated(file.get_uri()):
            print "updating ... " + file.get_uri()
            file.invalidate_extension_info()
            return False
        return True


    def _on_menu_remove_public_link(self, menu, file):
        if not self.mailru_client.is_configured:
            if not self.mailru_client.configure_with_gui():
                return  # the user refused configuration

        notification_text = 'Could not remove public link'
        try:
            public_url = self.mailru_client.remove_file_public_link(file.get_uri())
            notification_text = 'Public link removed successfully'

        except PyMailCloudError.AuthError:
            ErrorDialog('Mail.Ru autentification failed. Maybe password is incorrect.').show()
            if not self.mailru_client.configure_with_gui(): return

        except Exception as err:
            print(LOG_PREFIX + 'error while removing public link: ' + err)

        notification = Notify.Notification.new("Cloud@Mail.ru", notification_text, NOTIFY_ICON)
        notification.show()


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
            if not self.mailru_client.configure_with_gui(): return

        except Exception as err:
            print(LOG_PREFIX + 'error while getting public link: ' + err.message)

        notification = Notify.Notification.new("Cloud@Mail.ru", notification_text, NOTIFY_ICON)
        notification.show()


    def _to_clipboard(self, data):
        try:
            proc = subprocess.Popen(['xclip', '-selection', 'c'], stdin=subprocess.PIPE)
        except OSError as err:
            ErrorDialog('Failed to run xclip command. Maybe xclip is not installed? (' + err.message + ')').show();
            raise err

        try:
            outs, errs = proc.communicate(input=data.encode("utf-8"))
        except TimeoutExpired as err:
            proc.kill()
            ErrorDialog('Failed to communicate to xclip due to timeout. (' + err.message + ')').show();
            raise err
