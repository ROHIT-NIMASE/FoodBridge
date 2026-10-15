# FoodBridge

A surplus raw-ingredient resale and NGO redistribution platform.

## Core workflow
1. Businesses list unused, fresh raw ingredients.
2. Other businesses purchase surplus ingredients at discounted prices.
3. Unsold ingredients may be offered to registered NGOs if still safe and eligible.

## Frontend (Streamlit)
```
pip install -r requirements.txt
streamlit run main.py
python -m pytest            # UI + backend-contract tests
```
Demo logins (password `demo1234`): `seller@demo.com`, `bakery@demo.com`, `buyer@demo.com`, `ngo@demo.com`.

| Screen | Module |
|---|---|
| Router, sidebar, role-based navigation | `main.py` |
| Sign in / Register | `ui/login.py`, `ui/register.py` |
| Marketplace, search & filters, ingredient details, purchase request | `ui/marketplace.py` |
| Add / edit listing | `ui/listing_form.py` |
| Seller dashboard (listings, incoming orders, NGO requests) | `ui/seller_dashboard.py` |
| Buyer dashboard, order history | `ui/buyer_dashboard.py`, `ui/my_orders.py` |
| NGO offers, donation requests | `ui/ngo_dashboard.py`, `ui/donation_requests.py` |
| Impact statistics | `ui/impact_dashboard.py` |
| Shared helpers (session, flash messages, confirm dialogs, formatting, CSS) | `utils/helpers.py` |

### Connecting the backend
Screens only talk to `utils.helpers.backend()`. Until `services/*.py` are implemented it returns
`utils/demo_backend.py`, an in-memory stand-in that documents the methods, return shapes and error
behaviour (`ServiceError`, a `ValueError`) the UI expects. To connect the real services, wrap them in a
class with the same method names and return it from `backend()`.

## Planned technology stack
- Python (Streamlit UI)
- MySQL
- Git and GitHub
