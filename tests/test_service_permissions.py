"""Permission tests for Expiry Tracker Home Assistant services."""

from types import SimpleNamespace

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized

from custom_components.expiry_tracker.services import (
    MUTATIONS,
    _admin_only,
    async_register_services,
)


class Auth:
    def __init__(self, users):
        self.users = users
        self.lookups: list[str] = []

    async def async_get_user(self, user_id):
        self.lookups.append(user_id)
        return self.users.get(user_id)


class Services:
    def __init__(self):
        self.handlers = {}

    def has_service(self, domain, service):
        return False

    def async_register(self, domain, service, handler, **kwargs):
        self.handlers[(domain, service)] = handler

    def async_remove(self, domain, service):
        return None


def hass_for(users):
    return SimpleNamespace(services=Services(), auth=Auth(users))


def call_for(user_id):
    return SimpleNamespace(context=Context(user_id=user_id), data={})


async def test_every_mutation_service_rejects_non_admin_user_before_mutating():
    hass = hass_for({"regular": SimpleNamespace(is_admin=False)})
    await async_register_services(hass)

    for service in MUTATIONS:
        handler = hass.services.handlers[("expiry_tracker", service)]
        with pytest.raises(Unauthorized):
            await handler(call_for("regular"))

    assert hass.auth.lookups == ["regular"] * len(MUTATIONS)


async def test_admin_user_can_pass_mutation_permission_boundary():
    hass = hass_for({"admin": SimpleNamespace(is_admin=True)})
    calls = []

    async def handler(call):
        calls.append(call)
        return {"ok": True}

    wrapped = _admin_only(hass, handler)
    call = call_for("admin")

    assert await wrapped(call) == {"ok": True}
    assert calls == [call]
    assert hass.auth.lookups == ["admin"]


async def test_system_context_can_pass_without_user_lookup():
    hass = hass_for({})
    calls = []

    async def handler(call):
        calls.append(call)
        return {"ok": True}

    wrapped = _admin_only(hass, handler)
    call = call_for(None)

    assert await wrapped(call) == {"ok": True}
    assert calls == [call]
    assert hass.auth.lookups == []


async def test_unknown_user_is_not_treated_as_system_context():
    hass = hass_for({})

    async def handler(call):
        raise AssertionError("unauthorized call reached mutation handler")

    wrapped = _admin_only(hass, handler)

    with pytest.raises(Unauthorized):
        await wrapped(call_for("missing-user"))

    assert hass.auth.lookups == ["missing-user"]
