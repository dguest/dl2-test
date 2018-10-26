#!/usr/bin/env python3

from argparse import ArgumentParser
import json
import sys

def get_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('inputs_file')
    parser.add_argument('-t','--translator', default='mvtm2edm.json')
    return parser.parse_args()

def run():
    args = get_args()
    with open(args.inputs_file) as inputs:
        old_inputs = json.load(inputs)

    if args.translator:
        with open(args.translator) as tr:
            translations = json.load(tr)
        for invar in old_inputs['inputs']:
            invar['name'] = translations[invar['name']]

    sys.stdout.write(json.dumps(old_inputs, indent=2) + '\n')

if __name__ == '__main__':
    run()
