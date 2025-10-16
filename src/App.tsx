import React, { useEffect, useState } from "react";
import Header from "./components/Header";
import Toolbar from "./components/Toolbar";
import GlassCard from "./components/GlassCard";
import ProfilesTable from "./components/ProfilesTable";
import * as api from "./lib/api";

export default function App() {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const list = await api.getProfiles();
      setProfiles(list);
    } catch (error) {
      console.error("Failed to load profiles:", error);
    }
    setLoading(false);
  }

  useEffect(() => { 
    load(); 
  }, []);

  return (
    <div className="min-h-screen relative">
      {/* Градиентный фон как на мокапе */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-brand-500/35 via-brand-600/35 to-[#8b5cf6]/30" />
      <div className="relative max-w-7xl mx-auto px-6 py-6">
        <Header />
        <Toolbar onReload={load} />
        <GlassCard className="mt-4">
          <ProfilesTable data={profiles} loading={loading} onAction={load} />
        </GlassCard>
      </div>
    </div>
  );
}
