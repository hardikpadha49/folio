"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { Portfolio, Holding } from "@/types";
import {
  Briefcase,
  Plus,
  Trash2,
  TrendingUp,
  FolderPlus,
  PieChart,
  ShieldCheck,
  AlertCircle,
  Building,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolio, setSelectedPortfolio] = useState<Portfolio | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [loading, setLoading] = useState(true);
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
        setHoldings([]);
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

  // Load holdings when selectedPortfolio changes
  useEffect(() => {
    if (selectedPortfolio) {
      api.listHoldings(selectedPortfolio.id)
        .then((data) => setHoldings(data))
        .catch((err) => setError(err.message));
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
      // Reload holdings
      const updatedHoldings = await api.listHoldings(selectedPortfolio.id);
      setHoldings(updatedHoldings);
      // Update holding_count in portfolio list
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
      setHoldings((prev) => prev.filter((h) => h.id !== holdingId));
      loadPortfolios();
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

  const totalInvested = holdings.reduce((sum, h) => sum + h.invested_value, 0);

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
                Data isolation active. Your portfolios are strictly bound to your user record.
              </p>
            </div>

            <button
              onClick={() => setShowNewPortfolio(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-indigo-600/20 transition-all shrink-0"
            >
              <FolderPlus className="w-4 h-4" />
              New Portfolio
            </button>
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

          {/* Holdings & Analytics Overview Column */}
          <div className="lg:col-span-8">
            {selectedPortfolio ? (
              <div className="space-y-6">
                {/* Portfolio Summary Card */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-xl font-bold text-white">{selectedPortfolio.name}</h2>
                        <span className="text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-indigo-400 border border-indigo-500/20">
                          {selectedPortfolio.currency}
                        </span>
                      </div>
                      {selectedPortfolio.description && (
                        <p className="text-xs text-slate-400 mt-1">{selectedPortfolio.description}</p>
                      )}
                    </div>

                    <button
                      onClick={() => setShowAddHolding(true)}
                      className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md transition-all self-start sm:self-auto"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add Holding
                    </button>
                  </div>

                  {/* Quick Metric Badges */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-6">
                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800">
                      <p className="text-xs text-slate-400 font-medium">Total Cost Value</p>
                      <p className="text-lg font-bold text-white font-mono mt-1">
                        {selectedPortfolio.currency === "INR" ? "₹" : "$"}
                        {totalInvested.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                      </p>
                    </div>
                    <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-800">
                      <p className="text-xs text-slate-400 font-medium">Holdings Count</p>
                      <p className="text-lg font-bold text-white font-mono mt-1">
                        {holdings.length}
                      </p>
                    </div>
                    <div className="col-span-2 sm:col-span-1 p-4 rounded-xl bg-slate-800/40 border border-slate-800">
                      <p className="text-xs text-slate-400 font-medium">Phase 2 Status</p>
                      <div className="flex items-center gap-1.5 mt-1 text-xs text-amber-400 font-medium">
                        <TrendingUp className="w-4 h-4" />
                        <span>Ready for Live Market Feed</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Holdings Table */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
                  <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-white">Holdings</h3>
                    <span className="text-xs text-slate-500">Sorted by Ticker</span>
                  </div>

                  {holdings.length === 0 ? (
                    <div className="text-center p-8">
                      <PieChart className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                      <p className="text-sm text-slate-400">No holdings in this portfolio</p>
                      <button
                        onClick={() => setShowAddHolding(true)}
                        className="mt-3 px-3 py-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                      >
                        + Add your first holding
                      </button>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-800/50 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                          <tr>
                            <th className="py-3 px-4">Ticker</th>
                            <th className="py-3 px-4">Asset Class</th>
                            <th className="py-3 px-4">Sector</th>
                            <th className="py-3 px-4 text-right">Qty</th>
                            <th className="py-3 px-4 text-right">Avg Cost</th>
                            <th className="py-3 px-4 text-right">Invested Value</th>
                            <th className="py-3 px-4 text-center">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/80">
                          {holdings.map((h) => (
                            <tr key={h.id} className="hover:bg-slate-800/30 transition-colors">
                              <td className="py-3.5 px-4 font-mono font-bold text-white">
                                {h.ticker}
                                {h.name && <span className="block text-[11px] font-normal text-slate-400 font-sans">{h.name}</span>}
                              </td>
                              <td className="py-3.5 px-4">
                                <span className="px-2 py-0.5 rounded text-[11px] uppercase font-semibold bg-slate-800 text-slate-300">
                                  {h.asset_class}
                                </span>
                              </td>
                              <td className="py-3.5 px-4 text-slate-400">{h.sector || "—"}</td>
                              <td className="py-3.5 px-4 text-right font-mono text-slate-300">{h.quantity}</td>
                              <td className="py-3.5 px-4 text-right font-mono text-slate-300">
                                {selectedPortfolio.currency === "INR" ? "₹" : "$"}{h.average_cost.toLocaleString()}
                              </td>
                              <td className="py-3.5 px-4 text-right font-mono font-semibold text-emerald-400">
                                {selectedPortfolio.currency === "INR" ? "₹" : "$"}{h.invested_value.toLocaleString()}
                              </td>
                              <td className="py-3.5 px-4 text-center">
                                <button
                                  onClick={() => handleDeleteHolding(h.id)}
                                  className="text-slate-500 hover:text-rose-400 transition-colors"
                                  title="Remove Holding"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))}
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
                  placeholder="e.g. RELIANCE.NS, TCS.NS, INFY.NS"
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
