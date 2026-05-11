# =============================================================================
# Serve o front HTML5 (pasta web/) — sem Streamlit.
#
# Uso (na pasta frontend):
#   python app_web.py
#
# Por padrão escuta em 0.0.0.0 (todas as interfaces) para acessar pelo hostname/IP
# da máquina (ex.: http://stars-nte93:8502/). Para só localhost: WEB_HOST=127.0.0.1
#
# Backend FastAPI em outra porta (ex.: 8500). No navegador: localStorage "las_api_base"
# ou padrão http://localhost:8500 (ver web/app.js). Se abrir o front de outro PC na rede,
# configure las_api_base para http://<mesmo-host>:8500.
# =============================================================================

from __future__ import annotations

import os
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent / "web"
DEFAULT_PORT = 8502


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, format, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


def main() -> None:
    if not WEB_ROOT.is_dir():
        print(f"Pasta não encontrada: {WEB_ROOT}", file=sys.stderr)
        sys.exit(1)

    port = int(os.environ.get("WEB_PORT", str(DEFAULT_PORT)))
    host = os.environ.get("WEB_HOST", "0.0.0.0")

    server = ThreadingHTTPServer((host, port), _Handler)
    listen = f"http://{host}:{port}/"
    print(f"Local AI Stack (HTML5) escutando em {listen} (todas as interfaces)")
    print(f"Servindo arquivos de: {WEB_ROOT}")
    if host in ("0.0.0.0", "::"):
        print("  Acesso local: http://127.0.0.1:{}/ ou pelo hostname desta máquina.".format(port))
        print("  Firewall: libere a porta TCP {} (entrada) se acessar de outro equipamento.".format(port))
    print("Pressione Ctrl+C para encerrar.")

    if os.environ.get("WEB_NO_BROWSER") != "1":
        open_url = f"http://127.0.0.1:{port}/" if host in ("0.0.0.0", "::") else listen
        webbrowser.open(open_url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando.")
        server.shutdown()


if __name__ == "__main__":
    main()
