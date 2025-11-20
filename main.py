import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from jose import JWTError, jwt
from passlib.context import CryptContext

from database import db

# App setup
app = FastAPI(title="Buzz API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth config
SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Utils

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Models (request/response)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    default_city: Optional[str] = None


# Domain simplified schemas for endpoints
class OrganizerCreate(BaseModel):
    display_name: str
    description: Optional[str] = None
    website_url: Optional[str] = None
    instagram_handle: Optional[str] = None


class VenueCreate(BaseModel):
    name: str
    description: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str = "Austin"
    state: str = "TX"
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = None
    venue_type: str
    cover_image_url: Optional[str] = None


class EventCreate(BaseModel):
    venue_id: str
    title: str
    subtitle: Optional[str] = None
    description: str
    category: str
    tags: List[str] = []
    cover_image_url: Optional[str] = None
    min_age: Optional[int] = None
    status: str = "draft"


class EventInstanceCreate(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None
    timezone: str = "America/Chicago"
    sales_start_time: Optional[datetime] = None
    sales_end_time: Optional[datetime] = None


class TicketTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price_cents: int
    currency: str = "USD"
    total_capacity: int
    per_order_min: int = 1
    per_order_max: int = 10


class CartItem(BaseModel):
    ticket_type_id: str
    quantity: int = Field(ge=1)


class PriceCheckRequest(BaseModel):
    items: List[CartItem]


class OrderCreateRequest(BaseModel):
    items: List[CartItem]
    payment_provider: str = "test"


class OrderConfirmRequest(BaseModel):
    payment_reference: Optional[str] = None


# Dependency: get current user from Authorization header
class User(BaseModel):
    id: str
    name: str
    email: EmailStr
    is_admin: bool = False


def get_user_from_token(authorization: Optional[str] = Header(default=None)) -> Optional[User]:
    if not authorization:
        return None
    try:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        user_doc = db["user"].find_one({"id": user_id})
        if not user_doc:
            return None
        return User(id=user_doc["id"], name=user_doc.get("name", ""), email=user_doc["email"], is_admin=user_doc.get("is_admin", False))
    except JWTError:
        return None


def require_user(user: Optional[User] = Depends(get_user_from_token)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# Helper functions for IDs and timestamps

def now_ts():
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# Seed database if empty
@app.post("/api/seed")
def seed():
    # Only seed if no users exist
    if db["user"].count_documents({}) > 0:
        return {"message": "Already seeded"}

    # Users
    admin_id = new_id()
    user_id = new_id()
    db["user"].insert_many([
        {
            "id": admin_id,
            "name": "Admin User",
            "email": "admin@buzz.local",
            "password_hash": hash_password("password"),
            "avatar_url": None,
            "default_city": "Austin",
            "is_admin": True,
            "created_at": now_ts(),
            "updated_at": now_ts(),
        },
        {
            "id": user_id,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password_hash": hash_password("password"),
            "avatar_url": None,
            "default_city": "Austin",
            "is_admin": False,
            "created_at": now_ts(),
            "updated_at": now_ts(),
        },
    ])

    # Organizer for admin
    org_id = new_id()
    db["organizer"].insert_one({
        "id": org_id,
        "user_id": admin_id,
        "display_name": "East Side Comedy Collective",
        "description": "Indie comedy and live shows",
        "website_url": "https://escc.example.com",
        "instagram_handle": "@escc",
        "verification_status": "verified",
        "created_at": now_ts(),
        "updated_at": now_ts(),
    })

    # Venues
    venue_ids = []
    venues = [
        {
            "name": "Buzzroom on 6th",
            "address_line1": "123 E 6th St",
            "city": "Austin",
            "state": "TX",
            "venue_type": "club",
            "capacity": 300,
        },
        {
            "name": "Riverside Warehouse",
            "address_line1": "55 Riverside Dr",
            "city": "Austin",
            "state": "TX",
            "venue_type": "warehouse",
            "capacity": 800,
        },
        {
            "name": "East Side Studio",
            "address_line1": "910 Manor Rd",
            "city": "Austin",
            "state": "TX",
            "venue_type": "studio",
            "capacity": 120,
        },
    ]
    for v in venues:
        vid = new_id()
        v_doc = {
            "id": vid,
            "organizer_id": org_id,
            "description": None,
            "address_line1": v["address_line1"],
            "address_line2": None,
            "city": v["city"],
            "state": v["state"],
            "postal_code": None,
            "latitude": None,
            "longitude": None,
            "capacity": v.get("capacity"),
            "venue_type": v["venue_type"],
            "cover_image_url": None,
            "name": v["name"],
            "created_at": now_ts(),
            "updated_at": now_ts(),
        }
        db["venue"].insert_one(v_doc)
        venue_ids.append(vid)

    # Events + instances + tickets
    categories = ["music", "comedy", "nightlife", "workshop", "theatre"]
    event_ids = []
    for i in range(6):
        eid = new_id()
        venue_id = venue_ids[i % len(venue_ids)]
        cat = categories[i % len(categories)]
        title = [
            "Indie Night Live",
            "Standup Underground",
            "Neon Afterhours",
            "Ceramics 101",
            "Shakespeare in the Alley",
            "Techno Warehouse"
        ][i]
        db["event"].insert_one({
            "id": eid,
            "organizer_id": org_id,
            "venue_id": venue_id,
            "title": title,
            "subtitle": None,
            "description": f"An awesome {cat} experience in Austin.",
            "category": cat,
            "tags": [cat, "austin"],
            "cover_image_url": None,
            "min_age": 21 if cat in ["nightlife", "music"] else None,
            "status": "published",
            "approved": True,
            "created_at": now_ts(),
            "updated_at": now_ts(),
        })
        event_ids.append(eid)
        # Instances (3 weekends out)
        for w in range(1, 3 + 1):
            inst_id = new_id()
            start = datetime.now(timezone.utc) + timedelta(days=w * 7, hours=20)
            end = start + timedelta(hours=3)
            db["eventinstance"].insert_one({
                "id": inst_id,
                "event_id": eid,
                "start_time": start,
                "end_time": end,
                "timezone": "America/Chicago",
                "sales_start_time": datetime.now(timezone.utc) - timedelta(days=1),
                "sales_end_time": end,
                "is_cancelled": False,
                "created_at": now_ts(),
                "updated_at": now_ts(),
            })
            # Ticket types
            for t in [
                ("General Admission", 2500, 150),
                ("VIP", 6000, 40),
            ]:
                tt_id = new_id()
                db["tickettype"].insert_one({
                    "id": tt_id,
                    "event_instance_id": inst_id,
                    "name": t[0],
                    "description": None,
                    "price_cents": t[1],
                    "currency": "USD",
                    "total_capacity": t[2],
                    "remaining_capacity": t[2],
                    "per_order_min": 1,
                    "per_order_max": 6,
                    "resale_allowed": False,
                    "created_at": now_ts(),
                    "updated_at": now_ts(),
                })

    # A demo paid order for Jane
    # pick first event instance + GA ticket
    first_tt = db["tickettype"].find_one({})
    if first_tt:
        order_id = new_id()
        qty = 2
        subtotal = first_tt["price_cents"] * qty
        fee = int(subtotal * 0.1)
        db["order"].insert_one({
            "id": order_id,
            "user_id": user_id,
            "total_amount_cents": subtotal + fee,
            "currency": "USD",
            "service_fee_cents": fee,
            "status": "paid",
            "payment_provider": "test",
            "payment_reference": str(uuid.uuid4()),
            "created_at": now_ts(),
            "updated_at": now_ts(),
        })
        order_item_id = new_id()
        db["orderitem"].insert_one({
            "id": order_item_id,
            "order_id": order_id,
            "ticket_type_id": first_tt["id"],
            "quantity": qty,
            "unit_price_cents": first_tt["price_cents"],
            "created_at": now_ts(),
            "updated_at": now_ts(),
        })
        # create tickets
        inst_id = first_tt["event_instance_id"]
        for _ in range(qty):
            db["ticket"].insert_one({
                "id": new_id(),
                "order_item_id": order_item_id,
                "user_id": user_id,
                "ticket_type_id": first_tt["id"],
                "event_instance_id": inst_id,
                "qr_code_data": str(uuid.uuid4()),
                "status": "valid",
                "created_at": now_ts(),
                "updated_at": now_ts(),
            })

    return {"message": "Seeded"}


# Auth endpoints
@app.post("/api/auth/signup", response_model=TokenResponse)
def signup(req: SignupRequest):
    existing = db["user"].find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    uid = new_id()
    user_doc = {
        "id": uid,
        "name": req.name,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "avatar_url": None,
        "default_city": "Austin",
        "is_admin": False,
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }
    db["user"].insert_one(user_doc)
    token = create_access_token({"sub": uid})
    return TokenResponse(access_token=token)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    user = db["user"].find_one({"email": req.email})
    if not user or not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user["id"]})
    return TokenResponse(access_token=token)


@app.post("/api/auth/logout")
def logout():
    return {"message": "Logged out"}


@app.get("/api/auth/me")
def me(user: User = Depends(require_user)):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "is_admin": user.is_admin,
    }


