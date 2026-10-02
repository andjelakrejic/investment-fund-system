# Investment Fund Management System

A multi-service backend for managing an investment fund's assets. Employees propose
buying and selling assets, the director approves them, and approved orders can go
to an employee vote run by an Ethereum smart contract.

## Tech Stack
- **Python, Flask**: REST services
- **MySQL + SQLAlchemy**: user accounts
- **MongoDB + PyMongo**: assets, with flexible nested `info` fields
- **Redis**: queue of pending buy and sell orders
- **JWT**: authentication and role-based access
- **Solidity, Ethereum (Ganache)**: majority-vote smart contract for order approval
- **Docker, Docker Compose, Kubernetes**: containerization and orchestration
  (ConfigMaps and Secrets, persistent volumes, a replicated employee service)

## Architecture

| Service          | Responsibility |
|------------------|----------------|
| `authentication` | Registration, login (JWT), account deletion. Backed by MySQL. |
| `employee`       | Asset search with dynamic MongoDB filters, creating buy and sell orders (stored in Redis). |
| `director`       | Reviewing pending orders, approving or rejecting them, deploying voting contracts, category reports. |
| `solidity/`, `contracts/` | Voting smart contract. Only whitelisted voters can vote, each only once, and a strict majority decides. |

`director-no-blockchain` is a variant of the director service in which approval
happens immediately, without voting.

## API Overview

**Authentication**
- `POST /register`: register a new employee
- `POST /login`: returns a JWT access token (valid for 1 hour)
- `POST /delete`: delete your own account

**Employee**
- `POST /search`: filter assets by name, category, dates, and arbitrary nested
  `info` fields using MongoDB comparison operators
- `POST /create_buy_order`
- `POST /create_sell_order`

**Director**
- `GET /pending_orders`
- `POST /decision`: approve or reject an order; with blockchain enabled, this
  deploys a voting contract for the given voter addresses
- `GET /report`: money spent and earned per asset category

## Running

### Docker Compose
```bash
cp .env.example .env
docker compose up --build
```

### Kubernetes
```bash
kubectl apply -f kubernetes/
```

When it starts, the system automatically creates the database tables and a
default director account:

| Email                | Password        |
|----------------------|-----------------|
| onlymoney@gmail.com  | evenmoremoney   |

---
Course project for *Infrastructure for Electronic Business* at the School of
Electrical Engineering, University of Belgrade.