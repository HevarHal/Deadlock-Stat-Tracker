import { useEffect, useState } from 'react';
import './MatchHistory.css';

const number = value => value == null ? '—' : value.toLocaleString();
const date = timestamp => timestamp == null ? '—' : new Date(timestamp * 1000).toLocaleString(undefined, {
  month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
});
const duration = seconds => seconds == null ? '—' : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

export default function MatchHistory({ accountId, scope }) {
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);
  const [response, setResponse] = useState(null);
  const requestKey = `${accountId}:${scope}:${page}:${attempt}`;
  const pending = response?.key !== requestKey;
  const data = pending ? null : response?.data;
  const error = pending ? null : response?.error;

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/player/${accountId}/matches?scope=${encodeURIComponent(scope)}&page=${page}&page_size=20`, {
      signal: controller.signal,
    })
      .then(async result => {
        const body = await result.json();
        if (!result.ok) throw new Error(body.detail || 'Match history could not be loaded.');
        if (!controller.signal.aborted) setResponse({ key: requestKey, data: body });
      })
      .catch(reason => {
        if (!controller.signal.aborted) setResponse({ key: requestKey, error: reason.message });
      });
    return () => controller.abort();
  }, [accountId, scope, page, requestKey]);

  const first = data?.matches.length ? (page - 1) * data.pageSize + 1 : 0;
  const last = data ? Math.min(page * data.pageSize, data.totalMatches) : 0;

  return (
    <section className="match-history" aria-labelledby="match-history-heading" aria-busy={pending}>
      <div className="match-history-heading">
        <div>
          <h2 id="match-history-heading">Match History</h2>
          <p>{scope === 'season1' ? 'Season 1 · Ranked matches' : 'All dates · All match modes'} · Newest first</p>
        </div>
        {data && <span className="match-history-count">{number(data.totalMatches)} matches</span>}
      </div>

      {pending ? <p className="match-history-message" role="status">Loading matches…</p>
        : error ? (
          <div className="match-history-message" role="alert">
            <p>{error}</p>
            <button type="button" onClick={() => setAttempt(value => value + 1)}>Retry</button>
          </div>
        ) : !data?.matches.length ? (
          <p className="match-history-message">No matches found in this scope.</p>
        ) : (
          <>
            <div className="match-history-scroll" tabIndex={0} role="region" aria-label="Match history table; scroll horizontally for more columns">
              <table>
                <caption className="match-history-sr-only">Player match history, newest first. Dates are in your local time.</caption>
                <thead><tr>
                  {['Date', 'Hero', 'Mode', 'Result', 'K / D / A', 'Souls', 'Duration', 'Match ID'].map(label => <th key={label} scope="col">{label}</th>)}
                </tr></thead>
                <tbody>
                  {data.matches.map((match, index) => (
                    <tr key={match.matchId ?? index}>
                      <td>{match.startTime == null ? '—' : <time dateTime={new Date(match.startTime * 1000).toISOString()}>{date(match.startTime)}</time>}</td>
                      <td className="match-history-hero">{match.heroName}</td>
                      <td>{match.mode}</td>
                      <td><span className={`match-result ${match.result === 'Win' ? 'match-win' : match.result === 'Loss' ? 'match-loss' : 'match-neutral'}`}>{match.result}</span></td>
                      <td>{number(match.kills)} / {number(match.deaths)} / {number(match.assists)}</td>
                      <td>{number(match.souls)}</td>
                      <td>{duration(match.durationSeconds)}</td>
                      <td className="match-history-id">{match.matchId ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <nav className="match-history-pagination" aria-label="Match history pages">
              <span aria-live="polite">Showing {first}–{last} of {number(data.totalMatches)} · Local time</span>
              <div>
                <button type="button" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Previous</button>
                <span>Page {page} of {data.totalPages}</span>
                <button type="button" disabled={page >= data.totalPages} onClick={() => setPage(value => value + 1)}>Next</button>
              </div>
            </nav>
          </>
        )}
    </section>
  );
}
