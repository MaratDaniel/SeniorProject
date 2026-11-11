import { useEffect } from "react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router";
import { SpriteDefs } from "../components/Icons";

export function NotFound() {
  useEffect(() => {
    document.title = "Page not found | Adal";
  }, []);
  return (
    <div className="pg-me wrap">
      <div className="empty" style={{ marginTop: 64 }}>
        <p className="title">This page does not exist.</p>
        <p className="note">The link may be incomplete, or the page has moved.</p>
        <Link className="btn second" to="/">
          Go to the home page
        </Link>
      </div>
    </div>
  );
}

/** Shown when a route throws while rendering. */
export function RouteError() {
  const error = useRouteError();
  const detail = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : null;
  return (
    <div className="pg-me wrap">
      <SpriteDefs />
      <div className="empty" style={{ marginTop: 64 }}>
        <p className="title">Something went wrong on this page.</p>
        <p className="note">{detail ?? "Reload the page. If it keeps happening, go back to the home page."}</p>
        <a className="btn second" href="/">
          Go to the home page
        </a>
      </div>
    </div>
  );
}
