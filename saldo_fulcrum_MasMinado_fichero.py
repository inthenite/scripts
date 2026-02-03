import socket
import json
import hashlib
import base58
import sys
from bech32 import bech32_decode, convertbits
import bech32m
from bitcoinutils.setup import setup
from bitcoinutils.script import Script
from bitcoinutils.keys import P2wpkhAddress, P2wshAddress, P2shAddress, P2trAddress, PrivateKey

"""
 Devuelve el saldo de direcciones Bitcoin.
 Usamos fulcrum (Electrum) para consultar el saldo disponible
 Usamos un fichero de contabilidad con lo minado no gastado para sumar a lo previo
 Usamos un fichero de entrada con todas las direcciones a consultar
"""

FULCRUM_HOST = "127.0.0.1"
FULCRUM_PORT = 50001

def address_to_scriptpubkey(address):
    """ Convierto la dirección a scriptpubKey """
    # P2PKH
    if address.startswith("1"):
        decoded = base58.b58decode_check(address)
        pubkey_hash = decoded[1:]
        return b"\x76\xa9\x14" + pubkey_hash + b"\x88\xac"

    # P2SH
    if address.startswith("3"):
        decoded = base58.b58decode_check(address)
        script_hash = decoded[1:]
        return b"\xa9\x14" + script_hash + b"\x87"

    # Bech32
    if address.startswith("bc1q"):
        hrp, data = bech32_decode(address)
        if hrp != "bc":
            raise ValueError(f'HRP inválido {hrp} - {address}')

        witver = data[0]
        witprog = bytes(convertbits(data[1:], 5, 8, False))

        if witver == 0:
            return b"\x00" + bytes([len(witprog)]) + witprog
    # P2TR
    if address.startswith("bc1p"):
        witver, witprog = bech32m.decode("bc",address)
        if witver == 1:
            # P2TR (Taproot)
            if len(witprog) != 32:
                raise ValueError("Taproot (bc1p) debe tener exactamente 32 bytes en witness program")
            
            # scriptPubKey = OP_1 PUSH32 <32-byte-tweaked-key>
            return b"\x51\x20" + witprog
        
        else:
            raise ValueError(f"Versión witness no soportada para bc1p: {witver}")

    raise ValueError("Tipo de dirección no soportado")


def address_to_scripthash(address):
    """ Convierto de dirección a Hash invertido para consulta a Electrum """
    script_pubkey = address_to_scriptpubkey(address) # Primero obtengo el scriptpubKey
    sha = hashlib.sha256(script_pubkey).digest()
    hash = sha[::-1].hex()  # little-endian Electrum
    return hash


def electrum_request(method, params, sock):
    """ Conexión al RPC de Fulcrum """    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }

    sock.sendall((json.dumps(request) + "\n").encode())
    response = sock.recv(4096)
    return json.loads(response.decode())


def get_balance(address,sock):
    scripthash = address_to_scripthash(address)
    response = electrum_request(
        "blockchain.scripthash.get_balance",
        [scripthash], sock
    )
    return response["result"]

def carga_minado_no_gastado(direcciones):
    """ Cargamos un fichero de texto con las direcciones que han minado y no han gastado """
    with open('DirMinadoNoGastado.csv', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()           # quita \n y espacios sobrantes
            if not linea:                   # saltar líneas vacías
                continue
            valor, direccion = linea.split(',')
            if direccion in direcciones:
                direcciones[direccion] = direcciones[direccion] + float(valor)*100000000
            else:
                direcciones[direccion] = float(valor)*100000000
    return direcciones 


def carga_direcciones(fichero):
    """ Cargamos el fichero con direcciones, y obtenemos de una en una """
    sock = socket.create_connection((FULCRUM_HOST, FULCRUM_PORT)) # Aprovechamos la misma conexión
    direcciones = {}
    direcciones = carga_minado_no_gastado(direcciones)
    with open(fichero,'r') as f:
        for linea in f:
            linea = linea.strip()           # quita \n y espacios sobrantes
            if not linea:                   # saltar líneas vacías
                continue
            direccion = linea
            balance = get_balance(direccion,sock) 
            if direccion in direcciones:
                suma =  direcciones[direccion]
            else:
                suma = 0
            print(f"Saldo confirmado: {direccion} {balance['confirmed']} + {suma} = {balance['confirmed']+suma} sats ; No confirmado {balance['unconfirmed']} sats")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        carga_direcciones(sys.argv[1]) # El parámetro es el fichero de entrada
    else:
        print(f'{sys.argv[0]}: fichero_con_direcciones.txt')
