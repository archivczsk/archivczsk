#!/bin/bash

PLUGINPATH=/usr/lib/enigma2/python/Plugins/Extensions/archivCZSK

if [ "$1" = "test" ] ; then
	COMMITED_ONLY="no"
else
	COMMITED_ONLY="yes"
fi

# prepare directories

# ROOT_DIR -> root git directory
# TMP_DIR -> temp directory where all the packaging "magic" will be done
ROOT_DIR=$(pushd $(dirname $0) &> /dev/null; cd ..; pwd; popd &> /dev/null)
TMP_DIR=$(pushd $(dirname $0) &> /dev/null; cd tmp; pwd; popd &> /dev/null)

# extract version from version.py file
VER=`grep version ${ROOT_DIR}/src/version.py | cut -d \" -f2`

if [ -z `echo $VER | grep -E '^([0-9]{1,}\.)+[0-9]{1,}(~{1}[0-9]{1,})?$'` ] ; then
	echo "Version in wrong format - must be x.y.z eg. 1.4.9"
	exit 1
fi

# S -> source directory where source files used to build ipk will be copied
# P -> package dir - it is root dir of in package files
S=${TMP_DIR}/ipkg.src.$$
P=${TMP_DIR}/ipkg.tmp.$$

pushd ${ROOT_DIR} &> /dev/null

# extract latest commit date from git and build package name without extension
GITDATE=$(git log -1 --format="%ci" | awk -F" " '{ print $1 }' | tr -d "-")
VER_WITH_DATE=${VER}-${GITDATE}
PKG=${ROOT_DIR}/build/archivczsk_${VER_WITH_DATE}

rm -rf ${TMP_DIR}/ipkg.src*
rm -rf ${TMP_DIR}/ipkg.tmp*

mkdir -p ${P}
mkdir -p ${P}/DEBIAN
mkdir -p ${S}

# build package from HEAD revision or from what's on disc?
if [ "$COMMITED_ONLY" = "yes" ] ; then
	git archive --format=tar HEAD | (cd ${S} && tar xf -)
else
	cp -rP src locale -t ${S}
	mkdir -p ${S}/build/control
	cp build/control/* ${S}/build/control
fi

popd &> /dev/null

# set build version in control file
E_VER=$(printf '%s\n' "$VER" | sed -e 's/[\/&]/\\&/g')
cp ${S}/build/control/* ${P}/DEBIAN/
sed -i "s/Version:\ .*/Version:\ $E_VER/" ${P}/DEBIAN/control

# prepare in package directory structure
chmod 755 ${P}/DEBIAN/preinst
chmod 755 ${P}/DEBIAN/postinst
chmod 755 ${P}/DEBIAN/prerm
chmod 755 ${P}/DEBIAN/postrm

mkdir -p ${P}${PLUGINPATH}
mkdir -p ${P}${PLUGINPATH}/locale/cs/LC_MESSAGES/
mkdir -p ${P}${PLUGINPATH}/locale/sk/LC_MESSAGES/
mkdir -p ${P}/usr/lib/enigma2/python/Components/Converter/

# copy files into new direcotry structure
cp -rp ${S}/src/* ${P}${PLUGINPATH}
cp -p ${S}/src/converter/* ${P}/usr/lib/enigma2/python/Components/Converter/

echo "creating locales"
msgfmt ${S}/locale/cs.po -o ${P}${PLUGINPATH}/locale/cs/LC_MESSAGES/archivCZSK.mo
msgfmt ${S}/locale/sk.po -o ${P}${PLUGINPATH}/locale/sk/LC_MESSAGES/archivCZSK.mo

#echo "compiling to optimized python bytecode"
#python -O -m compileall ${P} 1> /dev/null

echo "cleanup of unnecessary files"
find ${P} -type f -name ".gitignore" -exec rm {} \;
rm -rf ${P}${PLUGINPATH}/converter
rm -rf ${P}${PLUGINPATH}/resources/data/*

# exec dpkg-deb to create fresh new deb package and create ipk from it
dpkg-deb --root-owner-group -Zgzip -b ${P} ${PKG}.deb
mv ${PKG}.deb ${PKG}.ipk

# some cleanup
rm -rf ${P}
rm -rf ${S}
