import re
import textwrap
from unittest import mock

import pytest

from hart.exceptions import UserError
from hart.providers import DOProvider, EC2Provider
from hart.roles import get_minion_arguments_for_role, build_minion_id


def test_get_minion_arguments_provider_inheritance(named_tempfile):
    named_tempfile.write(textwrap.dedent('''
        [hart]
        saltmaster = "salt.example.com"
        role_naming_scheme = "{role}.{provider}.example.com"
        salt_branch = "3001"

        [roles.myrole]
        private_networking = true

        [roles.myrole.ec2]
        region = "eu-central-1"
        size = "t3.nano"
        zone = "eu-central-1a"
    ''').encode('utf-8'))
    named_tempfile.close()

    provider = EC2Provider('key_id', 'secret_key')
    arguments = get_minion_arguments_for_role(named_tempfile.name, 'myrole', provider=provider)
    assert arguments == {
        'minion_id': 'myrole.ec2.example.com',
        'provider': provider,
        'region': 'eu-central-1',
        'size': 't3.nano',
        'private_networking': True,
        'salt_branch': '3001',
        'minion_config': {
            'master': 'salt.example.com',
            'master_tries': -1,
            'grains': {
                'roles': [
                    'myrole',
                ],
            },
        },
    }


def test_get_minion_arguments_region_inheritance(named_tempfile):
    named_tempfile.write(textwrap.dedent('''
        [hart]
        saltmaster = "salt.example.com"
        role_naming_scheme = "{role}.{provider}.example.com"
        salt_branch = "3002"

        [roles.myrole.do]
        size = "s-v2vcpu-2gb"

        [roles.myrole.do.sfo3]
        private_networking = true
        size = "s-4vcpu-4gb"
    ''').encode('utf-8'))
    named_tempfile.close()

    provider = DOProvider('foo')
    arguments = get_minion_arguments_for_role(named_tempfile.name, 'myrole',
        provider=provider, region='sfo3')
    assert arguments == {
        'minion_id': 'myrole.do.example.com',
        'provider': provider,
        'region': 'sfo3',
        'size': 's-4vcpu-4gb',
        'private_networking': True,
        'salt_branch': '3002',
        'minion_config': {
            'master': 'salt.example.com',
            'master_tries': -1,
            'grains': {
                'roles': [
                    'myrole',
                ],
            },
        },
    }


def test_get_minion_arguments_for_invalid_role(named_tempfile):
    named_tempfile.write(textwrap.dedent('''
        [roles.myrole]
        private_networking = true
    ''').encode('utf-8'))
    named_tempfile.close()

    with pytest.raises(UserError, match="Unknown role 'foo', must be one of 'myrole'"):
        get_minion_arguments_for_role(named_tempfile.name, 'foo')


def test_get_minion_arguments_for_invalid_role_no_roles(named_tempfile):
    with pytest.raises(UserError, match="Unknown role 'foo', no roles defined in config"):
        get_minion_arguments_for_role(named_tempfile.name, 'foo')


def test_build_templated_minion_id():
    assert build_minion_id('{role}.{zone}.{provider}.example',
        role='foo',
        zone='bar',
        provider='ec2',
    ) == 'foo.bar.ec2.example'


def test_build_unique_minion_id():
    minion_id = build_minion_id('{unique_id}.example')
    assert re.match(r'^[a-f0-9]{8}\.example$', minion_id) is not None


def test_build_minion_id_invalid_parameter():
    with pytest.raises(UserError, match=r"Invalid minion id template variable {foo}, must be one of {role}, {unique_id}"):
        build_minion_id('{foo}', role='1')



def test_get_minion_arguments_without_provider(named_tempfile):
    named_tempfile.write(textwrap.dedent('''
        [roles.myrole]
        private_networking = true
        provider = "do"
        size = "s-1vcpu-1gb"
        region = "sfo3"

        [providers.do]
        token = "foo"
    ''').encode('utf-8'))
    named_tempfile.close()

    with mock.patch('hart.roles.get_unique_id', lambda: 'unique'):
        arguments = get_minion_arguments_for_role(named_tempfile.name, 'myrole')
    assert arguments['minion_id'] == 'unique.sfo3.do.myrole'
    assert isinstance(arguments['provider'], DOProvider)
    assert arguments['region'] == 'sfo3'
    assert arguments['size'] == 's-1vcpu-1gb'
    assert arguments['private_networking'] == True
    assert arguments['minion_config'] == {
        'master_tries': -1,
        'grains': {
            'roles': [
                'myrole',
            ]
        },
    }


def test_get_minion_arguments_with_minion_config(named_tempfile):
    named_tempfile.write(textwrap.dedent('''
        [hart.minion_config.grains]
        "environment" = "prod"

        [roles.myrole]
        region = "sfo3"
    ''').encode('utf-8'))
    named_tempfile.close()

    arguments = get_minion_arguments_for_role(named_tempfile.name, 'myrole', provider=DOProvider('foo'))
    assert arguments['minion_config'] == {
        'master_tries': -1,
        'grains': {
            'environment': 'prod',
            'roles': [
                'myrole',
            ],
        },
    }
