# -*- coding: utf-8 -*-
"""
Define (ou troca) a senha do painel admin sem apagar config/admin.json
inteiro — mantém a mesma chave de sessão, então quem já estava logado
não precisa refazer login em outra aba/dispositivo por causa da troca.

Uso: python tools/definir_senha_admin.py
"""
import getpass
import hashlib
import json
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import CONFIG_DIR

ADMIN_JSON = os.path.join(CONFIG_DIR, "admin.json")


def main():
    senha = getpass.getpass("Nova senha do admin: ")
    if len(senha) < 4:
        print("Senha muito curta (mínimo 4 caracteres). Nada foi alterado.")
        return 1
    confirmacao = getpass.getpass("Confirme a nova senha: ")
    if senha != confirmacao:
        print("As senhas não coincidem. Nada foi alterado.")
        return 1

    if os.path.exists(ADMIN_JSON):
        with open(ADMIN_JSON, encoding="utf-8") as fp:
            dados = json.load(fp)
    else:
        dados = {"secret_key": secrets.token_hex(32)}

    dados["senha_hash"] = hashlib.sha256(senha.encode("utf-8")).hexdigest()

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(ADMIN_JSON, "w", encoding="utf-8") as fp:
        json.dump(dados, fp, indent=2)

    print("Senha do admin atualizada em", ADMIN_JSON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
