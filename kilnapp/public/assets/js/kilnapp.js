var state = "IDLE";
var state_last = "";
var graph = [ 'profile', 'live', 'rate' ];
var points = [];
var profiles = [];
var time_mode = 0;
var selected_profile = 0;
var selected_profile_name = 'cone-05-long-bisque.json';
var temp_scale = "C";
var time_scale_slope = "s";
var time_scale_profile = "h";
var time_scale_long = "Seconds";
var temp_scale_display = "C";
var kwh_rate = 0.26;
var currency_type = "EUR";
var edit_type = "rate";

var protocol = 'ws:';
if (window.location.protocol == 'https:') {
    protocol = 'wss:';
}
var host = "" + protocol + "//" + window.location.hostname + ":" + window.location.port;
var ws_status = new WebSocket(host + "/status");
var ws_control = new WebSocket(host + "/control");
var ws_config = new WebSocket(host + "/config");
var ws_storage = new WebSocket(host + "/storage");

if (window.webkitRequestAnimationFrame) window.requestAnimationFrame = window.webkitRequestAnimationFrame;

graph.profile = {
    label: "Profile",
    data: [],
    points: { show: false },
    color: "#75890c",
    draggable: false
};

graph.live = {
    label: "Live",
    data: [],
    points: { show: false },
    color: "#d8d3c5",
    draggable: false
};

graph.rate = {
    label: "Rate",
    data: [],
    points: { show: false },
    color: "#d8d3c5",
    draggable: false
};

function updateProfile(id) {
    selected_profile = id;
    selected_profile_name = profiles[id].name;
    var job_seconds = profiles[id].data.length === 0 ? 0 : parseInt(profiles[id].data[profiles[id].data.length - 1][0]);
    var kwh = (3850 * job_seconds / 3600 / 1000).toFixed(2);
    var cost =  (kwh * kwh_rate).toFixed(2);
    var job_time = new Date(job_seconds * 1000).toISOString().substr(11, 8);
    $('#sel_prof').html(profiles[id].name);
    $('#sel_prof_eta').html(job_time);
    $('#sel_prof_cost').html(kwh + ' kWh (' + currency_type + ': ' + cost + ')');
    graph.profile.data = profiles[id].data;
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ] , getOptions());
}

function deleteProfile() {
    var profile = { "type": "profile", "data": "", "name": selected_profile_name };
    var delete_struct = { "cmd": "DELETE", "profile": profile };

    var delete_cmd = JSON.stringify(delete_struct);
    console.log("Delete profile:" + selected_profile_name);

    ws_storage.send(delete_cmd);

    ws_storage.send('GET');
    selected_profile_name = profiles[0].name;

    state="IDLE";
    $('#edit').hide();
    $('#profile_selector').show();
    $('#btn_controls').show();
    $('#status').slideDown();
    $('#profile_table').slideUp();
    $('#e2').select2('val', 0);
    graph.profile.points.show = false;
    graph.profile.draggable = false;
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ], getOptions());
}

function updateProgress(percentage) {
    if (state=="RUNNING") {
        if (percentage > 100) percentage = 100;
        $('#progressBar').css('width', percentage + '%');
        if (percentage>5) $('#progressBar').html(parseInt(percentage) + '%');
    } else {
        $('#progressBar').css('width', 0 + '%');
        $('#progressBar').html('');
    }
}

function convertProfile2Rate() {
    data = graph.profile.data;
    last = graph.profile.data.length;
    rates = [];
    for (var i=1; i<graph.profile.data.length; i++) {
        temp = data[i][1];
        secs = data[i][0];
        since = secs - data[i-1][0];
        rate = Math.round(3600 * (temp - data[i-1][1]) / since);
        if (rate == 0) {
            rates.push([0, temp, since]);
        } else {
            if (i+1 < last && temp == data[i+1][1]) {
                i++;
                rates.push([rate, temp, data[i][0] - secs]);
            } else {
                rates.push([rate, temp, 0]);
            }
        }
        //console.log("Rate: " + rate + "  Temp: " + temp + "  Hold: " + hold)
    }
    graph.rate.data = rates;
}

