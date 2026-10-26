"use client";

import Link from "next/link";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import {
  TrendingUp,
  Shield,
  Layers,
  Cpu,
  BarChart3,
  CheckCircle2,
  Lock,
  ArrowRight,
} from "lucide-react";

export default function Home() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative overflow-hidden pt-20 pb-28 md:pt-32 md:pb-36">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(99,102,241,0.15),rgba(255,255,255,0))]" />

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 text-xs font-semibold mb-8 animate-pulse">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              Phase 1 Active: Secure Architecture & Foundation Verified
            </div>

            <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-4xl mx-auto leading-tight">
              Institutional-Grade{" "}
              <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-cyan-400 bg-clip-text text-transparent">
                Portfolio Intelligence
              </span>
            </h1>

            <p className="mt-6 text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
              Real calculations, mathematical optimization, strict user isolation,
              and AI advisory designed for high-conviction wealth management.
            </p>

            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              {user ? (
                <Link
                  href="/dashboard"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-xl shadow-indigo-600/25 transition-all"
                >
                  Go to Portfolio Dashboard
                  <ArrowRight className="w-4 h-4" />
                </Link>
              ) : (
                <>
                  <Link
                    href="/register"
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-white bg-indigo-600 hover:bg-indigo-500 shadow-xl shadow-indigo-600/25 transition-all"
                  >
                    Create Free Account
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                  <Link
                    href="/login"
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 transition-all"
                  >
                    Sign In
                  </Link>
                </>
              )}
            </div>

            {/* Architecture Highlights Badge */}
            <div className="mt-16 pt-12 border-t border-slate-800/80 grid grid-cols-2 md:grid-cols-4 gap-6 text-left max-w-4xl mx-auto">
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80">
                <Shield className="w-5 h-5 text-indigo-400 mb-2" />
                <h3 className="font-semibold text-white text-sm">Row-Level Isolation</h3>
                <p className="text-xs text-slate-400 mt-1">Queries strictly bounded to authenticated user UUID.</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80">
                <Lock className="w-5 h-5 text-violet-400 mb-2" />
                <h3 className="font-semibold text-white text-sm">Bcrypt & JWT Auth</h3>
                <p className="text-xs text-slate-400 mt-1">Access tokens + revokable refresh token rotation.</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80">
                <Layers className="w-5 h-5 text-cyan-400 mb-2" />
                <h3 className="font-semibold text-white text-sm">PostgreSQL 16</h3>
                <p className="text-xs text-slate-400 mt-1">Alembic-managed relational schema with foreign key cascades.</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80">
                <Cpu className="w-5 h-5 text-emerald-400 mb-2" />
                <h3 className="font-semibold text-white text-sm">FastAPI Engine</h3>
                <p className="text-xs text-slate-400 mt-1">Python 3.13 Apple Silicon backend with 30 passing tests.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Phase 1 Verification Checklist */}
        <section className="py-16 bg-slate-900/50 border-y border-slate-800/80">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-10">
              <h2 className="text-2xl font-bold text-white">Phase 1 Foundation Status</h2>
              <p className="text-slate-400 text-sm mt-1">Genuinely tested and active system components</p>
            </div>

            <div className="space-y-3">
              {[
                { title: "Native PostgreSQL 16 & Alembic Migrations", desc: "Users, RefreshTokens, Portfolios, and Holdings tables initialized with UUID primary keys." },
                { title: "Stateless JWT Auth with Refresh Rotation", desc: "HS256 tokens, bcrypt password hashing, and DB-tracked revocable refresh tokens." },
                { title: "Strict User-Level Data Isolation", desc: "Cross-user data leakage strictly blocked; accessing another user's portfolio safely yields 404." },
                { title: "Full Automated Test Suite", desc: "30 unit/integration tests passing with 100% coverage across auth, models, and portfolios." },
                { title: "FastAPI REST API & Next.js 16 Client", desc: "CORS-configured backend on port 8000 connected to typed client on port 3000." },
              ].map((item, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 p-4 rounded-xl bg-slate-900/80 border border-slate-800"
                >
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-sm font-semibold text-white">{item.title}</h3>
                    <p className="text-xs text-slate-400 mt-0.5">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-800/80 py-8 text-center text-xs text-slate-500">
        FolioPulse AI — Student Capstone Architecture — Phase 1 Complete
      </footer>
    </div>
  );
}
