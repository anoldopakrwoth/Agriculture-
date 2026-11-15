import express from 'express';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(root, 'data');
const storePath = path.join(dataDir, 'store.json');
const sessions = new Map();
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json({ limit: '1mb' }));
app.use(express.static(path.join(root, 'public')));
app.use('/images', express.static(path.join(root, 'frontend', 'static', 'images')));

const imageRoot = path.join(root, 'frontend', 'static', 'images');
const imageExtensions = new Set(['.jpg', '.jpeg', '.png', '.webp', '.gif']);

async function findImages(directory, relativeDirectory = '') {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const images = [];

  for (const entry of entries) {
    const relativePath = path.join(relativeDirectory, entry.name);
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      images.push(...await findImages(fullPath, relativePath));
    } else if (imageExtensions.has(path.extname(entry.name).toLowerCase())) {
      images.push({
        url: `/images/${relativePath.split(path.sep).join('/')}`,
        alt: path.basename(entry.name, path.extname(entry.name)).replace(/[_-]/g, ' ')
      });
    }
  }

  return images;
}

app.get('/api/images', async (request, response) => {
  try {
    const images = await findImages(imageRoot);
    images.sort((a, b) => a.url.localeCompare(b.url));
    response.json({ images });
  } catch (error) {
    console.error('Unable to load image gallery:', error);
    response.status(500).json({ error: 'Unable to load the image gallery.' });
  }
});

async function readStore() {
  try {
    return JSON.parse(await fs.readFile(storePath, 'utf8'));
  } catch {
    return { users: [], listings: [] };
  }
}

async function writeStore(store) {
  await fs.mkdir(dataDir, { recursive: true });
  await fs.writeFile(storePath, JSON.stringify(store, null, 2));
}

function hashPassword(password) {
  return crypto.createHash('sha256').update(password).digest('hex');
}

function userFromRequest(request, store) {
  const token = request.headers.authorization?.replace('Bearer ', '') || request.headers.cookie?.match(/agrilink_session=([^;]+)/)?.[1];
  const userId = token && sessions.get(token);
  return store.users.find((user) => user.id === userId) || null;
}

function publicUser(user) {
  if (!user) return null;
  return { id: user.id, username: user.username, email: user.email, role: user.role, isAdmin: user.isAdmin };
}

function requireUser(request, response, store) {
  const user = userFromRequest(request, store);
  if (!user) response.status(401).json({ error: 'Authentication required.' });
  return user;
}

app.get('/api/me', async (request, response) => {
  const store = await readStore();
  response.json({ user: publicUser(userFromRequest(request, store)) });
});

app.post('/api/auth/signup', async (request, response) => {
  const { username, email, password, role = 'buyer' } = request.body;
  if (!username || !email || !password) return response.status(400).json({ error: 'Username, email, and password are required.' });
  const store = await readStore();
  if (store.users.some((user) => user.username.toLowerCase() === username.toLowerCase() || user.email.toLowerCase() === email.toLowerCase())) {
    return response.status(409).json({ error: 'Username or email is already in use.' });
  }
  const user = { id: crypto.randomUUID(), username, email, password: hashPassword(password), role, isAdmin: false, createdAt: new Date().toISOString() };
  store.users.push(user);
  await writeStore(store);
  const token = crypto.randomUUID();
  sessions.set(token, user.id);
  response.setHeader('Set-Cookie', `agrilink_session=${token}; HttpOnly; SameSite=Lax; Path=/`);
  response.status(201).json({ user: publicUser(user) });
});

app.post('/api/auth/login', async (request, response) => {
  const store = await readStore();
  const { username, password } = request.body;
  const user = store.users.find((candidate) => candidate.username === username && candidate.password === hashPassword(password || ''));
  if (!user) return response.status(401).json({ error: 'Invalid username or password.' });
  const token = crypto.randomUUID();
  sessions.set(token, user.id);
  response.setHeader('Set-Cookie', `agrilink_session=${token}; HttpOnly; SameSite=Lax; Path=/`);
  response.json({ user: publicUser(user) });
});

app.post('/api/auth/logout', (request, response) => {
  const token = request.headers.authorization?.replace('Bearer ', '') || request.headers.cookie?.match(/agrilink_session=([^;]+)/)?.[1];
  if (token) sessions.delete(token);
  response.setHeader('Set-Cookie', 'agrilink_session=; Max-Age=0; Path=/');
  response.status(204).end();
});

app.get('/api/listings', async (request, response) => {
  const store = await readStore();
  response.json({ listings: store.listings.filter((listing) => listing.isAvailable).sort((a, b) => b.createdAt.localeCompare(a.createdAt)) });
});

app.post('/api/listings', async (request, response) => {
  const store = await readStore();
  const user = requireUser(request, response, store);
  if (!user) return;
  const { title, description, price, quantity, villageOrigin, targetTown, image } = request.body;
  if (!title || !description || !price || !quantity || !villageOrigin || !targetTown) return response.status(400).json({ error: 'All listing fields are required.' });
  const listing = { id: crypto.randomUUID(), sellerId: user.id, seller: user.username, title, description, price: Number(price), quantity, villageOrigin, targetTown, image: image || '', isAvailable: true, createdAt: new Date().toISOString() };
  store.listings.push(listing);
  await writeStore(store);
  response.status(201).json({ listing });
});

app.get('/api/listings/:id', async (request, response) => {
  const store = await readStore();
  const listing = store.listings.find((candidate) => candidate.id === request.params.id && candidate.isAvailable);
  if (!listing) return response.status(404).json({ error: 'Listing not found.' });
  response.json({ listing });
});

app.get('/api/dashboard', async (request, response) => {
  const store = await readStore();
  const user = requireUser(request, response, store);
  if (!user) return;
  if (!user.isAdmin) return response.status(403).json({ error: 'Admin access required.' });
  response.json({ totalUsers: store.users.length, totalListings: store.listings.length, activeListings: store.listings.filter((listing) => listing.isAvailable).length, farmers: store.users.filter((candidate) => candidate.role === 'farmer').length, buyers: store.users.filter((candidate) => candidate.role === 'buyer').length });
});

app.get('/{*splat}', (request, response) => response.sendFile(path.join(root, 'public', 'index.html')));

app.listen(port, () => console.log(`AgriLink JavaScript server running at http://localhost:${port}`));