function convertRate2Profile() {
    rates = graph.rate.data;
    if (temp_scale == "C") {
        data = [[0, 20]];
    } else {
        data = [[0, 65]];
    }

    lastsecs = 0;
    lasttemp = data[0][1];
    for (var i=0; i<rates.length; i++) {
        rate = rates[i][0];
        temp = rates[i][1];
        hold = rates[i][2];
        secs = Math.round(60 * (temp - lasttemp) / rate) * 60 + lastsecs;
        data.push([secs, temp]);
        if (hold > 0) {
            secs += hold;
            data.push([secs, temp]);
        }
        lastsecs = secs;
        lasttemp = temp;
    }
    graph.profile.data = data;
}

function updateProfileTable() {
    if (edit_type == "rate") {
        updateProfileTableRate()
    } else {
        updateProfileTablePoints()
    }
}

const cones_in_C_slow = {
  0: '', 540: 'Quartz', 570: '', 586: '022', 600: '021', 626: '020', 678:
  '019', 715: '018', 738: '017', 772: '016', 791: '015', 807: '014', 837:
  '013', 861: '012', 875: '011', 903: '010', 920: '09', 942: '08', 976:
  '07', 998: '06', 1015: '05.5', 1031: '05', 1063: '04', 1086: '03',
  1102: '02', 1119: '01', 1137: '1', 1142: '2', 1152: '3', 1162: '4',
  1186: '5', 1203: '5.5', 1222: '6', 1239: '7', 1249: '8', 1260: '9',
  1285: '10', 1293: '11', 1304: '12'
}

const cones_in_C_fast = {
  0: '', 540: 'Quartz', 570: '', 590: '022', 617: '021', 638: '020', 695:
  '019', 734: '018', 763: '017', 796: '016', 818: '015', 838: '014', 861:
  '013', 882: '012', 894: '011', 915: '010', 930: '09', 956: '08', 987:
  '07', 1013: '06', 1025: '05.5', 1044: '05', 1077: '04', 1104: '03',
  1122: '02', 1138: '01', 1154: '1', 1164: '2', 1170: '3', 1183: '4',
  1207: '5', 1225: '5.5', 1243: '6', 1257: '7', 1271: '8', 1280: '9',
  1305: '10', 1312: '11', 1324: '12',
}

function temp2cone(inputTemp, rate) {
    if (Math.abs(rate) < 100 ) {
        scale = cones_in_C_slow
    } else {
        scale = cones_in_C_fast
    }
    const temps = Object.keys(scale).map(Number).sort((a, b) => a - b);
    let lastTemp = null;
    for (const temp of temps) {
        if (inputTemp >= temp - 5 && inputTemp <= temp) {
            return scale[temp];
        } else if (temp <= inputTemp) {
            cone = scale[temp];
	}
    }
    if (cone.length > 0) {
        return `${cone}+`;
    } else {
        return '';
    }
}

