import { useState, useEffect } from "react";
import { API_BASE, apiFetch } from "@/lib/api";
import { readCachedUser } from "@/lib/auth-storage";

export function useAuth(setActiveTab: (tab: string) => void) {
  const [user, setUser] = useState<any>(null);
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authName, setAuthName] = useState("");
  const [authModalError, setAuthModalError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      setUser(readCachedUser());
    }
  }, []);

  const handleAuth = async (e: any) => {
    e.preventDefault();
    setAuthModalError(null);
    try {
      const url = authMode === "login" ? `${API_BASE}/auth/login` : `${API_BASE}/auth/register`;
      const body = authMode === "login"
        ? { email: authEmail, password: authPassword }
        : { email: authEmail, password: authPassword, full_name: authName };

      const data = await apiFetch<any>(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (authMode === "login") {
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("user_cache", JSON.stringify(data.user));
        setUser(data.user);
        setShowAuth(false);
      } else {
        setAuthMode("login");
        setAuthModalError("Registered successfully. Please login.");
      }
    } catch (err: any) {
      setAuthModalError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user_cache");
    setUser(null);
    setActiveTab("overview");
  };

  return {
    user, setUser,
    showAuth, setShowAuth,
    authMode, setAuthMode,
    authEmail, setAuthEmail,
    authPassword, setAuthPassword,
    authName, setAuthName,
    authModalError, setAuthModalError,
    handleAuth, handleLogout
  };
}
