import config
import logging

logging.basicConfig(level=config.log_level, format=config.log_format)
log = logging.getLogger(__name__)

from .plugins import plugin_manager
from .routes import app
plugin_manager.hook.start_plugin()

#import gevent
#import geventwebsocket
from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

def main():
    ssl_args = {}
    if hasattr(config, 'https_certfile') and hasattr(config, 'https_keyfile'):
        ssl_args = {
            'certfile': config.https_certfile,
            'keyfile': config.https_keyfile
        }
        log.info("Configuring for https using {}".format(config.https_certfile))

    ip = config.incoming_ip or "0.0.0.0"
    port = config.listening_port
    log.info("listening on {}:{}".format(ip, port))

    plugin_manager.hook.on_start()

    log.info("Starting kiln controller")
    server = WSGIServer((ip, port), app,
                        handler_class=WebSocketHandler, **ssl_args)
    server.serve_forever()

if __name__ == "__main__":
    main()
