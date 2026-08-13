"""Platform for sensor integration."""
from datetime import timedelta
import logging
import time
import json
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import (
    CONF_TOKEN,
    CONF_PORT,
    CONF_HOST,
    CONF_PATH,
    CONF_NAME,
    CONF_PROTOCOL,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "gitea"
CONF_REPOS = "repositories"
SCAN_INTERVAL_DISCOVERY = timedelta(minutes=15)

ATTR_REPO_NAME = "Repository"
ATTR_REPO_ID = "ID"
ATTR_DESCRIPTION = "Description"
ATTR_OPEN_ISSUES = "Open issues"
ATTR_DEFAULT_BR = "Branch"
ATTR_OWNER = "Owner"
ATTR_SIZE = "Size"
ATTR_PRIVATE_REPO = "isPrivate"
ATTR_FORK = "Forks"
ATTR_MIRROR = "isMirror"
ATTR_REPO_URL = "Repository Url"
ATTR_STARS = "Stars"
ATTR_WATCH = "Watchers"
ATTR_UPDATED_AT = "Updated at"
ATTR_LAST_ISSUE_LINK = "Last Issue Link"
ATTR_LAST_ISSUE_STATE = "Last Issue Status"
ATTR_LAST_ISSUE_TITLE = "Last Issue Title"
ATTR_ALL_ISSUES = "All Issues"
ATTR_AVATAR_URL = "Avatar Url"
ATTR_LANGUAGE = "Language"

URL_ISSUE = "/issues?state=all"

# Réutilisation de la session HTTP pour éviter la saturation des sockets
HTTP_SESSION = requests.Session()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Configuration des capteurs via ConfigEntry UI."""
    config = config_entry.data
    token = config.get(CONF_TOKEN)
    proto = config.get(CONF_PROTOCOL)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    known_repos = set()
    system_sensors_added = False

    def fetch_repos_data():
        """Exécuté dans un thread : effectue uniquement la requête HTTP réseau."""
        url = f"{proto}://{host}:{port}/api/v1/user/repos"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        try:
            response = HTTP_SESSION.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as err:
            _LOGGER.error("Error fetching Gitea repos via API: %s", err)
            return []

    async def discover_repos(now=None):
        """Exécuté sur l'event loop principal de Home Assistant."""
        nonlocal system_sensors_added
        entities = []

        # 1. Capteurs de diagnostic au premier passage
        if not system_sensors_added:
            _LOGGER.info("Creating diagnostic user and version entities...")
            system_sensors = [
                GiteaUserSensor(token, proto, host, port),
                GiteaVersionSensor(token, proto, host, port),
            ]
            async_add_entities(system_sensors, True)
            system_sensors_added = True

        # 2. Récupération distante des projets
        _LOGGER.info("Discovering Gitea repositories...")
        repos_data = await hass.async_add_executor_job(fetch_repos_data)

        for repo_info in repos_data:
            repo_path = repo_info.get("full_name")
            if repo_path and repo_path not in known_repos:
                known_repos.add(repo_path)
                entities.append(
                    GiteaSensor(token, proto, host, port, repo_path)
                )

        if entities:
            async_add_entities(entities, True)

    _LOGGER.info("Creating manual service...")
    async def handle_reload(call):
        await discover_repos()
    hass.services.async_register("gitea", "reload_repos", handle_reload)

    _LOGGER.info("First discovery of repos...")
    await discover_repos()

    # Planification dynamique de la recherche
    async_track_time_interval(
        hass,
        lambda now: hass.async_create_task(discover_repos(now)),
        SCAN_INTERVAL_DISCOVERY,
    )


class GiteaSensor(Entity):
    """Representation of a Repository Sensor."""

    def __init__(
            self,
            token=None,
            proto=None,
            host=None,
            port=None,
            repo=None,
    ):
        self._state = None
        self.token = token
        self.proto = proto
        self.api_url = host
        self.api_port = port
        self.repo = repo
        self.id_repo = None
        self.description = None
        self.open_issues_count = None
        self.default_branch = None
        self.size = None
        self.owner_name = None
        self.private = None
        self.mirror = None
        self.fork = None
        self.stars = None
        self.url = None
        self.watcher = None
        self.updated_at = None
        self.issue_title = None
        self.issue_link = None
        self.issue_state = None
        self.all_issues = None
        self.avatar_url = None
        self.language = None

    @property
    def name(self):
        repo_parts = self.repo.split("/")
        repo_name = repo_parts[1] if len(repo_parts) > 1 else self.repo
        return f"{DEFAULT_NAME}_repo_{repo_name}"

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        if self.mirror:
            return "mdi:format-horizontal-align-center"
        return "mdi:tea"

    @property
    def entity_picture(self) -> str | None:
        return self.avatar_url

    @property
    def unique_id(self):
        if self.id_repo:
            return f"gitea_repo_{self.id_repo}"
        return f"gitea_repo_{self.repo.replace('/', '_')}"

    @property
    def device_info(self) -> DeviceInfo:
        repo_parts = self.repo.split("/")
        repo_name = repo_parts[1] if len(repo_parts) > 1 else self.repo

        return DeviceInfo(
            identifiers={("gitea", f"repo_{self.id_repo or self.repo}")},
            name=f"Dépôt Git - {repo_name}",
            manufacturer="Gitea",
            model="Git Repository",
            configuration_url=self.url,
        )

    @property
    def extra_state_attributes(self):
        return {
            ATTR_REPO_ID: self.id_repo,
            ATTR_REPO_NAME: self.repo,
            ATTR_OWNER: self.owner_name,
            ATTR_PRIVATE_REPO: self.private,
            ATTR_FORK: self.fork,
            ATTR_MIRROR: self.mirror,
            ATTR_STARS: self.stars,
            ATTR_DESCRIPTION: self.description,
            ATTR_OPEN_ISSUES: self.open_issues_count,
            ATTR_DEFAULT_BR: self.default_branch,
            ATTR_REPO_URL: self.url,
            ATTR_SIZE: self.size,
            ATTR_WATCH: self.watcher,
            ATTR_UPDATED_AT: self.updated_at,
            ATTR_LAST_ISSUE_LINK: self.issue_link,
            ATTR_LAST_ISSUE_STATE: self.issue_state,
            ATTR_LAST_ISSUE_TITLE: self.issue_title,
            ATTR_ALL_ISSUES: self.all_issues,
            ATTR_AVATAR_URL: self.avatar_url,
            ATTR_LANGUAGE: self.language,
        }

    def update(self):
        time.sleep(0.2)  # Temporisation pour espacer les requêtes
        infos = self.api_call(self.generate_url())
        if not infos or "id" not in infos:
            return

        self.id_repo = infos["id"]
        self.description = infos["description"]
        self.open_issues_count = infos["open_issues_count"]
        self.default_branch = infos["default_branch"]
        self.size = f"{infos['size']} Ko"
        self.owner_name = infos["owner"]["login"]
        self.private = infos["private"]
        self.mirror = infos["mirror"]
        self.stars = infos["stars_count"]
        self.fork = infos["forks_count"]
        self.url = infos["html_url"]
        self._state = infos["default_branch"]
        self.watcher = infos["watchers_count"]
        self.updated_at = infos["updated_at"]
        self.avatar_url = infos["avatar_url"]
        self.language = infos.get("language")

        if infos.get("open_issues_count", 0) != 0:
            time.sleep(0.1)
            issues = self.api_call(self.generate_url(URL_ISSUE))

            # Vérification de sécurité avant d'accéder aux éléments de la liste
            if isinstance(issues, list) and len(issues) > 0:
                issues_tab = []
                self.issue_link = issues[0]["html_url"]
                self.issue_state = issues[0]["state"]
                self.issue_title = issues[0]["title"]

                for iss in issues:
                    card_items = {
                        "id": iss["id"],
                        "state": iss["state"],
                        "title": iss["title"],
                        "url": iss["html_url"],
                    }
                    issues_tab.append(card_items)

                self.all_issues = json.dumps(issues_tab)

    def generate_url(self, path=""):
        return f"{self.proto}://{self.api_url}:{self.api_port}/api/v1/repos/{self.repo.split('/')[0]}/{self.repo.split('/')[1]}{path}"

    def get_header(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def api_call(self, url):
        headers = self.get_header()
        for attempt in range(3):
            try:
                response = HTTP_SESSION.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as err:
                if attempt == 2:
                    _LOGGER.error("Erreur de connexion à Gitea (%s): %s", url, err)
                    return {}
                time.sleep(1)


class GiteaUserSensor(SensorEntity):
    """Diagnostic sensor for current Gitea user details."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:account-cog"

    def __init__(self, token, proto, host, port):
        self.token = token
        self.proto = proto
        self.host = host
        self.port = port
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return "Gitea User"

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def entity_picture(self) -> str | None:
        return self._attributes.get("avatar_url")

    @property
    def unique_id(self):
        return f"gitea_instance_{self.host}_{self.port}_user"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={("gitea", f"instance_{self.host}_{self.port}")},
            name=f"Gitea Server ({self.host})",
            manufacturer="Gitea",
            configuration_url=f"{self.proto}://{self.host}:{self.port}",
        )

    def update(self):
        url = f"{self.proto}://{self.host}:{self.port}/api/v1/user"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        try:
            response = HTTP_SESSION.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            user_info = response.json()

            self._state = user_info.get("full_name") or user_info.get("login")
            self._attributes = {
                "username": user_info.get("login"),
                "email": user_info.get("email"),
                "avatar_url": user_info.get("avatar_url"),
                "id": user_info.get("id"),
                "is_admin": user_info.get("is_admin"),
                "created_at": user_info.get("created"),
            }
        except Exception as err:
            _LOGGER.error("Error fetching Gitea user info: %s", err)


class GiteaVersionSensor(SensorEntity):
    """Diagnostic sensor for Gitea server version."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:git"

    def __init__(self, token, proto, host, port):
        self.token = token
        self.proto = proto
        self.host = host
        self.port = port
        self._state = None

    @property
    def name(self):
        return "Gitea Version"

    @property
    def native_value(self):
        return self._state

    @property
    def unique_id(self):
        return f"gitea_instance_{self.host}_{self.port}_version"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={("gitea", f"instance_{self.host}_{self.port}")},
            name=f"Gitea Server ({self.host})",
            manufacturer="Gitea",
            configuration_url=f"{self.proto}://{self.host}:{self.port}",
        )

    def update(self):
        url = f"{self.proto}://{self.host}:{self.port}/api/v1/version"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        try:
            response = HTTP_SESSION.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            self._state = data.get("version")
        except Exception as err:
            _LOGGER.error("Error fetching Gitea version: %s", err)