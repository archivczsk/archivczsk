#!/bin/sh

BASE_URL=https://raw.githubusercontent.com/archivczsk/archivczsk/main

get_last_ipk_name()
{
	output=`curl -s --insecure $BASE_URL/build/ipk/latest.xml`
	if [ "$output" = "" ] ; then
		echo "Nepodarilo sa stiahnut XML subor s informaciami o poslednej dostupnej verzii"
		exit 1
	fi

	ver=
	date=
	start_parsing=0
	for line in $output ; do
		key=`echo $line | cut -d = -f 1`
		case $key in
			(id)
				start_parsing=1
			;;
			(version)
				if [ $start_parsing = 1 ] ; then
					ver=`echo $line | cut -d '=' -f 2 | cut -d \" -f 2`
				fi
			;;
			(date)
				if [ $start_parsing = 1 ] ; then
					date=`echo $line | cut -d '=' -f 2 | cut -d \" -f 2`
				fi
			;;
		esac
	done

	if [ "$ver" != "" ] && [ "$date" != "" ] ; then
		echo "archivczsk_${ver}-${date}"
	else
		echo "Nepodarilo sa zistit meno aktualizacneho IPK suboru"
		exit 1
	fi
}

if [ -e /usr/bin/dpkg ] ; then
	pkg_type='deb'
else
	pkg_type='ipk'
fi

echo "Stahujem informacie o poslednej dostupnej verzii ..."
ipk_name=`get_last_ipk_name`
local_ipk_name=/tmp/${ipk_name}.${pkg_type}

echo "Stahujem instalacny IPK balik ..."
curl -s --insecure -o ${local_ipk_name} $BASE_URL/build/ipk/${ipk_name}.ipk

if [ ! -e ${local_ipk_name} ] ; then
	echo "Nepodarilo sa stiahnut instalacny IPK balik ..."
	exit 1
fi

echo "Instalujem archivczsk zo suboru ${local_ipk_name} ..."
if [ "${pkg_type}" = "deb" ] ; then
	dpkg --install ${local_ipk_name}
else
	opkg install --force-reinstall ${local_ipk_name}
fi

if [ $? != 0 ] ; then
	echo "Instalacia skoncila s chybou. Skontrolujte vypisy z balickovacieho systemu."
else
	if [ -e /usr/bin/systemctl ] ; then
		echo "Instalacia uspesna, restartujem graficke rozhranie pomocou systemctl ..."
		systemctl stop enigma2
		sleep 1
		systemctl start enigma2
	else
		echo "Instalacia uspesna, restartujem graficke rozhranie pomocou Openwebif ..."
		curl -s 'http://127.0.0.1/api/powerstate?newstate=3'
	fi
fi

rm ${local_ipk_name}
