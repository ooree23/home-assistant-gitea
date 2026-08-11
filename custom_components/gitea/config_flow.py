"""Config flow pour l'intégration Gitea."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
)

DOMAIN = "gitea"

class GiteaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration depuis l'interface Home Assistant."""

    async def async_step_user(self, user_input=None):
        """Étape initiale d'ajout."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"Gitea ({user_input[CONF_HOST]})",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_PROTOCOL, default="https"): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=3000): int,
                vol.Required(CONF_TOKEN): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)