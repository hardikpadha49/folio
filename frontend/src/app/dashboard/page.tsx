"use client";

import { useEffect, useState, useTransition, useRef } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import {
  Portfolio,
  Holding,
  PortfolioValuation,
  CSVPreviewResponse,
} from "@/types";
import {
  Briefcase,
  Plus,
  Trash2,
  TrendingUp,
  TrendingDown,
  FolderPlus,
  PieChart,
  ShieldCheck,
  AlertCircle,
  RefreshCw,
  Upload,
  Download,
  CheckCircle,
  FileText,
  Clock,
  AlertTriangle,
  X,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolio, setSelectedPortfolio] = useState<Portfolio | null>(null);
  const [valuation, setValuation] = useState<PortfolioValuation | null>(null);
  const [loading, setLoading] = useState(true);
  const [valuationLoading, setValuationLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New Portfolio Form State
  const [showNewPortfolio, setShowNewPortfolio] = useState(false);
  const [newPortfolioName, setNewPortfolioName] = useState("");
  const [newPortfolioDesc, setNewPortfolioDesc] = useState("");
  const [newPortfolioCurrency, setNewPortfolioCurrency] = useState("INR");
  const [creatingPortfolio, setCreatingPortfolio] = useState(false);

  // New Holding Form State
  const [showAddHolding, setShowAddHolding] = useState(false);
  const [newTicker, setNewTicker] = useState("");
  const [newName, setNewName] = useState("");
  const [newQuantity, setNewQuantity] = useState("");
  const [newAverageCost, setNewAverageCost] = useState("");
  const [newAssetClass, setNewAssetClass] = useState("equity");
  const [newSector, setNewSector] = useState("Technology");
  const [addingHolding, setAddingHolding] = useState(false);

  // CSV Import State
  const [showCSVModal, setShowCSVModal] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvPreview, setCsvPreview] = useState<CSVPreviewResponse | null>(null);
  const [csvLoading, setCsvLoading] = useState(false);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [csvSuccess, setCsvSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [, startTransition] = useTransition();

  // Auth gate
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  // Load portfolios
  const loadPortfolios = async () => {
    try {
      setError(null);
      const data = await api.listPortfolios();
      setPortfolios(data);
      if (data.length > 0 && !selectedPortfolio) {
        setSelectedPortfolio(data[0]);
      } else if (data.length === 0) {
        setSelectedPortfolio(null);
        setValuation(null);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      loadPortfolios();
    }
  }, [user]);

  // Load valuation whenever selectedPortfolio changes
  const loadValuation = async (refresh: boolean = false) => {
    if (!selectedPortfolio) return;
    setValuationLoading(true);
    try {
      const data = await api.getPortfolioValuation(selectedPortfolio.id, refresh);
      setValuation(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setValuationLoading(false);
    }
  };

  useEffect(() => {
    if (selectedPortfolio) {
      loadValuation(false);
    }
  }, [selectedPortfolio]);

  // Handle Portfolio Creation
  const handleCreatePortfolio = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingPortfolio(true);
    setError(null);
    try {
      const created = await api.createPortfolio({
        name: newPortfolioName,
        description: newPortfolioDesc || undefined,
        currency: newPortfolioCurrency,
      });
      setNewPortfolioName("");
      setNewPortfolioDesc("");
      setShowNewPortfolio(false);
      await loadPortfolios();
      setSelectedPortfolio(created);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setCreatingPortfolio(false);
    }
  };

  // Handle Portfolio Deletion
  const handleDeletePortfolio = async (id: string) => {
    if (!confirm("Are you sure you want to delete this portfolio?")) return;
    try {
      await api.deletePortfolio(id);
      setSelectedPortfolio(null);
      setValuation(null);
      await loadPortfolios();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    }
  };

  // Handle Add Holding
  const handleAddHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPortfolio) return;
    setAddingHolding(true);
    setError(null);
    try {
      await api.addHolding(selectedPortfolio.id, {
        ticker: newTicker,
        name: newName || undefined,
        quantity: parseFloat(newQuantity),
        average_cost: parseFloat(newAverageCost),
        asset_class: newAssetClass,
        sector: newSector || undefined,
      });
      setNewTicker("");
      setNewName("");
      setNewQuantity("");
      setNewAverageCost("");
      setShowAddHolding(false);
      await loadValuation(true);
      startTransition(() => {
        loadPortfolios();
      });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setAddingHolding(false);
    }
  };

  // Handle Delete Holding
  const handleDeleteHolding = async (holdingId: string) => {
    if (!selectedPortfolio) return;
    try {
      await api.deleteHolding(selectedPortfolio.id, holdingId);
      await loadValuation(true);
      loadPortfolios();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    }
  };

  // CSV File Selection & Preview
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedPortfolio) return;
    setSelectedFile(file);
    setCsvError(null);
    setCsvSuccess(null);
    setCsvLoading(true);

    try {
      const preview = await api.previewCSV(selectedPortfolio.id, file);
      setCsvPreview(preview);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setCsvError(err.message);
      }
      setCsvPreview(null);
    } finally {
      setCsvLoading(false);
    }
  };

  // CSV Commit
  const handleCommitCSV = async () => {
    if (!selectedFile || !selectedPortfolio || !csvPreview?.can_commit) return;
    setCsvLoading(true);
    setCsvError(null);
    try {
      const res = await api.commitCSV(selectedPortfolio.id, selectedFile);
      setCsvSuccess(res.message);
      setSelectedFile(null);
      setCsvPreview(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadValuation(true);
      await loadPortfolios();
      setTimeout(() => {
        setShowCSVModal(false);
        setCsvSuccess(null);
      }, 1500);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setCsvError(err.message);
      }
    } finally {
      setCsvLoading(false);
    }
  };

  // Download Template Handler
  const handleDownloadTemplate = async () => {
    try {
      const csvText = await api.downloadCSVTemplate();
      const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "holdings_template.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    }
  };

  if (authLoading || (!user && loading)) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const currencySymbol = selectedPortfolio?.currency === "INR" ? "₹" : "$";

  return (
    <div className="min-h-screen flex flex-col bg-slate-950">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* User Welcome & Stats Bar */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 mb-8 backdrop-blur-sm">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-white tracking-tight">
                  Welcome back, {user?.full_name}
                </h1>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Authenticated
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-1">
                Phase 2 Active: Online market quotes, multi-currency valuation, and validated CSV ingestion.
              </p>
            </div>

            <div className="flex items-center gap-3">
              {selectedPortfolio && (
                <button
                  onClick={() => setShowCSVModal(true)}
                  className="flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 rounded-xl text-sm font-semibold transition-all"
                >
                  <Upload className="w-4 h-4 text-indigo-400" />
                  Import CSV
                </button>
              )}
              <button
                onClick={() => setShowNewPortfolio(true)}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-indigo-600/20 transition-all shrink-0"
              >
                <FolderPlus className="w-4 h-4" />
                New Portfolio
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-xs text-rose-400/80 hover:text-rose-300">
              Dismiss
            </button>
          </div>
        )}

        {/* Main Grid: Portfolios on Left, Selected Portfolio Detail on Right */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Portfolio List Column */}
          <div className="lg:col-span-4 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
                My Portfolios ({portfolios.length})
              </h2>
            </div>

            {portfolios.length === 0 ? (
              <div className="text-center p-8 bg-slate-900/40 border border-slate-800 rounded-2xl">
                <Briefcase className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                <p className="text-sm text-slate-400 font-medium">No portfolios yet</p>
                <p className="text-xs text-slate-500 mt-1">Create one to start tracking your holdings.</p>
                <button
                  onClick={() => setShowNewPortfolio(true)}
                  className="mt-4 px-3 py-1.5 text-xs font-semibold text-indigo-400 bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/20 rounded-lg transition-colors"
                >
                  Create First Portfolio
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {portfolios.map((p) => {
                  const isSelected = selectedPortfolio?.id === p.id;
                  return (
                    <div
                      key={p.id}
                      onClick={() => setSelectedPortfolio(p)}
                      className={`p-4 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? "bg-indigo-600/10 border-indigo-500/40 shadow-lg shadow-indigo-500/5"
                          : "bg-slate-900/40 border-slate-800 hover:border-slate-700 hover:bg-slate-900/80"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="text-sm font-semibold text-white">{p.name}</h3>
                          {p.description && (
                            <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{p.description}</p>
                          )}
                        </div>
                        <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-300">
                          {p.currency}
                        </span>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                        <span>{p.holding_count} {p.holding_count === 1 ? "holding" : "holdings"}</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeletePortfolio(p.id);
                          }}
                          className="text-slate-500 hover:text-rose-400 transition-colors p-1"
                          title="Delete Portfolio"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Holdings & Real-Time Valuation Column */}
          <div className="lg:col-span-8">
            {selectedPortfolio ? (
              <div className="space-y-6">
                {/* Portfolio Summary Card with Real-Time Valuation Metrics */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-xl font-bold text-white">{selectedPortfolio.name}</h2>
                        <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-indigo-400 border border-indigo-500/20">
                          {selectedPortfolio.currency}
                        </span>
                        {valuation && !valuation.valuation_complete && (
                          <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            <AlertTriangle className="w-3 h-3" />
                            {valuation.valued_holdings_count}/{valuation.holdings_count} Priced
                          </span>
                        )}
                      </div>
                      {selectedPortfolio.description && (
                        <p className="text-xs text-slate-400 mt-1">{selectedPortfolio.description}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => loadValuation(true)}
                        disabled={valuationLoading}
                        className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition-all disabled:opacity-50"
                        title="Refresh Live Market Quotes"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${valuationLoading ? "animate-spin text-indigo-400" : ""}`} />
                        <span>Refresh Quotes</span>
                      </button>

                      <button
                        onClick={() => setShowAddHolding(true)}
                        className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md transition-all"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Add Holding
                      </button>
                    </div>
                  </div>

                  {/* Valuation Metric Badges */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800">
                      <p className="text-xs text-slate-400 font-medium">Cost Basis</p>
                      <p className="text-lg font-bold text-white font-mono mt-1">
                        {currencySymbol}
                        {(valuation?.total_cost_basis ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800">
                      <p className="text-xs text-slate-400 font-medium">Current Market Value</p>
                      <p className="text-lg font-bold text-white font-mono mt-1">
                        {valuation?.total_market_value !== null && valuation?.total_market_value !== undefined
                          ? `${currencySymbol}${valuation.total_market_value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`
                          : "—"}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800">
                      <p className="text-xs text-slate-400 font-medium">Unrealized P&L</p>
                      {valuation?.total_unrealized_pnl !== null && valuation?.total_unrealized_pnl !== undefined ? (
                        <div className="flex items-center gap-1.5 mt-1">
                          {valuation.total_unrealized_pnl >= 0 ? (
                            <TrendingUp className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <TrendingDown className="w-4 h-4 text-rose-400" />
                          )}
                          <span
                            className={`text-lg font-bold font-mono ${
                              valuation.total_unrealized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"
                            }`}
                          >
                            {valuation.total_unrealized_pnl >= 0 ? "+" : ""}
                            {currencySymbol}
                            {valuation.total_unrealized_pnl.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      ) : (
                        <p className="text-lg font-bold text-slate-500 font-mono mt-1">—</p>
                      )}
                    </div>

                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800">
                      <p className="text-xs text-slate-400 font-medium">Return on Cost</p>
                      {valuation?.total_unrealized_pnl_percent !== null && valuation?.total_unrealized_pnl_percent !== undefined ? (
                        <p
                          className={`text-lg font-bold font-mono mt-1 ${
                            valuation.total_unrealized_pnl_percent >= 0 ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {valuation.total_unrealized_pnl_percent >= 0 ? "+" : ""}
                          {valuation.total_unrealized_pnl_percent.toFixed(2)}%
                        </p>
                      ) : (
                        <p className="text-lg font-bold text-slate-500 font-mono mt-1">—</p>
                      )}
                    </div>
                  </div>

                  {/* Partial Data Notice Banner */}
                  {valuation && !valuation.valuation_complete && (
                    <div className="mt-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>
                        Some assets are unpriced due to market rate limits or unsupported ticker format. Total market value and returns currently reflect priced assets only.
                      </span>
                    </div>
                  )}
                </div>

                {/* Holdings Table with Live Prices & PnL */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
                  <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-white">Holdings & Live Market Valuation</h3>
                    {valuation?.as_of && (
                      <span className="text-[11px] text-slate-500 flex items-center gap-1 font-mono">
                        <Clock className="w-3 h-3" />
                        As of {new Date(valuation.as_of).toLocaleTimeString()}
                      </span>
                    )}
                  </div>

                  {!valuation || valuation.holdings.length === 0 ? (
                    <div className="text-center p-8">
                      <PieChart className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                      <p className="text-sm text-slate-400">No holdings in this portfolio</p>
                      <div className="mt-3 flex items-center justify-center gap-3">
                        <button
                          onClick={() => setShowAddHolding(true)}
                          className="px-3 py-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                        >
                          + Add holding
                        </button>
                        <span className="text-slate-600">•</span>
                        <button
                          onClick={() => setShowCSVModal(true)}
                          className="px-3 py-1.5 text-xs text-slate-300 hover:text-white font-medium"
                        >
                          Upload CSV
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-800/50 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                          <tr>
                            <th className="py-3 px-4">Ticker</th>
                            <th className="py-3 px-4">Class</th>
                            <th className="py-3 px-4 text-right">Qty</th>
                            <th className="py-3 px-4 text-right">Avg Cost</th>
                            <th className="py-3 px-4 text-right">Cost Basis</th>
                            <th className="py-3 px-4 text-right">Market Price</th>
                            <th className="py-3 px-4 text-right">Market Value</th>
                            <th className="py-3 px-4 text-right">P&L</th>
                            <th className="py-3 px-4 text-right">Alloc</th>
                            <th className="py-3 px-4 text-center">Status</th>
                            <th className="py-3 px-4 text-center">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/80">
                          {valuation.holdings.map((h) => {
                            const isProfitable = (h.unrealized_pnl ?? 0) >= 0;
                            return (
                              <tr key={h.holding_id} className="hover:bg-slate-800/30 transition-colors">
                                <td className="py-3.5 px-4 font-mono font-bold text-white">
                                  {h.ticker}
                                  {h.name && <span className="block text-[11px] font-normal text-slate-400 font-sans">{h.name}</span>}
                                </td>
                                <td className="py-3.5 px-4">
                                  <span className="px-2 py-0.5 rounded text-[11px] uppercase font-semibold bg-slate-800 text-slate-300">
                                    {h.asset_class}
                                  </span>
                                </td>
                                <td className="py-3.5 px-4 text-right font-mono text-slate-300">{h.quantity}</td>
                                <td className="py-3.5 px-4 text-right font-mono text-slate-300">
                                  {currencySymbol}{h.average_cost.toLocaleString()}
                                </td>
                                <td className="py-3.5 px-4 text-right font-mono text-slate-300">
                                  {currencySymbol}{h.cost_basis.toLocaleString()}
                                </td>
                                <td className="py-3.5 px-4 text-right font-mono">
                                  {h.market_price !== null && h.market_price !== undefined ? (
                                    <span className="text-white font-medium">
                                      {h.quote_currency === "INR" ? "₹" : "$"}{h.market_price.toLocaleString()}
                                    </span>
                                  ) : (
                                    <span className="text-slate-500">—</span>
                                  )}
                                </td>
                                <td className="py-3.5 px-4 text-right font-mono font-semibold">
                                  {h.market_value !== null && h.market_value !== undefined ? (
                                    <span className="text-white">
                                      {currencySymbol}{h.market_value.toLocaleString()}
                                    </span>
                                  ) : (
                                    <span className="text-slate-500">—</span>
                                  )}
                                </td>
                                <td className="py-3.5 px-4 text-right font-mono">
                                  {h.unrealized_pnl !== null && h.unrealized_pnl !== undefined ? (
                                    <div>
                                      <span className={isProfitable ? "text-emerald-400" : "text-rose-400"}>
                                        {isProfitable ? "+" : ""}{currencySymbol}{h.unrealized_pnl.toLocaleString()}
                                      </span>
                                      <span className={`block text-[10px] ${isProfitable ? "text-emerald-500" : "text-rose-500"}`}>
                                        ({isProfitable ? "+" : ""}{h.unrealized_pnl_percent?.toFixed(2)}%)
                                      </span>
                                    </div>
                                  ) : (
                                    <span className="text-slate-500">—</span>
                                  )}
                                </td>
                                <td className="py-3.5 px-4 text-right font-mono text-indigo-300">
                                  {h.allocation_percent !== null && h.allocation_percent !== undefined
                                    ? `${h.allocation_percent.toFixed(1)}%`
                                    : "—"}
                                </td>
                                <td className="py-3.5 px-4 text-center">
                                  <span
                                    title={h.status_note || h.data_status}
                                    className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                                      h.data_status === "VALID"
                                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                        : h.data_status === "STALE"
                                        ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                        : h.data_status === "FALLBACK"
                                        ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                                        : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                    }`}
                                  >
                                    {h.data_status}
                                  </span>
                                </td>
                                <td className="py-3.5 px-4 text-center">
                                  <button
                                    onClick={() => handleDeleteHolding(h.holding_id)}
                                    className="text-slate-500 hover:text-rose-400 transition-colors"
                                    title="Remove Holding"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center">
                <Briefcase className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <h3 className="text-base font-semibold text-white">Select a Portfolio</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                  Choose a portfolio from the left or create a new one to view its asset breakdown and holdings.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Modal: CSV Import Workflow */}
      {showCSVModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-400" />
                <h3 className="text-lg font-bold text-white">Import Holdings CSV</h3>
              </div>
              <button
                onClick={() => {
                  setShowCSVModal(false);
                  setSelectedFile(null);
                  setCsvPreview(null);
                  setCsvError(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-4 space-y-4">
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-800/40 border border-slate-800">
                <div className="text-xs text-slate-300">
                  <p className="font-semibold">Need the format?</p>
                  <p className="text-slate-400 mt-0.5">Use our standard CSV template with required headers.</p>
                </div>
                <button
                  onClick={handleDownloadTemplate}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-indigo-400 border border-indigo-500/20 rounded-lg text-xs font-semibold transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download Template
                </button>
              </div>

              {/* File Input */}
              <div className="border-2 border-dashed border-slate-700 hover:border-indigo-500/50 rounded-xl p-6 text-center transition-colors">
                <Upload className="w-8 h-8 text-indigo-400 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-200">
                  {selectedFile ? selectedFile.name : "Select or drag a .csv file"}
                </p>
                <p className="text-xs text-slate-500 mt-1">UTF-8 encoded CSV up to 5 MB</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                  id="csv-file-picker"
                />
                <label
                  htmlFor="csv-file-picker"
                  className="mt-3 inline-block px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-md"
                >
                  Browse Computer
                </label>
              </div>

              {csvLoading && (
                <div className="p-4 text-center">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-xs text-slate-400">Validating rows...</p>
                </div>
              )}

              {csvError && (
                <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{csvError}</span>
                </div>
              )}

              {csvSuccess && (
                <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 shrink-0" />
                  <span>{csvSuccess}</span>
                </div>
              )}

              {/* Validation Feedback & Preview */}
              {csvPreview && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-slate-300">Preview: {csvPreview.valid_rows_count} Valid Row(s)</span>
                    {csvPreview.errors_count > 0 ? (
                      <span className="text-rose-400">{csvPreview.errors_count} Error(s)</span>
                    ) : (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" /> Ready for Atomic Import
                      </span>
                    )}
                  </div>

                  {/* Errors List */}
                  {csvPreview.errors.length > 0 && (
                    <div className="max-h-32 overflow-y-auto p-3 rounded-xl bg-rose-500/5 border border-rose-500/20 space-y-1.5 text-[11px] text-rose-400">
                      {csvPreview.errors.map((err, i) => (
                        <div key={i} className="flex items-start gap-1.5">
                          <span className="font-bold font-mono">Row {err.row}:</span>
                          <span>{err.message}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Valid Rows Preview Table */}
                  {csvPreview.valid_rows.length > 0 && (
                    <div className="max-h-48 overflow-y-auto rounded-xl border border-slate-800">
                      <table className="w-full text-left text-[11px]">
                        <thead className="bg-slate-800/60 text-slate-400 uppercase font-semibold">
                          <tr>
                            <th className="py-2 px-3">Ticker</th>
                            <th className="py-2 px-3">Qty</th>
                            <th className="py-2 px-3">Avg Cost</th>
                            <th className="py-2 px-3">Class</th>
                            <th className="py-2 px-3 text-right">Invested</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                          {csvPreview.valid_rows.map((r, i) => (
                            <tr key={i} className="hover:bg-slate-800/30">
                              <td className="py-2 px-3 font-mono font-bold text-white">{r.ticker}</td>
                              <td className="py-2 px-3 font-mono">{r.quantity}</td>
                              <td className="py-2 px-3 font-mono">{r.average_cost}</td>
                              <td className="py-2 px-3 uppercase">{r.asset_class}</td>
                              <td className="py-2 px-3 text-right font-mono font-semibold text-emerald-400">
                                {currencySymbol}{r.invested_value.toLocaleString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowCSVModal(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCommitCSV}
                disabled={!csvPreview?.can_commit || csvLoading}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {csvLoading ? "Importing..." : `Confirm Import (${csvPreview?.valid_rows_count ?? 0} Holdings)`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: New Portfolio */}
      {showNewPortfolio && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl relative">
            <h3 className="text-lg font-bold text-white mb-4">Create New Portfolio</h3>
            <form onSubmit={handleCreatePortfolio} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Portfolio Name</label>
                <input
                  type="text"
                  required
                  value={newPortfolioName}
                  onChange={(e) => setNewPortfolioName(e.target.value)}
                  placeholder="e.g. Growth Portfolio 2026"
                  className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Description (Optional)</label>
                <textarea
                  value={newPortfolioDesc}
                  onChange={(e) => setNewPortfolioDesc(e.target.value)}
                  placeholder="e.g. High conviction long-term equity allocation"
                  rows={2}
                  className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Base Currency</label>
                <select
                  value={newPortfolioCurrency}
                  onChange={(e) => setNewPortfolioCurrency(e.target.value)}
                  className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:border-indigo-500"
                >
                  <option value="INR">INR (₹)</option>
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="GBP">GBP (£)</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowNewPortfolio(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingPortfolio}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md disabled:opacity-50"
                >
                  {creatingPortfolio ? "Creating..." : "Create Portfolio"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Add Holding */}
      {showAddHolding && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl relative">
            <h3 className="text-lg font-bold text-white mb-4">Add Holding to {selectedPortfolio?.name}</h3>
            <form onSubmit={handleAddHolding} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Ticker / Symbol</label>
                <input
                  type="text"
                  required
                  value={newTicker}
                  onChange={(e) => setNewTicker(e.target.value)}
                  placeholder="e.g. RELIANCE.NS, TCS.NS, AAPL"
                  className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm font-mono focus:outline-none focus:border-indigo-500 uppercase"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Company / Asset Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Reliance Industries Limited"
                  className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Quantity</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={newQuantity}
                    onChange={(e) => setNewQuantity(e.target.value)}
                    placeholder="10"
                    className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Average Cost</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={newAverageCost}
                    onChange={(e) => setNewAverageCost(e.target.value)}
                    placeholder="2500.00"
                    className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Asset Class</label>
                  <select
                    value={newAssetClass}
                    onChange={(e) => setNewAssetClass(e.target.value)}
                    className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:border-indigo-500"
                  >
                    <option value="equity">Equity</option>
                    <option value="debt">Debt</option>
                    <option value="etf">ETF</option>
                    <option value="commodity">Commodity</option>
                    <option value="reit">REIT</option>
                    <option value="cash">Cash</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Sector</label>
                  <input
                    type="text"
                    value={newSector}
                    onChange={(e) => setNewSector(e.target.value)}
                    placeholder="Energy, Tech..."
                    className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddHolding(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addingHolding}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md disabled:opacity-50"
                >
                  {addingHolding ? "Adding..." : "Add Holding"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
