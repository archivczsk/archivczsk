#!/bin/bash

D=$(pushd $(dirname $0) &> /dev/null; pwd; popd &> /dev/null)

if [ $# != 1 ]; then
	echo "Usage: $0 <enigma2 box hostname>"
	exit 1
fi

E2_HOST=$1

echo "creating ipk..."
${D}/build_ipk.sh test
IPK_PATH=$(find ${D} -maxdepth 1 -mmin 1 -name "*.ipk")
IPK_NAME=$(basename $IPK_PATH)

echo "uploading ipk to $E2_HOST..."
scp $IPK_NAME $E2_HOST:/tmp

echo "installing archivCZSK on $E2_HOST"
ssh $E2_HOST << EOFSSH
opkg --force-reinstall --force-downgrade install /tmp/$IPK_NAME
rm /tmp/$IPK_NAME
curl -m2 'http://127.0.0.1/api/powerstate?newstate=3'
EOFSSH

echo "restarting enigma2"
