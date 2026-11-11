import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, isApiError } from "../api/client";
import type { OutboxMessage } from "../api/types";
import { ErrorBanner, Loading } from "../components/Layout";
import { dateShort } from "../lib/format";

const APP_PATHS = ["/verify-email", "/reset-password"];

/** Links that point at this app open in place; anything else stays a plain external link. */
function MailLink({ href }: { href: string }) {
  let url: URL | null = null;
  try {
    url = new URL(href, window.location.origin);
  } catch {
    url = null;
  }
  if (!url || (url.protocol !== "http:" && url.protocol !== "https:")) return <span className="note">{href}</span>;
  const inApp = url.origin === window.location.origin || APP_PATHS.includes(url.pathname);
  if (inApp) return <Link to={`${url.pathname}${url.search}`}>{url.pathname}{url.search ? "?…" : ""}</Link>;
  return (
    <a href={url.toString()} rel="noreferrer noopener">
      {url.toString()}
    </a>
  );
}

export function DevMailbox() {
  const [messages, setMessages] = useState<OutboxMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api<OutboxMessage[]>("/api/dev/outbox", { auth: false })
      .then(setMessages)
      .catch((e) =>
        setError(
          isApiError(e) && e.status === 404
            ? "The dev mailbox is only available when the backend runs with ADAL_ENV=dev."
            : e instanceof Error
              ? e.message
              : "The mailbox could not be loaded.",
        ),
      );
  }, []);

  useEffect(() => {
    document.title = "Dev mailbox | Adal";
    load();
  }, [load]);

  return (
    <div className="pg-me wrap">
      <header className="page-head">
        <h1 className="headline">
          Dev <i>mailbox</i>
        </h1>
        <p className="lede">Email is not delivered in development. Verification and reset links land here instead.</p>
        <div className="acts-row">
          <button className="btn second" type="button" onClick={load}>
            Refresh
          </button>
        </div>
      </header>
      {error ? <ErrorBanner>{error}</ErrorBanner> : null}
      {messages === null && !error ? <Loading /> : null}
      {messages && messages.length === 0 ? <p className="note">No messages yet.</p> : null}
      <ul className="mailbox">
        {(messages ?? []).map((m) => (
          <li key={m.id} className="mail-item">
            <div className="mail-head">
              <b>{m.subject}</b>
              <span className="note">
                To {m.to} &middot; {dateShort(m.created_at)}
              </span>
            </div>
            <p className="mail-body">{m.body}</p>
            {m.links.length > 0 ? (
              <ul className="mail-links">
                {m.links.map((href) => (
                  <li key={href}>
                    <MailLink href={href} />
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
