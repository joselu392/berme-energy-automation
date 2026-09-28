PRAGMA foreign_keys = ON;

CREATE TABLE leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('instagram','whatsapp','web','referral','manual')),
  customer_type TEXT NOT NULL DEFAULT 'unknown' CHECK(customer_type IN ('home','business','community','unknown')),
  supply_type TEXT NOT NULL DEFAULT 'unknown' CHECK(supply_type IN ('electricity','gas','both','fuel','unknown')),
  status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','contacted','interested','waiting_bill','bill_received','proposal_sent','won','lost')),
  priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('high','medium','low')),
  notes TEXT NOT NULL DEFAULT '',
  consent INTEGER NOT NULL DEFAULT 0 CHECK(consent IN (0,1)),
  next_followup_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE activities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_followup ON leads(next_followup_at);
CREATE INDEX idx_activities_lead ON activities(lead_id);
