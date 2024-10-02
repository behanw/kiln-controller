import time
import os
import sys
import logging
import json

import config
from .plugins import plugin_manager
from .oven import Oven
from .ovenWatcher import OvenWatcher
from .firing_profile import Firing_Profile

import bottle
from jinja2 import Environment, FileSystemLoader
#from bottle import post, get
from geventwebsocket import WebSocketError

#plugin_manager.hook.start_plugin()
kiln = Oven.getOven()
kilnWatcher = OvenWatcher(kiln)
# this kilnwatcher is used in the oven class for restarts
kiln.set_ovenwatcher(kilnWatcher)

log = logging.getLogger(__name__)
app = bottle.Bottle()
public = os.path.join(os.path.dirname(os.path.realpath(__file__)), "public")
assets = os.path.join(public, "assets")

# Configure Jinja2
template_env = Environment(loader=FileSystemLoader('kilnapp/templates'))

# Function to render Jinja2 templates
def render_template(template_name, **context):
    return template_env.get_template(template_name).render(context)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/state')
def state():
    return render_template('state.html')


@app.get('/api/stats')
def handle_api():
    log.info("/api/stats command received")
    return kiln.pidstats()


@app.post('/api')
def handle_api():
    log.info("/api is alive")

    # run a kiln schedule
    if bottle.request.json['cmd'] == 'run':
        wanted = bottle.request.json['profile']
        log.info('api requested run of profile = %s' % wanted)

        # start at a specific minute in the schedule
        # for restarting and skipping over early parts of a schedule
        startat = 0;
        if 'startat' in bottle.request.json:
            startat = bottle.request.json['startat']

        #Shut off seek if start time has been set
        allow_seek = True
        if startat > 0:
            allow_seek = False

        # get the wanted profile/kiln schedule
        try:
            profile = Firing_Profile.load(wanted)
        except FileNotFoundError:
            return { "success" : False, "error" : "profile {} not found".format(wanted) }
        except e:
            raise(e)

        kiln.run_profile(profile, startat=startat, allow_seek=allow_seek)
        kilnWatcher.record(profile)

    elif bottle.request.json['cmd'] == 'pause':
        log.info("api pause command received")
        kiln.pause()

    elif bottle.request.json['cmd'] == 'resume':
        log.info("api resume command received")
        kiln.resume()

    elif bottle.request.json['cmd'] == 'stop':
        log.info("api stop command received")
        kiln.abort_run()

    elif bottle.request.json['cmd'] == 'memo':
        log.info("api memo command received")
        memo = bottle.request.json['memo']
        log.info("memo=%s" % (memo))

    # get stats during a run
    elif bottle.request.json['cmd'] == 'stats':
        log.info("api stats command received")
        return kiln.pidstats()

    return { "success" : True }


@app.route('/android-chrome-192x192.png')
@app.route('/android-chrome-512x512.png')
@app.route('/apple-touch-icon.png')
@app.route('/favicon-16x16.png')
@app.route('/favicon-32x32.png')
@app.route('/favicon.ico')
@app.route('/site.webmanifest')
def send_favicon():
    log.info(bottle.request.path)
    return bottle.static_file(bottle.request.path, root=public)


@app.route('/assets/:filename#.*#')
def send_static(filename):
    log.debug("serving {}".format(filename))
    return bottle.static_file(filename, root=assets)


def get_websocket_from_request():
    env = bottle.request.environ
    wsock = env.get('wsgi.websocket')
    if not wsock:
        abort(400, 'Expected WebSocket request.')
    return wsock


@app.route('/control')
def handle_control():
    wsock = get_websocket_from_request()
    log.info("websocket (control) opened")
    while True:
        try:
            message = wsock.receive()
            if message:
                log.info("Received (control): %s" % message)
                msgdict = json.loads(message)
                if msgdict.get("cmd") == "RUN":
                    log.info("RUN command received")
                    profile_obj = msgdict.get('profile')
                    if profile_obj:
                        profile = Firing_Profile(profile_obj)
                    kiln.run_profile(profile)
                    kilnWatcher.record(profile)
                elif msgdict.get("cmd") == "SIMULATE":
                    log.info("SIMULATE command received")
                elif msgdict.get("cmd") == "STOP":
                    log.info("Stop command received")
                    kiln.abort_run()
            time.sleep(1)
        except WebSocketError as e:
            log.error(e)
            break
    log.info("websocket (control) closed")


@app.route('/storage')
def handle_storage():
    wsock = get_websocket_from_request()
    log.info("websocket (storage) opened")
    while True:
        try:
            message = wsock.receive()
            if not message:
                break
            log.debug("websocket (storage) received: %s" % message)

            try:
                msgdict = json.loads(message)
            except:
                msgdict = {}

            if message == "GET":
                log.info("GET command received")
                wsock.send(Firing_Profile.get_all_json())
            elif msgdict.get("cmd") == "DELETE":
                log.info("DELETE command received")
                profile_obj = msgdict.get('profile')
                if Firing_Profile.delete(profile_obj):
                  msgdict["resp"] = "OK"
                wsock.send(json.dumps(msgdict))
                #wsock.send(Firing_Profile.get_all_json())
            elif msgdict.get("cmd") == "PUT":
                log.info("PUT command received")
                profile_obj = msgdict.get('profile')
                if profile_obj:
                    #del msgdict["cmd"]
                    if Firing_Profile.save(profile_obj):
                        msgdict["resp"] = "OK"
                    else:
                        msgdict["resp"] = "FAIL"
                    log.debug("websocket (storage) sent: %s" % message)

                    wsock.send(json.dumps(msgdict))
                    wsock.send(Firing_Profile.get_all_json())
            time.sleep(1)
        except WebSocketError:
            break
    log.info("websocket (storage) closed")


def get_config():
    return json.dumps({"temp_scale": config.temp_scale,
        "time_scale_slope": config.time_scale_slope,
        "time_scale_profile": config.time_scale_profile,
        "kwh_rate": config.kwh_rate,
        "currency_type": config.currency_type})

@app.route('/config')
def handle_config():
    wsock = get_websocket_from_request()
    log.info("websocket (config) opened")
    while True:
        try:
            message = wsock.receive()
            wsock.send(get_config())
        except WebSocketError:
            break
        time.sleep(1)
    log.info("websocket (config) closed")


@app.route('/status')
def handle_status():
    wsock = get_websocket_from_request()
    kilnWatcher.add_observer(wsock)
    log.info("websocket (status) opened")
    while True:
        try:
            message = wsock.receive()
            wsock.send("Your message was: %r" % message)
        except WebSocketError:
            break
        time.sleep(1)
    log.info("websocket (status) closed")
