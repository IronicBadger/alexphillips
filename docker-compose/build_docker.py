#!/usr/bin/env python3

import os, yaml, re, sys, requests
from os import listdir
from os.path import isfile, join

if (len(sys.argv) < 2):
    print("Must specify nginx conf directory")
    quit()

nginx_dir = os.path.abspath(sys.argv[1])

with open('docker-compose.yml', 'r') as fh:
    contents = yaml.load(fh, Loader=yaml.FullLoader)

if contents is None:
    print("No docker-compose.yml file found.")
    quit()

print("Removing existing nginx confs from {}...".format(nginx_dir))
for conf in [f for f in listdir(nginx_dir) if isfile(os.path.join(nginx_dir, f))]:
    conf = os.path.join(nginx_dir, conf)

    if re.search(r'\.keep\.', conf):
        continue

    if not re.search(r'\.conf$', conf):
        continue

    os.remove(conf)

with open('nginx.template') as f:
    template = f.read()

onlyfiles = [f for f in listdir('.') if isfile(join('.', f))]
for filename in onlyfiles:
    if re.search(r'^docker-compose', filename):
        continue
    if not re.search(r'\.ya?ml$', filename):
        continue

    with open(filename, 'r') as fh:
        contents = yaml.load(fh, Loader=yaml.FullLoader)

    if contents is None:
        continue

    for service_name in contents['services']:
        service = contents['services'][service_name]
        if 'labels' not in service:
            continue

        conf = None
        labels = dict(label.split('=') for label in service['labels'])

        # if 'template' in labels:
        # fetch the template contents
        print("Attempting to fetch conf for {}...".format(service_name))
        conf_resp = requests.get('https://raw.githubusercontent.com/linuxserver/reverse-proxy-confs/master/{}.subdomain.conf.sample'.format(labels['template'] if 'template' in labels else service_name))
        if conf_resp.status_code == 200:
            print("  Found config template for {}".format(service_name))
            conf = conf_resp.text
            conf = re.sub("server_name\s+.+?;", "server_name {};".format(labels['host']), conf)

            if 'port' in labels:
                conf = re.sub("upstream_port \d+;", "upstream_port {};".format(labels['port']), conf)
            if 'protocol' in labels:
                conf = re.sub("upstream_proto \w+;", "upstream_proto {};".format(labels['protocol']), conf)
            if 'upstream' in labels:
                conf = re.sub("upstream_app \w+;", "upstream_app {};".format(labels['upstream']), conf)
            if 'auth' in labels:
                conf = re.sub("^}", "\tinclude /config/nginx/2fa.conf;\n}", conf)
        else:
            print("  ERROR: No template found for {}".format(service_name))

        if conf is None and 'port' in labels:
            print("  Generating config from template for {}".format(service_name))
            host = labels['host']
            port = labels['port']
            protocol = labels['protocol'] if 'protocol' in labels else 'http'

            conf = template.replace("[[host]]", host)
            conf = conf.replace("[[port]]", port)
            conf = conf.replace("[[protocol]]", protocol)
            conf = conf.replace("[[service]]", labels['upstream'] if 'upstream' in labels else service_name)

            if 'auth' in labels:
                conf = conf.replace('[[auth]]', 'include /config/nginx/2fa.conf;')
            else:
                conf = conf.replace('[[auth]]', '')

        if conf is not None:
            with open(os.path.join(nginx_dir, "{}-generated.subdomain.conf".format(service_name)), "w") as f:
                f.write(conf)