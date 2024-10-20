import time
import os
import sys
import logging
import json

from settings import config
from plugins import plugin_manager
from .oven import Oven
from .ovenWatcher import OvenWatcher
from .firing_profile import Firing_Profile

import bottle
from jinja2 import Environment, FileSystemLoader
#from bottle import post, get
from geventwebsocket import WebSocketError

kiln = Oven.getOven()
plugin_manager.register(kiln)
plugin_manager.register(kiln.state)
kilnWatcher = OvenWatcher(kiln)
# this kilnwatcher is used in the oven class for restarts
kiln.set_ovenwatcher(kilnWatcher)

log = logging.getLogger(__name__)
app = bottle.Bottle()

# Webserver paths
public = config.get_location('server.location.public')
assets = config.get_file_at_location('server.location.public', 'assets')

# Configure Jinja2 templates
template_dir = config.get_location('server.location.templates')
template_env = Environment(loader=FileSystemLoader(template_dir))

# Render Jinja2 templates
def render_template(template_name, **context):
    return template_env.get_template(template_name).render(context)

web_verbose = config.get_log_subsystem('web')
def logi(message: str):
    if web_verbose:
        log.info(message)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/state')
def state():
    return render_template('state.html')


@app.get('/api/stats')
def handle_api():
    logi("/api/stats command received")
    return json.dumps(kiln.pidstats())


@app.post('/api')
def handle_api():
    logi("/api is alive")

    # run a kiln schedule
    if bottle.request.json['cmd'] == 'run':
        wanted = bottle.request.json['profile']
        logi('api requested run of profile = {}'.format(wanted))

        # start at a specific minute in the schedule
        # for restarting and skipping over early parts of a schedule
        startat = 0;
        if 'startat' in bottle.request.json:
            startat = bottle.request.json['startat']

        # get the wanted profile/kiln schedule
        try:
            profile = Firing_Profile.load(wanted)
        except FileNotFoundError:
            return { "success" : False, "error" : "profile {} not found".format(wanted) }
        except e:
            raise(e)

        kiln.run_profile(profile, startat=startat)
        kilnWatcher.record(profile)

    elif bottle.request.json['cmd'] == 'pause':
        logi("api pause command received")
        kiln.pause()

    elif bottle.request.json['cmd'] == 'resume':
        logi("api resume command received")
        kiln.resume()

    elif bottle.request.json['cmd'] == 'stop':
        logi("api stop command received")
        kiln.end_run()

    elif bottle.request.json['cmd'] == 'memo':
        logi("api memo command received")
        memo = bottle.request.json['memo']
        logi("memo={}".format(memo))

    # get stats during a run
    elif bottle.request.json['cmd'] == 'stats':
        logi("api stats command received")
        return kiln.pidstats()

    return { "success" : True }


@app.route('/<:re:android-chrome-.*png>')
@app.route('/apple-touch-icon.png')
@app.route('/<:re:favicon.*>')
@app.route('/site.webmanifest')
def send_favicon():
    logi(bottle.request.path)
    return bottle.static_file(bottle.request.path, root=public)


@app.route('/assets/<filename:re:.*>')
def send_static(filename):
    log.debug("serving {}".format(filename))
    return bottle.static_file(filename, root=assets)


def get_websocket_from_request():
    env = bottle.request.environ
    wsock = env.get('wsgi.websocket')
    if not wsock:
        bottle.abort(400, 'Expected WebSocket request.')
    return wsock


@app.route('/control')
def handle_control():
    wsock = get_websocket_from_request()
    logi("websocket (control) opened")
    while True:
        try:
            message = wsock.receive()
            if message:
                logi("Received (control): {}".format(message))
                msgdict = json.loads(message)

                if msgdict.get("cmd") == "RUN":
                    logi("RUN command received")
                    profile_obj = msgdict.get('profile')
                    if profile_obj:
                        profile = Firing_Profile(profile_obj)
                        kiln.run_profile(profile)
                        kilnWatcher.record(profile)
                    else:
                        log.error("Invalid profile provided, or firing profile not found")

                elif msgdict.get("cmd") == "SIMULATE":
                    logi("SIMULATE command received")

                elif msgdict.get("cmd") == "STOP":
                    logi("Stop command received")
                    kiln.end_run()

            time.sleep(1)
        except WebSocketError as e:
            #log.warning("Error not covered")
            log.error(e)
            break
    logi("websocket (control) closed")


@app.route('/storage')
def handle_storage():
    wsock = get_websocket_from_request()
    logi("websocket (storage) opened")
    while True:
        try:
            message = wsock.receive()
            if not message:
                break
            log.debug("websocket (storage) received: {}".format(message))

            try:
                msgdict = json.loads(message)
            except:
                msgdict = {}

            if message == "GET":
                logi("GET command received")
                wsock.send(Firing_Profile.get_all_json())

            elif msgdict.get("cmd") == "DELETE":
                logi("DELETE command received")
                profile_obj = msgdict.get('profile')
                if Firing_Profile.delete(profile_obj):
                  msgdict["resp"] = "OK"
                wsock.send(json.dumps(msgdict))
                #wsock.send(Firing_Profile.get_all_json())

            elif msgdict.get("cmd") == "PUT":
                logi("PUT command received")
                profile_obj = msgdict.get('profile')
                if profile_obj:
                    #del msgdict["cmd"]
                    if Firing_Profile.save(profile_obj):
                        msgdict["resp"] = "OK"
                    else:
                        msgdict["resp"] = "FAIL"
                    log.debug("websocket (storage) sent: {}".format(message))

                    wsock.send(json.dumps(msgdict))
                    wsock.send(Firing_Profile.get_all_json())
            time.sleep(1)
        except WebSocketError:
            break
    logi("websocket (storage) closed")


web_config = json.dumps({
        "temp_scale": config.get_tempunit(),
        "time_scale_slope": config.get_rateunit(),
        "time_scale_profile": config.get_timeunit(),
        "kwh_rate": config.get('general.cost.kwh_rate'),
        "currency_type": config.get('general.cost.currency_type'),
    })

@app.route('/config')
def handle_config():
    wsock = get_websocket_from_request()
    logi("websocket (config) opened")
    while True:
        try:
            message = wsock.receive()
            wsock.send(web_config)
        except WebSocketError:
            break
        time.sleep(1)
    logi("websocket (config) closed")


@app.route('/status')
def handle_status():
    wsock = get_websocket_from_request()
    kilnWatcher.add_observer(wsock)
    logi("websocket (status) opened")
    while True:
        try:
            message = wsock.receive()
            wsock.send("Your message was: {}".format(message))
        except WebSocketError:
            break
        time.sleep(1)
    logi("websocket (status) closed")
