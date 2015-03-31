
from gi.repository import Nautilus, GObject


class MailRuCloudExtension(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        pass


    def menu_activate_cb(self, menu, file):
        print "menu_activate_cb",file


    def get_file_items(self, window, files):
        if len(files) != 1:
            return
        
        file = files[0]

        item = Nautilus.MenuItem(
            name="MailRuCloudExtension::GetPublicLink",
            label="Get public link to '%s'" % file.get_name(),
            tip="Get public link to '%s'" % file.get_name()
        )
        item.connect('activate', self.menu_activate_cb, file)
        
        return [item]
