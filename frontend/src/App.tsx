import { createBrowserRouter, Outlet, ScrollRestoration } from "react-router";
import { SpriteDefs } from "./components/Icons";
import { AccountLayout, SiteLayout } from "./components/Layout";
import { CheckEmail, Forgot, ResetPassword, Security, SignIn, SignUp, VerifyEmail } from "./pages/Account";
import { AuctionPage } from "./pages/Auction";
import { Auctions } from "./pages/Auctions";
import { Checkout } from "./pages/Checkout";
import { DevMailbox } from "./pages/DevMailbox";
import { Home } from "./pages/Home";
import { Me } from "./pages/Me";
import { NotFound, RouteError } from "./pages/NotFound";
import { Sell } from "./pages/Sell";

function Root() {
  return (
    <>
      <SpriteDefs />
      <ScrollRestoration />
      <Outlet />
    </>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Root />,
    errorElement: <RouteError />,
    children: [
      {
        element: <SiteLayout />,
        children: [
          { index: true, element: <Home /> },
          { path: "auctions", element: <Auctions /> },
          { path: "auctions/:id", element: <AuctionPage /> },
          { path: "sell", element: <Sell /> },
          { path: "checkout/:id", element: <Checkout /> },
          { path: "me", element: <Me /> },
          { path: "dev/mailbox", element: <DevMailbox /> },
          { path: "*", element: <NotFound /> },
        ],
      },
      {
        element: <AccountLayout />,
        children: [
          { path: "account/sign-in", element: <SignIn /> },
          { path: "account/sign-up", element: <SignUp /> },
          { path: "account/check-email", element: <CheckEmail /> },
          { path: "account/security", element: <Security /> },
          { path: "account/forgot", element: <Forgot /> },
          { path: "verify-email", element: <VerifyEmail /> },
          { path: "reset-password", element: <ResetPassword /> },
        ],
      },
    ],
  },
]);
