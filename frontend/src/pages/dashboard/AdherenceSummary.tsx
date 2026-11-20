/**
 * The seven-day adherence figure.
 *
 * The important case is `rate === null`, which the API returns when no dose
 * has resolved yet. It must read as "no data", never as 0%. A new patient
 * shown "0% adherence" would look to a caregiver like someone who has missed
 * everything - a false alarm invented by the interface rather than found in
 * the data.
 *
 * The counts sit next to the percentage for the same reason the API returns
 * them: 80% over five doses and 80% over five hundred are different
 * situations, and the percentage alone hides which one you are looking at.
 */
import type { Adherence } from "../../api/types";
import { Card } from "../../components";
import { percent } from "./format";

export function AdherenceSummary({ adherence }: { adherence: Adherence | null }) {
  if (adherence === null) return null;

  const { rate, taken, missed, skipped, resolved, days } = adherence;

  return (
    <Card title={`Last ${days} days`}>
      {rate === null ? (
        <p className="dash-empty">
          Not enough history yet. Once you have logged a few doses, your
          adherence will appear here.
        </p>
      ) : (
        <div className="adherence">
          <p className="adherence__figure">
            <span className="adherence__value">{percent(rate)}</span>
            <span className="adherence__caption">of doses taken on time</span>
          </p>

          {/* aria-hidden: the bar only repeats the percentage above it, so
              announcing it again would be noise for a screen-reader user. */}
          <div
            className="adherence__bar"
            aria-hidden="true"
            data-level={rate >= 0.8 ? "good" : rate >= 0.5 ? "fair" : "low"}
          >
            <span style={{ width: `${Math.round(rate * 100)}%` }} />
          </div>

          <dl className="adherence__counts">
            <div>
              <dt>Taken</dt>
              <dd>{taken}</dd>
            </div>
            <div>
              <dt>Missed</dt>
              <dd>{missed}</dd>
            </div>
            <div>
              <dt>Skipped</dt>
              <dd>{skipped}</dd>
            </div>
          </dl>

          <p className="adherence__note">
            Based on {resolved} dose{resolved === 1 ? "" : "s"} that have come
            due. Deliberate skips are counted separately and do not lower the
            figure.
          </p>
        </div>
      )}
    </Card>
  );
}
