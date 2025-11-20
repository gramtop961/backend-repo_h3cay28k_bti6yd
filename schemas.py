from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

# Core domain schemas mapped to MongoDB collections (collection name = class name lowercased)

class User(BaseModel):
    id: Optional[str] = Field(default=None, description="UUID string")
    name: str
    email: EmailStr
    password_hash: Optional[str] = None
    avatar_url: Optional[str] = None
    default_city: str = "Austin"
    is_admin: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Organizer(BaseModel):
    id: Optional[str] = None
    user_id: str
    display_name: str
    description: Optional[str] = None
    website_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    verification_status: Literal["pending", "verified", "rejected"] = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Venue(BaseModel):
    id: Optional[str] = None
    organizer_id: str
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Event(BaseModel):
    id: Optional[str] = None
    organizer_id: str
    venue_id: str
    title: str
    subtitle: Optional[str] = None
    description: str
    category: Literal["music","comedy","nightlife","theatre","workshop","festival","other"]
    tags: List[str] = []
    cover_image_url: Optional[str] = None
    min_age: Optional[int] = None
    status: Literal["draft","published","cancelled","completed"] = "published"
    approved: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Eventinstance(BaseModel):
    id: Optional[str] = None
    event_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    timezone: str = "America/Chicago"
    sales_start_time: Optional[datetime] = None
    sales_end_time: Optional[datetime] = None
    is_cancelled: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Tickettype(BaseModel):
    id: Optional[str] = None
    event_instance_id: str
    name: str
    description: Optional[str] = None
    price_cents: int
    currency: str = "USD"
    total_capacity: int
    remaining_capacity: int
    per_order_min: int = 1
    per_order_max: int = 10
    resale_allowed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Order(BaseModel):
    id: Optional[str] = None
    user_id: str
    total_amount_cents: int
    currency: str = "USD"
    service_fee_cents: int
    status: Literal["pending","paid","cancelled","refunded"] = "pending"
    payment_provider: str = "test"
    payment_reference: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Orderitem(BaseModel):
    id: Optional[str] = None
    order_id: str
    ticket_type_id: str
    quantity: int
    unit_price_cents: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Ticket(BaseModel):
    id: Optional[str] = None
    order_item_id: str
    user_id: str
    ticket_type_id: str
    event_instance_id: str
    qr_code_data: str
    status: Literal["valid","checked_in","cancelled","refunded"] = "valid"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Review(BaseModel):
    id: Optional[str] = None
    user_id: str
    event_id: str
    rating: int
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