# Users
@app.get("/api/users/me")
def get_my_profile(user: User = Depends(require_user)):
    doc = db["user"].find_one({"id": user.id}, {"password_hash": 0, "_id": 0})
    return doc


@app.put("/api/users/me")
def update_my_profile(update: UserUpdate, user: User = Depends(require_user)):
    changes = {k: v for k, v in update.dict().items() if v is not None}
    changes["updated_at"] = now_ts()
    db["user"].update_one({"id": user.id}, {"$set": changes})
    doc = db["user"].find_one({"id": user.id}, {"password_hash": 0, "_id": 0})
    return doc


# Organizer endpoints
@app.post("/api/organizers")
def create_organizer(req: OrganizerCreate, user: User = Depends(require_user)):
    existing = db["organizer"].find_one({"user_id": user.id})
    if existing:
        return existing
    oid = new_id()
    doc = {
        "id": oid,
        "user_id": user.id,
        "display_name": req.display_name,
        "description": req.description,
        "website_url": req.website_url,
        "instagram_handle": req.instagram_handle,
        "verification_status": "verified",  # auto-verify for MVP
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }
    db["organizer"].insert_one(doc)
    return doc


@app.get("/api/organizers/me")
def get_my_organizer(user: User = Depends(require_user)):
    doc = db["organizer"].find_one({"user_id": user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Organizer not found")
    return doc


@app.get("/api/organizers/me/summary")
def organizer_summary(user: User = Depends(require_user)):
    org = db["organizer"].find_one({"user_id": user.id})
    if not org:
        raise HTTPException(status_code=404, detail="Organizer not found")
    events = list(db["event"].find({"organizer_id": org["id"]}))
    event_ids = [e["id"] for e in events]
    instances = list(db["eventinstance"].find({"event_id": {"$in": event_ids}}))
    inst_ids = [i["id"] for i in instances]
    ttypes = list(db["tickettype"].find({"event_instance_id": {"$in": inst_ids}}))
    order_items = list(db["orderitem"].find({"ticket_type_id": {"$in": [t["id"] for t in ttypes]}}))
    order_ids = [oi["order_id"] for oi in order_items]
    orders = list(db["order"].find({"id": {"$in": order_ids}, "status": "paid"}))
    revenue = sum(o.get("total_amount_cents", 0) for o in orders)
    tickets_sold = sum(oi.get("quantity", 0) for oi in order_items)
    return {
        "events_count": len(events),
        "tickets_sold": tickets_sold,
        "revenue_cents": revenue,
        "venues": list(db["venue"].find({"organizer_id": org["id"]}, {"_id": 0})),
        "events": [{"id": e["id"], "title": e["title"], "status": e["status"]} for e in events],
    }


# Venues
@app.get("/api/venues")
def list_venues(city: str = "Austin"):
    return list(db["venue"].find({"city": city}, {"_id": 0}))


@app.post("/api/venues")
def create_venue(req: VenueCreate, user: User = Depends(require_user)):
    org = db["organizer"].find_one({"user_id": user.id})
    if not org:
        raise HTTPException(status_code=403, detail="Organizer required")
    vid = new_id()
    doc = {"id": vid, "organizer_id": org["id"], **req.dict(), "created_at": now_ts(), "updated_at": now_ts()}
    db["venue"].insert_one(doc)
    return doc


@app.put("/api/venues/{venue_id}")
def update_venue(venue_id: str, req: VenueCreate, user: User = Depends(require_user)):
    org = db["organizer"].find_one({"user_id": user.id})
    venue = db["venue"].find_one({"id": venue_id})
    if not org or not venue or venue.get("organizer_id") != org["id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    changes = req.dict()
    changes["updated_at"] = now_ts()
    db["venue"].update_one({"id": venue_id}, {"$set": changes})
    return db["venue"].find_one({"id": venue_id}, {"_id": 0})


@app.get("/api/venues/{venue_id}")
def get_venue(venue_id: str):
    doc = db["venue"].find_one({"id": venue_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Venue not found")
    return doc


# Events
@app.get("/api/events")
def list_events(search: Optional[str] = None, category: Optional[str] = None, city: str = "Austin"):
    q: Dict[str, Any] = {"status": "published", "approved": True}
    if category:
        q["category"] = category
    # filter by venue city by joining manually
    venue_ids = [v["id"] for v in db["venue"].find({"city": city})]
    q["venue_id"] = {"$in": venue_ids}
    if search:
        q["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"subtitle": {"$regex": search, "$options": "i"}},
        ]
    events = list(db["event"].find(q, {"_id": 0}))
    # add first upcoming instance start time and min price
    for e in events:
        instances = list(db["eventinstance"].find({"event_id": e["id"], "is_cancelled": False}))
        instances.sort(key=lambda i: i.get("start_time"))
        e["upcoming_instances"] = [{"id": i["id"], "start_time": i["start_time"], "end_time": i.get("end_time") } for i in instances[:3]]
        # price
        tts = list(db["tickettype"].find({"event_instance_id": {"$in": [i["id"] for i in instances]}}))
        if tts:
            e["starting_price_cents"] = min(t.get("price_cents", 0) for t in tts)
        venue = db["venue"].find_one({"id": e["venue_id"]})
        e["venue_name"] = venue["name"] if venue else None
    return events


@app.get("/api/events/{event_id}")
def get_event(event_id: str):
    e = db["event"].find_one({"id": event_id}, {"_id": 0})
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    venue = db["venue"].find_one({"id": e["venue_id"]}, {"_id": 0})
    organizer = db["organizer"].find_one({"id": e["organizer_id"]}, {"_id": 0})
    instances = list(db["eventinstance"].find({"event_id": event_id, "is_cancelled": False}, {"_id": 0}))
    for inst in instances:
        tts = list(db["tickettype"].find({"event_instance_id": inst["id"]}, {"_id": 0}))
        inst["ticket_types"] = tts
    reviews = list(db["review"].find({"event_id": event_id}, {"_id": 0}))
    avg_rating = sum(r.get("rating", 0) for r in reviews) / len(reviews) if reviews else None
    return {**e, "venue": venue, "organizer": organizer, "instances": instances, "avg_rating": avg_rating, "reviews": reviews}


@app.post("/api/events")
def create_event(req: EventCreate, user: User = Depends(require_user)):
    org = db["organizer"].find_one({"user_id": user.id})
    if not org:
        raise HTTPException(status_code=403, detail="Organizer required")
    eid = new_id()
    doc = {
        "id": eid,
        "organizer_id": org["id"],
        **req.dict(),
        "approved": True,
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }
    db["event"].insert_one(doc)
    return doc


@app.put("/api/events/{event_id}")
def update_event(event_id: str, req: EventCreate, user: User = Depends(require_user)):
    org = db["organizer"].find_one({"user_id": user.id})
    ev = db["event"].find_one({"id": event_id})
    if not org or not ev or ev.get("organizer_id") != org["id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    changes = req.dict()
    changes["updated_at"] = now_ts()
    db["event"].update_one({"id": event_id}, {"$set": changes})
    return db["event"].find_one({"id": event_id}, {"_id": 0})


# Event instances
@app.post("/api/events/{event_id}/instances")
def add_instance(event_id: str, req: EventInstanceCreate, user: User = Depends(require_user)):
    ev = db["event"].find_one({"id": event_id})
    org = db["organizer"].find_one({"user_id": user.id})
    if not ev or not org or ev.get("organizer_id") != org["id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    iid = new_id()
    doc = {"id": iid, "event_id": event_id, **req.dict(), "created_at": now_ts(), "updated_at": now_ts()}
    db["eventinstance"].insert_one(doc)
    return doc


@app.get("/api/events/{event_id}/instances")
def list_instances(event_id: str):
    return list(db["eventinstance"].find({"event_id": event_id}, {"_id": 0}))


# Ticket types
@app.post("/api/event-instances/{instance_id}/ticket-types")
def add_ticket_type(instance_id: str, req: TicketTypeCreate, user: User = Depends(require_user)):
    inst = db["eventinstance"].find_one({"id": instance_id})
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    ev = db["event"].find_one({"id": inst["event_id"]})
    org = db["organizer"].find_one({"user_id": user.id})
    if not ev or not org or ev.get("organizer_id") != org["id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    ttid = new_id()
    doc = {
        "id": ttid,
        "event_instance_id": instance_id,
        "name": req.name,
        "description": req.description,
        "price_cents": req.price_cents,
        "currency": req.currency,
        "total_capacity": req.total_capacity,
        "remaining_capacity": req.total_capacity,
        "per_order_min": req.per_order_min,
        "per_order_max": req.per_order_max,
        "resale_allowed": False,
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }
    db["tickettype"].insert_one(doc)
    return doc


@app.get("/api/event-instances/{instance_id}/ticket-types")
def list_ticket_types(instance_id: str):
    return list(db["tickettype"].find({"event_instance_id": instance_id}, {"_id": 0}))


# Booking flow
SERVICE_FEE_RATE = 0.10


def _validate_availability(items: List[CartItem]):
    detailed = []
    for it in items:
        tt = db["tickettype"].find_one({"id": it.ticket_type_id})
        if not tt:
            raise HTTPException(status_code=404, detail=f"Ticket type not found: {it.ticket_type_id}")
        if it.quantity < tt.get("per_order_min", 1) or it.quantity > tt.get("per_order_max", 10):
            raise HTTPException(status_code=400, detail=f"Quantity out of bounds for {tt['name']}")
        if tt.get("remaining_capacity", 0) < it.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough capacity for {tt['name']}")
        detailed.append(tt)
    return detailed


@app.post("/api/cart/price-check")
def price_check(req: PriceCheckRequest):
    tts = _validate_availability(req.items)
    subtotal = 0
    for cart_item, tt in zip(req.items, tts):
        subtotal += tt["price_cents"] * cart_item.quantity
    fee = int(subtotal * SERVICE_FEE_RATE)
    return {"subtotal_cents": subtotal, "service_fee_cents": fee, "total_cents": subtotal + fee}


@app.post("/api/orders")
def create_order(req: OrderCreateRequest, user: User = Depends(require_user)):
    tts = _validate_availability(req.items)
    subtotal = sum(tt["price_cents"] * it.quantity for it, tt in zip(req.items, tts))
    fee = int(subtotal * SERVICE_FEE_RATE)
    order_id = new_id()
    order_doc = {
        "id": order_id,
        "user_id": user.id,
        "total_amount_cents": subtotal + fee,
        "currency": "USD",
        "service_fee_cents": fee,
        "status": "pending",
        "payment_provider": req.payment_provider,
        "payment_reference": None,
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }
    db["order"].insert_one(order_doc)
    # Items
    for it, tt in zip(req.items, tts):
        db["orderitem"].insert_one({
            "id": new_id(),
            "order_id": order_id,
            "ticket_type_id": tt["id"],
            "quantity": it.quantity,
            "unit_price_cents": tt["price_cents"],
            "created_at": now_ts(),
            "updated_at": now_ts(),
        })
        # For MVP, decrement capacity at order creation
        db["tickettype"].update_one({"id": tt["id"]}, {"$inc": {"remaining_capacity": -it.quantity}})
    return {"id": order_id, **order_doc}


@app.post("/api/orders/{order_id}/confirm")
def confirm_order(order_id: str, req: OrderConfirmRequest, user: User = Depends(require_user)):
    order = db["order"].find_one({"id": order_id})
    if not order or order.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("status") == "paid":
        return {"message": "Already confirmed"}
    db["order"].update_one({"id": order_id}, {"$set": {"status": "paid", "payment_reference": req.payment_reference or str(uuid.uuid4()), "updated_at": now_ts()}})
    # Create tickets for each item
    items = list(db["orderitem"].find({"order_id": order_id}))
    for item in items:
        tt = db["tickettype"].find_one({"id": item["ticket_type_id"]})
        inst_id = tt["event_instance_id"] if tt else None
        for _ in range(item["quantity"]):
            db["ticket"].insert_one({
                "id": new_id(),
                "order_item_id": item["id"],
                "user_id": user.id,
                "ticket_type_id": item["ticket_type_id"],
                "event_instance_id": inst_id,
                "qr_code_data": str(uuid.uuid4()),
                "status": "valid",
                "created_at": now_ts(),
                "updated_at": now_ts(),
            })
    return {"message": "Order confirmed"}


@app.get("/api/orders/me")
def my_orders(user: User = Depends(require_user)):
    orders = list(db["order"].find({"user_id": user.id}, {"_id": 0}))
    return orders


@app.get("/api/tickets/me")
def my_tickets(user: User = Depends(require_user)):
    tickets = list(db["ticket"].find({"user_id": user.id}, {"_id": 0}))
    # enrich with event and venue info
    for t in tickets:
        inst = db["eventinstance"].find_one({"id": t["event_instance_id"]})
        ev = db["event"].find_one({"id": inst["event_id"]}) if inst else None
        venue = db["venue"].find_one({"id": ev["venue_id"]}) if ev else None
        t["event"] = {"id": ev["id"], "title": ev["title"]} if ev else None
        t["instance"] = {"id": inst["id"], "start_time": inst["start_time"], "end_time": inst.get("end_time") } if inst else None
        t["venue"] = {"id": venue["id"], "name": venue["name"]} if venue else None
        tt = db["tickettype"].find_one({"id": t["ticket_type_id"]})
        if tt:
            t["ticket_type_name"] = tt["name"]
    return tickets


# Organizer analytics and attendees
@app.get("/api/organizers/me/events/{event_id}/attendees")
def attendees(event_id: str, user: User = Depends(require_user)):
    org = db["organizer"].find_one({"user_id": user.id})
    ev = db["event"].find_one({"id": event_id})
    if not org or not ev or ev.get("organizer_id") != org["id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    insts = list(db["eventinstance"].find({"event_id": event_id}))
    inst_ids = [i["id"] for i in insts]
    tts = list(db["tickettype"].find({"event_instance_id": {"$in": inst_ids}}))
    tt_ids = [t["id"] for t in tts]
    items = list(db["orderitem"].find({"ticket_type_id": {"$in": tt_ids}}))
    item_ids = [it["id"] for it in items]
    tickets = list(db["ticket"].find({"order_item_id": {"$in": item_ids}}, {"_id": 0}))
    return tickets


@app.get("/api/organizers/me/events/{event_id}/stats")
def event_stats(event_id: str, user: User = Depends(require_user)):
    org = db["organizer"].find_one({"user_id": user.id})
    ev = db["event"].find_one({"id": event_id})
    if not org or not ev or ev.get("organizer_id") != org["id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    insts = list(db["eventinstance"].find({"event_id": event_id}))
    inst_ids = [i["id"] for i in insts]
    tts = list(db["tickettype"].find({"event_instance_id": {"$in": inst_ids}}))
    tt_ids = [t["id"] for t in tts]
    items = list(db["orderitem"].find({"ticket_type_id": {"$in": tt_ids}}))
    order_ids = [it["order_id"] for it in items]
    paid_orders = list(db["order"].find({"id": {"$in": order_ids}, "status": "paid"}))
    revenue = sum(o.get("total_amount_cents", 0) for o in paid_orders)
    tickets_sold = sum(it.get("quantity", 0) for it in items)
    return {"tickets_sold": tickets_sold, "revenue_cents": revenue}


# Check-in
class CheckinRequest(BaseModel):
    ticket_qr_code_data: str


@app.post("/api/organizers/checkin")
def organizer_checkin(req: CheckinRequest, user: User = Depends(require_user)):
    org = db["organizer"].find_one({"user_id": user.id})
    if not org:
        raise HTTPException(status_code=403, detail="Organizer required")
    ticket = db["ticket"].find_one({"qr_code_data": req.ticket_qr_code_data})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    # ensure ticket belongs to this organizer's event
    inst = db["eventinstance"].find_one({"id": ticket["event_instance_id"]})
    ev = db["event"].find_one({"id": inst["event_id"]}) if inst else None
    if not ev or ev.get("organizer_id") != org["id"]:
        raise HTTPException(status_code=403, detail="Not allowed for this organizer")
    if ticket.get("status") == "checked_in":
        return {"status": "already_checked_in"}
    if ticket.get("status") != "valid":
        raise HTTPException(status_code=400, detail="Ticket not valid for check-in")
    db["ticket"].update_one({"id": ticket["id"]}, {"$set": {"status": "checked_in", "updated_at": now_ts()}})
    return {"status": "checked_in", "ticket_id": ticket["id"]}


# Admin (optional)
@app.get("/api/admin/events")
def admin_events(user: User = Depends(require_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return list(db["event"].find({}, {"_id": 0}))


@app.get("/")
def root():
    return {"message": "Buzz API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
