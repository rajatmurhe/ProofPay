from typing import Literal
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field, field_validator

MessageType = Literal['Transaction','Payment','Refund','OTP','Credit Card Bill','Offer/Promotion','Cashback/Reward','EMI','Failed Transaction','Other']
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')
class InputMessage(Strict):
    body: str = Field(min_length=1, max_length=20000)
    source: Literal['sms','email','paste'] = 'sms'
    source_id: str | None = Field(default=None,max_length=200)
    sender: str | None = Field(default=None,max_length=200)
    received_at: datetime | None = None
class Batch(Strict):
    messages: list[InputMessage] = Field(min_length=1,max_length=200)
class Money(Strict):
    role: Literal['purchase','refund','balance','total due','minimum due','reward','discount','threshold','payment','emi','transfer','unknown']
    minor: int = Field(ge=0,le=10**15)
    currency: str | None = Field(default=None,pattern=r'^[A-Z]{3}$')
    evidence: str = Field(max_length=100)
class Evidence(Strict):
    field: str
    value: str
    observed: bool = True
    excerpt: str = Field(max_length=160)
class EventData(Strict):
    financial_relevance: Literal['relevant'] = 'relevant'
    message_type: MessageType = 'Other'
    subtype: str = 'unknown'
    status: Literal['successful','pending','initiated','failed','reversed','unknown'] = 'unknown'
    direction: Literal['debit','credit','unknown'] = 'unknown'
    financial_effect: Literal['account inflow','account outflow','card liability increase','card liability decrease','non-monetary','unknown'] = 'unknown'
    amounts: list[Money] = Field(default_factory=list)
    merchant_original: str | None = None
    merchant: str | None = None
    category: str = 'Uncategorised'
    intermediary: str | None = None
    enrichment: str = 'none'
    issuer: str | None = None
    instrument_type: Literal['bank account','credit card','debit card','wallet','loan','unknown'] = 'unknown'
    instrument_last4: str | None = Field(default=None,pattern=r'^\d{4}$')
    instrument_identity: str = 'unresolved'
    rail: Literal['UPI','card','netbanking','wallet','unknown'] = 'unknown'
    counterparty: str | None = None
    benefit_type: str | None = None
    event_date: date | None = None
    due_date: date | None = None
    expiry_date: date | None = None
    timezone: str | None = None
    date_precision: str = 'unknown'
    date_inferred: bool = False
    transaction_ref: str | None = None
    order_ref: str | None = None
    refund_ref: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    validation: list[str] = Field(default_factory=list)
    quality: Literal['validated','needs review','unresolved'] = 'unresolved'
    mode: Literal['rules','fixture','live'] = 'rules'
    parser_version: str = 'rules-1.1'
class Correction(Strict):
    field: Literal['merchant','category','event_date','status']
    value: str = Field(min_length=1,max_length=100)
    reason: str = Field(min_length=1,max_length=200)
class LinkInput(Strict):
    left_id: str
    right_id: str
    kind: Literal['duplicate','refund']
class LinkAction(Strict):
    status: Literal['accepted','rejected','undone']

class Credentials(Strict):
    email: str = Field(min_length=3,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=12,max_length=128)
    @field_validator('email')
    @classmethod
    def normalise_email(cls,value):return value.lower()
class GmailImport(Strict):
    after: date
    before: date
    limit: int = Field(default=20,ge=1,le=50)
    consent: Literal[True]
    cursor: str | None = Field(default=None,max_length=4096)
    @field_validator('before')
    @classmethod
    def date_window(cls,value,info):
        start=info.data.get('after')
        if start and not 0 < (value-start).days <= 31:raise ValueError('Choose a window of 1 to 31 days')
        return value
