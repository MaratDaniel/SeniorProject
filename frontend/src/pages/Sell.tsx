import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { api, isApiError, serverNow, uploadImage } from "../api/client";
import type { AuctionDetail, Listing } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icons";
import { ErrorBanner, FieldError, Loading, RequireAuth } from "../components/Layout";
import { NoPhoto } from "../components/LotCard";
import { useToast } from "../components/Toasts";
import { useCategories } from "../hooks/useCategories";
import { dateLong, fromLocalInput, money, parseAmount, toCents, toLocalInput } from "../lib/format";

const MAX_PHOTOS = 8;
const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png"];

type Photo = {
  key: string;
  name: string;
  preview: string;
  status: "uploading" | "done" | "failed";
  progress: number;
  id?: number;
  url?: string;
  error?: string;
};

function roundedFuture(minutesAhead: number): Date {
  const d = new Date(Date.now() + minutesAhead * 60_000);
  d.setSeconds(0, 0);
  d.setMinutes(Math.ceil(d.getMinutes() / 5) * 5);
  return d;
}

function Gate({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <div className="pg-sell wrap">
      <header className="page-head">
        <h1 className="headline">{title}</h1>
        {children}
      </header>
    </div>
  );
}

export function Sell() {
  return (
    <RequireAuth>
      <SellGate />
    </RequireAuth>
  );
}

function SellGate() {
  const { user } = useAuth();
  useEffect(() => {
    document.title = "Create a listing | Adal";
  }, []);
  if (!user) return <Loading />;
  if (user.role === "buyer") {
    return (
      <Gate title={<>Selling needs a <i>seller</i> account</>}>
        <p className="lede">
          This account was created for buying. Create a separate account and choose "Buy and sell" to list items.
        </p>
        <div className="acts-row">
          <Link className="btn second" to="/auctions">
            Browse auctions
          </Link>
        </div>
      </Gate>
    );
  }
  if (!user.email_verified) {
    return (
      <Gate title={<>Confirm your <i>email</i> first</>}>
        <p className="lede">Selling opens once your address is confirmed. Open the link we sent to {user.email}.</p>
      </Gate>
    );
  }
  if (!user.mfa_enabled) {
    return (
      <Gate title={<>Turn on two-step <i>sign-in</i> first</>}>
        <p className="lede">Sellers sign in with a code from an authenticator app. It takes about a minute to set up.</p>
        <div className="acts-row">
          <Link className="btn" to="/account/security?next=%2Fsell">
            Set up two-step sign-in
          </Link>
        </div>
      </Gate>
    );
  }
  return <SellForm />;
}

