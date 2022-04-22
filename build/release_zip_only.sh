#!/bin/bash

version_cmp()
{
    [ "$1" = "`echo -e "$1\n$2" | sort -V | head -n1`" ]
}

ROOT_DIR=$(pushd $(dirname $0) &> /dev/null; cd ..; pwd; popd &> /dev/null)
VER=`grep version ${ROOT_DIR}/src/version.py | cut -d \" -f2`

if [ -z `echo $VER | grep '^[0-9]\+\.[0-9]\+\.[0-9]\+$'` ] ; then
	echo "Version in wrong format - must be x.y.z eg. 1.4.9"
	exit 1
fi

RELEASED_VER=`grep -v "?xml" ${ROOT_DIR}/build/plugin/update/app.xml | grep version | cut -d \" -f2`

if [ "$VER" = "$RELEASED_VER" ] ; then
	echo "Version $VER already released"
	exit 1
elif version_cmp "$VER" "$RELEASED_VER" ; then
	echo "Version $VER lower then latest released (${RELEASED_VER})"
	exit 1
fi

echo "Creating zip update version $VER for release"

TMP_DIR=$(pushd $(dirname $0) &> /dev/null; cd tmp; pwd; popd &> /dev/null)
cd $ROOT_DIR

rm -rf $TMP_DIR/archivCZSK/
sed -i "s/version = \".*\"/version = \"$VER\"/g" src/version.py
cp -a src/. $TMP_DIR/archivCZSK/
mkdir $TMP_DIR/archivCZSK/locale
mkdir $TMP_DIR/archivCZSK/locale/sk
mkdir $TMP_DIR/archivCZSK/locale/cs
mkdir $TMP_DIR/archivCZSK/locale/cs/LC_MESSAGES
mkdir $TMP_DIR/archivCZSK/locale/sk/LC_MESSAGES
msgfmt locale/sk.po -o $TMP_DIR/archivCZSK/locale/sk/LC_MESSAGES/archivCZSK.mo
msgfmt locale/cs.po -o $TMP_DIR/archivCZSK/locale/cs/LC_MESSAGES/archivCZSK.mo

cd $TMP_DIR
zip -FS -q -r $ROOT_DIR/build/plugin/update/version/archivczsk-$VER.zip archivCZSK -x "*.py[oc] *.sw[onp]" -x "*converter/*" -x "*Makefile.am" -x "*categories.xml" -x "*.gitignore"
rm -rf archivCZSK/

cd $ROOT_DIR
cp src/changelog.txt ${ROOT_DIR}/build/plugin/update/version/changelog-$VER.txt
sed -i "s/version=\".*\">/version=\"$VER\">/g" ${ROOT_DIR}/build/plugin/update/app.xml

echo " "
echo "****************************************************************"
echo "**** ZIP & changelog create to build/plugin/update/version/ ****"
echo "**** Please check this file: build/plugin/update/app.xml    ****"
echo "****                         src/version.py                 ****"
echo "****************************************************************"
echo " "
