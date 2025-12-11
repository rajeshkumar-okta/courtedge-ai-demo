'use client';

import { useState } from 'react';

export default function Home() {
  const [message, setMessage] = useState('');

  return (
    <main className="min-h-screen bg-gradient-to-b from-progear-900 to-progear-700">
      {/* Header */}
      <header className="border-b border-progear-600 bg-progear-800/50 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-progear-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xl">P</span>
            </div>
            <div>
              <h1 className="text-white font-semibold text-lg">ProGear Sales AI</h1>
              <p className="text-progear-300 text-sm">Secured by Okta + Auth0</p>
            </div>
          </div>
          <button className="px-4 py-2 bg-progear-500 hover:bg-progear-400 text-white rounded-lg transition-colors">
            Sign In with Okta
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Welcome Card */}
        <div className="bg-white/10 backdrop-blur rounded-2xl p-8 mb-8">
          <h2 className="text-2xl font-bold text-white mb-4">
            Welcome to ProGear Sales Assistant
          </h2>
          <p className="text-progear-200 mb-6">
            I can help you with orders, inventory, pricing, and customer information.
            Sign in with Okta to get started.
          </p>

          {/* Feature Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: 'Sales Agent', desc: 'Orders & quotes' },
              { name: 'Inventory Agent', desc: 'Stock levels' },
              { name: 'Pricing Agent', desc: 'Discounts' },
              { name: 'Customer Agent', desc: 'Accounts' },
            ].map((agent) => (
              <div
                key={agent.name}
                className="bg-progear-800/50 rounded-lg p-4 border border-progear-600"
              >
                <h3 className="text-white font-medium text-sm">{agent.name}</h3>
                <p className="text-progear-400 text-xs">{agent.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Chat Interface Placeholder */}
        <div className="bg-white/5 backdrop-blur rounded-2xl border border-progear-600 overflow-hidden">
          {/* Chat Messages Area */}
          <div className="h-96 p-4 overflow-y-auto">
            <div className="text-center text-progear-400 py-8">
              <p>Sign in to start chatting with the AI assistant</p>
            </div>
          </div>

          {/* Input Area */}
          <div className="border-t border-progear-600 p-4">
            <div className="flex gap-3">
              <input
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Ask about orders, inventory, pricing, or customers..."
                className="flex-1 bg-progear-800 border border-progear-600 rounded-lg px-4 py-3 text-white placeholder-progear-400 focus:outline-none focus:border-progear-400"
                disabled
              />
              <button
                className="px-6 py-3 bg-progear-500 hover:bg-progear-400 disabled:bg-progear-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
                disabled
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Security Info */}
        <div className="mt-8 text-center">
          <p className="text-progear-400 text-sm">
            This demo showcases Okta AI Agent security features including
            agent registration, token exchange (ID-JAG), and Auth0 FGA.
          </p>
        </div>
      </div>
    </main>
  );
}