function updateProfileTableRate() {
    convertProfile2Rate();

    var dph = 0;
    var slope = "";
    var color = "";

    var html = '<h3>Schedule Rates</h3><div class="form-switch" style="align: right; margin: -3em 0 0 15em;"><label class="switch"><input type="checkbox" checked><span class="slider round"></span></div>';
        html += '<div class="table-responsive" style="scroll: none"><table class="table table-striped">';
        html += '<tr><th style="width: 50px">#</th><th>Rate in &deg;' + temp_scale_display + '/' + time_scale_slope
                + '</th><th>Target Temperature in &deg;' + temp_scale_display
                + '</th><th>Cone Number</th><th>Hold Time in ' + time_scale_profile + '</th></tr>';

    for (var i=0; i<graph.rate.data.length; i++) {
        dph = graph.rate.data[i][0];
        if (dph  > 0) {
            slope = "up"; color="rgba(206, 5, 5, 1)";
        } else if (dph  < 0) {
            slope = "down"; color="rgba(23, 108, 204, 1)";
        } else if (dph == 0) {
            slope = "right"; color="grey";
        }
        temp = graph.rate.data[i][1];
        hold = graph.rate.data[i][2];

        html += '<tr><td><h4>' + (i+1) + '</h4></td>';
        html += '<td><div class="input-group"><span class="glyphicon glyphicon-circle-arrow-' + slope + ' input-group-addon ds-trend" style="background: ' + color + '"></span><input type="text" class="form-control" id="profiletable-0-' + i + '" value="' + formatDPH(dph) + '" style="width: 60px" /></div></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-1-' + i + '" value="' + temp + '" style="width: 60px" /></td>';
        html += '<td><input type="text" class="form-control ds-input" readonly value="' + temp2cone(temp, dph) + '" style="width: 100px" /></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-2-' + i + '" value="' + timeProfileFormatter(hold, true) + '" style="width: 60px" /></td>';
        html += '<td>&nbsp;</td></tr>';
    }

    html += '</table></div>';

    $('#profile_table').html(html);

    $(".form-switch").change(function(e) {
        edit_type = "points";
        updateProfileTablePoints();
    });

    //Link table to graph
    $(".form-control").change(function(e) {
        var id = $(this)[0].id; //e.currentTarget.attributes.id
        var value = parseInt($(this)[0].value);
        var fields = id.split("-");
        var col = parseInt(fields[1]);
        var row = parseInt(fields[2]);

        if (graph.profile.data.length > 0) {
            if (col == 0) {
                graph.rate.data[row][col] = value;
            } else if (col == 1) {
                graph.rate.data[row][col] = value;
            } else {
                graph.rate.data[row][col] = timeProfileFormatter(value, false);
            }
            convertRate2Profile();
            graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ], getOptions());
        }
        updateProfileTable();
    });
}

function updateProfileTablePoints() {
    var dps = 0;
    var slope = "";
    var color = "";

    var html = '<h3>Schedule Points</h3><div class="form-switch" style="align: right; margin: -3em 0 0 15em;"><label class="switch"><input type="checkbox"><span class="slider round"></span></div>';
        html += '<div class="table-responsive" style="scroll: none"><table class="table table-striped">';
        html += '<tr><th style="width: 50px">#</th><th>Target Time in ' + time_scale_long + '</th><th>Target Temperature in °' + temp_scale_display + '</th><th>Slope in &deg;' + temp_scale_display + '/' + time_scale_slope + '</th><th></th></tr>';

    for (var i=0; i<graph.profile.data.length; i++) {
        if (i>=1) dps =  ((graph.profile.data[i][1] - graph.profile.data[i - 1][1]) / (graph.profile.data[i][0] - graph.profile.data[i - 1][0]) * 10) / 10;
        if (dps  > 0) { slope = "up";     color="rgba(206, 5, 5, 1)"; } else
        if (dps  < 0) { slope = "down";   color="rgba(23, 108, 204, 1)"; dps *= -1; } else
        if (dps == 0) { slope = "right";  color="grey"; }

        html += '<tr><td><h4>' + (i + 1) + '</h4></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-0-' + i + '" value="' + timeProfileFormatter(graph.profile.data[i][0],true) + '" style="width: 60px" /></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-1-' + i + '" value="' + graph.profile.data[i][1] + '" style="width: 60px" /></td>';
        html += '<td><div class="input-group"><span class="glyphicon glyphicon-circle-arrow-' + slope + ' input-group-addon ds-trend" style="background: ' + color + '"></span><input type="text" class="form-control ds-input" readonly value="' + formatDPS(dps) + '" style="width: 100px" /></div></td>';
        html += '<td>&nbsp;</td></tr>';
    }

    html += '</table></div>';

    $('#profile_table').html(html);

    $(".form-switch").change(function(e) {
        edit_type = "rate";
        updateProfileTableRate();
    });

    //Link table to graph
    $(".form-control").change(function(e) {
        var id = $(this)[0].id; //e.currentTarget.attributes.id
        var value = parseInt($(this)[0].value);
        var fields = id.split("-");
        var col = parseInt(fields[1]);
        var row = parseInt(fields[2]);

        if (graph.profile.data.length > 0) {
            if (col == 0) {
                graph.profile.data[row][col] = timeProfileFormatter(value,false);
            } else {
                graph.profile.data[row][col] = value;
            }
            graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ], getOptions());
        }
        updateProfileTable();
    });
}