function SellForm() {
  const navigate = useNavigate();
  const toast = useToast();
  const categories = useCategories();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [startingPrice, setStartingPrice] = useState("");
  const [reserve, setReserve] = useState("");
  const [step, setStep] = useState("5.00");
  const [openNow, setOpenNow] = useState(true);
  const [opens, setOpens] = useState(() => toLocalInput(roundedFuture(60)));
  const [closes, setCloses] = useState(() => toLocalInput(roundedFuture(24 * 60)));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listingId, setListingId] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const photosRef = useRef(photos);

  useEffect(() => {
    photosRef.current = photos;
  }, [photos]);
  useEffect(() => () => photosRef.current.forEach((p) => URL.revokeObjectURL(p.preview)), []);
  useEffect(() => {
    if (!category && categories.length > 0) setCategory(categories[0].slug);
  }, [categories, category]);

  function addFiles(files: FileList | File[]) {
    const list = Array.from(files);
    const room = MAX_PHOTOS - photos.length;
    if (room <= 0) {
      toast("Photo limit reached", `A listing can have up to ${MAX_PHOTOS} photos.`);
      return;
    }
    for (const file of list.slice(0, room)) {
      const key = `${file.name}-${file.size}-${Math.random().toString(36).slice(2)}`;
      if (!ACCEPTED.includes(file.type)) {
        toast("Photo not added", `${file.name} is not a JPEG or PNG.`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        toast("Photo not added", `${file.name} is larger than 5 MB.`);
        continue;
      }
      const photo: Photo = { key, name: file.name, preview: URL.createObjectURL(file), status: "uploading", progress: 0 };
      setPhotos((ps) => [...ps, photo]);
      uploadImage(file, (progress) =>
        setPhotos((ps) => ps.map((p) => (p.key === key ? { ...p, progress } : p))),
      )
        .then((res) => {
          setPhotos((ps) => ps.map((p) => (p.key === key ? { ...p, status: "done", progress: 100, id: res.id, url: res.url } : p)));
        })
        .catch((err) => {
          const message = err instanceof Error ? err.message : "The upload failed.";
          setPhotos((ps) => ps.map((p) => (p.key === key ? { ...p, status: "failed", error: message } : p)));
        });
    }
    if (list.length > room) toast("Photo limit reached", `Only the first ${room} were added.`);
  }

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    if (e.target.files) addFiles(e.target.files);
    e.target.value = "";
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  }

  function removePhoto(key: string) {
    setPhotos((ps) => {
      const gone = ps.find((p) => p.key === key);
      if (gone) URL.revokeObjectURL(gone.preview);
      return ps.filter((p) => p.key !== key);
    });
  }

  function makeCover(key: string) {
    setPhotos((ps) => {
      const chosen = ps.find((p) => p.key === key);
      return chosen ? [chosen, ...ps.filter((p) => p.key !== key)] : ps;
    });
  }

  // ----- derived values for the preview and validation
  const startsIso = openNow ? null : fromLocalInput(opens);
  const endsIso = fromLocalInput(closes);
  const startingParsed = parseAmount(startingPrice);
  const reserveParsed = reserve.trim() ? parseAmount(reserve) : null;
  const cover = photos.find((p) => p.status !== "failed");

  function validate(): Record<string, string> {
    const e: Record<string, string> = {};
    const t = title.trim();
    if (t.length < 3) e.title = "Give the item a title of at least 3 characters.";
    else if (t.length > 80) e.title = "Keep the title to 80 characters.";
    if (description.length > 4000) e.description = "Keep the description to 4,000 characters.";
    if (!category) e.category = "Choose a category.";
    if (!startingParsed || toCents(startingParsed) < 1) e.starting_price = "Enter a starting price like 200.00.";
    if (reserve.trim()) {
      if (!reserveParsed) e.reserve_price = "Enter a reserve like 300.00, or leave it empty.";
      else if (startingParsed && toCents(reserveParsed) < toCents(startingParsed))
        e.reserve_price = "The reserve cannot be lower than the starting price.";
    }
    const stepParsed = parseAmount(step);
    if (!stepParsed || toCents(stepParsed) < 1) e.min_increment = "Enter a bid step of at least 0.01.";
    const start = openNow ? serverNow() : startsIso ? Date.parse(startsIso) : NaN;
    const end = endsIso ? Date.parse(endsIso) : NaN;
    if (!openNow && (Number.isNaN(start) || start < serverNow() - 60_000)) e.starts_at = "Choose an opening time that is not in the past.";
    if (Number.isNaN(end)) e.ends_at = "Choose a closing time.";
    else if (!Number.isNaN(start)) {
      if (end <= start) e.ends_at = "The closing time must be after the opening time. Move the closing time later and try again.";
      else if (end - start < 5 * 60_000) e.ends_at = "An auction runs for at least 5 minutes.";
      else if (end - start > 30 * 24 * 3600_000) e.ends_at = "An auction runs for at most 30 days.";
    }
    if (photos.some((p) => p.status === "uploading")) e.photos = "Wait for the photos to finish uploading.";
    return e;
  }

  async function publish(ev: FormEvent) {
    ev.preventDefault();
    setFormError(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) {
      setFormError("Some fields need attention.");
      return;
    }
    setBusy(true);
    try {
      let id = listingId;
      if (id === null) {
        const listing = await api<Listing>("/api/listings", {
          body: {
            title: title.trim(),
            description: description.trim(),
            category,
            starting_price: startingParsed,
            reserve_price: reserveParsed,
            image_ids: photos.filter((p) => p.status === "done" && p.id !== undefined).map((p) => p.id),
          },
        });
        id = listing.id;
        setListingId(id);
      }
      const auction = await api<AuctionDetail>(`/api/listings/${id}/auction`, {
        body: {
          format: "english",
          starts_at: openNow ? new Date(serverNow()).toISOString() : startsIso,
          ends_at: endsIso,
          min_increment: parseAmount(step),
        },
      });
      toast("Auction published", openNow ? "Bidding is open now." : `Bidding opens ${dateLong(auction.starts_at)}.`);
      navigate(`/auctions/${auction.id}`);
    } catch (err) {
      if (isApiError(err, "validation_error")) {
        const fields = err.fieldErrors();
        setErrors(fields);
        setFormError(Object.keys(fields).length ? "Some fields need attention." : err.message);
      } else if (isApiError(err, "invalid_schedule")) {
        setErrors({ ends_at: err.message });
        setFormError(listingId !== null ? "The listing is saved. Fix the schedule and publish again." : err.message);
      } else if (isApiError(err, "mfa_setup_required") || isApiError(err, "email_not_verified")) {
        setFormError(err.message);
      } else {
        setFormError(err instanceof Error ? err.message : "The auction could not be published.");
      }
    } finally {
      setBusy(false);
    }
  }

  const err = (key: string) => (errors[key] ? <FieldError id={`${key}-err`}>{errors[key]}</FieldError> : null);

  return (
    <div className="pg-sell wrap">
      <header className="page-head">
        <h1 className="headline">
          Create a <i>listing</i>
        </h1>
        <p className="lede">
          Choose how the item is sold, set the price and the schedule, and check what bidders will see before you publish.
        </p>
        <p className="secure" style={{ alignSelf: "flex-start" }}>
          <Icon name="lock" />
          Signed in with two-step sign-in, required for selling
        </p>
      </header>

      <div className="lay">
        <form onSubmit={publish} noValidate>
          {formError ? <ErrorBanner>{formError}</ErrorBanner> : null}

          <section className="sec" role="group" aria-labelledby="g1">
            <h2 className="legend" id="g1">
              <span className="num">1</span>The item
            </h2>
            <div className={`field${errors.title ? " bad" : ""}`}>
              <label htmlFor="title">Title</label>
              <input
                className="input"
                id="title"
                maxLength={80}
                value={title}
                aria-invalid={errors.title ? true : undefined}
                onChange={(e) => setTitle(e.target.value)}
              />
              {err("title") ?? <span className="hint">Say what it is in plain words. Up to 80 characters.</span>}
            </div>
            <div className={`field${errors.description ? " bad" : ""}`}>
              <label htmlFor="desc">Description</label>
              <textarea
                className="textarea"
                id="desc"
                maxLength={4000}
                placeholder="Condition, size, history, anything a buyer should know before bidding."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              {err("description")}
            </div>
            <div className={`field${errors.category ? " bad" : ""}`}>
              <label htmlFor="category">Category</label>
              <select className="select" id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
                {categories.length === 0 ? <option value="">Loading categories</option> : null}
                {categories.map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.name}
                  </option>
                ))}
              </select>
              {err("category")}
            </div>
            <div className="field">
              <span className="label">Photos</span>
              <div
                className={`drop${dragging ? " over" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
              >
                <Icon name="upload" />
                <p>
                  <b>Drop photos here</b> or choose them from your device
                </p>
                <button className="btn second" type="button" onClick={() => fileInput.current?.click()}>
                  Choose photos
                </button>
                <input
                  ref={fileInput}
                  className="vh"
                  type="file"
                  accept="image/jpeg,image/png"
                  multiple
                  tabIndex={-1}
                  aria-hidden="true"
                  onChange={onPick}
                />
                <p className="note">JPEG or PNG, up to 5 MB each, at most {MAX_PHOTOS}. The first photo is the cover.</p>
              </div>
              {err("photos")}
              {photos.length > 0 ? (
                <ul className="photo-list">
                  {photos.map((p, i) => (
                    <li key={p.key} className="drop has">
                      <img src={p.url ?? p.preview} alt={`Selected photo ${i + 1}`} />
                      <div>
                        <p>
                          <b>{p.name}</b>
                        </p>
                        {p.status === "uploading" ? (
                          <>
                            <div
                              className="prog"
                              role="progressbar"
                              aria-valuemin={0}
                              aria-valuemax={100}
                              aria-valuenow={p.progress}
                              aria-label={`Uploading ${p.name}`}
                            >
                              <i style={{ width: `${p.progress}%` }} />
                            </div>
                            <p className="note">Uploading {p.progress}%</p>
                          </>
                        ) : p.status === "failed" ? (
                          <p className="msg">
                            <Icon name="alert" />
                            <span>{p.error}</span>
                          </p>
                        ) : (
                          <p className="note">{i === 0 ? "Cover photo" : `Photo ${i + 1}`}</p>
                        )}
                      </div>
                      <div className="photo-acts">
                        {i > 0 && p.status === "done" ? (
                          <button className="link-btn" type="button" onClick={() => makeCover(p.key)}>
                            Make cover
                          </button>
                        ) : null}
                        <button className="link-btn" type="button" onClick={() => removePhoto(p.key)}>
                          Remove
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </section>

          <section className="sec" role="group" aria-labelledby="g2">
            <h2 className="legend" id="g2">
              <span className="num">2</span>How it is sold
            </h2>
            <div className="fmt" role="radiogroup" aria-label="Selling format">
              <label>
                <input type="radio" name="fmt" value="english" defaultChecked />
                <span>
                  <b>English</b>
                  <small>The price rises with each bid. Highest bid at close wins.</small>
                </span>
              </label>
              <label>
                <input type="radio" name="fmt" value="dutch" disabled />
                <span>
                  <b>Dutch</b>
                  <small>The price falls on a schedule. First to accept wins.</small>
                  <span className="soon">Coming soon</span>
                </span>
              </label>
              <label>
                <input type="radio" name="fmt" value="sealed_first_price" disabled />
                <span>
                  <b>Sealed first-price</b>
                  <small>One hidden bid each. Highest wins and pays their bid.</small>
                  <span className="soon">Coming soon</span>
                </span>
              </label>
              <label>
                <input type="radio" name="fmt" value="vickrey" disabled />
                <span>
                  <b>Sealed second-price</b>
                  <small>One hidden bid each. Highest wins, pays the second-highest.</small>
                  <span className="soon">Coming soon</span>
                </span>
              </label>
            </div>
          </section>

          <section className="sec" role="group" aria-labelledby="g3">
            <h2 className="legend" id="g3">
              <span className="num">3</span>Price and schedule
            </h2>
            <div className="two">
              <div className={`field${errors.starting_price ? " bad" : ""}`}>
                <label htmlFor="start">Starting price</label>
                <input
                  className="input"
                  id="start"
                  inputMode="decimal"
                  placeholder="200.00"
                  value={startingPrice}
                  onChange={(e) => setStartingPrice(e.target.value)}
                />
                {err("starting_price") ?? <span className="hint">The first bid must be at least this.</span>}
              </div>
              <div className={`field${errors.reserve_price ? " bad" : ""}`}>
                <label htmlFor="reserve">
                  Reserve price <span className="optional">(optional)</span>
                </label>
                <input
                  className="input"
                  id="reserve"
                  inputMode="decimal"
                  placeholder="Not set"
                  value={reserve}
                  onChange={(e) => setReserve(e.target.value)}
                />
                {err("reserve_price") ?? (
                  <span className="hint">Bidders never see this number. They only see whether it is met.</span>
                )}
              </div>
            </div>
            <div className="two">
              <div className={`field${errors.min_increment ? " bad" : ""}`}>
                <label htmlFor="step">Bid step</label>
                <input
                  className="input"
                  id="step"
                  inputMode="decimal"
                  value={step}
                  onChange={(e) => setStep(e.target.value)}
                />
                {err("min_increment") ?? <span className="hint">Each new bid must beat the current price by at least this.</span>}
              </div>
              <div />
            </div>
            <label className="check">
              <input type="checkbox" checked={openNow} onChange={(e) => setOpenNow(e.target.checked)} />
              Open bidding as soon as I publish
            </label>
            <div className="two">
              {!openNow ? (
                <div className={`field${errors.starts_at ? " bad" : ""}`}>
                  <label htmlFor="opens">Opens</label>
                  <input className="input" id="opens" type="datetime-local" value={opens} onChange={(e) => setOpens(e.target.value)} />
                  {err("starts_at")}
                </div>
              ) : null}
              <div className={`field${errors.ends_at ? " bad" : ""}`}>
                <label htmlFor="closes">Closes</label>
                <input
                  className="input"
                  id="closes"
                  type="datetime-local"
                  value={closes}
                  aria-invalid={errors.ends_at ? true : undefined}
                  onChange={(e) => setCloses(e.target.value)}
                />
                {err("ends_at")}
              </div>
            </div>
            <p className="note">Times are in your time zone. Auctions run for at least 5 minutes and at most 30 days.</p>
          </section>

          <div className="form-acts">
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Publishing" : "Publish auction"}
            </button>
          </div>
        </form>

        <aside className="preview" aria-label="What bidders will see">
          <div className="card">
            <div className="ph">{cover ? <img src={cover.url ?? cover.preview} alt="Cover photo preview" /> : <NoPhoto />}</div>
            <span className="pill plain" style={{ padding: 0 }}>
              {openNow ? "Opens when you publish" : startsIso ? `Opens ${dateLong(startsIso)}` : "Choose an opening time"}
            </span>
            <h2>{title.trim() || "Untitled item"}</h2>
            <p className="price">
              <span className="label">Starting price</span>
              <br />
              <b>{startingParsed ? money(startingParsed) : "0.00"}</b>
            </p>
            <ul className="ruled">
              <li>
                <Icon name="check" />
                <span>English auction: the highest bid at the close wins.</span>
              </li>
              <li>
                <Icon name="clock" />
                <span>{endsIso ? `Closes ${dateLong(endsIso)}` : "Choose a closing time"}</span>
              </li>
              <li>
                <Icon name="eye" />
                <span>{reserveParsed ? "Reserve price set. Bidders see whether it is met." : "No reserve price"}</span>
              </li>
              <li>
                <Icon name="arrow" />
                <span>Bids go up in steps of at least {parseAmount(step) ? money(parseAmount(step)) : "the bid step"}.</span>
              </li>
            </ul>
          </div>
          <p className="note">Rules are shown on the auction page before anyone bids. Changing them after the first bid is not allowed.</p>
        </aside>
      </div>
    </div>
  );
}
