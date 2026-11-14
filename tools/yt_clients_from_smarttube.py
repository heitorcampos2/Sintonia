#!/usr/bin/env python3
"""Gera docs/yt-clients.json a partir do código do SmartTube (MediaServiceCore, licença MIT).

O Sintonia (TV Android) baixa esse arquivo uma vez por dia e usa as versões de cliente da API do
YouTube que o SmartTube está usando. Uma tarefa agendada roda este script e publica quando muda.

uso: yt_clients_from_smarttube.py <pasta do MediaServiceCore> <saída.json>
"""
import json, re, subprocess, sys, datetime

root, out = sys.argv[1], sys.argv[2]
base = root + "/youtubeapi/src/main/java/com/liskovsoft"
consts = open(base + "/youtubeapi/innertube/utils/Constants.kt", encoding="utf-8").read()
headers = open(base + "/googlecommon/common/helpers/DefaultHeaders.kt", encoding="utf-8").read()


def hconst(name, depth=0):
    m = re.search(r'const val %s\s*=\s*(.+)' % re.escape(name), headers)
    if not m or depth > 5:
        return None
    v = m.group(1).strip()
    if v.startswith('"'):
        parts = re.findall(r'"((?:[^"\\]|\\.)*)"', v)
        return "".join(parts)
    return hconst(v.split()[0], depth + 1)


def client(var):
    # pega o bloco "val VAR = CLIENT(...)" que não está comentado
    for m in re.finditer(r'^\s*val %s = CLIENT\((.*?)^\s*\)' % var, consts, re.S | re.M):
        body = m.group(1)
        d = {}
        for k, v in re.findall(r'^\s*([A-Z_]+)\s*=\s*(.+?),?\s*$', body, re.M):
            v = v.strip().rstrip(",")
            if v.startswith('"'):
                d[k] = v.strip('"')
            elif v.startswith("DefaultHeaders."):
                d[k] = hconst(v.split(".", 1)[1])
            elif re.fullmatch(r"\d+", v):
                d[k] = int(v)
        return d
    return None


def innertube(var, name):
    c = client(var)
    if not c:
        return None
    o = {"clientName": name or c.get("NAME"), "clientVersion": c.get("VERSION")}
    for src, dst in (("OS_NAME", "osName"), ("OS_VERSION", "osVersion"), ("SDK_VERSION", "androidSdkVersion"),
                     ("DEVICE_MAKE", "deviceMake"), ("DEVICE_MODEL", "deviceModel")):
        if src in c:
            o[dst] = c[src]
    return {"context": o, "ua": c.get("USER_AGENT")}


clients = {
    "WEB": innertube("WEB", "WEB"),
    "ANDROID": innertube("ANDROID", "ANDROID"),
    "IOS": innertube("IOS", "IOS"),
    "ANDROID_VR": innertube("ANDROID_VR", "ANDROID_VR"),
}
clients = {k: v for k, v in clients.items() if v and v["context"].get("clientVersion") and v.get("ua")}
try:
    commit = subprocess.run(["git", "-C", root, "log", "-1", "--format=%H %cI"], capture_output=True, text=True).stdout.split()
except Exception:
    commit = []
data = {
    "about": "Clientes da API do YouTube usados pelo Sintonia, copiados do SmartTube (MediaServiceCore, MIT).",
    "smarttube": {"commit": commit[0] if commit else "", "date": commit[1] if len(commit) > 1 else ""},
    "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    # ordem de tentativa (vídeos comuns): HLS do iOS, VR (vídeo+áudio), Android (360p)
    "vodOrder": [c for c in ("IOS", "ANDROID_VR", "ANDROID") if c in clients],
    "liveOrder": [c for c in ("ANDROID", "IOS") if c in clients],
    "clients": clients,
}
json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v["context"]["clientVersion"] for k, v in clients.items()}))
