# ThinkBuddy Web Apps (Student App & Parent Site)

This monorepo contains the two independent web clients for ThinkBuddy:
1. **Student App** (`/apps/student`): Daily study routine, NCTB page-by-page study, interactive stopwatch, practice quiz runner, Leitner spaced revision, AI tutor, and parent invite code generation.
2. **Parent Site** (`/apps/parent`): Linked child study overview, daily study report with teacher feedback, routine overview, weak chapters analysis, and real-time notifications.
3. **Shared Package** (`/packages/shared`): Shared TypeScript definitions, Firebase Auth/Firestore helpers, natural Bangla i18n translations, design tokens, and routine data.

---

## 1. Local Development Setup

From the monorepo root:

```bash
# Install dependencies across all workspaces
npm install

# Run the Student App (http://localhost:3000)
npm run dev:student

# Run the Parent Site (http://localhost:3001)
npm run dev:parent
```

Both apps can also be previewed from production builds:
```bash
npm run build
npm --workspace=apps/student run preview   # http://localhost:3000
npm --workspace=apps/parent run preview    # http://localhost:3001
```

---

## 2. Environment Variables (.env)

Each app includes a `.env.example` template. Copy to `.env.local` or set directly in your Cloudflare Pages dashboard:

```ini
VITE_FIREBASE_API_KEY=AIzaSy...
VITE_FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=1029384756
VITE_FIREBASE_APP_ID=1:1029384756:web:...

# Inter-site cross navigation URLs
VITE_PARENT_SITE_URL=https://thinkbuddy-parent.pages.dev
VITE_STUDENT_APP_URL=https://thinkbuddy-student.pages.dev
```

*Note: If Firebase environment variables are omitted or in local testing mode, both apps automatically use the built-in resilient preview store (persisting in localStorage and supporting Google Sign-In, invite code generation, and parent-child linking) without errors.*

---

## 3. Firebase Console Configuration

### A. Enable Google Sign-In
1. In the [Firebase Console](https://console.firebase.google.com/), navigate to **Build > Authentication > Sign-in method**.
2. Enable **Google** provider and provide your support email.

### B. Add Authorized Domains
In **Authentication > Settings > Authorized domains**, add the Cloudflare Pages domains, Quick Tunnel domains, and local dev hosts:
- `localhost`
- `127.0.0.1`
- `thinkbuddy-student.pages.dev`
- `thinkbuddy-parent.pages.dev`
- `*.pages.dev`
- `*.trycloudflare.com` (for Cloudflare Quick Tunnels)

### C. Deploy Firestore Security Rules
Copy the rules from `packages/shared/src/firestore.rules` into **Firestore Database > Rules**:
- Enforces that students can read/write only their own documents and subcollections.
- Enforces that parents can only read documents belonging to their linked children.
- Public read/write on `/invites/{code}` for code-based family linking.

---

## 4. Deploying to Cloudflare Pages

Both apps are configured as static Single Page Applications (SPAs) with `_redirects` (`/* /index.html 200`) to guarantee deep-link refreshes work seamlessly.

### Build Settings for Cloudflare Pages:
| Project | Root Directory | Build Command | Build Output Directory |
|---|---|---|---|
| **Student App** | `apps/student` | `npm run build` | `dist` |
| **Parent Site** | `apps/parent` | `npm run build` | `dist` |

### Instant Cloudflare Quick Tunnels (Zero Configuration):
Both apps can be exposed to public Cloudflare HTTPS endpoints from your machine without credentials using the installed `cloudflared` CLI:

```bash
# Student App Tunnel (port 3000)
cloudflared tunnel --url http://127.0.0.1:3000

# Parent App Tunnel (port 3001)
cloudflared tunnel --url http://127.0.0.1:3001
```

### CLI Deploy Commands (Wrangler):
Ensure you have authenticated with Cloudflare (`npx wrangler login` or set `CLOUDFLARE_API_TOKEN` in CI):

```bash
# Deploy Student App to Cloudflare Pages
npm run deploy:student
# Live URL: https://thinkbuddy-student.pages.dev

# Deploy Parent Site to Cloudflare Pages
npm run deploy:parent
# Live URL: https://thinkbuddy-parent.pages.dev
```

---

## 5. Architectural & Design Highlights
- **Bangla-first:** 100% natural, student-friendly Bangla translations (`/packages/shared/src/i18n.ts`) with Hind Siliguri and Noto Sans Bengali typography and 1.68 line-height to prevent conjunct clipping.
- **Calm, Minimal Design:** `#F8FAFC` soft background with subtle dot grid, rounded cards (16–20px), and rich blue `#2563EB` primary color.
- **Full Dark Mode:** Designed `#0B1120` theme with automatic localStorage persistence.
- **Single Source of Truth for Routine & Today:** Editing routine slots updates today's timeline and task list simultaneously.
- **Fixed Bugs:**
  - Chapter chunking pill formatted cleanly without stray characters.
  - Removed empty pill artifact beside the Pro Verified badge.
  - Stopwatch persists elapsed time and running state across page refreshes.
  - Page completion checkmarks increment progress dynamically (`সম্পন্ন: ১ / ৩ পৃষ্ঠা`).

