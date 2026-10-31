import { applyHeroTheme } from './hero-theme.js';

const el = id => document.getElementById(id);
const format = value => value == null ? '—' : Number(value).toLocaleString();
let account = '', scope = 'all', page = 1, pages = 0, busy = false, heroes = [];
const catalog = fetch('assets/heroes.json').then(r => r.json()).then(data => { heroes = data; }).catch(() => {});
let portraits = [], ranks = [];
const tableAssets = Promise.all(['portraits', 'ranks'].map(name => fetch(`assets/${name}.json`).then(r => r.json())))
  .then(([p, r]) => { portraits = p.value || p; ranks = r.value || r; }).catch(() => {});
function portraitCell(td, match) {
  const hero = portraits.find(h => String(h.id) === String(match.heroId) || h.name === match.heroName);
  if (!hero?.portrait) { td.textContent = match.heroName; return; }
  const image = document.createElement('img');
  image.src = hero.portrait; image.alt = match.heroName; image.title = match.heroName;
  image.className = 'match-portrait';
  image.addEventListener('error', () => { td.textContent = match.heroName; });
  td.append(image);
}
function rankCell(td, match) {
  if (match.mode !== 'Ranked') { td.textContent = '—'; return; }
  const badge = match.rankedBadge;
  const tier = Number.isInteger(badge) ? Math.floor(badge / 10) : -1;
  const subrank = badge % 10;
  const rank = ranks.find(r => r.tier === tier);
  if (!rank || badge <= 0) { td.textContent = 'Unavailable'; td.title = 'No rank was reported for this match'; return; }
  const image = document.createElement('img');
  image.src = rank.images[`small_subrank${subrank}_webp`] || rank.images.small_webp;
  image.alt = `${rank.name}${subrank ? ` ${subrank}` : ''}`; image.title = image.alt;
  image.className = 'match-rank';
  image.addEventListener('error', () => { td.textContent = image.alt; });
  td.append(image);
}
function rows(matches) {
  el('rows').replaceChildren(...matches.map(m => {
    const row = document.createElement('tr');
    const date = new Date(m.startTime*1000).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
    const duration = m.durationSeconds == null ? '—' : `${Math.floor(m.durationSeconds/60)}:${String(m.durationSeconds%60).padStart(2,'0')}`;
    [date,m.heroName,m.mode,m.result,`${format(m.kills)} / ${format(m.deaths)} / ${format(m.assists)}`,format(m.souls),duration].forEach((value,i) => {
      const td = document.createElement('td');
      if(i===1) portraitCell(td,m);
      else if(i===3){const badge=document.createElement('span');badge.className=`result ${m.result==='Win'?'win':m.result==='Loss'?'loss':''}`;badge.textContent=value;td.append(badge);}else td.textContent=value;
      row.append(td);
      if(i===2){const rank=document.createElement('td');rankCell(rank,m);row.append(rank);}
    }); return row;
  }));
}
function profileRank(badge) {
  el('rank-label').textContent = scope === 'all' ? 'All-time highest rank' : 'Season 1 current rank';
  el('profile-rank').replaceChildren();
  rankCell(el('profile-rank'), {mode: 'Ranked', rankedBadge: badge});
  el('profile-rank').title = scope === 'all' ? 'Highest rank in available match history' : 'Latest reported rank within Season 1';
}
function clearStats() {
  for (const id of ['wins','losses','total','souls','unscored','kd','rate','hero-games']) el(id).textContent='—';
  el('hero-name').textContent='Most-played hero';
  el('hero-art').hidden=true;
  el('profile-rank').textContent='—';
  rows([]);
}
clearStats();
el('activity').textContent='Search for a player to load their stats.';
el('player-name').textContent='Find your player.';
el('player-id').textContent='Search by Steam name or account ID';
el('history-count').textContent='No player selected';
el('page-label').textContent='Select a player to view matches';
let playerName='';
async function json(url){const response=await fetch(url);if(!response.ok)throw Error(`Unable to load player data (${response.status}). Please try again.`);return response.json();}
function controls(){el('previous').disabled=busy||page<=1;el('next').disabled=busy||page>=pages;document.querySelectorAll('.scope button, #search button').forEach(b=>b.disabled=busy);}
async function load(summary=true, preserveProfile=false){
  if(!account||busy)return;busy=true;controls();el('activity').textContent='';
  el('history').setAttribute('aria-busy','true');
  const loadingRow=document.createElement('tr');
  const loadingCell=document.createElement('td');
  loadingCell.colSpan=8;loadingCell.className='history-loading';
  loadingCell.textContent='Loading match history…';
  loadingRow.append(loadingCell);el('rows').replaceChildren(loadingRow);
  el('history-count').textContent='Loading matches…';
  try{
    const [stats,history]=await Promise.all([summary?json(`/api/player/${account}/summary?scope=${scope}`):null,json(`/api/player/${account}/matches?scope=${scope}&page=${page}&page_size=5`)]);
    if(stats){
      const m=stats.metrics; if(!m)throw Error('Player summary is unavailable.');
      for(const [id,key] of Object.entries({wins:'wins',losses:'losses',total:'totalMatches',souls:'avgSoulsCollected',unscored:'unscored',kd:'killDeathRatio'}))el(id).textContent=format(m[key]);
      el('rate').textContent=m.winRatePercentage==null?'—':`${m.winRatePercentage}%`;
      const name=(scope === 'all' ? m.overallMostPlayedHero : m.dominantHero)||'Unknown';

      el('hero-name').textContent=name;
      el('hero-games').textContent=format(scope === 'all' ? m.overallMostPlayedHeroMatches : m.dominantHeroMatches);
      el('hero-scope').textContent=scope === 'all' ? 'MOST PLAYED HERO · ALL TIME' : 'MOST PLAYED HERO · SEASON 1 RANKED';
      el('player-name').textContent=playerName || `Player ${account}`;el('player-id').textContent=`Steam account ID · ${account}`;
      await catalog;const hero=heroes.find(h=>h.name.toLowerCase()===String(name).toLowerCase()||String(h.id)===String(name));
      applyHeroTheme(name, hero?.image);
      el('hero-art').hidden=!hero?.image;if(hero?.image){el('hero-art').dataset.fallback=hero.fallbackImage || '';el('hero-art').src=hero.image;el('hero-art').alt=`${hero.name}, this player's most-used hero`;}
    }
    await tableAssets;
    profileRank(scope === 'all' ? history.highestRankBadge : history.rankBadge);
    rows(history.matches);pages=history.totalPages;el('history-count').textContent=`${format(history.totalMatches)} matches`;el('page-label').textContent=pages?`Page ${page} of ${pages}`:'No matches in this scope';
    el('activity').textContent='';
  }catch(error){if(summary && !preserveProfile)clearStats();el('activity').textContent=error.message;el('rows').replaceChildren();el('history-count').textContent='Match history unavailable';pages=0;el('page-label').textContent='Try loading the player again';}
  finally{busy=false;el('history').removeAttribute('aria-busy');controls();}
}
el('hero-art').addEventListener('error',()=>{
  const image=el('hero-art');
  if(image.dataset.fallback){const fallback=image.dataset.fallback;delete image.dataset.fallback;image.src=fallback;}
  else image.hidden=true;
});
async function selectPlayer(id, name='', avatar='') {
  account=String(id); playerName=name; page=1;
  const profileAvatar=el('player-avatar');
  profileAvatar.hidden=!avatar;
  if(avatar){profileAvatar.src=avatar;profileAvatar.alt=`${name || 'Player'} Steam avatar`;}
  else profileAvatar.removeAttribute('src');
  el('search-results').replaceChildren();
  clearStats();
  await load();
}
el('search').addEventListener('submit', async event => {
  event.preventDefault(); if(busy)return;
  const query=event.currentTarget.querySelector('input').value.trim();
  if(!query)return;
  if(/^\d+$/.test(query)){await selectPlayer(query);return;}
  busy=true;controls();el('activity').textContent='Searching Steam players…';
  el('search-results').replaceChildren();
  try {
    const result=await json(`/api/player/search?query=${encodeURIComponent(query)}`);
    for(const player of result.players || []) {
      const button=document.createElement('button');button.type='button';
      button.textContent=`${player.playerName} · ${player.accountId}`;
      if(player.avatar){
        const avatar=document.createElement('img');avatar.src=player.avatar;avatar.alt='';avatar.className='search-avatar';
        avatar.addEventListener('error',()=>avatar.remove());button.prepend(avatar);
      }
      button.addEventListener('click',()=>{if(!busy)selectPlayer(player.accountId,player.playerName,player.avatar);});
      el('search-results').append(button);
    }
    el('activity').textContent=result.players?.length?'':'No matching players found.';
  }catch(error){el('activity').textContent=error.message;}
  finally{busy=false;el('history').removeAttribute('aria-busy');controls();}
});
document.querySelectorAll('[data-scope]').forEach(button=>button.addEventListener('click',()=>{if(busy)return;scope=button.dataset.scope;document.querySelectorAll('[data-scope]').forEach(b=>b.classList.toggle('selected',b===button));page=1;if(account){load(true,true);}else el('rank-label').textContent=scope === 'all' ? 'All-time highest rank' : 'Season 1 current rank';}));
el('previous').addEventListener('click',()=>{if(!busy&&page>1){page--;load(false);}});
el('next').addEventListener('click',()=>{if(!busy&&page<pages){page++;load(false);}});
el('player-avatar').addEventListener('error',()=>{el('player-avatar').hidden=true;});

function fitPlayerName() {
  const name=el('player-name');
  name.style.removeProperty('font-size');
  const available=name.clientWidth;
  if(!available)return;
  const base=parseFloat(getComputedStyle(name).fontSize);
  if(name.scrollWidth>available){
    name.style.fontSize=`${base * available / name.scrollWidth * .97}px`;
  }
}
let nameFitFrame;
function scheduleNameFit(){cancelAnimationFrame(nameFitFrame);nameFitFrame=requestAnimationFrame(fitPlayerName);}
new ResizeObserver(scheduleNameFit).observe(document.querySelector('.player-identity'));
new MutationObserver(scheduleNameFit).observe(el('player-name'),{childList:true,characterData:true,subtree:true});
new MutationObserver(scheduleNameFit).observe(el('player-avatar'),{attributes:true,attributeFilter:['hidden']});
document.fonts.ready.then(scheduleNameFit);
