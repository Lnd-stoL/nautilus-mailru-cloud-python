#! /bin/bash

nautilus -q

rm /usr/share/nautilus-python/extensions/mailru-cloud.py
rm /usr/share/nautilus-python/extensions/mailru-cloud.pyc
cp ./mailru-cloud.py /usr/share/nautilus-python/extensions/mailru-cloud.py
cp ../PyMailCloud/PyMailCloud.py /usr/share/nautilus-python/extensions/PyMailCloud.py
cd /usr/share/nautilus-python/extensions
chmod 777 ./mailru-cloud.py

nautilus --no-desktop 

