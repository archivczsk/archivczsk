#!/bin/bash

version_cmp()
{
    [ "$1" = "`echo -e "$1\n$2" | sort -V | head -n1`" ]
}

ROOT_DIR=$(pushd $(dirname $0) &> /dev/null; cd ..; pwd; popd &> /dev/null)
BUILD_DIR=${ROOT_DIR}/build

if [ $# = 1 ] ; then
	VER=${1}
	FORCE="no"
elif [ $# = 2 ] ; then
	VER=${1}
	FORCE="no"
	
	if [ "$2" = "force" ] ; then
		FORCE="yes"
	fi
else
	echo "Usage: $0 version [force]"
	exit 1
fi

if [ -z `echo $VER | grep '^[0-9]\+\.[0-9]\+\.[0-9]\+$'` ] ; then
	echo "Version in wrong format - must be x.y.z eg. 1.4.9"
	exit 1
fi

cd ${BUILD_DIR}


if [ ${FORCE} = "no" ] ; then
	# get latest released version
	RELEASED_VER=`grep -v "?xml" ipk/latest.xml | grep version | cut -d \" -f2`

	if [ "$VER" = "$RELEASED_VER" ] ; then
		echo "ERROR: Version $VER already released"
		exit 1
	elif version_cmp "$VER" "$RELEASED_VER" ; then
		echo "ERROR: Version $VER lower then latest released (${RELEASED_VER})"
		exit 1
	fi
fi

ACT_VER=`grep version ${ROOT_DIR}/src/version.py | cut -d \" -f 2`
echo "Setting version to ${VER} (previous was ${ACT_VER})"
sed -i "s/version = \".*\"/version = \"${VER}\"/g" ${ROOT_DIR}/src/version.py

echo "Commiting new version to git"
git add ${ROOT_DIR}/src/version.py
git commit -m "release version ${VER}"

echo "Creating IPK package from latest commited git status ..."
./build_ipk.sh
IPK_PATH=$(find . -maxdepth 1 -mmin 1 -name "*.ipk")
IPK_NAME=$(basename $IPK_PATH)
IPK_VER=`echo ${IPK_NAME} | cut -d _ -f 2 | cut -d - -f 1`
IPK_DATE=`echo ${IPK_NAME} | cut -d - -f 2 | cut -d . -f 1`

echo "IPK with version ${IPK_VER} and date ${IPK_DATE} created"

mv ${IPK_PATH} ipk/
sed -i "s/\tversion=\".*\"/\tversion=\"$IPK_VER\"/g" ipk/latest.xml
sed -i "s/\tdate=\".*\">/\tdate=\"$IPK_DATE\">/g" ipk/latest.xml

echo "Updating release commit"
git add ipk/${IPK_NAME} ipk/latest.xml
git commit --amend -m "release version ${IPK_VER}"

echo "Version ${IPK_VER} prepared for release"
echo "Use \"git push\" to send new version to the wild world and hope for the best :-)" 
