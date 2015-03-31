#! /bin/bash

rm /usr/share/nautilus-python/extensions/mailru-cloud.py
cp ./mailru-cloud.py /usr/share/nautilus-python/extensions/mailru-cloud.py
cd /usr/share/nautilus-python/extensions
chmod 777 ./mailru-cloud.py

nautilus -q
nautilus --no-desktop 

