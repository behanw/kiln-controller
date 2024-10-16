import logging
from settings import config
log = logging.getLogger(__name__)

from .plugins import plugin_manager
from .routes import app
plugin_manager.hook.start_plugin()

from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

def main():
    ip = config.get('server.incoming_ip', '0.0.0.0', "No IP address specified for the web server")
    port = config.get('server.listening_port', 8081, "No port specified for the web server")

    ssl_args = {}
    if config.get('server.use_tls', False):
        certfile = config.get('server.https_certfile', None, 'No valid HTTPS certificate file specified')
        keyfile = config.get('server.https_keyfile', None, 'No valid HTTPS key file specified')
        ssl_args = { 'certfile': certfile, 'keyfile': keyfile }
        log.info("Listening on {}:{} with https using {}".format(ip, port, certfile))
    else:
        log.info("Listening on {}:{} with http".format(ip, port))

    log.info("Starting plugins")
    plugin_manager.hook.on_start()

    log.info("Starting kiln controller")
    server = WSGIServer((ip, port), app, handler_class=WebSocketHandler, **ssl_args)
    server.serve_forever()

if __name__ == "__main__":
    main()