function timeProfileFormatter(val, down) {
    var rval = val
    switch(time_scale_profile){
        case "m":
            if (down) {rval = val / 60;} else {rval = val * 60;}
            break;
        case "h":
            if (down) {rval = val / 3600;} else {rval = val * 3600;}
            break;
    }
    return Math.round(rval);
}

function formatDPS(val) {
    var tval = val;
    if (time_scale_slope == "m") {
        tval = val * 60;
    } else if (time_scale_slope == "h") {
        tval = val * 3600;
    }
    return Math.round(tval);
}

function formatDPH(val) {
    var tval = val;
    if (time_scale_slope == "m") {
        tval = val / 60;
    } else if (time_scale_slope == "s") {
        tval = val / 3600;
    }
    return Math.round(tval);
}

function hazardTemp() {
    if (temp_scale == "F") {
        return (1500 * 9 / 5) + 32
    } else {
        return 1500
    }
}

function timeTickFormatter(val,axis) {
    // hours
    if (axis.max>3600) {
        //var hours = Math.floor(val / (3600));
        //return hours;
        return Math.floor(val / 3600);
    }

    // minutes
    if (axis.max<=3600) {
        return Math.floor(val / 60);
    }

    // seconds
    if (axis.max<=60) {
        return val;
    }
}

function runTask() {
    var cmd = {
        "cmd": "RUN",
        "profile": profiles[selected_profile]
    }

    graph.live.data = [];
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ] , getOptions());

    ws_control.send(JSON.stringify(cmd));
}

function runTaskSimulation() {
    var cmd = {
        "cmd": "SIMULATE",
        "profile": profiles[selected_profile]
    }

    graph.live.data = [];
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ] , getOptions());

    ws_control.send(JSON.stringify(cmd));
}

function abortTask() {
    var cmd = {"cmd": "STOP"};
    ws_control.send(JSON.stringify(cmd));
}

function enterNewMode() {
    state="EDIT"
    $('#status').slideUp();
    $('#edit').show();
    $('#profile_selector').hide();
    $('#btn_controls').hide();
    $('#form_profile_name').attr('value', '');
    $('#form_profile_name').attr('placeholder', 'Please enter a name');
    graph.profile.points.show = true;
    graph.profile.draggable = true;
    graph.profile.data = [];
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ], getOptions());
    updateProfileTable();
}

function enterEditMode() {
    state="EDIT"
    $('#status').slideUp();
    $('#edit').show();
    $('#profile_selector').hide();
    $('#btn_controls').hide();
    console.log(profiles);
    $('#form_profile_name').val(profiles[selected_profile].name);
    graph.profile.points.show = true;
    graph.profile.draggable = true;
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ], getOptions());
    updateProfileTable();
    toggleTable();
}

function leaveEditMode() {
    selected_profile_name = $('#form_profile_name').val();
    ws_storage.send('GET');
    state="IDLE";
    $('#edit').hide();
    $('#profile_selector').show();
    $('#btn_controls').show();
    $('#status').slideDown();
    $('#profile_table').slideUp();
    graph.profile.points.show = false;
    graph.profile.draggable = false;
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ], getOptions());
}

