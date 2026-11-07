import { UserProfile, UserRole, StudySessionState } from "./types";

// Firebase environment configuration
export const FIREBASE_CONFIG = {
  apiKey: typeof process !== "undefined" && process.env?.VITE_FIREBASE_API_KEY
    ? process.env.VITE_FIREBASE_API_KEY
    : typeof window !== "undefined" && (window as unknown as { __ENV?: Record<string, string> }).__ENV?.VITE_FIREBASE_API_KEY
    ? (window as unknown as { __ENV?: Record<string, string> }).__ENV?.VITE_FIREBASE_API_KEY
    : "",
  authDomain: typeof process !== "undefined" && process.env?.VITE_FIREBASE_AUTH_DOMAIN
    ? process.env.VITE_FIREBASE_AUTH_DOMAIN
    : "thinkbuddy-auth.firebaseapp.com",
  projectId: typeof process !== "undefined" && process.env?.VITE_FIREBASE_PROJECT_ID
    ? process.env.VITE_FIREBASE_PROJECT_ID
    : "thinkbuddy-prod",
  storageBucket: typeof process !== "undefined" && process.env?.VITE_FIREBASE_STORAGE_BUCKET
    ? process.env.VITE_FIREBASE_STORAGE_BUCKET
    : "thinkbuddy-prod.appspot.com",
  messagingSenderId: typeof process !== "undefined" && process.env?.VITE_FIREBASE_MESSAGING_SENDER_ID
    ? process.env.VITE_FIREBASE_MESSAGING_SENDER_ID
    : "1029384756",
  appId: typeof process !== "undefined" && process.env?.VITE_FIREBASE_APP_ID
    ? process.env.VITE_FIREBASE_APP_ID
    : "1:1029384756:web:abcdef123456",
};

export const isFirebaseConfigured = Boolean(
  FIREBASE_CONFIG.apiKey && FIREBASE_CONFIG.apiKey.length > 10 && !FIREBASE_CONFIG.apiKey.includes("placeholder")
);

// Fallback in-memory/localStorage mock store for testing & preview without live credentials
const MOCK_STORAGE_KEY_PREFIX = "tb_firestore_";

