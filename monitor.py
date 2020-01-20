#!/usr/bin/env python

from prometheus_client import Gauge
from prometheus_client import Summary
from prometheus_client import start_http_server
from dateutil.parser import parse
import time, sys, warnings, os, traceback, subprocess, json
import math, datetime
import configparser as ConfigParser

chainstartdate = 1576264417
height=0
heightold=0
slotlatency=0
lastslotdelta=0
slotdelta=0
heightdelta=0
lastheightdelta=0

EXPORTER_PORT = int(os.getenv('PORT', '8000'), 10)
SLEEP_TIME = 1
JORMUNGANDR_API = os.getenv('JORMUNGANDR_RESTAPI_URL',
                  os.getenv('JORMUNGANDR_API', 'http://127.0.0.1:3100/api'))
os.environ['JORMUNGANDR_RESTAPI_URL'] = JORMUNGANDR_API
ADDRESSES = os.getenv('MONITOR_ADDRESSES', '').split()
NODE_METRICS = [
    "total_stake",
    "value_taxed",
    "value_for_stakers",
    "thisepochstake",
    "total_stake2",
    "value_taxed2",
    "value_for_stakers2",
    "thisepochstake2",
    "blockRecvCnt",
    "lastBlockDate",
    "lastBlockFees",
    "lastBlockHash",
    "lastBlockHeight",
    "lastBlockSum",
    "lastBlockTime",
    "lastBlockTx",
    "txRecvCnt",
    "uptime",
    "connections",
    "lastBlockEpoch",
    "lastBlockSlot",
    "currentslot",
    "slotdelta",
    "slotlatency",
    "heightdelta"
]
PIECE_METRICS = [
    "lastBlockHashPiece1",
    "lastBlockHashPiece2",
    "lastBlockHashPiece3",
    "lastBlockHashPiece4",
    "lastBlockHashPiece5",
    "lastBlockHashPiece6",
    "lastBlockHashPiece7",
    "lastBlockHashPiece8"
]
NaN = float('NaN')


def metric_gauge(metric):
    return Gauge(f'jormungandr_{metric}', 'Jormungandr {metric}')


def piece_gauge(metric):
    return Gauge(f'jormungandr_{metric}', 'Jormungandr {metric}')


jormungandr_metrics = {metric: metric_gauge(metric) for metric in NODE_METRICS}
jormungandr_pieces = {metric: piece_gauge(metric) for metric in PIECE_METRICS}

jormungandr_funds = Gauge(f'jormungandr_address_funds',
                                 f'Jomungandr Address funds in Lovelace',
                                 ['addr'])
jormungandr_counts = Gauge(f'jormungandr_address_counts',
                                 f'Jomungandr Address counter',
                                 ['addr'])

to_reset = [
    jormungandr_metrics,
    jormungandr_pieces
]

to_reset_with_labels = [
    jormungandr_funds,
    jormungandr_counts
]


JORMUNGANDR_METRICS_REQUEST_TIME = Summary(
    'jormungandr_metrics_process_time',
    'Time spent processing jormungandr metrics')


