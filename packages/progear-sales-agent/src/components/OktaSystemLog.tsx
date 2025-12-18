'use client';

import { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle, XCircle, Shield, Bot, User, Server, AlertCircle } from 'lucide-react';

interface OktaLog {
  timestamp: string;
  event_type: string;
  display_message: string;
  outcome: {
    result: string;
    reason?: string;
  };
  actor: {
    id: string;
    type: string;
    name: string;
    alternate_id?: string;
  };
  user_on_behalf_of?: {
    id: string;
    email: string;
    name: string;
  };
  id_jag?: {
    scope?: string;
    subject?: string;
  };
  details: {
    auth_server?: string;
    requested_scopes?: string;
    granted_scopes?: string;
    grant_type?: string;
  };
  severity: string;
}

interface OktaLogsResponse {
  logs: OktaLog[];
  count: number;
  time_range?: {
    since: string;
    minutes: number;
  };
  error?: string;
  demo_mode?: boolean;
}

export default function OktaSystemLog() {
  const [logs, setLogs] = useState<OktaLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    setError(null);

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const response = await fetch(`${backendUrl}/api/okta/logs?minutes=30&limit=10`);

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const data: OktaLogsResponse = await response.json();

      if (data.error) {
        setError(data.error);
        setLogs([]);
      } else {
        setLogs(data.logs || []);
      }
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs');
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const isFailure = (log: OktaLog) => log.outcome?.result === 'FAILURE';
  const isSuccess = (log: OktaLog) => log.outcome?.result === 'SUCCESS';

  return (
    <div className="mt-4">
      {/* Refresh Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm text-gray-500">
          {lastRefresh && (
            <span>Last updated: {lastRefresh.toLocaleTimeString()}</span>
          )}
        </div>
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 bg-okta-blue/10 hover:bg-okta-blue/20 text-okta-blue rounded-lg text-sm font-medium transition disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-4">
          <div className="flex items-center gap-2 text-yellow-800">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Unable to fetch live logs</span>
          </div>
          <p className="text-sm text-yellow-700 mt-1">{error}</p>
        </div>
      )}

      {/* Loading State */}
      {loading && logs.length === 0 && (
        <div className="bg-gray-100 rounded-xl p-8 text-center">
          <RefreshCw className="w-8 h-8 text-gray-400 animate-spin mx-auto mb-2" />
          <p className="text-gray-500">Loading Okta system logs...</p>
        </div>
      )}

      {/* No Logs State */}
      {!loading && !error && logs.length === 0 && (
        <div className="bg-gray-50 rounded-xl p-8 text-center">
          <Shield className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500">No token exchange events in the last 30 minutes</p>
          <p className="text-sm text-gray-400 mt-1">Try making a request in the chat to generate events</p>
        </div>
      )}

      {/* Logs Display */}
      {logs.length > 0 && (
        <div className="bg-gray-900 rounded-xl p-5 text-sm font-mono overflow-x-auto space-y-4">
          <div className="text-gray-400 mb-2">// Live Okta System Logs - Token Exchange Events</div>

          {logs.map((log, idx) => (
            <div
              key={idx}
              className={`p-4 bg-gray-800/50 rounded-lg border-l-4 ${
                isFailure(log) ? 'border-red-500' : 'border-green-500'
              }`}
            >
              {/* Header */}
              <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                <div className="flex items-center gap-2">
                  <span className={`font-semibold ${isFailure(log) ? 'text-red-400' : 'text-green-400'}`}>
                    {log.display_message || log.event_type}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    isFailure(log)
                      ? 'bg-red-500/20 text-red-400'
                      : 'bg-green-500/20 text-green-400'
                  }`}>
                    {log.outcome?.result}
                  </span>
                </div>
                <span className="text-gray-500 text-xs">{formatTimestamp(log.timestamp)}</span>
              </div>

              {/* Attribution - Agent and User */}
              <div className="grid md:grid-cols-2 gap-4 mb-3">
                {/* Agent (Actor) */}
                <div className="bg-gray-700/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-blue-400 text-xs mb-2">
                    <Bot className="w-3.5 h-3.5" />
                    <span className="uppercase tracking-wide">Agent (Actor)</span>
                  </div>
                  <div className="text-white font-semibold">{log.actor?.name || 'Unknown'}</div>
                  <div className="text-gray-400 text-xs mt-1 font-mono">{log.actor?.id}</div>
                </div>

                {/* User (On Behalf Of) */}
                <div className="bg-gray-700/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-purple-400 text-xs mb-2">
                    <User className="w-3.5 h-3.5" />
                    <span className="uppercase tracking-wide">User (On Behalf Of)</span>
                  </div>
                  {log.user_on_behalf_of ? (
                    <>
                      <div className="text-white font-semibold">{log.user_on_behalf_of.name}</div>
                      <div className="text-gray-400 text-xs mt-1">{log.user_on_behalf_of.email}</div>
                    </>
                  ) : log.id_jag?.subject ? (
                    <div className="text-gray-400 text-xs font-mono">{log.id_jag.subject}</div>
                  ) : (
                    <div className="text-gray-500 italic">Not available</div>
                  )}
                </div>
              </div>

              {/* Details */}
              <div className="space-y-1.5 text-xs">
                {log.details?.auth_server && (
                  <div className="flex items-center gap-2">
                    <Server className="w-3 h-3 text-gray-500" />
                    <span className="text-gray-500">MCP Server:</span>
                    <span className="text-cyan-300">{log.details.auth_server}</span>
                  </div>
                )}

                {(log.details?.requested_scopes || log.id_jag?.scope) && (
                  <div>
                    <span className="text-gray-500">Requested Scope:</span>{' '}
                    <span className={isFailure(log) ? 'text-red-400 line-through' : 'text-orange-300'}>
                      {log.details?.requested_scopes || log.id_jag?.scope}
                    </span>
                  </div>
                )}

                {log.details?.granted_scopes && isSuccess(log) && (
                  <div>
                    <span className="text-gray-500">Granted Scope:</span>{' '}
                    <span className="text-green-300">{log.details.granted_scopes}</span>
                  </div>
                )}

                {isFailure(log) && log.outcome?.reason && (
                  <div className="mt-2 p-2 bg-red-500/10 rounded border border-red-500/30">
                    <span className="text-red-400">
                      <Shield className="w-3 h-3 inline mr-1" />
                      Denied: {log.outcome.reason}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Value Proposition */}
      <div className="mt-4 grid md:grid-cols-3 gap-4">
        <div className="p-4 bg-purple-50 rounded-lg border-l-4 border-purple-500">
          <div className="font-semibold text-purple-800">Complete Attribution</div>
          <div className="text-sm text-purple-700 mt-1">
            Every request shows both the AI agent AND the user it acted on behalf of.
          </div>
        </div>
        <div className="p-4 bg-green-50 rounded-lg border-l-4 border-green-500">
          <div className="font-semibold text-green-800">Real-Time Visibility</div>
          <div className="text-sm text-green-700 mt-1">
            Live logs from Okta showing actual governance decisions.
          </div>
        </div>
        <div className="p-4 bg-blue-50 rounded-lg border-l-4 border-blue-500">
          <div className="font-semibold text-blue-800">Policy Enforcement</div>
          <div className="text-sm text-blue-700 mt-1">
            See exactly when and why access was granted or denied.
          </div>
        </div>
      </div>
    </div>
  );
}
