"""Signal API requests, configuration and pipeline integration."""
import pytest
import requests

import config_wizard
from flathunter.config import Config, YamlConfig
from flathunter.exceptions import ConfigException
from flathunter.heartbeat import Heartbeat
from flathunter.notifiers import SenderSignal
from flathunter.processor import ProcessorChain


def signal_config(**overrides):
    return YamlConfig({'notifiers': ['signal'], 'signal': {
        'api_url': 'http://localhost:8080/', 'number': '+359888000001',
        'recipients': ['+359888000002', 'group.test'], **overrides}})


@pytest.mark.parametrize('status', [200, 201, 204])
def test_send_text(requests_mock, status):
    requests_mock.post('http://localhost:8080/v2/send', status_code=status)
    SenderSignal(signal_config()).notify('Нова обява')
    assert requests_mock.last_request.json() == {
        'message': 'Нова обява', 'number': '+359888000001',
        'recipients': ['+359888000002', 'group.test']}
    assert requests_mock.last_request.timeout == 30


@pytest.mark.parametrize('status', [400, 401, 500])
def test_http_failure(requests_mock, status):
    requests_mock.post('http://localhost:8080/v2/send', status_code=status)
    with pytest.raises(requests.HTTPError):
        SenderSignal(signal_config()).notify('message')


def test_timeout(requests_mock):
    requests_mock.post('http://localhost:8080/v2/send', exc=requests.Timeout)
    with pytest.raises(requests.Timeout):
        SenderSignal(signal_config()).notify('message')


@pytest.mark.parametrize('overrides', [
    {'api_url': ''}, {'api_url': 'ftp://example.com'}, {'number': 359888000001},
    {'number': ''}, {'recipients': []}, {'recipients': '+359888000002'},
    {'recipients': [123]}, {'recipients': [' ']},
])
def test_invalid_config(overrides):
    with pytest.raises(ConfigException):
        SenderSignal(signal_config(**overrides))


def test_pipeline_and_heartbeat(requests_mock):
    requests_mock.post('http://localhost:8080/v2/send')
    config = signal_config()
    config.config['message'] = '{title} {address} {durations} {url}'
    expose = {'title': 'Дава под наем', 'address': 'София', 'url': 'https://www.imot.bg/'}
    chain = ProcessorChain.builder(config).send_messages().build()
    assert list(chain.process([expose])) == [expose]
    assert requests_mock.last_request.json()['message'] == 'Дава под наем София  https://www.imot.bg/'
    heartbeat = Heartbeat(config, 'hour')
    heartbeat.send_heartbeat(heartbeat.interval)
    assert 'heartbeat' in requests_mock.last_request.json()['message']


def test_environment_overrides(monkeypatch, tmp_path):
    config_file = tmp_path / 'config.yaml'
    config_file.write_text('signal:\n  api_url: http://fallback:8080\n  number: "+123"\n  recipients: ["+456"]\n')
    config = Config(str(config_file))
    assert config.signal_recipients() == ['+456']
    monkeypatch.setenv('FLATHUNTER_SIGNAL_API_URL', 'http://signal:8080')
    monkeypatch.setenv('FLATHUNTER_SIGNAL_NUMBER', '+359888000001')
    monkeypatch.setenv('FLATHUNTER_SIGNAL_RECIPIENTS', '+359888000002, group.test,')
    assert config.signal_api_url() == 'http://signal:8080'
    assert config.signal_number() == '+359888000001'
    assert config.signal_recipients() == ['+359888000002', 'group.test']


def test_wizard(monkeypatch):
    answers = iter(['http://signal:8080', '+123', '+456, group.test'])
    monkeypatch.setattr(config_wizard, 'prompt_with_default', lambda *args: next(answers))
    result = config_wizard.configure_notifier('signal', YamlConfig())
    assert result == {'signal': {'api_url': 'http://signal:8080', 'number': '+123',
                                 'recipients': ['+456', 'group.test']}}
