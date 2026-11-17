import React, { useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  Clock,
  Cpu,
  ExternalLink,
  FileText,
  HelpCircle,
  Layers,
  Loader2,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  Terminal,
  User as UserIcon,
  XCircle,
} from 'lucide-react';
import {
  AgentRunResponse,
  runAgentChat,
  submitEmployeeResolutionFeedback,
  User,
} from '../services/api';

export interface EmployeeChatPageProps {
  currentUser: User | null;
  onNavigate?: (page: string) => void;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  response?: AgentRunResponse;
  timestamp: string;
  isError?: boolean;
}

export const EmployeeChatPage: React.FC<EmployeeChatPageProps> = ({ currentUser, onNavigate }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);
  const [feedbackGiven, setFeedbackGiven] = useState<{ [key: string]: boolean }>({});
  const [feedbackErrors, setFeedbackErrors] = useState<{ [key: string]: string }>({});
  const [threadId, setThreadId] = useState<string | undefined>(() =>
    currentUser ? sessionStorage.getItem(`resolvex-agent-thread-${currentUser.id}`) || undefined : undefined,
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Sync threadId to sessionStorage
  useEffect(() => {
    if (currentUser && threadId) {
      sessionStorage.setItem(`resolvex-agent-thread-${currentUser.id}`, threadId);
    }
  }, [currentUser, threadId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [messages, loading]);

  // Cycle loading stages while waiting for agent graph
  useEffect(() => {
    if (!loading) {
      setLoadingStage(0);
      return;
    }
    const interval = setInterval(() => {
      setLoadingStage((prev) => (prev + 1) % 5);
    }, 1800);
    return () => clearInterval(interval);
  }, [loading]);

  const STAGES = [
    'Triage Agent classifying category & severity...',
    'Knowledge Agent retrieving runbooks & SOPs via RAG...',
    'Diagnostic Agent running authorized MCP diagnostics...',
    'Resolution Agent formulating evidence-based solution...',
    'Ticket Agent updating incident lifecycle state...',
  ];

  const scenarioPrompts = [
    {
      title: 'Portal Connectivity',
      prompt: 'My laptop is connected to Wi-Fi, but the company portal is not opening.',
      tag: 'Network / Wi-Fi',
      icon: '🌐',
    },
    {
      title: 'VPN Tunnel Issue',
      prompt: 'I cannot connect to the corporate VPN.',
      tag: 'VPN / Security',
      icon: '🔒',
    },
    {
      title: 'Software Request',
      prompt: 'I need Python installed on my company laptop.',
      tag: 'Sensitive / Approval',
      icon: '📦',
    },
    {
      title: 'Production Outage',
      prompt: 'The production application is unavailable.',
      tag: 'Critical / Server',
      icon: '🚨',
    },
  ];

  const handleSendMessage = async (textToSend: string) => {
    const trimmed = textToSend.trim();
    if (!trimmed || loading) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setLoading(true);

    try {
      const data = await runAgentChat(userMsg.text, threadId);
      if (data.thread_id) setThreadId(data.thread_id);

      const agentMsg: ChatMessage = {
        id: `resp-${Date.now()}`,
        sender: 'agent',
        text:
          data.proposed_resolution?.trim() ||
          (data.errors.length
            ? `The multi-agent workflow encountered an error: ${data.errors.join('; ')}`
            : 'Investigation completed. Please review the ticket details below or contact support.'),
        response: data,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        isError: true,
        text: `Error processing request: ${err.message || 'Server error occurred.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleResolutionFeedback = async (message: ChatMessage, resolved: boolean) => {
    if (!message.response?.incident_id) {
      setFeedbackErrors((prev) => ({ ...prev, [message.id]: 'No ticket was created for this conversation.' }));
      return;
    }
    const ticketId = `INC-${String(message.response.incident_id).padStart(6, '0')}`;
    try {
      await submitEmployeeResolutionFeedback(ticketId, resolved);
      setFeedbackErrors((prev) => ({ ...prev, [message.id]: '' }));
      setFeedbackGiven((prev) => ({ ...prev, [message.id]: true }));
    } catch (cause) {
      setFeedbackErrors((prev) => ({
        ...prev,
        [message.id]: cause instanceof Error ? cause.message : 'Feedback could not be saved.',
      }));
    }
  };

  const handleResetConversation = () => {
    if (currentUser) {
      sessionStorage.removeItem(`resolvex-agent-thread-${currentUser.id}`);
    }
    setThreadId(undefined);
    setMessages([]);
    setFeedbackGiven({});
    setFeedbackErrors({});
  };

  return (
    <div className="flex flex-col h-full bg-slate-50/60 select-none">
      {/* Header Bar */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shrink-0 shadow-2xs">
        <div className="flex items-center space-x-3.5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-blue to-brand-violet text-white flex items-center justify-center shadow-md shadow-brand-blue/20">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-slate-900 leading-none">ResolveX AI Support</h1>
              <span className="text-[10px] font-bold text-brand-blue bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                LangGraph 6-Agent Swarm
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Autonomous IT triage, knowledge runbooks (RAG), Model Context Protocol (MCP) diagnostics, and ticket management.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleResetConversation}
              className="text-xs font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition flex items-center space-x-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>New Conversation</span>
            </button>
          )}
          {onNavigate && (
            <button
              type="button"
              onClick={() => onNavigate('home')}
              className="text-xs font-semibold text-brand-blue hover:text-blue-800 px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 transition flex items-center space-x-1"
            >
              <span>Employee Portal</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </header>

      {/* Suggested Scenarios Bar */}
      <section aria-label="Quick scenarios" className="bg-slate-100/90 border-b border-slate-200/90 px-6 py-2.5 flex items-center space-x-3 overflow-x-auto shrink-0">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 flex items-center shrink-0">
          <Sparkles className="w-3.5 h-3.5 text-brand-blue mr-1.5" />
          Common Scenarios:
        </span>
        <div className="flex items-center space-x-2">
          {scenarioPrompts.map((sc, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handleSendMessage(sc.prompt)}
              disabled={loading}
              className="shrink-0 bg-white hover:bg-blue-50 border border-slate-200 hover:border-brand-blue/40 text-slate-700 text-xs px-3 py-1.5 rounded-lg font-medium transition shadow-2xs flex items-center space-x-1.5 disabled:opacity-50"
            >
              <span className="text-sm">{sc.icon}</span>
              <span className="font-semibold text-slate-800">{sc.title}</span>
              <span className="text-[10px] text-brand-violet bg-purple-50 border border-purple-200/60 px-1.5 py-0.2 rounded font-semibold">
                {sc.tag}
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* Conversation Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {messages.length === 0 ? (
          /* Welcome Card */
          <div className="max-w-xl mx-auto my-auto py-12 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-brand-blue via-indigo-600 to-brand-violet text-white flex items-center justify-center shadow-lg shadow-brand-blue/25 mb-4">
              <Bot className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">How can ResolveX AI help you today?</h2>
            <p className="mt-2 text-xs sm:text-sm text-slate-500 leading-relaxed max-w-md">
              Describe your IT hardware, software, or access issue in plain text. Our multi-agent swarm will automatically triage the issue, search verified runbooks, execute diagnostics, and coordinate ticket resolution.
            </p>

            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
              {scenarioPrompts.map((sc, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSendMessage(sc.prompt)}
                  className="p-3.5 rounded-xl border border-slate-200 bg-white hover:border-brand-blue hover:bg-blue-50/50 shadow-2xs transition-all group"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-xs text-slate-800 group-hover:text-brand-blue transition-colors">
                      {sc.title}
                    </span>
                    <span className="text-sm">{sc.icon}</span>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-snug">{sc.prompt}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className="space-y-3">
              {/* Message Bubble */}
              <div
                className={`flex items-start space-x-3 ${
                  msg.sender === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {msg.sender === 'agent' && (
                  <div className="w-8 h-8 rounded-xl bg-navy-900 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-2xs">
                    <Bot className="w-4 h-4" />
                  </div>
                )}
                <div
                  className={`max-w-2xl rounded-2xl p-4 shadow-2xs text-xs sm:text-sm leading-relaxed ${
                    msg.sender === 'user'
                      ? 'bg-brand-blue text-white rounded-tr-none'
                      : msg.isError
                      ? 'bg-rose-50 border border-rose-200 text-rose-800 rounded-tl-none'
                      : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                  <span
                    className={`block text-[10px] mt-2 font-mono ${
                      msg.sender === 'user' ? 'text-blue-200 text-right' : 'text-slate-400'
                    }`}
                  >
                    {msg.timestamp}
                  </span>
                </div>
                {msg.sender === 'user' && (
                  <div className="w-8 h-8 rounded-xl bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 mt-0.5 font-bold text-xs shadow-2xs">
                    <UserIcon className="w-4 h-4" />
                  </div>
                )}
              </div>

              {/* Rich Telemetry & Decision Card (returned by agent workflow) */}
              {msg.response && (
                <div className="ml-11 max-w-2xl bg-white rounded-2xl border border-slate-200 shadow-sm p-4 sm:p-5 space-y-4">
                  {/* Status Banner */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                    <div className="flex items-center space-x-2">
                      {msg.response.incident_id && (
                        <button
                          type="button"
                          onClick={() => onNavigate?.('home')}
                          title="View in My Tickets"
                          className="text-xs font-bold text-brand-blue hover:underline flex items-center gap-1"
                        >
                          <span>INC-{String(msg.response.incident_id).padStart(6, '0')}</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      )}
                      <span
                        className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                          msg.response.priority === 'critical'
                            ? 'bg-rose-100 text-rose-700 border border-rose-200'
                            : msg.response.priority === 'high'
                            ? 'bg-amber-100 text-amber-700 border border-amber-200'
                            : 'bg-blue-100 text-blue-700 border border-blue-200'
                        }`}
                      >
                        {msg.response.priority} Priority
                      </span>
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                        Status: {msg.response.ticket_status}
                      </span>
                      {msg.response.assigned_engineer_name && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 border border-violet-200 flex items-center gap-1">
                          <UserIcon className="w-3 h-3" />
                          <span>{msg.response.assigned_engineer_name}</span>
                        </span>
                      )}
                      {msg.response.lifecycle_phase && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {msg.response.lifecycle_phase.replace(/_/g, ' ')}
                        </span>
                      )}
                    </div>

                    {msg.response.is_demo && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-brand-violet border border-purple-200">
                        DEMO MODE: simulated
                      </span>
                    )}
                  </div>

                  {/* Contextual Continuity Notification */}
                  {msg.response.employee_notification && (
                    <div className="bg-blue-50 border border-blue-200 rounded-xl p-3.5 text-xs text-blue-900 flex items-start space-x-2.5">
                      <Sparkles className="w-4 h-4 text-brand-blue shrink-0 mt-0.5" />
                      <div>
                        <p className="font-bold text-blue-950">Incident Continuity Update</p>
                        <p className="mt-0.5 leading-relaxed text-blue-800">{msg.response.employee_notification}</p>
                      </div>
                    </div>
                  )}

                  {/* Multi-Agent Decision Trace */}
                  {msg.response.agent_trace?.length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center">
                        <Layers className="w-3.5 h-3.5 mr-1 text-brand-blue" />
                        Agent Decision Trace ({msg.response.agent_trace.length} steps)
                      </h4>
                      <div className="space-y-1.5">
                        {msg.response.agent_trace.map((tr, idx) => (
                          <div
                            key={idx}
                            className="text-xs bg-slate-50 border border-slate-100 rounded-lg p-2.5 flex items-start justify-between"
                          >
                            <div className="flex items-start space-x-2">
                              <span className="font-bold text-brand-blue shrink-0">
                                [{tr.agent}]
                              </span>
                              <span className="text-slate-700">{tr.summary}</span>
                            </div>
                            <span className="text-[10px] font-mono text-slate-400 shrink-0 ml-2">
                              {tr.duration_ms}ms
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Retrieved Knowledge Sources (RAG Citations) */}
                  {msg.response.retrieved_chunks?.length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center">
                        <FileText className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                        Retrieved Knowledge Runbooks (RAG Citations)
                      </h4>
                      <div className="space-y-2">
                        {msg.response.retrieved_chunks.map((chk, idx) => (
                          <div
                            key={idx}
                            className="text-xs bg-emerald-50/60 border border-emerald-200/70 rounded-xl p-3"
                          >
                            <div className="flex items-center justify-between font-bold text-emerald-900 mb-1">
                              <span className="truncate">{chk.doc}</span>
                              <span className="text-[10px] font-mono bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full shrink-0">
                                Relevance: {chk.score}
                              </span>
                            </div>
                            <p className="text-slate-700 italic text-[11px] line-clamp-3">
                              "{chk.chunk}"
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* MCP Protocol Diagnostics */}
                  {msg.response.diagnostics?.length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center">
                        <Activity className="w-3.5 h-3.5 mr-1 text-brand-violet" />
                        Model Context Protocol (MCP) Diagnostics
                      </h4>
                      <div className="space-y-2">
                        {msg.response.diagnostics.map((diag, idx) => (
                          <div
                            key={idx}
                            className="text-xs bg-purple-50/50 border border-purple-200/70 rounded-xl p-3"
                          >
                            <div className="flex items-center justify-between mb-1.5 font-mono">
                              <span className="font-bold text-purple-900">
                                Tool: {diag.tool}
                              </span>
                              {diag.simulated && (
                                <span className="bg-amber-100 text-amber-800 text-[10px] font-bold px-2 py-0.5 rounded-full border border-amber-300">
                                  Simulated
                                </span>
                              )}
                            </div>
                            <pre className="text-[11px] font-mono text-slate-700 bg-white p-2.5 rounded-lg border border-purple-100 overflow-x-auto max-h-40">
                              {JSON.stringify(diag.result, null, 2)}
                            </pre>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Sensitive Action Approval Notice */}
                  {msg.response.requires_approval && (
                    <div className="bg-amber-50 border border-amber-300 rounded-xl p-3.5 text-xs text-amber-900 flex items-start space-x-2.5">
                      <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="font-bold">Human Authorization Required</p>
                        <p className="mt-0.5 leading-relaxed">
                          This sensitive operation requires review by a Support Engineer or Administrator before execution.
                          Approval workflow <strong>#{msg.response.approval_id}</strong> is registered with status <strong>PENDING</strong>.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Resolution Confirmation Feedback */}
                  {feedbackErrors[msg.id] && (
                    <p role="alert" className="text-xs text-rose-600 font-medium">
                      {feedbackErrors[msg.id]}
                    </p>
                  )}

                  {!msg.response.requires_approval && (
                    <div className="pt-3 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                      <span className="text-xs text-slate-600 font-medium">
                        Did this resolve your issue?
                      </span>
                      {feedbackGiven[msg.id] ? (
                        <span className="text-xs font-semibold text-emerald-600 flex items-center">
                          <CheckCircle2 className="w-4 h-4 mr-1 text-emerald-500" /> Resolution feedback recorded
                        </span>
                      ) : (
                        <div className="flex space-x-2">
                          <button
                            type="button"
                            onClick={() => handleResolutionFeedback(msg, true)}
                            className="px-3 py-1.5 text-xs font-bold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg border border-emerald-300 transition flex items-center space-x-1"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Resolved</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleResolutionFeedback(msg, false)}
                            className="px-3 py-1.5 text-xs font-bold bg-rose-50 text-rose-700 hover:bg-rose-100 rounded-lg border border-rose-300 transition flex items-center space-x-1"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            <span>Not Resolved</span>
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {/* Loading Multi-Agent Progress Bar */}
        {loading && (
          <div className="ml-11 max-w-md bg-white border border-brand-blue/30 rounded-2xl p-4 shadow-sm space-y-2">
            <div className="flex items-center space-x-2 text-xs font-bold text-brand-blue">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Multi-Agent Swarm Active</span>
            </div>
            <p className="text-xs text-slate-600 leading-snug animate-pulse">
              {STAGES[loadingStage]}
            </p>
            <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-brand-blue h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${((loadingStage + 1) / STAGES.length) * 100}%` }}
              />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Message Composer */}
      <footer className="p-4 bg-white border-t border-slate-200 shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage(inputText);
          }}
          className="flex items-center space-x-3 max-w-4xl mx-auto"
        >
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Describe your IT issue (e.g. 'Cannot connect to VPN' or 'Install Python')..."
            disabled={loading}
            className="flex-1 bg-slate-50 border border-slate-300 focus:border-brand-blue focus:bg-white focus:outline-none rounded-xl px-4 py-3 text-xs sm:text-sm text-slate-800 placeholder-slate-400 transition"
          />
          <button
            type="submit"
            disabled={!inputText.trim() || loading}
            className="bg-brand-blue hover:bg-blue-600 disabled:opacity-50 text-white px-5 py-3 rounded-xl font-bold text-xs sm:text-sm transition flex items-center space-x-1.5 shadow-sm shadow-brand-blue/20"
          >
            <span>Send</span>
            <Send className="w-4 h-4" />
          </button>
        </form>
      </footer>
    </div>
  );
};