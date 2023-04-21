"""The OpenAI sensor"""

import openai
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant, callback
import logging


_LOGGER = logging.getLogger(__name__)

ATTR_MODEL = "model"
ATTR_MOOD = "mood"
ATTR_PROMPT = "prompt"
CONF_MODEL = "model"
CONF_MOOD = "mood"
DEFAULT_NAME = "hassio_openai_response"
DEFAULT_MODEL = "gpt-3.5-turbo"
DEFAULT_MOOD = "You are a helpful assistant"
DOMAIN = "openai_response"
SERVICE_OPENAI_INPUT = "openai_input"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): cv.string,
        vol.Optional(CONF_MOOD, default=DEFAULT_MOOD): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Setting up the sensor"""
    api_key = config[CONF_API_KEY]
    name = config[CONF_NAME]
    model = config[CONF_MODEL]
    mood = config[CONF_MOOD]

    openai.api_key = api_key

    sensor = OpenAIResponseSensor(hass, name, model, mood)
    async_add_entities([sensor], True)

    @callback
    async def async_generate_openai_request(service):
        """Handling service call"""
        _LOGGER.debug(service.data)
        sensor.request_running(
            service.data.get(ATTR_MODEL, config[CONF_MODEL]),
            service.data.get(ATTR_PROMPT),
            service.data.get(ATTR_MOOD, config[CONF_MOOD]),
        )
        response = await hass.async_add_executor_job(
            generate_openai_response_sync,
            service.data.get(ATTR_MODEL, config[CONF_MODEL]),
            service.data.get(ATTR_PROMPT),
            service.data.get(ATTR_MOOD, config[CONF_MOOD]),
        )
        _LOGGER.debug(response)
        sensor.response_received(response["choices"][0]["message"]["content"])

    hass.services.async_register(
        DOMAIN, SERVICE_OPENAI_INPUT, async_generate_openai_request
    )
    return True


def generate_openai_response_sync(model: str, prompt: str, mood: str):
    """Do the real OpenAI request"""
    _LOGGER.debug("Model: %s, Mood: %s, Prompt: %s", model, mood, prompt)
    return openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": mood},
            {"role": "user", "content": prompt},
        ],
    )


class OpenAIResponseSensor(SensorEntity):
    """The OpenAI sensor"""

    def __init__(self, hass: HomeAssistant, name: str, model: str, mood: str) -> None:
        self._hass = hass
        self._name = name
        self._model = model
        self._default_mood = mood
        self._mood = None
        self._prompt = None
        self._attr_native_value = None
        self._response_text = ""

    @property
    def name(self):
        return self._name

    @property
    def extra_state_attributes(self):
        return {
            "response_text": self._response_text,
            "mood": self._mood,
            "prompt": self._prompt,
            "model": self._model,
        }

    def request_running(self, model, prompt, mood=None):
        """Staring a new request"""
        self._model = model
        self._prompt = prompt
        self._mood = mood or self._default_mood
        self._response_text = ""
        self._attr_native_value = "requesting"
        self.async_write_ha_state()

    def response_received(self, response_text):
        """Updating the sensor state"""
        self._response_text = response_text
        self._attr_native_value = "response_received"
        self.async_write_ha_state()

    async def async_generate_openai_response(self, entity_id, old_state, new_state):
        """Updating the sensor from the input_text"""
        new_text = new_state.state

        if new_text:
            self.request_running(self._model, new_text)
            response = await self._hass.async_add_executor_job(
                generate_openai_response_sync,
                self._model,
                new_text,
                self._mood,
            )
            self.response_received(response["choices"][0]["message"]["content"])

    async def async_added_to_hass(self):
        """Added to hass"""
        self.async_on_remove(
            self._hass.helpers.event.async_track_state_change(
                "input_text.gpt_input", self.async_generate_openai_response
            )
        )

    async def async_update(self):
        """Ignore other updates"""
        pass
