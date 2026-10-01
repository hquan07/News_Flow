import base64
from types import SimpleNamespace

import pytest
from bson import ObjectId

from api.main import app
from api.routers import auth


@pytest.mark.asyncio
async def test_avatar_change_requires_login(async_client):
    response = await async_client.delete(
        "/api/v1/auth/avatar", headers={"Authorization": ""}
    )
    assert response.status_code == 401


@pytest.fixture
def avatar_account(monkeypatch):
    account_id = ObjectId()
    account = {"_id": account_id, "email": "avatar@example.com", "full_name": "Avatar User"}

    class Users:
        async def find_one(self, query, _projection=None):
            return account if query.get("_id") == account_id else None

        async def update_one(self, query, update):
            if query.get("_id") != account_id:
                return SimpleNamespace(matched_count=0)
            account.update(update.get("$set", {}))
            for key in update.get("$unset", {}):
                account.pop(key, None)
            return SimpleNamespace(matched_count=1)

    monkeypatch.setattr(auth, "get_mongo_db", lambda: SimpleNamespace(users=Users()))
    app.dependency_overrides[auth.get_current_user] = lambda: {
        "sub": str(account_id),
        "email": account["email"],
        "role": "user",
        "permissions": ["dashboard.read"],
    }
    yield account
    app.dependency_overrides.pop(auth.get_current_user, None)


@pytest.mark.asyncio
async def test_avatar_upload_persists_and_can_be_removed(async_client, avatar_account):
    image = b"\xff\xd8\xff" + b"test-image" + b"\xff\xd9"
    data_url = "data:image/jpeg;base64," + base64.b64encode(image).decode()

    saved = await async_client.put("/api/v1/auth/avatar", json={"data_url": data_url})
    assert saved.status_code == 200
    assert avatar_account["avatar_data_url"] == data_url

    profile = await async_client.get("/api/v1/auth/me")
    assert profile.json()["avatar_data_url"] == data_url

    removed = await async_client.delete("/api/v1/auth/avatar")
    assert removed.status_code == 200
    assert "avatar_data_url" not in avatar_account
    assert (await async_client.get("/api/v1/auth/me")).json()["avatar_data_url"] is None


@pytest.mark.asyncio
async def test_avatar_rejects_non_image_and_oversized_payload(async_client, avatar_account):
    invalid = await async_client.put(
        "/api/v1/auth/avatar", json={"data_url": "data:image/svg+xml;base64,PHN2Zz4="}
    )
    assert invalid.status_code == 400

    oversized_image = b"\xff\xd8\xff" + b"x" * (512 * 1024) + b"\xff\xd9"
    oversized = await async_client.put(
        "/api/v1/auth/avatar",
        json={"data_url": "data:image/jpeg;base64," + base64.b64encode(oversized_image).decode()},
    )
    assert oversized.status_code in (400, 422)
    assert "avatar_data_url" not in avatar_account
