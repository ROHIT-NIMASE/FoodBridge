"""In-memory stand-in for the FoodBridge backend services.

The real services (services/*.py, owned by Member 1) are still empty
placeholders, so the UI talks to *this* object through utils.helpers.backend().
It defines the contract the UI expects. When the real services are ready, wrap
them in a class exposing the same method names and return the same dict shapes,
then switch helpers.backend() over - no screen code has to change.

Rules the UI relies on
----------------------
* Every method that can fail raises ServiceError (a ValueError) with a message
  that is safe to show to the user.
* Listings, orders and donation requests come back as plain dicts, already
  joined with the names the screens need (seller_name, buyer_name, ...).
* Quantity is *reserved* when an order / donation request is created and given
  back when it is cancelled, rejected or declined.
"""
from __future__ import annotations

import hashlib
import hmac
import itertools
import os
import re
import threading
from datetime import datetime, timedelta

# ----------------------------------------------------------------- constants
ROLE_BUSINESS = "business"
ROLE_NGO = "ngo"

CATEGORIES = ["Vegetables", "Fruits", "Dairy & Eggs", "Grains & Pulses",
              "Bakery", "Spices & Oils", "Meat & Seafood", "Other"]
CONDITIONS = ["Fresh", "Good", "Best used soon"]
UNITS = ["kg", "L", "dozen", "pack"]
MASS_UNITS = ("kg", "L")          # only these count towards impact totals
DONATION_WINDOW_HOURS = 48        # unsold stock this close to its deadline can be offered to NGOs

# who may move an order / donation request to which status
SELLER_ORDER_TRANSITIONS = {
    "Pending": ["Confirmed", "Rejected"],
    "Confirmed": ["Ready for collection", "Cancelled"],
    "Ready for collection": ["Completed", "Cancelled"],
}
BUYER_ORDER_TRANSITIONS = {"Pending": ["Cancelled"], "Confirmed": ["Cancelled"]}
SELLER_DONATION_TRANSITIONS = {"Requested": ["Approved", "Declined"],
                               "Approved": ["Collected", "Cancelled"]}
NGO_DONATION_TRANSITIONS = {"Requested": ["Cancelled"], "Approved": ["Cancelled"]}
RELEASES_STOCK = {"Cancelled", "Rejected", "Declined"}


class ServiceError(ValueError):
    """A problem the user can fix or should be told about."""


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000).hex()