function newPoint() {
    if (graph.profile.data.length > 0) {
        var pointx = parseInt(graph.profile.data[graph.profile.data.length - 1][0]) + 15;
    } else {
        var pointx = 0;
    }
    graph.profile.data.push([pointx, Math.floor((Math.random() * 230) + 25)]);
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ], getOptions());
    updateProfileTable();
}

function delPoint() {
    graph.profile.data.splice(-1,1)
    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ], getOptions());
    updateProfileTable();
}

function toggleTable() {
    if ($('#profile_table').css('display') == 'none') {
        $('#profile_table').slideDown();
    } else {
        $('#profile_table').slideUp();
    }
}

function saveProfile() {
    name = $('#form_profile_name').val();
    var rawdata = graph.plot.getData()[0].data
    var data = [];
    var last = -1;

    for (var i=0; i<rawdata.length; i++) {
        if (rawdata[i][0] > last) {
            data.push([rawdata[i][0], rawdata[i][1]]);
        } else {
            $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>ERROR 88:</b><br/>An oven is not a time-machine", {
                ele: 'body', // which element to append to
                type: 'alert', // (null, 'info', 'error', 'success')
                offset: {from: 'top', amount: 250}, // 'top', or 'bottom'
                align: 'center', // ('left', 'right', or 'center')
                width: 385, // (integer, or 'auto')
                delay: 5000,
                allow_dismiss: true,
                stackup_spacing: 10 // spacing between consecutively stacked growls.
            });

            return false;
        }

        last = rawdata[i][0];
    }

    convertProfile2Rate();

    var profile = { "type": "profile", "data": data, "rate": graph.rate.data, "name": name, "temp_units": temp_scale }
    var put = { "cmd": "PUT", "profile": profile }

    var put_cmd = JSON.stringify(put);

    ws_storage.send(put_cmd);

    leaveEditMode();
}

function get_tick_size() {
    //switch(time_scale_profile){
    //  case "s":
    //    return 1;
    //  case "m":
    //    return 60;
    //  case "h":
    //    return 3600;
    //  }
    return 3600;
}

function getOptions() {
    var options = {
        series: {
            lines: {
                show: true
            },
            points: {
                show: true,
                radius: 5,
                symbol: "circle"
            },
            shadowSize: 3
        },
        xaxis: {
            min: 0,
            tickColor: 'rgba(216, 211, 197, 0.2)',
            tickFormatter: timeTickFormatter,
            tickSize: get_tick_size(),
            font: {
                size: 14,
                lineHeight: 14,
                weight: "normal",
                family: "Digi",
                variant: "small-caps",
                color: "rgba(216, 211, 197, 0.85)"
            }
        },
        yaxis: {
            min: 0,
            tickDecimals: 0,
            draggable: false,
            tickColor: 'rgba(216, 211, 197, 0.2)',
            font: {
                size: 14,
                lineHeight: 14,
                weight: "normal",
                family: "Digi",
                variant: "small-caps",
                color: "rgba(216, 211, 197, 0.85)"
            }
        },
        grid: {
            color: 'rgba(216, 211, 197, 0.55)',
            borderWidth: 1,
            labelMargin: 10,
            mouseActiveRadius: 50
        },
        legend: {
            show: false
        }
    }

    return options;
}