# Decorate function with metric.
@JORMUNGANDR_METRICS_REQUEST_TIME.time()
def process_jormungandr_metrics():

    # Process jcli returned metrics
    metrics = jcli_rest(['node', 'stats', 'get'])

    metrics['connections'] = 0#len(jcli_rest(['network', 'stats', 'get']))

    try:
        metrics['lastBlockTime'] = parse(metrics['lastBlockTime']).timestamp()
    except:
        print(f'failed to parse lastBlockTime: {metrics["lastBlockTime"]}')
        metrics['lastBlockTime'] = NaN

    try:
        metrics['lastBlockEpoch'] = metrics['lastBlockDate'].split('.')[0]
        metrics['lastBlockSlot'] = metrics['lastBlockDate'].split('.')[1]
    except:
        print(f'failed to parse lastBlockDate into pieces: {metrics["lastBlockDate"]}')

    # get stake pool metrics
    metrics2 = jcli_rest(['stake-pool', 'get', '8c92fb7b01d78e9974d3a146ac144597303dc6419cf90062456deb8140e3a81b'])
    #print(metrics2['rewards']['value_for_stakers']/1000000)
    metrics['total_stake']=metrics2['total_stake']/1000000
    metrics['value_for_stakers']=metrics2['rewards']['value_for_stakers']/1000000
    metrics['value_taxed']=metrics2['rewards']['value_taxed']/1000000

    # get stake pool metrics
    metrics3 = jcli_rest(['stake-pool', 'get', 'a57ba451ea1af35bb07042640345d873b6076509536f71a2dcd23e5d4612174f'])
    #print(metrics2['rewards']['value_for_stakers']/1000000)
    metrics['total_stake2']=metrics3['total_stake']/1000000
    metrics['value_for_stakers2']=metrics3['rewards']['value_for_stakers']/1000000
    metrics['value_taxed2']=metrics3['rewards']['value_taxed']/1000000

    try:
       os.system('jcli rest v0 node stats get --host "http://127.0.0.1:3100/api" > nodestatsx')
    except:
        donothing=0
            
    fin = open("nodestatsx", "rt")
    data = fin.read()
    data = data.replace(': ', '= ')
    data = data.replace('---', '[nodestats]')
    fin.close()

    fin = open("nodestatsx", "wt")
    fin.write(data)
    fin.close()

    config = ConfigParser.ConfigParser()
    config.read("nodestatsx")

    global height
    global heightold
    global heightdelta
    global lastheightdelta

    heightold = height
    height = config.get("nodestats", "lastBlockHeight")
    height = height[1:]
    height = height[:-1]
    height = int(height)
    heightdelta=height-heightold
    if heightdelta == 0:
        heightdelta=1
    else:
        donothing=0 

    global slotlatency
    global lastslotdelta
    global slotdelta

    #get time
    nowtime = int(datetime.datetime.now().strftime("%s"))
    chaintime = nowtime - chainstartdate
    currentslot = int(math.floor((chaintime % 86400) / 2))
    metrics['currentslot'] = currentslot
    lastslot=float(metrics['lastBlockSlot'])
    lastslotdelta=slotdelta
    slotdelta=currentslot-lastslot
    metrics['slotdelta']=slotdelta
    
    if slotdelta < lastslotdelta:
        slotlatency=slotdelta
        metrics['slotlatency'] = slotlatency
        lastheightdelta=heightdelta
        metrics['heightdelta']=lastheightdelta
    else:
        metrics['slotlatency'] = slotlatency
        metrics['heightdelta']=lastheightdelta



    try:
        epochstakecommand = "jcli rest v0 stake get --host " + "http://127.0.0.1:3100/api" + \
            " | grep -A 1 8c92fb7b01d78e9974d3a146ac144597303dc6419cf90062456deb8140e3a81b | sed -e 's/-//g' | sed -e 's/8c92fb7b01d78e9974d3a146ac144597303dc6419cf90062456deb8140e3a81b//g' | sed -r '/^\s*$/d' | awk '{$1=$1;print}' > thisepochstake"
        os.system(epochstakecommand)
    except:
        print("failed to grab current stake")
        
    with open('thisepochstake') as f:
        try:
            thisepochstake = float(f.readline()) / 1000000
        except:
            print("something wrong, "), thisepochstake
        # get epoch number
        
    metrics['thisepochstake'] = thisepochstake

    try:
        epochstakecommand2 = "jcli rest v0 stake get --host " + "http://127.0.0.1:3100/api" + \
            " | grep -A 1 a57ba451ea1af35bb07042640345d873b6076509536f71a2dcd23e5d4612174f | sed -e 's/-//g' | sed -e 's/a57ba451ea1af35bb07042640345d873b6076509536f71a2dcd23e5d4612174f//g' | sed -r '/^\s*$/d' | awk '{$1=$1;print}' > thisepochstake2"
        os.system(epochstakecommand2)
    except:
        print("failed to grab current stake")
        
    with open('thisepochstake2') as f:
        try:
            thisepochstake2 = float(f.readline()) / 1000000
        except:
            thisepochstake2=0
            print("something wrong, "), thisepochstake2
        # get epoch number
        
    metrics['thisepochstake2'] = thisepochstake2
    
    for metric, gauge in jormungandr_metrics.items():
        gauge.set(sanitize(metrics[metric]))

    # Process pieced metrics from jcli parent metrics
    try:
        blockHashPieces = {}
        lastBlockHashProcess = hex(int(metrics['lastBlockHash'],16))[2:]
        for i, (x, y) in enumerate(list(zip(range(-64,8,8),range(-56,8,8))),1):
            if y == 0:
                y = None
            blockHashPieces['lastBlockHashPiece'+str(i)] = int(lastBlockHashProcess[slice(x,y)],16)
        for metric, gauge in jormungandr_pieces.items():
            gauge.set(sanitize(blockHashPieces[metric]))
    except:
        print(f'failed to parse lastBlockHash pieces: {metrics["lastBlockHash"]}')
        for gauge in jormungandr_pieces.values():
            gauge.set(NaN)



JORMUNGANDR_ADDRESSES_REQUEST_TIME = Summary(
    'jormungandr_addresses_process_time',
    'Time spent processing jormungandr addresses')


@JORMUNGANDR_ADDRESSES_REQUEST_TIME.time()
def process_jormungandr_addresses():
    for address in ADDRESSES:
        data = jcli_rest(['account', 'get', address])
        jormungandr_funds.labels(addr=address).set(sanitize(data['value']))
        jormungandr_counts.labels(addr=address).set(sanitize(data['counter']))


def sanitize(metric):
    if isinstance(metric, str):
        try:
            metric = float(metric)
        except ValueError:
            try:
                metric = int(metric, 16)
            except ValueError:
                metric = NaN
    elif not isinstance(metric, (float, int)):
        metric = NaN
    return metric


def jcli_rest(args):
    flags = ['--host', JORMUNGANDR_API, '--output-format', 'json']
    params = ['jcli', 'rest', 'v0'] + args + flags
    result = subprocess.run(params, stdout=subprocess.PIPE)
    return json.loads(result.stdout)


if __name__ == '__main__':
    # Start up the server to expose the metrics.
    print(f"Starting metrics at http://localhost:{EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    # Main Loop: Process all API's and sleep for a certain amount of time
    while True:
        try:
            process_jormungandr_metrics()
            process_jormungandr_addresses()
        except:
            traceback.print_exc(file=sys.stdout)
            print("failed to process jormungandr metrics")
            for d in to_reset:
                for gauge in d.values():
                    gauge.set(NaN)
            for gauge in to_reset_with_labels:
                gauge._metrics.clear()
        time.sleep(SLEEP_TIME)
