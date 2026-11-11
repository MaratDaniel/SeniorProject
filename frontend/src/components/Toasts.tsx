import { createContext, use, useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon } from "./Icons";

type Toast = { id: number; title: string; body?: string; leaving: boolean };
type ToastFn = (title: string, body?: string) => void;

const ToastContext = createContext<ToastFn | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const toast = useCallback<ToastFn>((title, body) => {
    const id = nextId.current++;
    setToasts((list) => [...list, { id, title, body, leaving: false }]);
    window.setTimeout(() => {
      setToasts((list) => list.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
      window.setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), 320);
    }, 4600);
  }, []);

  const value = useMemo(() => toast, [toast]);

  return (
    <ToastContext value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast${t.leaving ? " out" : ""}`}>
            <span className="t-ic"><Icon name="check" /></span>
            <div>
              <b>{t.title}</b>
              {t.body ? <span>{t.body}</span> : null}
            </div>
          </div>
        ))}
      </div>
    </ToastContext>
  );
}

export function useToast(): ToastFn {
  const value = use(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider");
  return value;
}
