const app = document.querySelector('#app');
const nav = document.querySelector('#nav');
let currentUser = null;

async function api(url, options = {}) {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(body?.error || 'Request failed.');
  return body;
}

function renderNav() {
  nav.innerHTML = currentUser
    ? `<a href="#marketplace">Marketplace</a><a href="#new-listing">Post Harvest</a>${currentUser.isAdmin ? '<a href="#dashboard">Dashboard</a>' : ''}<button id="logout">Sign out</button>`
    : '<a href="#marketplace">Marketplace</a><a href="#login">Sign in</a><a class="button" href="#signup">Create account</a>';
  document.querySelector('#logout')?.addEventListener('click', async () => { await api('/api/auth/logout', { method: 'POST' }); currentUser = null; render(); });
}

function hero() {
  return `<section class="hero"><div><div class="kicker">The harvest, closer to home</div><h1>Good food starts with a good connection.</h1><p>AgriLink brings farmers and buyers together in one trusted marketplace. Discover fresh produce, fair prices, and a clearer route from soil to table.</p><div class="actions"><a class="button" href="#new-listing">Post your harvest</a><a class="button secondary" href="#marketplace">Browse produce</a></div></div><img src="/images/hero-market.jpg" alt="Fresh produce at a farm market"></section>`;
}

function listingCard(listing) {
  return `<article class="card">${listing.image ? `<img src="${listing.image}" alt="${listing.title}">` : ''}<h3>${listing.title}</h3><div class="price">UGX ${Number(listing.price).toLocaleString()} / ${listing.quantity}</div><div class="tags">From ${listing.villageOrigin} · For ${listing.targetTown}<br>Posted by ${listing.seller}</div><p class="muted">${listing.description}</p></article>`;
}

async function marketplace() {
  const [{ listings }, { images }] = await Promise.all([api('/api/listings'), api('/api/images')]);
  const gallery = images.map((image) => `<figure class="gallery-item"><img src="${image.url}" alt="${image.alt}" loading="lazy"><figcaption>${image.alt}</figcaption></figure>`).join('');
  app.innerHTML = `${hero()}<section class="intro-grid"><div><div class="kicker" style="color:var(--clay)">A visual harvest</div><h2>Stories from the soil</h2><p class="muted">Every image in the AgriLink collection comes from the farm, the market, or the people who connect them.</p></div><div class="intro-note"><strong>${images.length} photos</strong><span>in the community archive</span></div></section><section class="gallery" aria-labelledby="gallery-title"><div class="section-head"><div><div class="kicker" style="color:var(--clay)">Community archive</div><h2 id="gallery-title">From the farm community</h2></div><p class="muted">Scroll through the people, places, and produce behind each listing.</p></div><div class="gallery-grid">${gallery}</div></section><section class="section-head"><div><div class="kicker" style="color:var(--clay)">Fresh listings</div><h2>Available produce</h2></div><p class="muted">Direct from growers and ready for the market.</p></section><div class="grid listings">${listings.length ? listings.map(listingCard).join('') : '<div class="card"><h3>No produce yet</h3><p class="muted">Be the first farmer to post a harvest.</p></div>'}</div>`;
}

function authPage(type) {
  const signup = type === 'signup';
  app.innerHTML = `<section class="form-wrap"><div class="kicker" style="color:var(--clay)">${signup ? 'Join the network' : 'Welcome back'}</div><h2>${signup ? 'Create your account' : 'Sign in to AgriLink'}</h2><p class="muted">${signup ? 'Connect your harvest with buyers who are ready for it.' : 'Pick up where your marketplace work left off.'}</p><form id="auth-form">${signup ? '<label>Username<input name="username" required></label><label>Email<input name="email" type="email" required></label><label>Role<select name="role"><option value="buyer">Buyer</option><option value="farmer">Farmer</option></select></label>' : '<label>Username<input name="username" required></label>'}<label>Password<input name="password" type="password" required></label><button class="button" type="submit">${signup ? 'Create account' : 'Sign in'}</button></form></section>`;
  document.querySelector('#auth-form').addEventListener('submit', async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); try { const result = await api(`/api/auth/${signup ? 'signup' : 'login'}`, { method:'POST', body:JSON.stringify(data) }); currentUser = result.user; location.hash = 'marketplace'; render(); } catch (error) { event.target.insertAdjacentHTML('beforebegin', `<div class="notice">${error.message}</div>`); } });
}

function newListing() {
  if (!currentUser) return (location.hash = 'login');
  app.innerHTML = `<section class="form-wrap"><div class="kicker" style="color:var(--clay)">Share the harvest</div><h2>Post a new listing</h2><form id="listing-form"><label>Produce title<input name="title" placeholder="Fresh tomatoes" required></label><label>Description<textarea name="description" required></textarea></label><label>Price<input name="price" type="number" min="1" step="0.01" required></label><label>Quantity<input name="quantity" placeholder="20 crates" required></label><label>Village origin<input name="villageOrigin" required></label><label>Target town<input name="targetTown" required></label><label>Image URL<input name="image" placeholder="Optional image URL"></label><button class="button" type="submit">Publish listing</button></form></section>`;
  document.querySelector('#listing-form').addEventListener('submit', async (event) => { event.preventDefault(); try { await api('/api/listings', { method:'POST', body:JSON.stringify(Object.fromEntries(new FormData(event.target))) }); location.hash = 'marketplace'; render(); } catch (error) { event.target.insertAdjacentHTML('beforebegin', `<div class="notice">${error.message}</div>`); } });
}

async function dashboard() {
  try { const metrics = await api('/api/dashboard'); app.innerHTML = `<section class="section-head"><div><div class="kicker" style="color:var(--clay)">Operations</div><h2>Admin dashboard</h2></div><p class="muted">Marketplace overview and activity.</p></section><div class="metrics">${[['Users', metrics.totalUsers], ['Listings', metrics.totalListings], ['Active', metrics.activeListings], ['Farmers', metrics.farmers]].map(([label, value]) => `<div class="card metric"><span class="muted">${label}</span><strong>${value}</strong></div>`).join('')}</div>`; } catch (error) { app.innerHTML = `<div class="form-wrap"><div class="notice">${error.message}</div></div>`; }
}

async function render() { renderNav(); const route = location.hash.slice(1) || 'marketplace'; if (route === 'login' || route === 'signup') return authPage(route); if (route === 'new-listing') return newListing(); if (route === 'dashboard') return dashboard(); return marketplace(); }

window.addEventListener('hashchange', render);
api('/api/me').then(({ user }) => { currentUser = user; render(); });
