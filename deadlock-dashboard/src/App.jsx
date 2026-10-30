import { useState, useEffect } from 'react';
import { Shield, Target, Flame, Trophy, Search, Loader2 } from 'lucide-react';
import MatchHistory from './MatchHistory';

function App() {
  // Uses a default active public community profile to ensure the first render works
  const [accountId, setAccountId] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchResults, setSearchResults] = useState([]);
  const [scope, setScope] = useState('season1');

  useEffect(() => {
    if (!accountId) return;
    const controller = new AbortController();
    console.log(`Pipeline query executing via proxy for player profile: ${accountId} (${scope})`);

    fetch(`/api/player/${accountId}/summary?scope=${encodeURIComponent(scope)}`, { signal: controller.signal })
      .then(res => {
        if (!res.ok) {
          throw new Error(`Profile not found or API error (Status: ${res.status})`);
        }
        return res.json();
      })
      .then(json => {
        if (json.hasRankedMatches === false) {
          setData({ ...(json.metrics || {}), hasRankedMatches: false });
        } else if (json.metrics) {
          setData({ ...json.metrics, hasRankedMatches: true });
        } else {
          throw new Error("JSON payload missing expected internal metrics keys.");
        }
        setLoading(false);
      })
      .catch(err => {
        if (controller.signal.aborted) return;
        console.error("Fetch operation failed:", err);
        setError(err.message);
        setLoading(false);
      });
    return () => controller.abort();
  }, [accountId, scope]);

  const handleSearchSubmit = async (e) => {
    e.preventDefault();
    const query = searchInput.trim();
    if (!query) return;

    setError(null);
    try {
      const response = await fetch(`/api/player/search?query=${encodeURIComponent(query)}`);
      if (!response.ok) throw new Error(`Player search failed (Status: ${response.status})`);
      const json = await response.json();
      setSearchResults(json.players || []);
      if (!json.players?.length) setError('No matching Steam players found.');
    } catch (err) {
      setSearchResults([]);
      setError(err.message);
    }
  };

  const selectPlayer = (player) => {
    setSearchResults([]);
    if (String(player.accountId) !== accountId) {
      setLoading(true);
      setError(null);
      setAccountId(String(player.accountId));
    }
  };

  return (
    <div style={{ backgroundColor: '#121214', color: '#E1E1E6', minHeight: '100vh', padding: '40px', fontFamily: 'sans-serif' }}>

      {/* HEADER WITH INTEGRATED INTERACTIVE CONTROLS */}
      <header style={{ borderBottom: '1px solid #29292E', paddingBottom: '20px', marginBottom: '30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px' }}>

        <div style={{ marginTop: '40px', color: '#7C7C8A' }}>
          Search for a player by name or account ID to load their stats.
        </div>

        <div>
          <h1 style={{ fontSize: '28px', color: '#FFB800', margin: 0 }}>DEADLOCK TELEMETRY</h1>
          <p style={{ color: '#7C7C8A', marginTop: '5px' }}>Full-Stack Performance Tracker & Match Analytics Engine</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#202024', border: '1px solid #29292E', borderRadius: '6px', padding: '6px' }}>
          {['season1', 'all'].map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => {
                if (option !== scope && accountId) {
                  setLoading(true);
                  setError(null);
                }
                setScope(option);
              }}
              style={{
                backgroundColor: scope === option ? '#FFB800' : 'transparent',
                color: scope === option ? '#121214' : '#E1E1E6',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                padding: '8px 12px',
                fontWeight: 'bold',
                textTransform: 'capitalize'
              }}
            >
              {option === 'season1' ? 'Season 1' : 'All Matches'}
            </button>
          ))}
        </div>

        {/* SEARCH BAR INPUT FOR DYNAMIC LOOKUPS */}
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '10px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={18} color="#7C7C8A" style={{ position: 'absolute', left: '12px' }} />
            <input 
              type="text" 
              placeholder="Enter Steam player name..." 
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              style={{ backgroundColor: '#202024', border: '1px solid #29292E', borderRadius: '6px', color: '#E1E1E6', padding: '10px 12px 10px 40px', fontSize: '14px', width: '240px', outline: 'none' }}
            />
          </div>
          <button 
            type="submit" 
            style={{ backgroundColor: '#FFB800', color: '#121214', border: 'none', borderRadius: '6px', padding: '10px 20px', fontWeight: 'bold', cursor: 'pointer' }}
          >
            Search
          </button>
        </form>
        {searchResults.length > 0 && (
          <div style={{ width: '100%', display: 'grid', gap: '8px' }}>
            {searchResults.map((player) => (
              <button key={player.accountId} onClick={() => selectPlayer(player)} style={{ display: 'flex', alignItems: 'center', gap: '10px', backgroundColor: '#202024', border: '1px solid #29292E', color: '#E1E1E6', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', textAlign: 'left' }}>
                <img src={player.avatar} alt="" width="32" height="32" style={{ borderRadius: '4px' }} />
                <span>{player.playerName} <small style={{ color: '#7C7C8A' }}>({player.accountId})</small></span>
              </button>
            ))}
          </div>
        )}
      </header>

      {/* CONDITIONAL INTERFACE BODY LOADING BLOCK */}
      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '40px' }}>
          <Loader2 size={24} color="#FFB800" style={{ animation: 'spin 1s linear infinite' }} />
          <h3>Syncing with Valve Match Logs...</h3>
          <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
        </div>
      ) : error ? (
        <div style={{ backgroundColor: '#202024', padding: '30px', borderRadius: '8px', borderLeft: '4px solid #F75A68', marginTop: '20px' }}>
          <h3 style={{ color: '#F75A68', margin: '0 0 10px 0' }}>Data Pipeline Exception</h3>
          <p style={{ color: '#E1E1E6', margin: 0 }}>{error}</p>
          <button onClick={() => { setAccountId(''); setData(null); setLoading(false); setError(null); }} style={{ marginTop: '15px', background: 'none', border: '1px solid #7C7C8A', color: '#7C7C8A', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer' }}>
            Clear player
          </button>
        </div>
      ) : data?.hasRankedMatches === false ? (
        <div style={{ marginTop: '30px', color: '#7C7C8A' }}>
          <h2 style={{ color: '#E1E1E6', fontWeight: 'bold' }}>This player has no ranked matches</h2>
          <button onClick={() => { setAccountId(''); setData(null); setLoading(false); setError(null); }} style={{ marginTop: '15px', background: 'none', border: '1px solid #7C7C8A', color: '#7C7C8A', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer' }}>
            Search another player
          </button>
        </div>
      ) : (
        <div>
          <div style={{ marginBottom: '20px', color: '#7C7C8A' }}>
            Displaying <strong style={{ color: '#FFB800', textTransform: 'capitalize' }}>{scope === 'season1' ? 'Season 1 Ranked' : 'All Matches'} </strong>
            processed matrix rows for ID: <strong style={{ color: '#FFB800' }}>{accountId}</strong>
          </div>

          {/* TELEMETRY ANALYTICS METRICS LAYER */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px' }}>
            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #FFB800' }}>
              <Target size={24} color="#FFB800" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>Total Matches</h3>
              <p style={{ fontSize: '32px', fontWeight: 'bold', margin: 0 }}>{(data?.totalMatches ?? 0).toLocaleString()}</p>
            </div>

            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #00B37E' }}>
              <Trophy size={24} color="#00B37E" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>Win Rate</h3>
              <p style={{ fontSize: '32px', fontWeight: 'bold', margin: 0 }}>{data?.winRatePercentage || 0}%</p>
            </div>

            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #00B37E' }}>
              <Trophy size={24} color="#00B37E" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>Games Won</h3>
              <p style={{ fontSize: '32px', fontWeight: 'bold', margin: 0 }}>{data?.wins || 0}</p>
            </div>

            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #F75A68' }}>
              <Target size={24} color="#F75A68" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>Games Lost</h3>
              <p style={{ fontSize: '32px', fontWeight: 'bold', margin: 0 }}>{data?.losses || 0}</p>
            </div>

            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #7C7C8A' }}>
              <Shield size={24} color="#7C7C8A" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>Unscored</h3>
              <p style={{ fontSize: '32px', fontWeight: 'bold', margin: 0 }}>{data?.unscored || 0}</p>
            </div>

            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #F75A68' }}>
              <Target size={24} color="#F75A68" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>Kill / Death Ratio</h3>
              <p style={{ fontSize: '32px', fontWeight: 'bold', margin: 0 }}>{data?.killDeathRatio || 0}</p>
            </div>

            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #FFB800' }}>
              <Flame size={24} color="#FFB800" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>Avg Souls / Match</h3>
              <p style={{ fontSize: '32px', fontWeight: 'bold', margin: 0 }}>{(data?.avgSoulsCollected || 0).toLocaleString()}</p>
            </div>

            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #8257E5' }}>
              <Shield size={24} color="#8257E5" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>{scope === 'season1' ? 'Season 1 Most Played' : 'Most Played Overall'}</h3>
              <p style={{ fontSize: '28px', fontWeight: 'bold', margin: 0 }}>{data?.dominantHero || 'Unknown'} <span style={{ color: '#7C7C8A', fontSize: '16px' }}>({data?.dominantHeroMatches || 0})</span></p>
            </div>

            <div style={{ backgroundColor: '#202024', padding: '20px', borderRadius: '8px', borderLeft: '4px solid #8257E5' }}>
              <Shield size={24} color="#8257E5" />
              <h3 style={{ color: '#7C7C8A', margin: '10px 0 5px 0' }}>Most Played Overall</h3>
              <p style={{ fontSize: '28px', fontWeight: 'bold', margin: 0 }}>{data?.overallMostPlayedHero || 'Unknown'} <span style={{ color: '#7C7C8A', fontSize: '16px' }}>({data?.overallMostPlayedHeroMatches || 0})</span></p>
            </div>
          </div>
        </div>
      )
    }
      {accountId && <MatchHistory key={`${accountId}:${scope}`} accountId={accountId} scope={scope} />}
    </div>
  );
}

export default App;
