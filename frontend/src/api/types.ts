// Mirrors docs/API.md. Money is always a string with two decimals; times are ISO 8601 UTC strings.

export type Role = "buyer" | "seller" | "admin";

export type User = {
  id: number;
  email: string;
  role: Role;
  email_verified: boolean;
  mfa_enabled: boolean;
  created_at: string;
};

export type AuctionStatus = "scheduled" | "active" | "closed" | "no_sale" | "cancelled";
export type AuctionFormat = "english" | "dutch" | "sealed_first_price" | "vickrey";

export type AuctionCard = {
  id: number;
  listing_id: number;
  title: string;
  category: string;
  cover_url: string | null;
  format: AuctionFormat;
  status: AuctionStatus;
  starting_price: string;
  current_price: string | null;
  bid_count: number;
  starts_at: string;
  ends_at: string;
  reserve_met: boolean | null;
};

export type Bid = { bidder_number: number; amount: string; placed_at: string };

export type Viewer = {
  is_seller: boolean;
  bidder_number: number | null;
  is_leader: boolean;
  transaction_id: number | null;
};

export type AuctionDetail = AuctionCard & {
  description: string;
  images: { id: number; url: string }[];
  min_increment: string;
  min_next_bid: string | null;
  server_time: string;
  bids: Bid[];
  leader_bidder_number: number | null;
  winner_bidder_number: number | null;
  final_price: string | null;
  closed_at: string | null;
  viewer: Viewer | null;
};

export type AuctionPublic = Omit<AuctionDetail, "viewer">;

export type Listing = {
  id: number;
  title: string;
  description: string;
  category: string;
  starting_price: string;
  reserve_price: string | null;
  images: { id: number; url: string }[];
  status: "active" | "withdrawn";
  auction_id: number | null;
  created_at: string;
};

export type Delivery = { full_name: string; address: string; city: string; postal_code: string };

export type TransactionStatus = "pending" | "completed" | "expired";

export type Transaction = {
  id: number;
  reference: string;
  auction_id: number;
  title: string;
  cover_url: string | null;
  amount: string;
  status: TransactionStatus;
  role: "buyer" | "seller";
  created_at: string;
  expires_at: string;
  completed_at: string | null;
  won_at: string;
  delivery: Delivery | null;
};

export type Category = { slug: string; name: string };

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type LoginResult =
  | { status: "ok"; access_token: string; user: User }
  | { status: "mfa_required"; mfa_ticket: string };

export type SessionResult = { access_token: string; user: User };

export type MfaSetup = { secret: string; otpauth_uri: string; qr_svg: string };

export type OutboxMessage = {
  id: number;
  to: string;
  subject: string;
  body: string;
  links: string[];
  created_at: string;
};

export type AuctionEvent =
  | { type: "snapshot"; auction: AuctionPublic }
  | { type: "status_changed"; auction_id: number; status: AuctionStatus }
  | {
      type: "bid_placed";
      auction_id: number;
      bid: Bid;
      current_price: string;
      min_next_bid: string;
      bid_count: number;
      reserve_met: boolean | null;
      leader_bidder_number: number;
      ends_at: string;
    }
  | { type: "time_extended"; auction_id: number; ends_at: string }
  | {
      type: "auction_closed";
      auction_id: number;
      status: "closed" | "no_sale";
      final_price: string | null;
      winner_bidder_number: number | null;
      closed_at: string;
    };

export type ApiErrorBody = {
  error: { code: string; message: string; details?: Record<string, unknown> };
};
