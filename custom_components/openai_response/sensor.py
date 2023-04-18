import openai
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
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
# DOMAIIN = "openai"
SERVICE_OPENAI_INPUT = "openai_input"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): cv.string,
        vol.Optional(CONF_MOOD, default=DEFAULT_MOOD): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    api_key = config[CONF_API_KEY]
    name = config[CONF_NAME]
    model = config[CONF_MODEL]
    mood = config[CONF_MOOD]

    openai.api_key = api_key

    sensor = OpenAIResponseSensor(hass, name, model, mood)
    async_add_entities([sensor], True)

    @callback
    async def async_generate_openai_request(service):
        _LOGGER.error(service)
        _LOGGER.error(service.data)
        response = await hass.async_add_executor_job(
            generate_openai_response_sync,
            service.data.get(ATTR_MODEL, config[CONF_MODEL]),
            service.data.get(ATTR_PROMPT),
            service.data.get(ATTR_MOOD, config[CONF_MOOD]),
        )
        _LOGGER.error(response)
        sensor._response_text = response["choices"][0]["message"]["content"]
        sensor._state = "response_received"
        sensor.async_write_ha_state()

    hass.services.async_register(
        "openai", SERVICE_OPENAI_INPUT, async_generate_openai_request
    )


def generate_openai_response_sync(model, prompt, mood):
    _LOGGER.error("Model: %s, Mood: %s, Prompt: %s", model, mood, prompt)
    return openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": mood},
            {"role": "user", "content": prompt},
        ],
    )


class OpenAIResponseSensor(SensorEntity):
    def __init__(self, hass, name, model, mood):
        self._hass = hass
        self._name = name
        self._model = model
        self._default_mood = mood
        self._mood = None
        self._state = None
        self._response_text = ""

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {"response_text": self._response_text, "mood": self._mood}

    async def async_generate_openai_response(
        self, entity_id, old_state, new_state, mood=None
    ):
        new_text = new_state.state
        self._mood = mood or self._default_mood

        if new_text:
            response = await self._hass.async_add_executor_job(
                generate_openai_response_sync,
                self._model,
                new_text,
                self._mood,
            )
            self._response_text = response["choices"][0]["message"]["content"]
            self._state = "response_received"
            self.async_write_ha_state()

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._hass.helpers.event.async_track_state_change(
                "input_text.gpt_input", self.async_generate_openai_response
            )
        )

    async def async_update(self):
        pass
