#!/bin/bash

if [ $# != 1 ] ; then
	echo "Usage: $0 version"
	exit 1
fi

VER=${1}

if [ -z `echo $VER | grep '^[0-9]\+\.[0-9]\+\.[0-9]\+$'` ] ; then
	echo "Version in wrong format - must be x.y.z eg. 1.4.9"
	exit 1
fi

ROOT_DIR=$(pushd $(dirname $0) &> /dev/null; cd ..; pwd; popd &> /dev/null)
ACT_VER=`grep version ${ROOT_DIR}/src/version.py | cut -d \" -f 2`
sed -i "s/version = \".*\"/version = \"${VER}\"/g" ${ROOT_DIR}/src/version.py
echo "Version changed from ${ACT_VER} to ${VER}"
