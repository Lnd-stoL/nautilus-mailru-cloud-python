
from gi.repository import Nautilus, GObject, Gtk
import urllib
import lib_nautilus_mailru_cloud as lib_nmrc

#-----------------------------------------------------------------------------------------------------------------------

class PasswordEntryDialog(Gtk.Dialog):
    def __init__(self, *args, **kwargs):
        '''
        Creates a new EntryDialog. Takes all the arguments of the usual
        MessageDialog constructor plus one optional named argument
        "default_value" to specify the initial contents of the entry.
        '''
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


#-----------------------------------------------------------------------------------------------------------------------

class MailRuCloudExtension(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        pass


    def _initLib(self):
        if not lib_nmrc.mail_cloud is None: return True

        lib_nmrc.init()
        if lib_nmrc.mail_cloud is None:
            dlg = PasswordEntryDialog()
            pwd_str = dlg.run()
            dlg.destroy()
            if pwd_str is None: return
            lib_nmrc.save_config(pwd_str)
            lib_nmrc.init()

        return not lib_nmrc.mail_cloud is None


    def menu_get_public_link(self, menu, file):
        if not self._initLib(): return

        path = urllib.unquote(file.get_uri().replace('file://', '')).decode('utf8')
        print path
        lib_nmrc.copy_public_link(path)


    def get_file_items(self, window, files):
        if len(files) != 1:
            return

        file = files[0]
        if file.get_uri().find(lib_nmrc.get_mailru_cloud_path()) == -1:
            return   # not in mail.ru cloud directory

        top_mailru_item = Nautilus.MenuItem(
            name="MailRuCloudExtension::TopMenu",
            label="Mail.Ru@Cloud"
        )

        mailru_submenu = Nautilus.Menu()
        top_mailru_item.set_submenu(mailru_submenu)

        public_link_item = Nautilus.MenuItem(
            name="MailRuCloudExtension::GetPublicLink",
            label="Copy public link to '%s'" % file.get_name(),
            tip="Copy public link to '%s'" % file.get_name()
        )
        public_link_item.connect('activate', self.menu_get_public_link, file)
        mailru_submenu.append_item(public_link_item)

        return [top_mailru_item]
