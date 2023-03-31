#!/bin/bash

PLUGINPATH=/usr/lib/enigma2/python/Plugins/Extensions/archivCZSK

if [ "$1" = "test" ] ; then
	COMMITED_ONLY="no"
else
	COMMITED_ONLY="yes"
fi

# if ADDONS_COMMIT is not set, then no addons will be packed to ipk/deb
# ADDONS_COMMIT="a6336a067dec9ff441e1779496c27496213c9fa2"

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
# DP -> dependencies dir - directory where dependencies will be stored
S=${TMP_DIR}/ipkg.src.$$
P=${TMP_DIR}/ipkg.tmp.$$
DP=${TMP_DIR}/ipkg.deps

P27="https://www.python.org/ftp/python/2.7.5/Python-2.7.5.tgz"

pushd ${ROOT_DIR} &> /dev/null

# extract latest commit date from git and build package name without extension
GITDATE=$(git log -1 --format="%ci" | awk -F" " '{ print $1 }' | tr -d "-")
VER_WITH_DATE=${VER}-${GITDATE}
PKG=${ROOT_DIR}/build/archivczsk_${VER_WITH_DATE}

rm -rf ${TMP_DIR}/ipkg.src*
rm -rf ${TMP_DIR}/ipkg.tmp*

mkdir -p ${P}
mkdir -p ${P}/DEBIAN
mkdir -p ${DP}
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

# prepare python dependencies - do we need that???
if [ -d ${DP}/Python-2.7 ]; then
	echo "python packages are already downloaded"
else
	echo "downloading neccesary python packages..."
	curl $P27 -s -o ${DP}/Python-2.7.5.tgz
	tar -C ${DP} -xzf ${DP}/Python-2.7.5.tgz
	mv ${DP}/Python-2.7.5 ${DP}/Python-2.7
fi

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
touch ${P}${PLUGINPATH}/firsttime

echo "creating locales"
msgfmt ${S}/locale/cs.po -o ${P}${PLUGINPATH}/locale/cs/LC_MESSAGES/archivCZSK.mo
msgfmt ${S}/locale/sk.po -o ${P}${PLUGINPATH}/locale/sk/LC_MESSAGES/archivCZSK.mo

#echo "compiling to optimized python bytecode"
#python -O -m compileall ${P} 1> /dev/null

