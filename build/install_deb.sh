#!/bin/bash

D=$(pushd $(dirname $0) &> /dev/null; pwd; popd &> /dev/null)

if [ $# != 1 ]; then
	echo "Usage: $0 <enigma2 box hostname>"
	exit 1
fi

E2_HOST=$1

echo "creating deb..."
${D}/build_ipk.sh test
IPK_PATH=$(find ${D} -maxdepth 1 -mmin 1 -name "*.ipk")
IPK_NAME=$(basename $IPK_PATH)
DEB_NAME=$(basename $IPK_PATH .ipk).deb

echo "uploading deb to $E2_HOST..."
scp -O $IPK_NAME $E2_HOST:/tmp/${DEB_NAME}

echo "installing archivCZSK on $E2_HOST"
ssh $E2_HOST << EOFSSH
dpkg -i /tmp/$DEB_NAME
rm /tmp/$DEB_NAME
echo -n "newstate=3&sessionid=" > /tmp/.e2s
curl -s -X POST "http://127.0.0.1/web/session" | grep e2sessionid|sed 's/e2sessionid\|<\|>\|\///g' >> /tmp/.e2s
cat /tmp/.e2s | xargs curl -s -X POST "http://127.0.0.1/web/powerstate" -d
rm /tmp/.e2s
EOFSSH

echo "restarting enigma2"
