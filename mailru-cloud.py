
from gi.repository import Nautilus, GObject
import urllib
import lib_nautilus_mailru_cloud as lib_nmrc


class MailRuCloudExtension(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        pass


    def menu_get_public_link(self, menu, file):
        #print "menu_activate_cb",file
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
            label="Mail.Ru Cloud"
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