echo "cleanup of unnecessary files"
find ${P} -type f -name ".gitignore" -exec rm {} \;
rm -rf ${P}${PLUGINPATH}/converter
rm -rf ${P}${PLUGINPATH}/resources/data/*

# if we have ADDONS_COMMIT, then download latest addons and add them to package
if ! [ -z "${ADDONS_COMMIT}" ]; then
	if [ -e /usr/bin/python3 ] ; then
		py_cmd=python3
	else
		py_cmd=python
	fi

	$py_cmd ${S}/build/plugin/src/script/getaddons.py addons ${P} $ADDONS_COMMIT
fi

# prepare and add dependencies
mkdir -p ${P}/tmp/archivczsk
mkdir -p ${P}/tmp/archivczsk/python2.7

cp -p ${DP}/Python-2.7/Lib/encodings/utf_8.py ${P}/tmp/archivczsk/python2.7/utf_8.py
cp -p ${DP}/Python-2.7/Lib/encodings/cp1251.py ${P}/tmp/archivczsk/python2.7/cp1251.py
cp -p ${DP}/Python-2.7/Lib/encodings/cp1252.py ${P}/tmp/archivczsk/python2.7/cp1252.py
cp -p ${DP}/Python-2.7/Lib/encodings/cp1253.py ${P}/tmp/archivczsk/python2.7/cp1253.py
cp -p ${DP}/Python-2.7/Lib/encodings/cp1254.py ${P}/tmp/archivczsk/python2.7/cp1254.py
cp -p ${DP}/Python-2.7/Lib/encodings/cp1256.py ${P}/tmp/archivczsk/python2.7/cp1256.py
cp -p ${DP}/Python-2.7/Lib/encodings/iso8859_6.py ${P}/tmp/archivczsk/python2.7/iso8859_6.py
cp -p ${DP}/Python-2.7/Lib/encodings/iso8859_7.py ${P}/tmp/archivczsk/python2.7/iso8859_7.py
cp -p ${DP}/Python-2.7/Lib/encodings/iso8859_9.py ${P}/tmp/archivczsk/python2.7/iso8859_9.py
cp -p ${DP}/Python-2.7/Lib/encodings/iso8859_15.py ${P}/tmp/archivczsk/python2.7/iso8859_15.py

cp -p ${DP}/Python-2.7/Lib/encodings/hex_codec.py ${P}/tmp/archivczsk/python2.7/hex_codec.py
cp -p ${DP}/Python-2.7/Lib/encodings/string_escape.py ${P}/tmp/archivczsk/python2.7/string_escape.py
cp -p ${DP}/Python-2.7/Lib/encodings/latin_1.py ${P}/tmp/archivczsk/python2.7/latin_1.py
cp -p ${DP}/Python-2.7/Lib/encodings/utf_16.py ${P}/tmp/archivczsk/python2.7/utf_16.py
cp -p ${DP}/Python-2.7/Lib/encodings/idna.py ${P}/tmp/archivczsk/python2.7/idna.py
cp -p ${DP}/Python-2.7/Lib/encodings/iso8859_2.py ${P}/tmp/archivczsk/python2.7/iso8859_2.py
cp -p ${DP}/Python-2.7/Lib/encodings/cp1250.py ${P}/tmp/archivczsk/python2.7/cp1250.py
cp -p ${DP}/Python-2.7/Lib/decimal.py ${P}/tmp/archivczsk/python2.7/decimal.py
cp -p ${DP}/Python-2.7/Lib/formatter.py ${P}/tmp/archivczsk/python2.7/formatter.py
cp -p ${DP}/Python-2.7/Lib/markupbase.py ${P}/tmp/archivczsk/python2.7/markupbase.py
cp -p ${DP}/Python-2.7/Lib/HTMLParser.py ${P}/tmp/archivczsk/python2.7/HTMLParser.py
cp -p ${DP}/Python-2.7/Lib/htmlentitydefs.py ${P}/tmp/archivczsk/python2.7/htmlentitydefs.py
cp -p ${DP}/Python-2.7/Lib/htmllib.py ${P}/tmp/archivczsk/python2.7/htmllib.py
cp -p ${DP}/Python-2.7/Lib/sgmllib.py ${P}/tmp/archivczsk/python2.7/sgmllib.py
cp -p ${DP}/Python-2.7/Lib/stringprep.py ${P}/tmp/archivczsk/python2.7/stringprep.py
cp -p ${DP}/Python-2.7/Lib/numbers.py ${P}/tmp/archivczsk/python2.7/numbers.py
cp -p ${DP}/Python-2.7/Lib/subprocess.py ${P}/tmp/archivczsk/python2.7/subprocess.py
cp -p ${DP}/Python-2.7/Lib/_LWPCookieJar.py ${P}/tmp/archivczsk/python2.7/_LWPCookieJar.py
cp -p ${DP}/Python-2.7/Lib/_MozillaCookieJar.py ${P}/tmp/archivczsk/python2.7/_MozillaCookieJar.py
cp -p ${DP}/Python-2.7/Lib/cookielib.py ${P}/tmp/archivczsk/python2.7/cookielib.py
cp -p ${DP}/Python-2.7/Lib/shutil.py ${P}/tmp/archivczsk/python2.7/shutil.py
cp -p ${DP}/Python-2.7/Lib/fnmatch.py ${P}/tmp/archivczsk/python2.7/fnmatch.py
cp -p ${DP}/Python-2.7/Lib/threading.py ${P}/tmp/archivczsk/python2.7/threading.py
cp -p ${DP}/Python-2.7/Lib/zipfile.py ${P}/tmp/archivczsk/python2.7/zipfile.py
cp -p ${DP}/Python-2.7/Lib/httplib.py ${P}/tmp/archivczsk/python2.7/httplib.py
cp -p ${DP}/Python-2.7/Lib/stat.py ${P}/tmp/archivczsk/python2.7/stat.py

# exec dpkg-deb to create fresh new deb package and create ipk from it
dpkg-deb --root-owner-group -Zgzip -b ${P} ${PKG}.deb
mv ${PKG}.deb ${PKG}.ipk

# some cleanup
rm -rf ${P}
rm -rf ${S}

#rm -rf ${DP}