class DemoBackend:
    def __init__(self, seed: bool = True):
        self._lock = threading.RLock()
        self._ids = itertools.count(1)
        self._users, self._listings, self._orders, self._donations = {}, {}, {}, {}
        if seed:
            self._seed()

    # ---------------------------------------------------------------- users
    def register_user(self, name, email, password, role, org_name, location, phone=""):
        errors = []
        name, org_name, location = (name or "").strip(), (org_name or "").strip(), (location or "").strip()
        email = (email or "").strip().lower()
        if not name: errors.append("Your name is required.")
        if not org_name: errors.append("Organisation name is required.")
        if not location: errors.append("Location is required.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): errors.append("Enter a valid email address.")
        if len(password or "") < 8: errors.append("Password must be at least 8 characters.")
        if role not in (ROLE_BUSINESS, ROLE_NGO): errors.append("Choose an account type.")
        if errors:
            raise ServiceError(" ".join(errors))
        with self._lock:
            if any(u["email"] == email for u in self._users.values()):
                raise ServiceError("An account with this email already exists.")
            uid = next(self._ids)
            salt = os.urandom(16)
            self._users[uid] = {"id": uid, "name": name, "email": email, "role": role,
                                "org_name": org_name, "location": location, "phone": phone.strip(),
                                "created_at": datetime.now(), "_salt": salt, "_hash": _hash(password, salt)}
            return self._public_user(self._users[uid])

    def authenticate(self, email, password):
        email = (email or "").strip().lower()
        with self._lock:
            for u in self._users.values():
                if u["email"] == email and hmac.compare_digest(u["_hash"], _hash(password or "", u["_salt"])):
                    return self._public_user(u)
        return None

    def get_user(self, user_id):
        u = self._users.get(user_id)
        return self._public_user(u) if u else None

    @staticmethod
    def _public_user(u):
        return {k: v for k, v in u.items() if not k.startswith("_")}

    # ------------------------------------------------------------- listings
    def create_listing(self, seller_id, data):
        with self._lock:
            self._require_role(seller_id, ROLE_BUSINESS, "Only business accounts can list ingredients.")
            fields = self._clean_listing(data)
            lid = next(self._ids)
            self._listings[lid] = {"id": lid, "seller_id": seller_id, **fields,
                                   "quantity_available": fields["quantity"], "cancelled": False,
                                   "created_at": datetime.now()}
            return self._view_listing(self._listings[lid])

    def update_listing(self, listing_id, seller_id, data):
        with self._lock:
            l = self._own_listing(listing_id, seller_id)
            if l["cancelled"]:
                raise ServiceError("A cancelled listing cannot be edited.")
            fields = self._clean_listing(data)
            reserved = l["quantity"] - l["quantity_available"]
            if fields["quantity"] < reserved:
                raise ServiceError(f"{reserved:g} {l['unit']} is already reserved by orders or donations, "
                                   f"so the total quantity cannot go below that.")
            l.update(fields)
            l["quantity_available"] = fields["quantity"] - reserved
            return self._view_listing(l)

    def cancel_listing(self, listing_id, seller_id):
        with self._lock:
            l = self._own_listing(listing_id, seller_id)
            if l["cancelled"]:
                raise ServiceError("This listing is already cancelled.")
            l["cancelled"] = True
            for o in self._orders.values():
                if o["listing_id"] == listing_id and o["status"] in ("Pending", "Confirmed", "Ready for collection"):
                    self._set_status(o, "Cancelled")
            for d in self._donations.values():
                if d["listing_id"] == listing_id and d["status"] in ("Requested", "Approved"):
                    self._set_status(d, "Cancelled")
            l["quantity_available"] = 0
            return self._view_listing(l)

    def get_listing(self, listing_id):
        l = self._listings.get(listing_id)
        return self._view_listing(l) if l else None

    def seller_listings(self, seller_id):
        return sorted((self._view_listing(l) for l in self._listings.values() if l["seller_id"] == seller_id),
                      key=lambda x: x["created_at"], reverse=True)

    def search_listings(self, query="", location="", category=None, conditions=None,
                        min_price=None, max_price=None, min_quantity=None,
                        sort="Collect-by soonest"):
        """Public marketplace: only listings that can still be bought."""
        q, loc = (query or "").strip().lower(), (location or "").strip().lower()
        out = []
        for l in self._listings.values():
            v = self._view_listing(l)
            if v["status"] != "Available":
                continue
            if q and q not in " ".join([v["name"], v["category"], v["description"]]).lower():
                continue
            if loc and loc not in v["location"].lower(): continue
            if category and category != "All" and v["category"] != category: continue
            if conditions and v["condition"] not in conditions: continue
            if min_price is not None and v["price"] < min_price: continue
            if max_price is not None and v["price"] > max_price: continue
            if min_quantity and v["quantity_available"] < min_quantity: continue
            out.append(v)
        keys = {"Collect-by soonest": lambda x: x["deadline"],
                "Price: low to high": lambda x: x["price"],
                "Price: high to low": lambda x: -x["price"],
                "Quantity: most first": lambda x: -x["quantity_available"],
                "Biggest discount": lambda x: -x["discount_pct"]}
        return sorted(out, key=keys.get(sort, keys["Collect-by soonest"]))

    # --------------------------------------------------------------- orders
    def place_order(self, listing_id, buyer_id, quantity, note=""):
        with self._lock:
            self._require_role(buyer_id, ROLE_BUSINESS, "Only business accounts can buy ingredients.")
            l = self._listings.get(listing_id)
            if not l: raise ServiceError("This listing no longer exists.")
            v = self._view_listing(l)
            if l["seller_id"] == buyer_id: raise ServiceError("You cannot buy your own listing.")
            if v["status"] != "Available": raise ServiceError(f"This listing is {v['status'].lower()}.")
            quantity = self._positive(quantity, "Quantity")
            if quantity > l["quantity_available"]:
                raise ServiceError(f"Only {l['quantity_available']:g} {l['unit']} is available.")
            l["quantity_available"] -= quantity
            oid, now = next(self._ids), datetime.now()
            self._orders[oid] = {"id": oid, "listing_id": listing_id, "buyer_id": buyer_id,
                                 "seller_id": l["seller_id"], "quantity": quantity,
                                 "unit_price": l["price"], "total": round(quantity * l["price"], 2),
                                 "note": (note or "").strip(), "status": "Pending",
                                 "created_at": now, "updated_at": now, "completed_at": None}
            return self._view_order(self._orders[oid])

    def buyer_orders(self, buyer_id):
        return self._sorted(self._view_order(o) for o in self._orders.values() if o["buyer_id"] == buyer_id)

    def seller_orders(self, seller_id):
        return self._sorted(self._view_order(o) for o in self._orders.values() if o["seller_id"] == seller_id)

    def set_order_status(self, order_id, actor_id, new_status):
        with self._lock:
            o = self._orders.get(order_id)
            if not o: raise ServiceError("Order not found.")
            self._transition(o, actor_id, new_status, SELLER_ORDER_TRANSITIONS, BUYER_ORDER_TRANSITIONS,
                             seller_key="seller_id", other_key="buyer_id")
            return self._view_order(o)

    # ------------------------------------------------------------ donations
    def donation_offers(self):
        """Listings an NGO may ask for: opted in by the seller, unsold and close to deadline."""
        return sorted((v for v in map(self._view_listing, self._listings.values()) if v["donation_eligible"]),
                      key=lambda x: x["deadline"])

    def request_donation(self, listing_id, ngo_id, quantity, note=""):
        with self._lock:
            self._require_role(ngo_id, ROLE_NGO, "Only registered NGOs can request donations.")
            l = self._listings.get(listing_id)
            if not l: raise ServiceError("This listing no longer exists.")
            if not self._view_listing(l)["donation_eligible"]:
                raise ServiceError("This item is not currently available for donation.")
            quantity = self._positive(quantity, "Quantity")
            if quantity > l["quantity_available"]:
                raise ServiceError(f"Only {l['quantity_available']:g} {l['unit']} is available.")
            l["quantity_available"] -= quantity
            did, now = next(self._ids), datetime.now()
            self._donations[did] = {"id": did, "listing_id": listing_id, "ngo_id": ngo_id,
                                    "seller_id": l["seller_id"], "quantity": quantity,
                                    "note": (note or "").strip(), "status": "Requested",
                                    "created_at": now, "updated_at": now, "completed_at": None}
            return self._view_donation(self._donations[did])

    def ngo_requests(self, ngo_id):
        return self._sorted(self._view_donation(d) for d in self._donations.values() if d["ngo_id"] == ngo_id)

    def seller_donation_requests(self, seller_id):
        return self._sorted(self._view_donation(d) for d in self._donations.values() if d["seller_id"] == seller_id)

    def set_donation_status(self, request_id, actor_id, new_status):
        with self._lock:
            d = self._donations.get(request_id)
            if not d: raise ServiceError("Donation request not found.")
            self._transition(d, actor_id, new_status, SELLER_DONATION_TRANSITIONS, NGO_DONATION_TRANSITIONS,
                             seller_key="seller_id", other_key="ngo_id")
            return self._view_donation(d)

    # --------------------------------------------------------------- impact
    def impact_stats(self, user_id=None):
        """Totals for the whole platform, or only transactions `user_id` took part in."""
        def mine(rec, *keys):
            return user_id is None or any(rec[k] == user_id for k in keys)

        resold = donated = revenue = 0.0
        orders = donations = 0
        timeline = {}
        for o in self._orders.values():
            if o["status"] == "Completed" and mine(o, "buyer_id", "seller_id"):
                kg = self._mass(o["quantity"], self._listings[o["listing_id"]]["unit"])
                resold += kg; revenue += o["total"]; orders += 1
                timeline.setdefault(o["completed_at"].date(), [0.0, 0.0])[0] += kg
        for d in self._donations.values():
            if d["status"] == "Collected" and mine(d, "ngo_id", "seller_id"):
                kg = self._mass(d["quantity"], self._listings[d["listing_id"]]["unit"])
                donated += kg; donations += 1
                timeline.setdefault(d["completed_at"].date(), [0.0, 0.0])[1] += kg
        active = sum(1 for l in self._listings.values()
                     if self._view_listing(l)["status"] == "Available" and mine(l, "seller_id"))
        return {"resold_kg": resold, "revenue": revenue, "orders_completed": orders,
                "donated_kg": donated, "donations_completed": donations, "active_listings": active,
                "timeline": [{"date": k, "resold_kg": v[0], "donated_kg": v[1]} for k, v in sorted(timeline.items())]}

    # ------------------------------------------------------------- internals
    @staticmethod
    def _mass(qty, unit):
        return qty if unit in MASS_UNITS else 0.0

    @staticmethod
    def _sorted(rows):
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    @staticmethod
    def _positive(value, label):
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ServiceError(f"{label} must be a number.")
        if value <= 0:
            raise ServiceError(f"{label} must be greater than zero.")
        return value

    def _require_role(self, user_id, role, message):
        u = self._users.get(user_id)
        if not u or u["role"] != role:
            raise ServiceError(message)

    def _own_listing(self, listing_id, seller_id):
        l = self._listings.get(listing_id)
        if not l: raise ServiceError("Listing not found.")
        if l["seller_id"] != seller_id: raise ServiceError("You can only manage your own listings.")
        return l

    def _clean_listing(self, data):
        errors = []
        name = (data.get("name") or "").strip()
        location = (data.get("location") or "").strip()
        if not name: errors.append("Ingredient name is required.")
        if not location: errors.append("Location is required.")
        nums = {}
        for key, label in (("quantity", "Quantity"), ("price", "Price per unit")):
            try:
                nums[key] = self._positive(data.get(key), label)
            except ServiceError as e:
                errors.append(str(e))
        original = data.get("original_price")
        if original in (None, "", 0):
            original = nums.get("price")
        else:
            try:
                original = self._positive(original, "Original price")
            except ServiceError as e:
                errors.append(str(e)); original = None
        if original and nums.get("price") and original < nums["price"]:
            errors.append("Original price cannot be lower than the discounted price.")
        deadline = data.get("deadline")
        if not isinstance(deadline, datetime): errors.append("Collection deadline is required.")
        elif deadline <= datetime.now(): errors.append("Collection deadline must be in the future.")
        category, condition, unit = data.get("category", "Other"), data.get("condition", "Fresh"), data.get("unit", "kg")
        if category not in CATEGORIES: errors.append("Choose a valid category.")
        if condition not in CONDITIONS: errors.append("Choose a valid condition.")
        if unit not in UNITS: errors.append("Choose a valid unit.")
        if errors:
            raise ServiceError(" ".join(errors))
        return {"name": name, "category": category, "quantity": nums["quantity"], "unit": unit,
                "price": nums["price"], "original_price": original, "condition": condition,
                "location": location, "deadline": deadline,
                "description": (data.get("description") or "").strip(),
                "donate_if_unsold": bool(data.get("donate_if_unsold"))}

    def _view_listing(self, l):
        now = datetime.now()
        if l["cancelled"]: status = "Cancelled"
        elif l["deadline"] <= now: status = "Expired"
        elif l["quantity_available"] <= 0: status = "Sold out"
        else: status = "Available"
        seller = self._users[l["seller_id"]]
        orig = l["original_price"] or l["price"]
        eligible = (status == "Available" and l["donate_if_unsold"]
                    and l["deadline"] <= now + timedelta(hours=DONATION_WINDOW_HOURS))
        return {**l, "status": status, "seller_name": seller["org_name"], "seller_location": seller["location"],
                "reserved": l["quantity"] - l["quantity_available"], "donation_eligible": eligible,
                "discount_pct": round((1 - l["price"] / orig) * 100) if orig else 0}

    def _view_order(self, o):
        l, buyer, seller = self._listings[o["listing_id"]], self._users[o["buyer_id"]], self._users[o["seller_id"]]
        return {**o, "listing_name": l["name"], "unit": l["unit"], "location": l["location"],
                "deadline": l["deadline"], "buyer_name": buyer["org_name"], "seller_name": seller["org_name"]}

    def _view_donation(self, d):
        l, ngo, seller = self._listings[d["listing_id"]], self._users[d["ngo_id"]], self._users[d["seller_id"]]
        return {**d, "listing_name": l["name"], "unit": l["unit"], "location": l["location"],
                "deadline": l["deadline"], "ngo_name": ngo["org_name"], "seller_name": seller["org_name"]}

    def _set_status(self, rec, new_status):
        rec["status"], rec["updated_at"] = new_status, datetime.now()
        if new_status in ("Completed", "Collected"):
            rec["completed_at"] = rec["updated_at"]
        if new_status in RELEASES_STOCK:
            self._listings[rec["listing_id"]]["quantity_available"] += rec["quantity"]

    def _transition(self, rec, actor_id, new_status, seller_map, other_map, seller_key, other_key):
        if actor_id == rec[seller_key]: allowed = seller_map
        elif actor_id == rec[other_key]: allowed = other_map
        else: raise ServiceError("You are not allowed to change this.")
        if new_status not in allowed.get(rec["status"], []):
            raise ServiceError(f"Cannot change status from {rec['status']} to {new_status}.")
        self._set_status(rec, new_status)

    # ----------------------------------------------------------------- seed
    def _seed(self):
        def user(name, email, role, org, loc):
            return self.register_user(name, email, "demo1234", role, org, loc)["id"]
        s1 = user("Asha Kulkarni", "seller@demo.com", ROLE_BUSINESS, "Green Valley Kitchens", "Kothrud, Pune")
        s2 = user("Ravi Joshi", "bakery@demo.com", ROLE_BUSINESS, "Sahyadri Bakery & Foods", "Aundh, Pune")
        b1 = user("Neha Deshmukh", "buyer@demo.com", ROLE_BUSINESS, "Spice Route Café", "Camp, Pune")
        n1 = user("Meera Patil", "ngo@demo.com", ROLE_NGO, "Annadaan Foundation", "Hadapsar, Pune")

        def hrs(h): return datetime.now() + timedelta(hours=h)
        specs = [  # seller, name, category, qty, unit, price, original, condition, location, deadline_h, donate
            (s1, "Tomatoes", "Vegetables", 120, "kg", 18, 32, "Fresh", "Kothrud, Pune", 52, False),
            (s1, "Basmati rice", "Grains & Pulses", 80, "kg", 55, 90, "Good", "Hinjewadi, Pune", 96, False),
            (s1, "Fresh paneer", "Dairy & Eggs", 25, "kg", 180, 300, "Best used soon", "Baner, Pune", 14, True),
            (s2, "Onions", "Vegetables", 200, "kg", 14, 28, "Good", "Hadapsar, Pune", 120, False),
            (s2, "Whole wheat flour", "Grains & Pulses", 150, "kg", 26, 42, "Fresh", "Wakad, Pune", 144, False),
            (s1, "Spinach", "Vegetables", 35, "kg", 20, 45, "Best used soon", "Kothrud, Pune", 9, True),
            (s2, "Milk", "Dairy & Eggs", 60, "L", 30, 54, "Fresh", "Viman Nagar, Pune", 30, True),
            (s2, "Bread loaves", "Bakery", 50, "pack", 25, 45, "Best used soon", "Aundh, Pune", 20, True),
            (s1, "Turmeric powder", "Spices & Oils", 20, "kg", 150, 240, "Fresh", "Camp, Pune", 480, False),
            (s2, "Sunflower oil", "Spices & Oils", 45, "L", 95, 140, "Good", "Pimpri, Pune", 240, False),
            (s1, "Cabbage", "Vegetables", 40, "kg", 12, 24, "Good", "Kothrud, Pune", 70, False),
        ]
        ids = []
        for sid, name, cat, qty, unit, price, orig, cond, loc, h, don in specs:
            ids.append(self.create_listing(sid, dict(name=name, category=cat, quantity=qty, unit=unit, price=price,
                       original_price=orig, condition=cond, location=loc, deadline=hrs(h),
                       description=f"Surplus {name.lower()} from our kitchen, stored properly and ready to collect.",
                       donate_if_unsold=don))["id"])
        tomatoes, rice, paneer, onions, flour, spinach, milk, bread, _, _, cabbage = ids
        self.cancel_listing(cabbage, s1)

        def done(order, days_ago):
            for st in ("Confirmed", "Ready for collection", "Completed"):
                self.set_order_status(order["id"], self._orders[order["id"]]["seller_id"], st)
            self._orders[order["id"]]["completed_at"] = datetime.now() - timedelta(days=days_ago)
            self._orders[order["id"]]["created_at"] = datetime.now() - timedelta(days=days_ago, hours=5)
        done(self.place_order(onions, b1, 40, "Need for weekend banquet"), 3)
        done(self.place_order(flour, b1, 30), 1)
        self.place_order(tomatoes, b1, 15, "Pick up around 5 pm")
        o = self.place_order(rice, b1, 10)
        self.set_order_status(o["id"], s1, "Confirmed")
        d = self.request_donation(milk, n1, 12, "For community kitchen")
        for st in ("Approved", "Collected"):
            self.set_donation_status(d["id"], self._donations[d["id"]]["seller_id"], st)
        self._donations[d["id"]]["completed_at"] = datetime.now() - timedelta(days=2)
        self._donations[d["id"]]["created_at"] = datetime.now() - timedelta(days=2, hours=6)
        d2 = self.request_donation(spinach, n1, 10)
        self.set_donation_status(d2["id"], s1, "Approved")
