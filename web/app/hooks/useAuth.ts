"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function useAuth() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    // Check if running in browser
    if (typeof window === "undefined") return;

    const storedToken = localStorage.getItem("postbox-auth-token");
    if (storedToken) {
      setIsAuthenticated(true);
      setToken(storedToken);
    } else {
      setIsAuthenticated(false);
      // Redirect to login if not authenticated
      if (window.location.pathname !== "/login") {
        router.push("/login");
      }
    }
  }, [router]);

  const logout = () => {
    localStorage.removeItem("postbox-auth-token");
    localStorage.removeItem("postbox-user-id");
    setIsAuthenticated(false);
    setToken(null);
    router.push("/login");
  };

  return {
    isAuthenticated,
    token,
    logout,
  };
}
