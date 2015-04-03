#! /bin/bash

EXTENSIONS_DIR="/usr/share/nautilus-python/extensions"

cp ./mailru-cloud.py $EXTENSIONS_DIR/mailru-cloud.py
cp ../PyMailCloud/PyMailCloud.py $EXTENSIONS_DIR/PyMailCloud.py

cd $EXTENSIONS_DIR
chmod 777 ./mailru-cloud.py

nautilus -q
nautilus --no-desktop 

