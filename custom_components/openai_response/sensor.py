import openai
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback


CONF_MODEL = "model"
DEFAULT_NAME = "hassio_openai_response"
DEFAULT_MODEL = "text-davinci-003"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    api_key = config[CONF_API_KEY]
    name = config[CONF_NAME]
    model = config[CONF_MODEL]

    openai.api_key = api_key

    async_add_entities([OpenAIResponseSensor(hass, name, model)], True)


def generate_openai_response_sync(model, prompt, temperature, max_tokens, top_p, frequency_penalty, presence_penalty):
    return openai.Completion.create(
        model=model,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
    )


class OpenAIResponseSensor(SensorEntity):
    def __init__(self, hass, name, model):
        self._hass = hass
        self._name = name
        self._model = model
        self._state = None
        self._prompt = ""
        self._response_text = ""

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {"prompt": self._prompt, "response_text": self._response_text}

    async def async_generate_openai_response(self, entity_id, old_state, new_state):
        new_text = new_state.state
        if new_text:
            response = await self._hass.async_add_executor_job(
                generate_openai_response_sync,
                self._model,
                new_text,
                0.9,
                964,
                1,
                0,
                0
            )
            self._prompt = new_text
            self._response_text = response["choices"][0]["text"]
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
