"""Signal notifications via a separately configured signal-cli-rest-api service."""
from urllib.parse import urlsplit

import requests

from flathunter.abstract_notifier import Notifier
from flathunter.abstract_processor import Processor
from flathunter.exceptions import ConfigException


class SenderSignal(Processor, Notifier):
    """Send listing and heartbeat messages using the Signal REST API."""

    def __init__(self, config):
        self.config = config
        api_url = config.signal_api_url()
        self.number = config.signal_number()
        self.recipients = config.signal_recipients()
        if (not isinstance(api_url, str) or
                urlsplit(api_url).scheme not in ('http', 'https') or
                not urlsplit(api_url).netloc):
            raise ConfigException('signal.api_url must be an HTTP(S) base URL')
        if not isinstance(self.number, str) or not self.number.strip():
            raise ConfigException('signal.number must be a quoted Signal account number')
        if (not isinstance(self.recipients, list) or not self.recipients or
                any(not isinstance(value, str) or not value.strip() for value in self.recipients)):
            raise ConfigException('signal.recipients must be a non-empty list of quoted recipients')
        self.send_url = api_url.rstrip('/') + '/v2/send'

    def process_expose(self, expose):
        """Send an expose with the configured message template."""
        self.notify(self.config.message_format().format(
            **dict(expose, durations=expose.get('durations', ''))).strip())
        return expose

    def notify(self, message):
        """Send text; propagate transport and HTTP errors to the caller."""
        response = requests.post(self.send_url, json={
            'message': message,
            'number': self.number,
            'recipients': self.recipients,
        }, timeout=30)
        response.raise_for_status()
