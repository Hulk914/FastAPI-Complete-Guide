"""Exercise CRUD through HTTP, including authentication and ownership checks."""

import pytest

PRODUCT = {"name": "Notebook", "desc": "A useful notebook", "price": 1299}


def test_complete_crud_flow(client, owner):
    seller, headers = owner
    response = client.post("/product", json=PRODUCT, headers=headers)
    assert response.status_code == 201
    product = response.json()
    assert product == {**PRODUCT, "id": 1, "seller_id": seller["id"]}
    path = f"/product/{product['id']}"
    assert client.get(path, headers=headers).json() == product
    assert client.get("/product", headers=headers).json() == [product]

    updated = {**PRODUCT, "name": "Updated notebook", "price": 1599}
    response = client.put(path, json=updated, headers=headers)
    assert response.status_code == 200
    assert response.json() == {**product, **updated}
    # Read in a new request/session: the write must actually have committed.
    assert client.get(path, headers=headers).json() == response.json()

    response = client.delete(path, headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(path, headers=headers).status_code == 404
    assert client.delete(path, headers=headers).status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/product"),
        ("GET", "/product/1"),
        ("POST", "/product"),
        ("PUT", "/product/1"),
        ("DELETE", "/product/1"),
        ("GET", "/seller/me"),
    ],
)
def test_every_protected_route_requires_authentication(client, method, path):
    response = client.request(method, path, json=PRODUCT if method in {"POST", "PUT"} else None)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_other_seller_can_read_but_cannot_modify(client, owner, account_factory):
    _, owner_headers = owner
    _, other_headers = account_factory("bob")
    product = client.post("/product", json=PRODUCT, headers=owner_headers).json()
    path = f"/product/{product['id']}"
    assert client.get(path, headers=other_headers).status_code == 200
    assert client.put(path, json={**PRODUCT, "price": 1}, headers=other_headers).status_code == 403
    assert client.delete(path, headers=other_headers).status_code == 403
    assert client.get(path, headers=owner_headers).json() == product


def test_owner_is_taken_from_token_not_hardcoded(client, owner, account_factory):
    bob, headers = account_factory("bob")
    response = client.post("/product", json=PRODUCT, headers=headers)
    assert response.json()["seller_id"] == bob["id"]
    assert bob["id"] != owner[0]["id"]
    assert (
        client.post("/product", json={**PRODUCT, "seller_id": 1}, headers=headers).status_code
        == 422
    )


@pytest.mark.parametrize(
    "change",
    [
        {"name": "   "},
        {"name": "x" * 101},
        {"desc": ""},
        {"desc": "x" * 1001},
        {"price": -1},
        {"price": 2_147_483_648},
        {"price": 1.5},
        {"price": True},
        {"price": "100"},
        {"price": None},
        {"unexpected": "value"},
    ],
)
def test_product_validation(client, owner, change):
    assert client.post("/product", json={**PRODUCT, **change}, headers=owner[1]).status_code == 422


def test_put_requires_full_representation(client, owner):
    headers = owner[1]
    product = client.post("/product", json=PRODUCT, headers=headers).json()
    response = client.put(f"/product/{product['id']}", json={"name": "Only name"}, headers=headers)
    assert response.status_code == 422


def test_free_product_and_whitespace_normalization(client, owner):
    response = client.post(
        "/product", json={**PRODUCT, "name": " Notebook ", "price": 0}, headers=owner[1]
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Notebook"
    assert response.json()["price"] == 0


def test_pagination_is_bounded_and_deterministic(client, owner):
    headers = owner[1]
    for index in range(3):
        client.post("/product", json={**PRODUCT, "name": str(index)}, headers=headers)
    response = client.get("/product?offset=1&limit=1", headers=headers)
    assert [item["name"] for item in response.json()] == ["1"]
    assert client.get("/product?offset=99", headers=headers).json() == []


@pytest.mark.parametrize(
    "query", ["offset=-1", "offset=999999999999999999999", "limit=0", "limit=101"]
)
def test_invalid_pagination(client, owner, query):
    assert client.get(f"/product?{query}", headers=owner[1]).status_code == 422


@pytest.mark.parametrize("product_id", ["abc", "0", "-1", str(2**63)])
def test_invalid_product_id(client, owner, product_id):
    assert client.get(f"/product/{product_id}", headers=owner[1]).status_code == 422


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_missing_product_returns_404(client, owner, method):
    response = client.request(
        method, "/product/999", json=PRODUCT if method == "PUT" else None, headers=owner[1]
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}
