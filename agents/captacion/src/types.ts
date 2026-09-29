export interface Env {
  DB: D1Database;
  AI: Ai;
  ASSETS: Fetcher;
  ADMIN_TOKEN: string;
  APP_NAME: string;
}

export const STATUSES = [
  "new", "contacted", "interested", "waiting_bill", "bill_received",
  "proposal_sent", "won", "lost",
] as const;

export type LeadStatus = typeof STATUSES[number];

export interface LeadInput {
  name: string;
  phone?: string;
  email?: string;
  source?: "instagram" | "whatsapp" | "web" | "referral" | "manual";
  customer_type?: "home" | "business" | "community" | "unknown";
  supply_type?: "electricity" | "gas" | "both" | "fuel" | "unknown";
  notes?: string;
  consent?: boolean;
  status?: LeadStatus;
  priority?: "high" | "medium" | "low";
  next_followup_at?: string;
}
