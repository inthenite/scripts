#!/usr/bin/env python3
import json
import hashlib
import base58
import requests
import sys
from datetime import datetime, timezone

from requests.sessions import SessionRedirectMixin
from bitcoinlib.encoding import pubkeyhash_to_addr_bech32

# Configuración conexión Bitcoin Core RPC
BITCOIN_RPC_URL = "http://127.0.0.1:8332/"
RPC_COOKIE_FILE = "/home/student/.bitcoin/.cookie"
user, password = None, None

def bitcoin_rpc_init():
    """ Inicialización del RPC de Bitcoin Core """
    with open(RPC_COOKIE_FILE, "r") as f:
        cookie = f.read().strip()
    user, password = cookie.split(":")
    headers = {"content-type": "application/json"}

    sesion = requests.Session()
    sesion.auth = (user, password)
    sesion.headers.update(headers)

    return sesion

def bitcoin_rpc(sesion, method, params=[]):
    """ Conexión al RPC de Bitcoin Core """

    
    payload = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params})
    r = sesion.post(BITCOIN_RPC_URL, data=payload)
    # r = requests.post(BITCOIN_RPC_URL, headers=headers, data=payload, auth=(user, password))
    r.raise_for_status()
    resp = r.json()
    if "error" in resp and resp["error"]:
        raise RuntimeError(resp["error"])
    return resp["result"]

def script_to_address(script):
    """ Convertir de formato script a direccion """
    # P2PKH
    if script[:3] == b"\x76\xa9\x14":
        h160 = script[3:23]
        return base58.b58encode_check(b"\x00" + h160).decode(),"Conv-P2PKH"
    # P2SH
    if script[:2] == b"\xa9\x14":
        h160 = script[2:22]
        return base58.b58encode_check(b"\x05" + h160).decode(),"Conv-P2SH"
    # Bech32
    if script[:2] == b"\x00\x14":
        return pubkeyhash_to_addr_bech32(script[2:], prefix="bc"),"Conv-Bech32"
    if script[:2] == b"\x00\x20":
        return pubkeyhash_to_addr_bech32(script[2:], prefix="bc"),"Conv-Bech32"
    # P2TR
    if script[:2] == b"\x51\x20":
        return pubkeyhash_to_addr_bech32(script[2:], prefix="bc"),"Conv-P2TR"
    # P2PK antiguo
    if script[-1] == 0xac:
        pubkey = script[1:-1]
        h160 = hashlib.new("ripemd160", hashlib.sha256(pubkey).digest()).digest()
        return base58.b58encode_check(b"\x00" + h160).decode(),"Conv-P2PK"
    return "unknown","unknown"

# -----------------------------
# Extraer y averiguar el tipo de dirección
# -----------------------------

def address_type(address):
    if address.startswith("1"):
        return "P2PKH"
    elif address.startswith("3"):
        return "P2SH"
    elif address.startswith("bc1q") and len(address)==42:
        return "P2WPKH"
    elif address.startswith("bc1q") and len(address)==62:
        return "P2WSH"
    elif address.startswith("bc1p"):
        return "P2TR"
    else:
        return "unknown"

def dime_direccion(tx):
    """ Devolvemos la dirección y el tipo dentro de la transacción """
    addr = "unknown"
    tipo_addr = "unknown"
    if "address" not in tx:
        #print(f'No hay dirección en el scriptPubKey - {addr}')
        script_bytes = bytes.fromhex(tx["hex"])
    else:
        addr = tx["address"]
        tipo_addr = address_type(addr)

    #Si no hay dirección (¿bloque antiguo?), convertir script
    if addr == "unknown":
    #Convirtiendo script a dirección...
        addr_tmp,tipo_addr = script_to_address(script_bytes)
        if addr_tmp != "unknown":
            addr = addr_tmp
    return addr, tipo_addr

def contabilizar(contabilidad,addr,op,valor):
    """  Contabilizamos las transacciones: Sumamos o restamos (según op) en la dirección addr el contenido de valor """
    if op == "-":
        valor = valor * (-1)
    if addr in contabilidad:
        contabilidad[addr] = contabilidad[addr] + valor
    else:
        contabilidad[addr] = valor

def main(inicio, fin, salida):
    sesion = bitcoin_rpc_init()
    contabilidad = {} # Parejas de dirección y saldo en la dirección
    with open(salida, "w",  buffering=1024*1024) as f:
        f.write("height,txid,value_btc,address,spent,block_time\n")

        for h in range(inicio, fin + 1):
            try:
                # Obtener hash del bloque
                blockhash = bitcoin_rpc(sesion, "getblockhash", [h])
                # Obtener bloque completo con todas las transacciones
                block = bitcoin_rpc(sesion, "getblock", [blockhash, 3])  #2 es mejor que 3, porque no te da la información de inputs
                coinbase_tx = block["tx"][0]
                txid = coinbase_tx["txid"]
                block_time = datetime.fromtimestamp(block["time"], tz=timezone.utc).isoformat()
                vout_index = 0
                script_bytes = b""

                #Empezamos por el Coinbase
                for idx, vout in enumerate(coinbase_tx["vout"]):
                    addr , tipo_addr = dime_direccion(vout["scriptPubKey"])
                    # Comprobar si el UTXO está gastado usando gettxout
                    utxo = bitcoin_rpc(sesion, "gettxout", [txid, idx])
                    spent = utxo is None

                    # Escribir CSV
                    if vout["value"] > 0:
                        f.write(f"{h},{idx},{txid},{vout["value"]:.8f},{addr},{tipo_addr},{block_time},{spent}\n")
                        if cuenta:
                            contabilizar(contabilidad,addr,"+",vout["value"]) # Contabilizamos los coinbase 

                #Pasamos por el resto de los bloques
                if len(block["tx"]) != 0 and cuenta:    # Si es mayor que 0 hay más transacciones en el bloque y si quieremos contabilidad
                    for resto_tx in block["tx"][1:]:
                        #print(f'Vamos con la tx {resto_tx}')
                        #Restamos los vins
                        for vins in resto_tx["vin"]:
                            #print(f'El VIN X -> {vins}')
                            addr, tipo_addr = dime_direccion(vins["prevout"]["scriptPubKey"]) 
                            contabilizar(contabilidad,addr,"-",vins["prevout"]["value"])
                        #Sumamos los vouts
                        for vouts in resto_tx["vout"]:
                            #print(f'EL VOUT X -> {vouts}')
                            addr, tipo_addr = dime_direccion(vouts["scriptPubKey"])
                            contabilizar(contabilidad,addr,"+",vouts["value"])

                #print(f"Bloque {h} OK")

            except Exception as ex:
                print(f"Error en bloque {h}: {ex}")
                f.write(f"{h},ERROR,0.0,ERROR,ERROR,ERROR\n")
    if cuenta:
        print("Contabilidad a fichero:")
        with open('contabilidad.csv', 'w', encoding='utf-8',buffering=1024*1024) as f:
            f.writelines(f"{k},{v}\n" for k, v in sorted(contabilidad.items(), key=lambda x: x[1], reverse=True))


# -----------------------------
# Entrada por línea de comandos
# -----------------------------
if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(f"Uso: {sys.argv[0]} <bloque_inicio> <bloque_fin> <salida.csv> [cuenta]")
        sys.exit(1)
    cuenta = True if sys.argv[4] == "cuenta" else False # Hacemos contabilidad 
    inicio = int(sys.argv[1])
    fin = int(sys.argv[2])
    salida = sys.argv[3]
    main(inicio, fin, salida)

