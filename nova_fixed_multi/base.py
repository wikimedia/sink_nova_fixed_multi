# Copyright 2015 Andrew Bogott for the Wikimedia Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


# This is a slight form of the designate source file found at
# designate/notification_handler/base.py

import abc
from oslo.config import cfg
from designate import exceptions
from designate.openstack.common import log as logging
from designate.central import rpcapi as central_rpcapi
from designate.context import DesignateContext
from designate.notification_handler.base import BaseAddressHandler
from designate.notification_handler.base import get_ip_data
from designate.plugin import ExtensionPlugin

LOG = logging.getLogger(__name__)
central_api = central_rpcapi.CentralAPI()


class BaseAddressMultiHandler(BaseAddressHandler):
    def _create(self, addresses, extra, managed=True,
                resource_type=None, resource_id=None):
        """
        Create a a record from addresses

        :param addresses: Address objects like
                          {'version': 4, 'ip': '10.0.0.1'}
        :param extra: Extra data to use when formatting the record
        :param managed: Is it a managed resource
        :param resource_type: The managed resource type
        :param resource_id: The managed resource ID
        """
        LOG.debug('Using DomainID: %s' % cfg.CONF[self.name].domain_id)
        domain = self.get_domain(cfg.CONF[self.name].domain_id)
        LOG.debug('Domain: %r' % domain)

        data = extra.copy()
        LOG.debug('Event data: %s' % data)
        data['domain'] = domain['name']

        context = DesignateContext.get_admin_context(all_tenants=True)

        for addr in addresses:
            event_data = data.copy()
            event_data.update(get_ip_data(addr))

            if addr['version'] == 4:
                reverse_format = cfg.CONF[self.name].get('reverse_format')
                reverse_domain_id = cfg.CONF[self.name].get('reverse_domain_id')
                if reverse_format and reverse_domain_id:
                    reverse_domain = self.get_domain(reverse_domain_id)
                    LOG.debug('Reverse domain: %r' % reverse_domain)

                    ip_digits = addr['address'].split('.')
                    ip_digits.reverse()
                    name = "%s.in-addr.arpa." % '.'.join(ip_digits)

                    recordset_values = {
                        'domain_id': reverse_domain['id'],
                        'name': name,
                        'type': 'PTR',
                    }
                    recordset = self._find_or_create_recordset(
                        context, **recordset_values)

                    record_values = { 'data': reverse_format % event_data }

                    if managed:
                        record_values.update({
                            'managed': managed,
                            'managed_plugin_name': self.get_plugin_name(),
                            'managed_plugin_type': self.get_plugin_type(),
                            'managed_resource_type': resource_type,
                            'managed_resource_id': resource_id})

                    LOG.debug('Creating record in %s / %s with values %r',
                              reverse_domain['id'], recordset['id'], record_values)
                    central_api.create_record(context,
                                              reverse_domain['id'],
                                              recordset['id'],
                                              record_values)

            for fmt in cfg.CONF[self.name].get('format'):
                recordset_values = {
                    'domain_id': domain['id'],
                    'name': fmt % event_data,
                    'type': 'A' if addr['version'] == 4 else 'AAAA'}

                recordset = self._find_or_create_recordset(
                    context, **recordset_values)

                record_values = {
                    'data': addr['address']}

                if managed:
                    record_values.update({
                        'managed': managed,
                        'managed_plugin_name': self.get_plugin_name(),
                        'managed_plugin_type': self.get_plugin_type(),
                        'managed_resource_type': resource_type,
                        'managed_resource_id': resource_id})

                LOG.debug('Creating record in %s / %s with values %r',
                          domain['id'], recordset['id'], record_values)
                central_api.create_record(context,
                                          domain['id'],
                                          recordset['id'],
                                          record_values)