$(document).ready(function() {
    if (!("WebSocket" in window)) {
        $('#chatLog, input, button, #examples').fadeOut("fast");
        $('<p>Oh no, you need a browser that supports WebSockets. How about <a href="http://www.google.com/chrome">Google Chrome</a>?</p>').appendTo('#container');
    } else {
        // Status Socket ////////////////////////////////
        ws_status.onopen = function() {
            console.log("Status Socket has been opened");

//            $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span>Getting data from server", {
//                ele: 'body', // which element to append to
//                type: 'success', // (null, 'info', 'error', 'success')
//                offset: {from: 'top', amount: 250}, // 'top', or 'bottom'
//                align: 'center', // ('left', 'right', or 'center')
//                width: 385, // (integer, or 'auto')
//                delay: 2500,
//                allow_dismiss: true,
//                stackup_spacing: 10 // spacing between consecutively stacked growls.
//            });
        };

        ws_status.onclose = function() {
            $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>ERROR 1:</b><br/>Status Websocket not available", {
                ele: 'body', // which element to append to
                type: 'error', // (null, 'info', 'error', 'success')
                offset: {from: 'top', amount: 250}, // 'top', or 'bottom'
                align: 'center', // ('left', 'right', or 'center')
                width: 385, // (integer, or 'auto')
                delay: 5000,
                allow_dismiss: true,
                stackup_spacing: 10 // spacing between consecutively stacked growls.
            });
            setInterval(() => {
                $.get(window.location.href, function(data) {
                    if (data) {
                        window.location.reload();
                        //history.pushState(null, null, window.location.href);
                    }
                });
            }, 5000);
        };

        ws_status.onmessage = function(e) {
            x = JSON.parse(e.data);
            if (x.type == "backlog") {
                if (x.profile) {
                    selected_profile_name = x.profile.name;
                    $.each(profiles,  function(i,v) {
                        if (v.name == x.profile.name) {
                            updateProfile(i);
                            $('#e2').select2('val', i);
                        }
                    });
                }

                $.each(x.log, function(i,v) {
                    graph.live.data.push([v.runtime, v.temperature]);
                    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ] , getOptions());
                });
            }

            if (state!="EDIT") {
                state = x.state;
                if (state!=state_last) {
                    if (state_last == "RUNNING" && state != "PAUSED" ) {
                        console.log(state);
                        $('#target_temp').html('---');
                        updateProgress(0);
                        $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>Run completed</b>", {
                            ele: 'body', // which element to append to
                            type: 'success', // (null, 'info', 'error', 'success')
                            offset: {from: 'top', amount: 250}, // 'top', or 'bottom'
                            align: 'center', // ('left', 'right', or 'center')
                            width: 385, // (integer, or 'auto')
                            delay: 0,
                            allow_dismiss: true,
                            stackup_spacing: 10 // spacing between consecutively stacked growls.
                        });
                    }
                }

                if (state=="RUNNING") {
                    $("#nav_start").hide();
                    $("#nav_stop").show();

                    graph.live.data.push([x.runtime, x.temperature]);
                    graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ] , getOptions());

                    left = parseInt(x.totaltime - x.runtime);
                    eta = new Date(left * 1000).toISOString().substr(11, 8);

                    updateProgress(parseFloat(x.runtime) / parseFloat(x.totaltime) * 100);
                    $('#state').html('<span class="glyphicon glyphicon-time" style="font-size: 22px; font-weight: normal"></span><span style="font-family: Digi; font-size: 40px;">' + eta + '</span>');
                    $('#target_temp').html(parseInt(x.target));
                    $('#cost').html(x.currency_type + parseFloat(x.cost).toFixed(2));
                } else {
                    $("#nav_start").show();
                    $("#nav_stop").hide();
                    $('#state').html('<p class="ds-text">' + state + '</p>');
                }
                $('#act_temp').html(parseInt(x.temperature));

                heat_rate = parseInt(x.heat_rate)
                if (heat_rate > 9999) { heat_rate = 9999; }
                if (heat_rate < -9999) { heat_rate = -9999; }
                $('#heat_rate').html(heat_rate);

                $('#ext_ctrl_temp').html(parseInt(x.ext_ctrl_temp));
                $('#ext_sitter_temp').html(parseInt(x.ext_sitter_temp));
                $('#ext_upper_amps').html(parseFloat(x.ext_upper_amps));
                $('#ext_lower_amps').html(parseFloat(x.ext_lower_amps));
                $('#ext_caution').html(x.ext_caution);
                $('#ext_estop').html(x.ext_estop);
                $('#ext_heartbeat').html(x.ext_heartbeat);

                if (typeof x.pidstats !== 'undefined') {
                    $('#heat').html('<div class="bar" style="height:' + x.pidstats.out * 70 + '%;"></div>')
                }
                if (x.cool > 0.5) { $('#cool').addClass("ds-led-cool-active"); } else { $('#cool').removeClass("ds-led-cool-active"); }
                if (x.air > 0.5) { $('#air').addClass("ds-led-air-active"); } else { $('#air').removeClass("ds-led-air-active"); }
                if (x.temperature > hazardTemp()) { $('#hazard').addClass("ds-led-hazard-active"); } else { $('#hazard').removeClass("ds-led-hazard-active"); }
                if ((x.door == "OPEN") || (x.door == "UNKNOWN")) { $('#door').addClass("ds-led-door-open"); } else { $('#door').removeClass("ds-led-door-open"); }

                state_last = state;
            }
        };

        // Config Socket /////////////////////////////////

        ws_config.onopen = function() {
            ws_config.send('GET');
        };

        ws_config.onmessage = function(e) {
            console.log (e.data);
            x = JSON.parse(e.data);
            temp_scale = x.temp_scale;
            time_scale_slope = x.time_scale_slope;
            time_scale_profile = x.time_scale_profile;
            kwh_rate = x.kwh_rate;
            currency_type = x.currency_type;

            if (temp_scale == "C") {temp_scale_display = "C";} else {temp_scale_display = "F";}

            $('#act_temp_scale').html('º' + temp_scale_display);
            $('#target_temp_scale').html('º' + temp_scale_display);
            $('#heat_rate_temp_scale').html('º' + temp_scale_display);

            switch(time_scale_profile){
                case "s":
                    time_scale_long = "Seconds";
                    break;
                case "m":
                    time_scale_long = "Minutes";
                    break;
                case "h":
                    time_scale_long = "Hours";
                    break;
            }

        }

        // Control Socket ////////////////////////////////

        ws_control.onopen = function() {

        };

        ws_control.onmessage = function(e) {
            // Data from Simulation
            console.log ("control socket has been opened")
            console.log (e.data);
            x = JSON.parse(e.data);
            graph.live.data.push([x.runtime, x.temperature]);
            graph.plot = $.plot("#graph_container", [ graph.profile, graph.live ] , getOptions());

        }

        // Storage Socket ///////////////////////////////

        ws_storage.onopen = function() {
            ws_storage.send('GET');
        };

        ws_storage.onmessage = function(e) {
            message = JSON.parse(e.data);

            if (message.resp) {
                if (message.resp == "FAIL") {
                    if (confirm('Overwrite?')) {
                        message.force=true;
                        console.log("Sending: " + JSON.stringify(message));
                        ws_storage.send(JSON.stringify(message));
                    } else {
                        // do nothing
                    }
                }

                return;
            }

            // the message is an array of profiles
            // FIXME: this should be better, maybe a {"profiles": ...} container?
            profiles = message.sort(function(a, b){
                if(a.name < b.name) return -1;
                if(a.name > b.name) return 1;
                return 0;
            });
            // delete old options in select
            $('#e2').find('option').remove().end();
            // check if current selected value is a valid profile name
            // if not, update with first available profile name
            var valid_profile_names = profiles.map(function(a) {return a.name;});
            if (valid_profile_names.length > 0 &&
                    $.inArray(selected_profile_name, valid_profile_names) === -1) {
                selected_profile = 0;
                selected_profile_name = valid_profile_names[0];
            }

            // fill select with new options from websocket
            for (var i=0; i<profiles.length; i++) {
                var profile = profiles[i];
                //console.log(profile.name);
                $('#e2').append('<option value="' + i + '">' + profile.name + '</option>');

                if (profile.name == selected_profile_name) {
                    selected_profile = i;
                    $('#e2').select2('val', i);
                    updateProfile(i);
                }
            }
        };

        $("#e2").select2( {
            placeholder: "Select Profile",
            allowClear: true,
            minimumResultsForSearch: -1
        });

        $("#e2").on("change", function(e) {
            updateProfile(e.val);
        });
    }
});
