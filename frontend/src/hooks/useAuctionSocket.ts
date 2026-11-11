import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { AuctionEvent } from "../api/types";

export type SocketState = "connecting" | "open" | "lost";

/**
 * Live events for one auction. Reconnects with backoff; every (re)connect starts with a
 * `snapshot`, so the caller simply replaces its state on that event.
 */
export function useAuctionSocket(auctionId: number | null, onEvent: (event: AuctionEvent) => void): SocketState {
  const [state, setState] = useState<SocketState>("connecting");
  const handler = useRef(onEvent);
  useLayoutEffect(() => {
    handler.current = onEvent;
  });

  useEffect(() => {
    if (auctionId === null) return;
    let socket: WebSocket | null = null;
    let stopped = false;
    let attempt = 0;
    let timer: number | undefined;

    const connect = () => {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${window.location.host}/ws/auctions/${auctionId}`);
      socket.onopen = () => {
        attempt = 0;
        setState("open");
      };
      socket.onmessage = (message) => {
        if (typeof message.data !== "string") return;
        let event: AuctionEvent;
        try {
          event = JSON.parse(message.data) as AuctionEvent;
        } catch {
          return;
        }
        if (event && typeof event === "object" && "type" in event) handler.current(event);
      };
      socket.onclose = () => {
        if (stopped) return;
        setState("lost");
        const delay = Math.min(15000, 1000 * 2 ** attempt) + Math.floor(Math.random() * 400);
        attempt += 1;
        timer = window.setTimeout(connect, delay);
      };
      socket.onerror = () => socket?.close();
    };

    const reconnectNow = () => {
      if (socket && socket.readyState === WebSocket.CLOSED) {
        window.clearTimeout(timer);
        attempt = 0;
        connect();
      }
    };

    setState("connecting");
    connect();
    window.addEventListener("online", reconnectNow);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      window.removeEventListener("online", reconnectNow);
      socket?.close();
    };
  }, [auctionId]);

  return state;
}
