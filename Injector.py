from flask import Flask, request, jsonify, render_template, send_from_directory
import pymem
import pymem.process
import re
import time
import urllib.request
import psutil
import subprocess

app = Flask(__name__)

PROCESS_NAME = "RobloxPlayerBeta.exe"
HPP_URL = "https://raw.githubusercontent.com/creatornawaf/FFlags-Offsets/refs/heads/main/FFlags.hpp"

pm = None
base_address = None

OFFSETS = {}


# -------------------------
# load .hpp flags
# -------------------------

def load_hpp():

    global OFFSETS

    try:
        response = urllib.request.urlopen(HPP_URL)
        text = response.read().decode("utf-8")
    except Exception as e:
        print(f"Error fetching HPP from URL: {e}")
        return

    matches = re.findall(
        r'([A-Za-z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+)',
        text
    )

    OFFSETS = {

        name:int(offset,16)

        for name,offset in matches

    }

    print("loaded",len(OFFSETS),"flags")
    print("Join Our Discord Server https://discord.gg/U5TwSnQh6e")


# -------------------------
# detect flag type
# -------------------------

def detect_type(flag):

    if flag.startswith(("DFFlag","FFlag","BFlag")):
        return "bool"

    if flag.startswith(("DFInt","FInt","FLog")):
        return "int"

    if flag.startswith(("FFloat","DFFloat")):
        return "float"

    if flag.startswith(("FString","DFString")):
        return "string"

    return "int"


def is_text_value(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return True
        if stripped.lower() in ["true", "false"]:
            return False
        try:
            int(stripped)
            return False
        except ValueError:
            pass
        try:
            float(stripped)
            return False
        except ValueError:
            pass
        return True
    return False


# -------------------------
# auto inject
# -------------------------

def auto_inject():

    global pm, base_address

    print("waiting for roblox...")

    while True:

        try:

            pm = pymem.Pymem(PROCESS_NAME)

            module = pymem.process.module_from_name(
                pm.process_handle,
                PROCESS_NAME
            )

            base_address = module.lpBaseOfDll

            print("attached to roblox")

            break

        except:

            time.sleep(2)


# -------------------------
# write memory
# -------------------------

def write_value(addr, flag_type, value):

    if flag_type == "bool":

        pm.write_bool(
            addr,
            value in ["1","true","True",True]
        )


    elif flag_type == "int":

        pm.write_int(
            addr,
            int(value)
        )


    elif flag_type == "float":

        pm.write_float(
            addr,
            float(value)
        )


    elif flag_type == "string":

        data = value.encode() + b"\x00"

        pm.write_bytes(
            addr,
            data,
            len(data)
        )


# -------------------------
# pointer-safe setter
# -------------------------

def set_flag(name,value):

    if name not in OFFSETS:

        return "flag not found"


    offset = OFFSETS[name]

    addr = base_address + offset

    flag_type = detect_type(name)


    # try direct write

    try:

        write_value(addr,flag_type,value)

        print(name,"direct")

        return "direct"

    except:

        pass


    # try pointer write

    try:

        ptr = pm.read_longlong(addr)

        write_value(ptr,flag_type,value)

        print(name,"pointer")

        return "pointer"

    except:

        pass

    # fallback: if the value looks like text, try writing as string directly
    if flag_type != "string" and is_text_value(value):
        try:
            write_value(addr,"string",value)
            print(name,"direct-string-fallback")
            return "direct-string"
        except:
            pass

        try:
            ptr = pm.read_longlong(addr)
            write_value(ptr,"string",value)
            print(name,"pointer-string-fallback")
            return "pointer-string"
        except:
            pass

    return "failed"


# -------------------------
# flask routes
# -------------------------

@app.route("/")
def home():

    return render_template("index.html")


@app.route('/Discord.png')
def discord_icon():
    return send_from_directory('templates', 'Discord.png')


@app.route("/flags")
def flags():

    return OFFSETS


@app.route("/setflag",methods=["POST", "GET"])
def api_setflag():

    data = request.json

    name = data["flag"]

    value = data["value"]

    mode = set_flag(name,value)

    return {

        "flag":name,

        "mode":mode

    }

@app.route("/inject", methods=["POST", "GET"])
def api_inject():

    auto_inject()
    print("injected successfully!")

    return "injected"


@app.route("/restart_roblox", methods=["POST"])
def restart_roblox():


    roblox_path = None

    for proc in psutil.process_iter(['name', 'exe']):

        try:

            if proc.info['name'] == "RobloxPlayerBeta.exe":

                roblox_path = proc.info['exe']

                proc.kill()

        except:
            pass

    time.sleep(2)

    if roblox_path:

        subprocess.Popen(roblox_path)

        auto_inject()

        return "restarted"

    return "roblox not found"

@app.route("/uninject", methods=["POST"])
def uninject():

    import psutil

    targets = [
        "cmd.exe",
    ]

    for proc in psutil.process_iter(['pid', 'name']):

        try:

            if proc.info['name'] in targets:

                proc.kill()

        except:
            pass

    return "uninjected"

@app.route("/restart_injector", methods=["POST"])
def restart_injector():

    import os
    import time
    import subprocess
    import threading

    current_pid = os.getpid()

    bat_path = os.path.abspath("startserver.bat")

    def restart():

        time.sleep(1)

        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

        os._exit(0)

    threading.Thread(target=restart).start()

    return "restarting"


# -------------------------
# start
# -------------------------


load_hpp()

auto_inject()

app.run(port=5000)
