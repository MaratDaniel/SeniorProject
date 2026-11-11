import { useEffect, useState } from "react";

const DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

// Each digit is a vertical reel that rolls to its value (adal.css .snum).
// When the number of characters changes the reels are rebuilt without animation.
function Reels({ value }: { value: string }) {
  const [snap, setSnap] = useState(true);
  useEffect(() => {
    let second = 0;
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => setSnap(false));
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
  }, []);

  return (
    <span className={`snum${snap ? " snap" : ""}`}>
      <span className="vh">{value}</span>
      {value.split("").map((ch, i) =>
        /\d/.test(ch) ? (
          <span key={i} className="d" aria-hidden="true">
            <span style={{ transform: `translateY(-${Number(ch) * 1.1}em)` }}>
              {DIGITS.map((d) => (
                <b key={d}>{d}</b>
              ))}
            </span>
          </span>
        ) : (
          <span key={i} className="c" aria-hidden="true">
            {ch}
          </span>
        ),
      )}
    </span>
  );
}

export function SlidingNumber({ value }: { value: string }) {
  return <Reels key={value.length} value={value} />;
}