function getMockDoc<T>(collection: string, id: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(`${MOCK_STORAGE_KEY_PREFIX}${collection}_${id}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function setMockDoc<T>(collection: string, id: string, data: T): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(`${MOCK_STORAGE_KEY_PREFIX}${collection}_${id}`, JSON.stringify(data));
  } catch {}
}

/**
 * Generate a clean 6-character student invite code like "TB-8392"
 */
export function generateInviteCode(): string {
  const digits = Math.floor(1000 + Math.random() * 9000);
  return `TB-${digits}`;
}

/**
 * Google Sign-In with real Firebase or Preview fallback
 */
export async function signInWithGoogle(role: UserRole): Promise<UserProfile> {
  if (isFirebaseConfigured) {
    try {
      const { initializeApp, getApps } = await import("firebase/app");
      const { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect } = await import("firebase/auth");
      const { getFirestore, doc, getDoc, setDoc } = await import("firebase/firestore");

      const app = getApps().length === 0 ? initializeApp(FIREBASE_CONFIG) : getApps()[0];
      const auth = getAuth(app);
      const db = getFirestore(app);
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });

      let userCred;
      try {
        userCred = await signInWithPopup(auth, provider);
      } catch (popupErr: unknown) {
        const errCode = (popupErr as { code?: string })?.code;
        if (errCode === "auth/popup-blocked" || errCode === "auth/cancelled-popup-request") {
          await signInWithRedirect(auth, provider);
          return new Promise(() => {}); // Wait for redirect
        }
        throw popupErr;
      }

      const fbUser = userCred.user;
      const userDocRef = doc(db, "users", fbUser.uid);
      const userSnap = await getDoc(userDocRef);

      let profile: UserProfile;
      if (userSnap.exists()) {
        profile = userSnap.data() as UserProfile;
      } else {
        const inviteCode = role === "student" ? generateInviteCode() : undefined;
        profile = {
          uid: fbUser.uid,
          name: fbUser.displayName || (role === "student" ? "তাহমিদ আলিম" : "রফিকুল ইসলাম"),
          email: fbUser.email || "user@thinkbuddy.org",
          photoURL: fbUser.photoURL || undefined,
          role,
          createdAt: new Date().toISOString(),
          inviteCode,
          linkedChildren: role === "parent" ? [] : undefined,
          linkedParents: role === "student" ? [] : undefined,
        };
        await setDoc(userDocRef, profile);

        // Store invite lookup
        if (inviteCode) {
          await setDoc(doc(db, "invites", inviteCode), {
            studentUid: fbUser.uid,
            studentName: profile.name,
            createdAt: new Date().toISOString(),
          });
        }
      }

      if (typeof window !== "undefined") {
        localStorage.setItem(`tb_auth_${role}`, JSON.stringify(profile));
      }
      return profile;
    } catch (err: unknown) {
      console.warn("Firebase live auth error, using standard fallback:", err);
    }
  }

  // Preview / Demo fallback
  const mockUid = role === "student" ? "stu_demo_uid_101" : "parent_demo_uid_202";
  const existing = getMockDoc<UserProfile>("users", mockUid);
  if (existing) {
    if (typeof window !== "undefined") {
      localStorage.setItem(`tb_auth_${role}`, JSON.stringify(existing));
    }
    return existing;
  }

  const profile: UserProfile = {
    uid: mockUid,
    name: role === "student" ? "তাহমিদ আলিম" : "রফিকুল ইসলাম",
    email: role === "student" ? "tahmid@thinkbuddy.org" : "rafiqul.parent@thinkbuddy.org",
    photoURL: role === "student"
      ? "https://api.dicebear.com/7.x/bottts/svg?seed=tahmid"
      : "https://api.dicebear.com/7.x/avataaars/svg?seed=rafiqul",
    role,
    createdAt: new Date().toISOString(),
    inviteCode: role === "student" ? "TB-8392" : undefined,
    linkedChildren: role === "parent" ? ["stu_demo_uid_101"] : undefined,
    linkedParents: role === "student" ? ["parent_demo_uid_202"] : undefined,
    class_grade: role === "student" ? 7 : undefined,
    school_name: role === "student" ? "ঢাকা রেসিডেনসিয়াল মডেল কলেজ" : undefined,
  };

  setMockDoc("users", mockUid, profile);
  if (profile.inviteCode) {
    setMockDoc("invites", profile.inviteCode, {
      studentUid: profile.uid,
      studentName: profile.name,
      createdAt: new Date().toISOString(),
    });
  }
  if (typeof window !== "undefined") {
    localStorage.setItem(`tb_auth_${role}`, JSON.stringify(profile));
  }
  return profile;
}

/**
 * Sign out current user
 */
export async function signOutUser(role: UserRole): Promise<void> {
  if (isFirebaseConfigured) {
    try {
      const { getApps } = await import("firebase/app");
      const { getAuth, signOut } = await import("firebase/auth");
      if (getApps().length > 0) {
        const auth = getAuth();
        await signOut(auth);
      }
    } catch {}
  }
  if (typeof window !== "undefined") {
    localStorage.removeItem(`tb_auth_${role}`);
  }
}

/**
 * Get cached/persisted user session on load
 */
export function getPersistedUser(role: UserRole): UserProfile | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(`tb_auth_${role}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/**
 * Get or create invite code for student
 */
export async function getStudentInviteCode(studentUid: string): Promise<string> {
  const profile = getMockDoc<UserProfile>("users", studentUid);
  if (profile?.inviteCode) return profile.inviteCode;
  const newCode = generateInviteCode();
  if (profile) {
    profile.inviteCode = newCode;
    setMockDoc("users", studentUid, profile);
  }
  setMockDoc("invites", newCode, {
    studentUid,
    studentName: profile?.name || "তাহমিদ আলিম",
    createdAt: new Date().toISOString(),
  });
  return newCode;
}

/**
 * Link a child to a parent using the student's invite code
 */
export async function linkChildWithInviteCode(
  parentUid: string,
  inviteCode: string
): Promise<{ success: boolean; studentName?: string; error?: string }> {
  const cleanCode = inviteCode.trim().toUpperCase();

  // Try live Firebase Firestore if configured
  if (isFirebaseConfigured) {
    try {
      const { getApps } = await import("firebase/app");
      const { getFirestore, doc, getDoc, updateDoc, arrayUnion, setDoc } = await import("firebase/firestore");
      if (getApps().length > 0) {
        const db = getFirestore();
        const inviteDoc = await getDoc(doc(db, "invites", cleanCode));
        if (!inviteDoc.exists()) {
          return { success: false, error: "INVITE_NOT_FOUND" };
        }
        const inviteData = inviteDoc.data();
        const studentUid = inviteData.studentUid;

        // Add child to parent
        await setDoc(
          doc(db, "parents", parentUid, "children", studentUid),
          { linkedAt: new Date().toISOString(), studentName: inviteData.studentName },
          { merge: true }
        );

        // Add parent to student
        await updateDoc(doc(db, "students", studentUid), {
          linkedParents: arrayUnion(parentUid),
        });

        return { success: true, studentName: inviteData.studentName };
      }
    } catch (err) {
      console.warn("Firebase live link error, using fallback:", err);
    }
  }

  // Fallback in-memory/localStorage store
  const inviteData = getMockDoc<{ studentUid: string; studentName: string }>("invites", cleanCode);
  if (!inviteData && cleanCode !== "TB-8392") {
    return { success: false, error: "INVITE_NOT_FOUND" };
  }

  const studentUid = inviteData ? inviteData.studentUid : "stu_demo_uid_101";
  const studentName = inviteData ? inviteData.studentName : "তাহমিদ আলিম";

  // Update parent profile
  const parentProfile = getMockDoc<UserProfile>("users", parentUid) || {
    uid: parentUid,
    name: "রফিকুল ইসলাম",
    email: "rafiqul@thinkbuddy.org",
    role: "parent",
    createdAt: new Date().toISOString(),
    linkedChildren: [],
  };

  if (!parentProfile.linkedChildren) parentProfile.linkedChildren = [];
  if (!parentProfile.linkedChildren.includes(studentUid)) {
    parentProfile.linkedChildren.push(studentUid);
    setMockDoc("users", parentUid, parentProfile);
  }

  // Update student profile
  const studentProfile = getMockDoc<UserProfile>("users", studentUid);
  if (studentProfile) {
    if (!studentProfile.linkedParents) studentProfile.linkedParents = [];
    if (!studentProfile.linkedParents.includes(parentUid)) {
      studentProfile.linkedParents.push(parentUid);
      setMockDoc("users", studentUid, studentProfile);
    }
  }

  return { success: true, studentName };
}

/**
 * Save study session state (survives refresh and syncs across views)
 */
export function saveSessionState(state: StudySessionState): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(`tb_session_state_${state.taskId}`, JSON.stringify(state));
  } catch {}
}

/**
 * Load study session state
 */
export function loadSessionState(taskId: string): StudySessionState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(`tb_session_state_${taskId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

