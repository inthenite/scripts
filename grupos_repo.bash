#!/bin/bash
#Crea los ficheros para un repositorio yum

#Creación de los ficheros xml para grupos
if [ ! -d repogroupxml ] ;
then
  mkdir repogroupxml
  if [ $? -gt 0 ] ;
  then
   echo "$0: error al crear el directorio de ficheros xml para grupos"
  fi
fi

#Extracción de los nombres de los ficheros rpm para meterlos en los grupos
for directorios in $(ls)
do
 lista=""
 if [ -d $directorios ] ;
 then
   for ficheros in $directorios/*rpm
   do
     nombre=$(rpm -q -p -i $ficheros 2> /dev/null| grep ^Name | cut -d ":" -f 2)
     lista="$lista $nombre"
   done
   echo "El directorio $directorios tiene:$lista" 
   yum-groups-manager -n $directorios --id=$directorios --save=repogroupxml/$directorios.xml --mandatory $lista
 fi
done
echo "DIRECTORIOS: $directorios"

#Juntar los ficheros xml de grupos
(
head -3 repogroupxml/$directorios.xml
for xmls in repogroupxml/*xml
do
   lineas=$(cat $xmls | wc -l )
   cat $xmls | head -$(($lineas - 1)) | tail -$(($lineas - 5))
done  
tail -1 repogroupxml/$directorios.xml
) > repogroupxml/total.xml


createrepo --update -g repogroupxml/total.xml $(pwd)
