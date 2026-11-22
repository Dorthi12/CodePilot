import React, { useState } from 'react';
import { AgentPanel } from './features/agentic_workspace/components/AgentPanel';
import { FindingsDashboard } from './features/findings/components/FindingsDashboard';
import { Bot, Bug, Shield, Terminal } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'a3_findings' | 'm1_agents'>('a3_findings');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased flex flex-col">
      {/* Navigation Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">
              CP
            </div>
            <div>
              <span className="font-bold text-sm tracking-wide text-white">CodePilot</span>
              <span className="text-[10px] text-slate-400 block font-mono">The Knowledge of Athena</span>
            </div>
          </div>

          {/* Feature switcher tabs */}
          <nav className="flex items-center gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('a3_findings')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'a3_findings'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Bug className="w-4 h-4" />
              <span>A3: Bug & Smell Detection</span>
            </button>
            <button
              onClick={() => setActiveTab('m1_agents')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'm1_agents'
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Bot className="w-4 h-4" />
              <span>M1: Multi-Agent Analysis</span>
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1">
        {activeTab === 'a3_findings' ? <FindingsDashboard /> : <AgentPanel />}
      </main>
    </div>
  );
}
