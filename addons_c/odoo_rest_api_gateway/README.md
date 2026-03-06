# 🚀 REST API Gateway Pro – Odoo 19

**Production-ready REST API with JWT Auth, API Keys, Rate Limiting, Swagger & Analytics Dashboard.**

---

## 🔥 Features

| Feature                 | Description                                              |
| ----------------------- | -------------------------------------------------------- |
| **JWT Authentication**  | Login → access_token + refresh_token (1h / 7d)           |
| **API Key Management**  | Per-app keys with scopes, rate limits, IP whitelist      |
| **Products API**        | CRUD + pagination, search, category filter, field select |
| **Orders API**          | Create, list, confirm, cancel sale orders                |
| **Customers API**       | CRUD for res.partner contacts                            |
| **Rate Limiting**       | Per-minute and per-hour throttling with auto-block       |
| **Request Logging**     | Full audit trail with response times and payloads        |
| **Analytics Dashboard** | OWL 2 dashboard with charts, top endpoints, top IPs      |
| **Swagger / OpenAPI 3** | Auto-generated interactive docs at `/api/docs`           |
| **CORS Support**        | Full cross-origin support for frontend apps              |
| **Company Isolation**   | Multi-company ready                                      |

---

## 📡 API Endpoints

### Authentication

| Method | Endpoint               | Description           |
| ------ | ---------------------- | --------------------- |
| POST   | `/api/v1/auth/login`   | Login, get JWT tokens |
| POST   | `/api/v1/auth/refresh` | Refresh access token  |
| GET    | `/api/v1/auth/me`      | Get current user info |
| POST   | `/api/v1/auth/logout`  | Logout                |

### Products

| Method | Endpoint                | Description      |
| ------ | ----------------------- | ---------------- |
| GET    | `/api/v1/products`      | List (paginated) |
| GET    | `/api/v1/products/<id>` | Get single       |
| POST   | `/api/v1/products`      | Create           |
| PUT    | `/api/v1/products/<id>` | Update           |
| DELETE | `/api/v1/products/<id>` | Archive          |

### Orders

| Method | Endpoint                      | Description |
| ------ | ----------------------------- | ----------- |
| GET    | `/api/v1/orders`              | List        |
| GET    | `/api/v1/orders/<id>`         | Get single  |
| POST   | `/api/v1/orders`              | Create      |
| POST   | `/api/v1/orders/<id>/confirm` | Confirm     |
| POST   | `/api/v1/orders/<id>/cancel`  | Cancel      |

### Customers

| Method | Endpoint                 | Description |
| ------ | ------------------------ | ----------- |
| GET    | `/api/v1/customers`      | List        |
| GET    | `/api/v1/customers/<id>` | Get single  |
| POST   | `/api/v1/customers`      | Create      |
| PUT    | `/api/v1/customers/<id>` | Update      |
| DELETE | `/api/v1/customers/<id>` | Archive     |

### Docs

| Method | Endpoint       | Description           |
| ------ | -------------- | --------------------- |
| GET    | `/api/docs`    | Swagger UI            |
| GET    | `/api/v1/spec` | OpenAPI 3.0 JSON spec |

---

## 🔑 Authentication Examples

### Login

```bash
curl -X POST http://localhost:8069/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin"}'
```

### Use Token

```bash
curl http://localhost:8069/api/v1/products \
  -H "Authorization: Bearer <access_token>"
```

### Use API Key

```bash
curl http://localhost:8069/api/v1/products \
  -H "X-API-Key: <your_api_key>"
```

---

## ⚙️ Installation

1. Copy `odoo_rest_api_gateway/` into your Odoo 19 addons path
2. Install PyJWT: `pip install PyJWT`
3. Update module list and install **REST API Gateway Pro**

---

## 📋 Dependencies

- `base`, `web`, `sale_management`, `product`, `contacts`
- Python: `PyJWT`

---

## 📄 License

LGPL-3 – Proprietary
