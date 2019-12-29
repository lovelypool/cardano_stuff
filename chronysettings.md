## Prometheus/Grafana and Chrony Tuning Guide for Cardano Stake Pool Operators

###### Shout out and thank you goes out to @ilap for his first mention of time synchronized drift.

### Pre-Requisites

##### You must install and run the following software on your node:
  - **Jormungandr** (v0.8.5 is the latest as of last article edit) (accessible globally in your $PATH)
  - **JCLI** (accessible globally in your $PATH)
  - **Prometheus** (wget the links from here in terminal, extract and run binary https://prometheus.io/download/)
  - **Prometheus Node Exporter** (download form above link, search node exporter)
  - **Grafana** (https://grafana.com/grafana/download)
  - Download the **monitoring repo** from the **IOHK jormungandr-nix repo**:  https://github.com/input-output-hk/jormungandr-nix/tree/master/nixos/jormungandr-monitor
  - **Chrony** (sudo apt-get install chrony)

### Quick Setup
Note - you do not need to install the jormungandr datasource to tune your time synchronized drift.  You may ignore all jormungandr related information if all you want to do is experiment with time drift.  Adding the jormungandr datasource allows you to also monitor and log your node stats, such as uptime and block height, into a time series database for review in the future.

1. Your Prometheus YAML config file needs to include the following for the new "jormungandr" datasource, as well as the "node exporter" data source
```  
  - job_name: 'node_exporter'
    static_configs:
    - targets: ['localhost:9100']
  - job_name: 'jormungandr'
    static_configs:
    - targets: ['localhost:8000']
```
2. Change your Grafana or Jormungandr from port 3000.  They both use port 3000 as default.

3. If you are running this on a server w/ terminal only access, you will need to SSH tunnel into your server's web server ports in order to access the grafana webpage on your local machine:
```
ssh -N -L PORT2TUNNEL:127.0.0.1:PORT2TUNNEL root@serveripaddress

Example for grafana (port 3000 is default, change to 3001 so it doesnt collide with Jormungandr default port)
ssh -N -L 3001:127.0.0.1:3001 root@serveripaddress

You can now enter 127.0.0.1:3001 to access Grafana web server from your local web browser
```

4. The Prometheus Node Exporter is the service that provides the "Time Synchronized Drift" data.

![Drift Result Image](https://raw.githubusercontent.com/lovelypool/cardano_stuff/master/drift1.png)

You can find import the Grafana dashboard that has this graph for Node Exporter by importing this into Grafana: https://grafana.com/grafana/dashboards/1860


5. Make sure you can see your jormungandr job and node_exporter job "Targets" in the Prometheus dashboard (port 9090), under Status->Targets.  It may take 15 seconds to appear upon starting Prometheus, as that is the default "scrape rate" for data collection.
[picture to come soon]

6. Add the node_exporter and jormungandr datasource in Grafana.  

For now, please watch this excellent straightforward youtube video for a great tutorial on how to install Prometheus, Grafana, and Node Exporter: https://www.youtube.com/watch?v=4WWW2ZLEg74

7. Edit your chrony configuration file: 
```
sudo nano /etc/chrony/chrony.conf
```

8. The recommended settings from Ilap are as follows:

```# 3 sources per time servers.
pool ntp.ubuntu.com        iburst maxsources 3
pool time.nist.gov         iburst maxsources 3
pool us.pool.ntp.org       iburst maxsources 3

keyfile /etc/chrony/chrony.keys

driftfile /var/lib/chrony/chrony.drift

logdir /var/log/chrony

maxupdateskew 10.0

rtcsync

# Make steps in 100ms.
makestep 0.1 3
````

After experimenting with these settings, it looks like we need to make some modifications.  The time synchronized drift is pretty good (20-50msec) at the start, but over time, the slew rate of the time correction changes, and your time drift will slowly get worse and worse again until its back to where it was before we made any correction.

This seemed very irregular and I wanted to try and understand what was the cause and to fix it so we can get latency <10msec.

![Drift Result Image](https://raw.githubusercontent.com/lovelypool/cardano_stuff/master/drift2.png)

First, run the command:
```
chronyc sources
```
This shows you the current servers that are being used for time syncing and their associated drift.

I found that the recommended pools in the config file above do not have the best drift for my server.  Instead, I found that google's NTP time server provides the best latency so far:

```
pool time.google.com
```

On average, the pools from Ubuntu and the .gov/.org servers were giving me 20-60msec drift.  Google, however is <10msec on all connections for my server.  So, I commented out all other pools for now except Google.

***iburst*** means that chrony will try to synchronize to the time servers very fast at the beginning, but will over time get slower and slower if no polling rate is set.  So, we make the following modifications to set a constant min and max polling rate, as well as allow synchronization on any clock cycle, and not just at the start of chronyd:

```
#pool ntp.ubuntu.com        iburst maxsources 3
pool time.google.com       iburst minpoll 1 maxpoll 2 maxsources 3
#pool time.nist.giv         iburst maxsources 3
#pool us.pool.ntp.org       iburst maxsources 3

# Step the system clock instead of slewing it if the adjustment is larger than
# 0.1 second, on any clock update (-1)    // (3) in the first three clock updates.
makestep 0.1 -1
```

A few more modifications were added.  Here is my complete chrony.conf file:

```
# ool ntp.ubuntu.com        iburst maxsources 3
pool time.google.com       iburst minpoll 1 maxpoll 2 maxsources 3
# pool time.nist.giv         iburst maxsources 3
# pool us.pool.ntp.org       iburst maxsources 3

# This directive specify the location of the file containing ID/key pairs for
# NTP authentication.
keyfile /etc/chrony/chrony.keys

# This directive specify the file into which chronyd will store the rate
# information.
driftfile /var/lib/chrony/chrony.drift

# Uncomment the following line to turn logging on.
#log tracking measurements statistics

# Log files location.
logdir /var/log/chrony

# Stop bad estimates upsetting machine clock.
maxupdateskew 5.0

# This directive enables kernel synchronisation (every 11 minutes) of the
# real-time clock. Note that it can’t be used along with the 'rtcfile' directive.
rtcsync

# Step the system clock instead of slewing it if the adjustment is larger than
# 0.1 seconds, on any clock update.
makestep 0.1 -1

# Get TAI-UTC offset and leap seconds from the system tz database.
leapsectz right/UTC

# Serve time even if not synchronized to a time source.
local stratum 10
```


The results are excellent!!

![Drift Result Image](https://raw.githubusercontent.com/lovelypool/cardano_stuff/master/drift3.png)

We are now stable at 7.5ms with a nice even synchronization period!

![Drift Result Image2](https://raw.githubusercontent.com/lovelypool/cardano_stuff/master/drift4.png)
