#!/bin/bash
# Análisis de los logs de sshd sobre los intentos de entrada
# inthenite.com

# Variables entorno
# Raiz para todos los ficheros
fcab=/tmp/$$
# Fichero con la suma de todos los logs de sshd
finicial=${fcab}.logs
# Fichero con unicamente las líneas de Failed
ffailed=${fcab}.failed
# Fichero con la lista de todos los usuarios repetidos
fuser=${fcab}.user
# Fichero con la lista de todos los usuarios únicos y la cuenta del número de veces por cada uno
fuseruni=${fcab}.useruni
# Fichero con todas las direcciones IP ordenadas y repetidas
fip=${fcab}.ip
# Fichero con las direcciones IP únicas y la cuenta del número de veces por cada una
fipuni=${fcab}.ipuni
# Fichero con las direcciones IP únicas sin cuenta de número de veces
fuip=${fcab}.uip
# Variable que nos indica si usamos o no el token de ipinfo.io
usando_token="no"
# Variable para hacer las peticiones con el token
token=""
# Directorio para guardar los ficheros ipinfo
dirip=/tmp/ipinfo
# Fichero con toda la info de ipinfo de todas las IPs
fipinfo=${fcab}.ipinfo
# Fichero con todos los ASN únicos y ordenados por número de veces
fasnuni=${fcab}.asnuni
# Fichero con los paises
fpaises=${fcab}.paises

# 1 Analizar parámetros de entrada
# Se revisa el token de ipinfo
# Se comprueba si se pide ayuda
if [ $# -gt 1 ] ;
then
    echo "Uso: $0 [token ipinfo.io | --help ]"
    exit 1
elif [ $# -eq 0 ] ;
then
    echo "Iniciando análisis sin token ipinfo, máximo soportado 1000 IPs"
else
    case "$1" in
        *hel* )  echo "Ayuda"
                 exit 0
                 ;;
        *      ) echo "Comprobando el token"
                 error=$(curl -s https://ipinfo.io/192.168.1.1?token=$1 2> /dev/null | grep error | wc -l)
		 if [ $error -gt 0 ] ;
                 then
                     echo "$0: error en el token"
                     exit 1
                 else
                     usando_token="si"
                     token="?token=$1"
                     echo "Token ipinfo ok"
                 fi
                 ;;
    esac 
fi
echo ""

# 2 Buscar ficheros de log y generar fichero para análisis
if [ -f /var/log/secure ] ;
then
    # Fichero de log es secure
    log_ssh=secure
else
    if [ -f /var/log/auth.log ] ;
    then
        # Fichero de log es auth.log
        log_ssh=auth.log
    else
        echo "$0: No se encuentran ni secure ni auth.log"
        exit 1
    fi
fi

echo "Inicio del análisis con el fichero de log $log_ssh"
for fichero in  $(ls /var/log/${log_ssh}*); 
do
    echo "Usando fichero: $fichero"
    if [[ "${fichero: -1}" == "z" || "${fichero: -1}" == "Z" ]] ;
    then
        zcat $fichero >> $finicial
    else
        cat $fichero >> $finicial
    fi
done
echo " "

# 3 Analisis 
# 3.1 Análisis número de intentos
cat $finicial | grep Failed | grep ssh2$ > $ffailed
res_31=$( cat $ffailed | wc -l )
echo "Número de intentos de entrada: $res_31"
# 3.2 Análisis de los usuarios
cat $ffailed | sed "s/invalid user //g" | awk '{split($0,f,"for "); print f[2]}' | cut -d " " -f 1 | sort > $fuser
cat $fuser | uniq -c | sort -n > $fuseruni
res_32=$( cat $fuseruni | wc -l )
echo "Número de usuarios diferentes que han intentado entrar: $res_32"
echo "Fichero con los usuarios y número de intentos: $fuseruni"
echo "Top #5 de usuarios"
tail -5 $fuseruni
echo ""

# 4 Análisis IPs
cat $ffailed | awk '{split($0,f,"from "); print f[2]}' |cut -d " " -f 1 | sort > $fip
cat $fip | uniq -c | sort -n > $fipuni
res_41=$( cat $fipuni | wc -l )
echo "Número de direcciones ip diferentess: $res_41"
echo "Fichero con las direcciones IP y número de intentos: $fipuni"
cat $fip | uniq > $fuip
echo "Top #5 de direcciones IP"
tail -5  $fipuni
echo ""

# 5 Descarga de datos de ipinfo.io
if [[ $res_41 -eq 0 ]] ;
then
    echo  "No hay direcciones que analizar"
    exit 5
fi

if [[ "$usando_token" == "no" && $res_41 -gt 1000 ]] ;
then
    echo "Error: número máximo de direcciones ip alcanzadas sin token"
    echo "Pide un token gratuito en https://ipinfo.io/signup"
    exit 5
fi

mkdir -p $dirip
if [ ! -d $dirip ] ;
then
    echo "$0: error al crear el directorio $dirip"
    exit 6
fi

#Generamos un fichero .ipinfo por cada
cuantos=0
for ip in $(cat $fuip)
do
    if [ ! -f $dirip/${ip}.ipinfo ] ;
    then
        curl -s https://ipinfo.io/$ip$token > $dirip/${ip}.ipinfo 
    fi
    cat $dirip/${ip}.ipinfo >> $fipinfo
    cuantos=$(($cuantos + 1))
    echo -ne "$cuantos de $res_41 \033[0K\r"
done

cat $fipinfo  | grep \"org\" | cut -d: -f2 | sort | uniq -c | sort -n > $fasnuni
res_51=$(cat $fasnuni | wc -l)
echo "Número de ASN diferentess: $res_51"
echo "Fichero con las ASN y número de IPs por ASN: $fasnuni"
echo "Top #5 de ASN"
tail -5 $fasnuni
echo ""

#6 Otros análisis
# Nombre de host
res_42=$(grep \"hostname\" $fipinfo | wc -l)
echo "De las $res_41 direcciones IP sólo $res_42 tienen nombre de host"
# Paises
cat $fipinfo | grep country\": | cut -d: -f2 | sed "s/,//g" | sort | uniq -c| sort -n > $fpaises
res_43=$(cat $fpaises  | wc -l)
echo "Número total de paises diferentes $res_43"
echo "Fichero paises $fpaises"
echo "Top #5 de paises"
tail -5 $fpaises
echo ""


# 7 Ficheros utilizados
