#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2014 Telefónica Investigación y Desarrollo, S.A.U
#
# This file is part of FI-WARE project.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# You may obtain a copy of the License at:
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For those usages not covered by the Apache version 2.0 License please
# contact with opensource@tid.es
#
__author__ = 'arobres'

import requests

from fiware_cloto.cloto.tests.acceptance_tests.commons.configuration import TENANT_ID, USER, PASSWORD, KEYSTONE_URL


def get_token():
    body = '{"auth": {"tenantName": "%s", "passwordCredentials":{"username": "%s", "password": "%s"}}}' \
           % (TENANT_ID, USER, PASSWORD)
    headers = {'content-type': 'application/json', 'Accept': 'application/json'}
    r = requests.request(method='post', url=KEYSTONE_URL, data=body, headers=headers)
    response = r.json()
    token_id = response['access']['token']['id']
    tenant_id = response['access']['token']['tenant']['id']
    return token_id, tenant_id