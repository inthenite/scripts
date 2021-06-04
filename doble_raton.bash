#!/bin/bash
#Activamos el doble ratón
cuantos=$(xinput | grep pointer | grep slave |wc -l)
if [ "$cuantos" -lt 3 ] ;
then
  echo "No hay suficientes ratones"
  exit 2
else
  #Me quedo con el último ratón
  cual=$(xinput | grep pointer | grep slave | cut -d "=" -f 2 | awk '{print $1}'| tail -1)
  xinput create-master raton2
  xinput reattach $cual "raton2 pointer"
fi


