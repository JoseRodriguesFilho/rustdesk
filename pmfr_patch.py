"""PMFR: personalização do cliente RustDesk, aplicada pelo build.py durante o build.

- embute ID server, key e API server;
- embute as configurações de res/pmfr-custom.json (mesmo formato do cliente
  personalizado do Pro: default-settings / override-settings / chaves fixas);
- se a variável PMFR_PRESET_PASSWORD existir (secret do GitHub), embute a senha
  permanente já com hash + salt (a senha em texto puro não vai para o .exe).
"""
import json
import os
import pathlib
import re
import secrets
import string
import base64
import hashlib

ID_SERVER = "192.168.253.103"
PUB_KEY = "Thp8okCj4ZfMN8jpgOfLhOgi7CyXqo3GFZJlhzYOhsI="
API_SERVER = "http://192.168.253.103:21114"

ROOT = pathlib.Path(__file__).resolve().parent


def _sub_once(text, old, new, what):
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"PMFR-PATCH: trecho não encontrado ({what})")
    return text.replace(old, new, 1)


def patch_server():
    cfg = ROOT / "libs" / "hbb_common" / "src" / "config.rs"
    t = cfg.read_text(encoding="utf-8")
    n = re.sub(r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];',
               f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{ID_SERVER}"];', t)
    n = re.sub(r'pub const RS_PUB_KEY: &str = "[^"]*";',
               f'pub const RS_PUB_KEY: &str = "{PUB_KEY}";', n)
    if f'"{ID_SERVER}"' not in n or f'"{PUB_KEY}"' not in n:
        raise SystemExit("PMFR-PATCH: não consegui alterar " + str(cfg))
    cfg.write_text(n, encoding="utf-8")
    print("PMFR-PATCH: ID server ->", ID_SERVER)


def patch_common():
    common = ROOT / "src" / "common.rs"
    s = common.read_text(encoding="utf-8")
    # 1) API padrão
    s = _sub_once(s, '"https://admin.rustdesk.com".to_owned()',
                  f'"{API_SERVER}".to_owned()', "API padrão")
    # 2) separa a leitura do JSON da verificação de assinatura do Pro
    s = _sub_once(
        s,
        '''        log::error!("Failed to dec custom client config");
        return;
    };
    let Ok(mut data) =
        serde_json::from_slice::<std::collections::HashMap<String, serde_json::Value>>(&data)''',
        '''        log::error!("Failed to dec custom client config");
        return;
    };
    read_custom_client_json(&data);
}

pub fn read_custom_client_json(data: &[u8]) {
    let Ok(mut data) =
        serde_json::from_slice::<std::collections::HashMap<String, serde_json::Value>>(data)''',
        "read_custom_client")
    # 3) aplica o JSON embutido sempre que o cliente carrega a personalização
    s = _sub_once(
        s,
        "pub fn load_custom_client() {\n",
        '''pub fn load_custom_client() {
    {
        const PMFR: &str = include_str!("../res/pmfr-custom.json");
        if !PMFR.trim().is_empty() {
            read_custom_client_json(PMFR.as_bytes());
            return;
        }
    }
''',
        "load_custom_client")
    common.write_text(s, encoding="utf-8")
    print("PMFR-PATCH: API padrão ->", API_SERVER)


def prepare_json():
    p = ROOT / "res" / "pmfr-custom.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    pw = os.environ.get("PMFR_PRESET_PASSWORD", "")
    if pw:
        salt = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        h1 = hashlib.sha256(pw.encode() + salt.encode()).digest()
        data["password"] = "00" + base64.b64encode(h1).decode()
        data["salt"] = salt
        print("PMFR-PATCH: senha permanente embutida (hash + salt)")
    else:
        print("PMFR-PATCH: AVISO - secret PMFR_PRESET_PASSWORD vazio; cliente SEM senha permanente")
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print("PMFR-PATCH: configurações ->", ", ".join(sorted(data.get("override-settings", {}))))


def run():
    patch_server()
    patch_common()
    prepare_json()
